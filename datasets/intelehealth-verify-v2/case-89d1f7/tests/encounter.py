"""Canonical intake encounter record.

Not a doctor–patient dialogue. Protocols are CHW history-taking trees.
The verifier writes this from patient state + the agent's proposal(s) +
the grade. The agent does not author the trace (that would be tamperable).

One-shot tasks: fixture answers, then one proposed action.
Rollout tasks: proposal / environment-answer pairs, then close.
"""

from __future__ import annotations

from typing import Any

from protocol_walker import Protocol


def _node_text(protocol: Protocol, node_id: str | None) -> str | None:
    if not node_id:
        return None
    node = protocol.get_node(node_id)
    return node.text if node else None


def _history_turns(patient: dict[str, Any], protocol: Protocol) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    for i, answer in enumerate(patient.get("answers") or []):
        qid = answer.get("question_id")
        option_ids = list(answer.get("option_ids") or [])
        turns.append(
            {
                "t": i,
                "kind": "answered",
                "source": "fixture",
                "question_id": qid,
                "question_text": _node_text(protocol, qid),
                "option_ids": option_ids,
                "option_texts": [_node_text(protocol, oid) for oid in option_ids],
                "free_text": answer.get("free_text"),
            }
        )
    return turns


def answered_turn(
    question_id: str,
    option_ids: list[str],
    protocol: Protocol,
    t: int,
    *,
    free_text: str | None = None,
    source: str = "environment",
) -> dict[str, Any]:
    return {
        "t": t,
        "kind": "answered",
        "source": source,
        "question_id": question_id,
        "question_text": _node_text(protocol, question_id),
        "option_ids": option_ids,
        "option_texts": [_node_text(protocol, oid) for oid in option_ids],
        "free_text": free_text,
    }


def _proposal_turn(
    proposal: dict[str, Any] | None,
    protocol: Protocol,
    t: int,
) -> dict[str, Any]:
    if not isinstance(proposal, dict):
        return {
            "t": t,
            "kind": "proposal",
            "source": "agent",
            "action": None,
            "note": "Proposal missing or not a JSON object.",
        }
    action = proposal.get("action")
    turn: dict[str, Any] = {
        "t": t,
        "kind": "proposal",
        "source": "agent",
        "action": action,
        "role": "intake",
    }
    if action == "ask_question":
        qid = proposal.get("question_id")
        option_ids = list(proposal.get("option_ids") or [])
        turn.update(
            {
                "question_id": qid,
                "question_text": _node_text(protocol, qid),
                "option_ids": option_ids,
                "option_texts": [_node_text(protocol, oid) for oid in option_ids],
            }
        )
    elif action == "close_and_act":
        turn["disposition"] = proposal.get("disposition")
    return turn


def build_encounter(
    patient: dict[str, Any],
    protocol: Protocol,
    proposal: dict[str, Any] | None,
    result: dict[str, Any],
) -> dict[str, Any]:
    history = _history_turns(patient, protocol)
    steps = [*history, _proposal_turn(proposal, protocol, t=len(history))]
    return {
        "schema_version": "0.1.0",
        "kind": "intake_encounter",
        "note": (
            "CHW intake trace, not a clinician consult. History turns are the "
            "synthetic fixture. The last turn is the agent's one proposed action."
        ),
        "protocol_id": protocol.protocol_id,
        "protocol_name": protocol.name,
        "engine_version": protocol.engine_version,
        "patient": {
            "age": patient.get("age"),
            "label": patient.get("label"),
        },
        "steps": steps,
        "grade": {
            "verdict": result.get("verdict"),
            "reward": result.get("reward"),
            "criteria": result.get("criteria"),
            "reasons": result.get("reasons"),
        },
    }


def build_rollout_encounter(
    patient: dict[str, Any],
    protocol: Protocol,
    steps: list[dict[str, Any]],
    result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "kind": "intake_encounter",
        "note": (
            "CHW intake trace, not a clinician consult. Proposal turns are the "
            "agent. Answer turns are the hidden patient_script, applied only "
            "after ALLOW. The agent does not author answers."
        ),
        "protocol_id": protocol.protocol_id,
        "protocol_name": protocol.name,
        "engine_version": protocol.engine_version,
        "patient": {
            "age": patient.get("age"),
            "label": patient.get("label"),
        },
        "steps": steps,
        "grade": {
            "verdict": result.get("verdict"),
            "reward": result.get("reward"),
            "criteria": result.get("criteria"),
            "reasons": result.get("reasons"),
        },
    }
