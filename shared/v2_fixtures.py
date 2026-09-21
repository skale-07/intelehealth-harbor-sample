"""Verifier-side V2 fixture definitions. Not copied into agent images."""

from __future__ import annotations

import copy
from typing import Any

from grade import expected_disposition
from protocol_walker import Protocol

PROTOCOL_ID = "ID_c492cec3-f0e8-4ab1-8b31-fd2f3b557e0b"
PROTOCOL_NAME = "Chest pain"
POLICY_ID = "demo-chest-pain-disposition-v2"
POLICY_VERSION = "0.2.0"

Q_DURATION = "ID_6b85e860-b27a-46e6-a60f-a6c10eb8b7db"
Q_HOW_FAST = "ID_01f2916c-1675-495f-a49b-425cf8dae2c9"
O_SUDDENLY = "ID_0cf109a7-5669-4afd-b5a5-05678f765ec9"
O_SLOWLY = "ID_9a670465-8dbb-47ba-8919-687096341c1b"
Q_CHEST_PART = "ID_d693c0a4-8021-4c2c-9b3c-fe2ca352cf6a"
O_CENTRE = "ID_96949bd1-cf34-4d25-9d65-d0c6bd60cf56"
O_LEFT_SIDE = "ID_b6ccd295-a061-4974-9d97-8983588424c7"
O_RIGHT_SIDE = "ID_1c51bdc9-0069-46e9-9e7e-6bff95f8eacf"
O_EPIGASTRIC = "ID_eca8a1f2-e03c-459f-99a0-85bfd5547764"
Q_WORSEN = "ID_7d090a35-4685-4063-9101-f5ca9dcdb11c"
O_MENSTRUAL = "ID_4fc5d549-740f-434b-83c8-56f9e0e66acc"
Q_MOVE = "ID_8acf327f-18e6-48db-aba5-f9052276ed0c"
O_MOVE_NO = "ID_253612f4-b3c6-41ec-826f-e76fc6b7cb19"
O_MOVE_YES = "ID_ab8419e3-3590-4916-8fa4-bfc101a63217"
Q_MOVES_TO = "ID_e9a1aaab-f1e9-4dbd-8c58-3c7e77995b3e"
O_LEFT_ARM = "ID_cde9e257-f3f9-43f3-89ac-128783747ceb"
Q_ASSOCIATED = "ID_2a5f6982-0694-48b5-8faa-06241e5e2279"
O_DIFF_BREATHING = "ID_f11aa381-71db-4773-940a-2b44b7b0c5e9"
O_COUGH = "ID_f55be4f7-196f-4afc-88fc-90127231e1ac"

ESCALATE_OPTION_IDS = (
    "ID_f11aa381-71db-4773-940a-2b44b7b0c5e9",
    "ID_eb2cd4bb-d56a-4cb4-aa06-e76ef12b7cb1",
    "ID_51003f2b-659b-4098-9ea1-bd6a6824e7a4",
    "ID_cde9e257-f3f9-43f3-89ac-128783747ceb",
    "ID_57a7f558-1937-4bdf-917d-504a9fa67195",
)

NEUTRAL_LABEL = "Synthetic fixture — not a real visit"

DEMO_RULES: dict[str, Any] = {
    "policy_id": POLICY_ID,
    "version": POLICY_VERSION,
    "source": "DEMO_POLICY",
    "validated_clinically": False,
    "applies_to_protocol": PROTOCOL_ID,
    "applies_to_protocol_name": PROTOCOL_NAME,
    "IMPORTANT": (
        "These option IDs exist in Chest pain.json as ordinary answers. "
        "The protocol does not label them as red flags or dispositions. "
        "Mapping selected IDs to urgent vs local_management is synthetic demo policy."
    ),
    "provenance_note": [
        "Chest pain.json is a history-taking grammar.",
        "escalate_option_ids are an interpretation layer baked only into the verifier image.",
        "The agent sandbox must not contain this file.",
    ],
    "escalation_disposition": "urgent",
    "default_disposition": "local_management",
    "blocks_dispositions": ["local_management"],
    "escalate_option_ids": list(ESCALATE_OPTION_IDS),
}


def _ans(question_id: str, option_ids: list[str] | None = None, free_text: str | None = None) -> dict[str, Any]:
    return {
        "question_id": question_id,
        "option_ids": list(option_ids or []),
        "free_text": free_text,
    }


