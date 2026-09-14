"""Greedy Chest pain intake policy. Harbor oracle for chest-pain-intake.

Asks the first legal unanswered question. When none remain, closes urgent.
urgent, not local_management: this sample chart selects a demo-policy option,
and local_management would ESCALATE.
"""

from __future__ import annotations

from typing import Any


def propose(state: dict[str, Any], protocol: Any) -> dict[str, Any]:
    age = int(state["age"])
    answers = state.get("answers") or []
    answered = {a["question_id"] for a in answers if a.get("question_id")}
    selected: set[str] = set()
    for answer in answers:
        selected.update(answer.get("option_ids") or [])
    legal = protocol.get_legal_next_questions(selected, answered, age)
    if not legal:
        return {
            "schema_version": "0.1.0",
            "protocol_id": protocol.name,
            "action": "close_and_act",
            "disposition": "urgent",
        }
    question = legal[0]
    option_ids = [
        o.id
        for o in protocol.options_for(question.id)
        if protocol.is_age_eligible(o, age)
    ]
    return {
        "schema_version": "0.1.0",
        "protocol_id": protocol.name,
        "action": "ask_question",
        "question_id": question.id,
        "option_ids": option_ids,
    }
