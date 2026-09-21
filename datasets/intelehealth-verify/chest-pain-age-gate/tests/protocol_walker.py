"""Index an Intelehealth intake-protocol JSON for deterministic checks.

The source files under data/intake_protocols/ are history-taking grammars.
They encode question IDs, isRequired, age_min/age_max, and nested follow-ups.
They do not encode diagnoses, treatments, or escalation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

KIND_ROOT = "root"
KIND_QUESTION = "question"
KIND_OPTION = "option"


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class ProtocolNode:
    id: str
    text: str
    kind: str
    depth: int
    parent_id: str | None
    is_required: bool = False
    age_min: int | None = None
    age_max: int | None = None
    multi_choice: bool | None = None
    input_type: str | None = None
    having_nested_question: bool = False
    exclude_from_multi_choice: bool = False
    child_ids: tuple[str, ...] = ()

    @property
    def is_question(self) -> bool:
        return self.kind == KIND_QUESTION

    @property
    def is_option(self) -> bool:
        return self.kind == KIND_OPTION


class Protocol:
    def __init__(self, raw: dict[str, Any], source_file: str) -> None:
        self.source_file = source_file
        self.protocol_id: str = raw["id"]
        self.name: str = raw["text"]
        self.engine_version: str = raw.get("engineVersion", "unknown")
        self.nodes: dict[str, ProtocolNode] = {}
        self._build(raw)

    def _build(self, raw: dict[str, Any]) -> None:
        def visit(raw_node: dict[str, Any], depth: int, parent_id: str | None) -> str:
            node_id = raw_node["id"]
            if depth == 0:
                kind = KIND_ROOT
            else:
                kind = KIND_QUESTION if depth % 2 == 1 else KIND_OPTION
            child_ids = [
                visit(child, depth + 1, node_id)
                for child in raw_node.get("options") or []
            ]
            self.nodes[node_id] = ProtocolNode(
                id=node_id,
                text=raw_node.get("text", ""),
                kind=kind,
                depth=depth,
                parent_id=parent_id,
                is_required=_as_bool(raw_node.get("isRequired")),
                age_min=_as_int(raw_node.get("age_min")),
                age_max=_as_int(raw_node.get("age_max")),
                multi_choice=(
                    _as_bool(raw_node["multi-choice"])
                    if "multi-choice" in raw_node
                    else None
                ),
                input_type=raw_node.get("input-type"),
                having_nested_question=_as_bool(raw_node.get("havingNestedQuestion")),
                exclude_from_multi_choice=_as_bool(
                    raw_node.get("exclude-from-multi-choice")
                ),
                child_ids=tuple(child_ids),
            )
            return node_id

        visit(raw, 0, None)
        self.root_id = self.protocol_id

    def get_node(self, node_id: str) -> ProtocolNode | None:
        return self.nodes.get(node_id)

    def has_node(self, node_id: str) -> bool:
        return node_id in self.nodes

    def questions(self) -> list[ProtocolNode]:
        return [n for n in self.nodes.values() if n.is_question]

    def top_level_questions(self) -> list[ProtocolNode]:
        return [n for n in self.nodes.values() if n.is_question and n.depth == 1]

    def options_for(self, question_id: str) -> list[ProtocolNode]:
        node = self.get_node(question_id)
        if node is None:
            return []
        return [self.nodes[cid] for cid in node.child_ids]

    def ancestors(self, node_id: str) -> Iterator[ProtocolNode]:
        node = self.get_node(node_id)
        while node is not None and node.parent_id is not None:
            node = self.get_node(node.parent_id)
            if node is not None:
                yield node

    def activating_option(self, question_id: str) -> ProtocolNode | None:
        node = self.get_node(question_id)
        if node is None or node.parent_id is None:
            return None
        parent = self.get_node(node.parent_id)
        return parent if parent is not None and parent.is_option else None

    def is_age_eligible(self, node: ProtocolNode, age: int) -> bool:
        if node.age_min is not None and age < node.age_min:
            return False
        if node.age_max is not None and age > node.age_max:
            return False
        return True

    def age_violation(self, node_id: str, age: int) -> ProtocolNode | None:
        node = self.get_node(node_id)
        if node is None:
            return None
        if not self.is_age_eligible(node, age):
            return node
        for ancestor in self.ancestors(node_id):
            if not self.is_age_eligible(ancestor, age):
                return ancestor
        return None

    def is_branch_active(self, question_id: str, selected_option_ids: set[str]) -> bool:
        node = self.get_node(question_id)
        if node is None:
            return False
        if node.depth == 1:
            return True
        gate = self.activating_option(question_id)
        if gate is None:
            return True
        if gate.id not in selected_option_ids:
            return False
        grandparent = self.get_node(gate.parent_id) if gate.parent_id else None
        if grandparent is not None and grandparent.is_question:
            return self.is_branch_active(grandparent.id, selected_option_ids)
        return True

    def get_applicable_required_questions(
        self, selected_option_ids: set[str], age: int
    ) -> list[ProtocolNode]:
        return [
            q
            for q in self.questions()
            if q.is_required
            and self.is_branch_active(q.id, selected_option_ids)
            and self.age_violation(q.id, age) is None
        ]

    def get_legal_next_questions(
        self, selected_option_ids: set[str], answered_ids: set[str], age: int
    ) -> list[ProtocolNode]:
        legal = [
            q
            for q in self.questions()
            if q.id not in answered_ids
            and self.is_branch_active(q.id, selected_option_ids)
            and self.age_violation(q.id, age) is None
        ]
        return sorted(legal, key=lambda q: (q.depth, self._order_index(q.id)))

    def _order_index(self, node_id: str) -> int:
        try:
            return list(self.nodes).index(node_id)
        except ValueError:
            return 1 << 30


def load_protocol(path: str | Path) -> Protocol:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Protocol(raw, source_file=path.name)