COMPLETE_ANSWERS: list[dict[str, Any]] = [
    _ans(Q_DURATION, free_text="2 hours"),
    _ans(Q_HOW_FAST, [O_SUDDENLY]),
    _ans(Q_CHEST_PART, [O_CENTRE]),
    _ans("ID_3c1f1576-9508-4c74-a35e-3f75acf9da60", ["ID_9ead6dc9-2c99-4689-a00f-7a609d6832f7"]),
    _ans("ID_b021c353-3d82-4a5c-8917-ff38d6662a7b", ["ID_fabe45f8-6764-4d1e-8d0d-a40261db550c"]),
    _ans("ID_50cd4b8c-6e8d-4998-baaa-373c277e22b7", ["ID_753b626a-c30b-4429-bb02-e8b3decda82e"]),
    _ans("ID_c23fe3d8-ba59-40d0-b2fc-4013cd21a87d", ["ID_e7e21222-516f-4bb7-be53-06f1ba010bbe"]),
    _ans("ID_a5beb441-0cc1-422b-9805-946de317e2dd", ["ID_02fcb080-4efa-4608-8f19-985938576463"]),
    _ans(Q_WORSEN, ["ID_383a59a3-8a12-4098-b8b9-124eea1cd8bb"]),
    _ans("ID_d203fe4b-4015-47cc-b999-c7cb0c6b9f7d", ["ID_7e612f07-cb15-4ea1-afdd-c714aacf64d8"]),
    _ans(Q_MOVE, [O_MOVE_NO]),
    _ans(Q_ASSOCIATED, [O_DIFF_BREATHING]),
    _ans("ID_f4f25bdb-2a37-417e-9387-78645ed31fbf", ["ID_e27aa693-f730-4308-912a-58edaae5f822"]),
    _ans("ID_20412fe8-64a9-4a42-bfee-d868b2273262", ["ID_f9f4a188-9c0d-4ece-ad75-9c9a38760747"]),
    _ans("ID_3c11df65-58f2-4319-ba52-bddc2f0acb39", free_text="No treatment taken."),
    _ans("ID_46dcaefb-657b-421c-a711-b839f28dfa8c", free_text="No additional information."),
]


def _replace_option(answers: list[dict[str, Any]], question_id: str, option_ids: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    found = False
    for ans in answers:
        if ans["question_id"] == question_id:
            item = dict(ans)
            item["option_ids"] = list(option_ids)
            out.append(item)
            found = True
        else:
            out.append(copy.deepcopy(ans))
    if not found:
        raise ValueError(f"question {question_id} not in answers")
    return out


def ask(question_id: str, option_ids: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "protocol_id": PROTOCOL_NAME,
        "action": "ask_question",
        "question_id": question_id,
        "option_ids": list(option_ids),
    }


def close(disposition: str) -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "protocol_id": PROTOCOL_NAME,
        "action": "close_and_act",
        "disposition": disposition,
    }


ORACLE_HOW_FAST = ask(Q_HOW_FAST, [O_SUDDENLY, O_SLOWLY])
ORACLE_CHEST_PART = ask(Q_CHEST_PART, [O_LEFT_SIDE, O_RIGHT_SIDE, O_CENTRE, O_EPIGASTRIC])
FOIL_MENSTRUAL = ask(Q_WORSEN, [O_MENSTRUAL])
FOIL_NESTED = ask(Q_MOVES_TO, [O_LEFT_ARM])


def patient_state(age: int, answers: list[dict[str, Any]], label: str = NEUTRAL_LABEL) -> dict[str, Any]:
    return {
        "age": age,
        "protocol_id": PROTOCOL_ID,
        "protocol_name": PROTOCOL_NAME,
        "label": label,
        "answers": copy.deepcopy(answers),
    }


def answers_to_script(answers: list[dict[str, Any]]) -> dict[str, Any]:
    script: dict[str, Any] = {}
    for ans in answers:
        script[ans["question_id"]] = {
            "option_ids": list(ans.get("option_ids") or []),
            "free_text": ans.get("free_text"),
        }
    return script


def _case(
    *,
    case_id: str,
    task_kind: str,
    suite: str,
    pair_id: str,
    variant: str,
    age: int,
    answers: list[dict[str, Any]],
    oracle: dict[str, Any] | None,
    close_disposition: str | None,
    label: str = NEUTRAL_LABEL,
    patient_script: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy_id = POLICY_ID if task_kind in {"one_shot_close", "rollout_intake"} else None
    return {
        "case_id": case_id,
        "task_kind": task_kind,
        "suite": suite,
        "pair_id": pair_id,
        "variant": variant,
        "policy_id": policy_id,
        "close_disposition": close_disposition,
        "age": age,
        "label": label,
        "answers": copy.deepcopy(answers),
        "oracle": copy.deepcopy(oracle),
        "patient_script": copy.deepcopy(patient_script),
        "patient_state": patient_state(age, answers, label),
    }


def iter_cases() -> list[dict[str, Any]]:
    duration_only = [_ans(Q_DURATION, free_text="2 days")]
    nested_inactive = [
        _ans(Q_DURATION, free_text="2 days"),
        _ans(Q_HOW_FAST, [O_SUDDENLY]),
        _ans(Q_MOVE, [O_MOVE_NO]),
    ]
    nested_active = [
        _ans(Q_DURATION, free_text="2 days"),
        _ans(Q_HOW_FAST, [O_SUDDENLY]),
        _ans(Q_MOVE, [O_MOVE_YES]),
    ]
    escalate_answers = copy.deepcopy(COMPLETE_ANSWERS)
    default_answers = _replace_option(COMPLETE_ANSWERS, Q_ASSOCIATED, [O_COUGH])
    inv_b = list(reversed(default_answers))
    return [
        _case(
            case_id="case-01a7c9",
            task_kind="one_shot_question",
            suite="age_eligibility",
            pair_id="pair-age-01",
            variant="ineligible",
            age=8,
            answers=duration_only,
            oracle=ORACLE_HOW_FAST,
            close_disposition=None,
        ),
        _case(
            case_id="case-12c4e8",
            task_kind="one_shot_question",
            suite="age_eligibility",
            pair_id="pair-age-01",
            variant="eligible",
            age=12,
            answers=duration_only,
            oracle=ORACLE_HOW_FAST,
            close_disposition=None,
        ),
        _case(
            case_id="case-23d5f1",
            task_kind="one_shot_question",
            suite="nested_branch",
            pair_id="pair-nest-01",
            variant="inactive",
            age=55,
            answers=nested_inactive,
            oracle=ORACLE_CHEST_PART,
            close_disposition=None,
        ),
        _case(
            case_id="case-34e6a2",
            task_kind="one_shot_question",
            suite="nested_branch",
            pair_id="pair-nest-01",
            variant="active",
            age=55,
            answers=nested_active,
            oracle=ORACLE_CHEST_PART,
            close_disposition=None,
        ),
        _case(
            case_id="case-45f7b3",
            task_kind="one_shot_close",
            suite="disposition",
            pair_id="pair-disp-01",
            variant="escalate",
            age=55,
            answers=escalate_answers,
            oracle=close("urgent"),
            close_disposition="urgent",
        ),
        _case(
            case_id="case-56a8c4",
            task_kind="one_shot_close",
            suite="disposition",
            pair_id="pair-disp-01",
            variant="default",
            age=55,
            answers=default_answers,
            oracle=close("local_management"),
            close_disposition="local_management",
        ),
        _case(
            case_id="case-67b9d5",
            task_kind="one_shot_close",
            suite="invariance",
            pair_id="pair-inv-01",
            variant="alpha",
            age=55,
            answers=default_answers,
            oracle=close("local_management"),
            close_disposition="local_management",
            label="fixture-alpha",
        ),
        _case(
            case_id="case-78c0e6",
            task_kind="one_shot_close",
            suite="invariance",
            pair_id="pair-inv-01",
            variant="beta",
            age=55,
            answers=inv_b,
            oracle=close("local_management"),
            close_disposition="local_management",
            label="fixture-beta",
        ),
        _case(
            case_id="case-89d1f7",
            task_kind="rollout_intake",
            suite="rollout",
            pair_id="pair-roll-01",
            variant="escalate",
            age=55,
            answers=[],
            oracle=None,
            close_disposition="urgent",
            patient_script=answers_to_script(escalate_answers),
        ),
        _case(
            case_id="case-90e2a8",
            task_kind="rollout_intake",
            suite="rollout",
            pair_id="pair-roll-01",
            variant="default",
            age=55,
            answers=[],
            oracle=None,
            close_disposition="local_management",
            patient_script=answers_to_script(default_answers),
        ),
    ]


def selected_option_ids(answers: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for ans in answers:
        ids.update(ans.get("option_ids") or [])
    return ids


def validate_case(case: dict[str, Any], protocol: Protocol) -> None:
    case_id = case["case_id"]
    age = int(case["age"])
    answers = case["answers"]
    for ans in answers:
        qid = ans["question_id"]
        qnode = protocol.get_node(qid)
        if qnode is None or not qnode.is_question:
            raise AssertionError(f"{case_id}: {qid} is not a protocol question")
        if protocol.age_violation(qid, age) is not None:
            raise AssertionError(f"{case_id}: question {qid} is age-ineligible at age {age}")
        selected = selected_option_ids(answers)
        if not protocol.is_branch_active(qid, selected):
            raise AssertionError(f"{case_id}: question {qid} is nested but inactive")
        for oid in ans.get("option_ids") or []:
            onode = protocol.get_node(oid)
            if onode is None:
                raise AssertionError(f"{case_id}: option {oid} does not exist")
            if onode.parent_id != qid:
                raise AssertionError(f"{case_id}: option {oid} does not belong to {qid}")
            if protocol.age_violation(oid, age) is not None:
                raise AssertionError(f"{case_id}: option {oid} is age-ineligible at age {age}")
    agent_patient = case["patient_state"]
    for leaked in ("suite", "pair_id", "variant", "policy_id", "expected_disposition", "oracle"):
        if leaked in agent_patient:
            raise AssertionError(f"{case_id}: patient_state contains {leaked}")
    if case["task_kind"] in {"one_shot_close", "rollout_intake"}:
        if DEMO_RULES["escalation_disposition"] != "urgent":
            raise AssertionError("Phase 1 escalation_disposition must be urgent")
        if DEMO_RULES["default_disposition"] != "local_management":
            raise AssertionError("Phase 1 default_disposition must be local_management")
        if case["task_kind"] == "one_shot_close":
            final_answers = answers
        else:
            final_answers = [
                _ans(qid, entry.get("option_ids") or [], entry.get("free_text"))
                for qid, entry in (case["patient_script"] or {}).items()
            ]
        selected = selected_option_ids(final_answers)
        answered = {a["question_id"] for a in final_answers}
        missing = [
            q.id
            for q in protocol.get_applicable_required_questions(selected, age)
            if q.id not in answered
        ]
        if missing:
            raise AssertionError(f"{case_id}: incomplete required questions {missing}")
        patient = {"age": age, "answers": final_answers}
        expected = expected_disposition(patient, DEMO_RULES)
        if expected != case["close_disposition"]:
            raise AssertionError(
                f"{case_id}: close_disposition {case['close_disposition']!r} != policy {expected!r}"
            )
    if case["oracle"] is not None:
        qid = case["oracle"].get("question_id")
        if qid:
            node = protocol.get_node(qid)
            if node is None or not node.is_question:
                raise AssertionError(f"{case_id}: oracle question {qid} missing")
            for oid in case["oracle"].get("option_ids") or []:
                opt = protocol.get_node(oid)
                if opt is None or opt.parent_id != qid:
                    raise AssertionError(f"{case_id}: oracle option {oid} invalid for {qid}")


def manifest_payload() -> dict[str, Any]:
    cases = []
    for case in iter_cases():
        cases.append(
            {
                "case_id": case["case_id"],
                "task_kind": case["task_kind"],
                "suite": case["suite"],
                "pair_id": case["pair_id"],
                "variant": case["variant"],
                "policy_id": case["policy_id"],
                "close_disposition": case["close_disposition"],
                "oracle": case["oracle"],
            }
        )
    return {
        "dataset": "intelehealth-verify-v2",
        "generated_by": "shared/build_v2_tasks.py",
        "protocol_file": "Chest pain.json",
        "policy_id": POLICY_ID,
        "validated_clinically": False,
        "note": (
            "Verifier-side fixture index. Synthetic DEMO_POLICY maps selected "
            "escalate_option_ids to urgent, else local_management. Not a clinical rule."
        ),
        "cases": cases,
    }
