"""Verifier-side V3 fixture definitions. Not copied into agent images.

V2 stays frozen. Age leftover is only Q_WORSEN. Nested leftover is only
Q_MOVES_TO when the parent option is selected, else close.
"""

from __future__ import annotations

import copy
from typing import Any

from grade import expected_disposition
from protocol_walker import Protocol
from v2_fixtures import (
    COMPLETE_ANSWERS,
    ESCALATE_OPTION_IDS,
    NEUTRAL_LABEL,
    O_COUGH,
    O_DIFF_BREATHING,
    O_MENSTRUAL,
    O_MOVE_NO,
    O_MOVE_YES,
    O_SLOWLY,
    O_SUDDENLY,
    PROTOCOL_ID,
    PROTOCOL_NAME,
    Q_ASSOCIATED,
    Q_HOW_FAST,
    Q_MOVE,
    Q_MOVES_TO,
    Q_WORSEN,
    _ans,
    _replace_option,
    answers_to_script,
    ask,
    close,
    patient_state,
    selected_option_ids,
)

POLICY_ID = "demo-chest-pain-disposition-v3"
POLICY_VERSION = "0.3.0"

O_WORSEN_NONE = "ID_d1f66d19-85c6-4939-bd70-0c32e4dfeb0e"
O_WORSEN_ARM = "ID_ccd281a7-cc17-4e00-8f08-89a288a70f92"
O_WORSEN_PRESS = "ID_2aee2f3d-6787-488a-977e-abe4144dc0e6"
O_WORSEN_EXERTION = "ID_383a59a3-8a12-4098-b8b9-124eea1cd8bb"
O_WORSEN_FLAT = "ID_ced87aad-6cb8-48c8-99c0-23dbb8338a19"
O_WORSEN_SIDES = "ID_d54ed407-f2e6-414b-bd3a-68d11aad4643"
O_WORSEN_COUGHING = "ID_39d597b5-ee0d-4b5b-8aef-fdefadcad337"
O_WORSEN_BREATHING = "ID_be752347-0d0e-4b9d-915c-fd9279303290"
O_WORSEN_FOOD = "ID_69190530-3dcd-4cc2-aa26-400d18e7de0d"
O_WORSEN_OTHER = "ID_cc15473e-1761-4958-9d32-6b7b27ddc48d"

WORSEN_CHILD_OPTIONS = [
    O_WORSEN_NONE,
    O_WORSEN_ARM,
    O_WORSEN_PRESS,
    O_WORSEN_EXERTION,
    O_WORSEN_FLAT,
    O_WORSEN_SIDES,
    O_WORSEN_COUGHING,
    O_WORSEN_BREATHING,
    O_WORSEN_FOOD,
    O_WORSEN_OTHER,
]
WORSEN_ADULT_OPTIONS = [
    O_WORSEN_NONE,
    O_WORSEN_ARM,
    O_WORSEN_PRESS,
    O_WORSEN_EXERTION,
    O_WORSEN_FLAT,
    O_WORSEN_SIDES,
    O_WORSEN_COUGHING,
    O_WORSEN_BREATHING,
    O_WORSEN_FOOD,
    O_MENSTRUAL,
    O_WORSEN_OTHER,
]

O_MOVES_LEFT_ARM = "ID_cde9e257-f3f9-43f3-89ac-128783747ceb"
MOVES_TO_OPTIONS = [
    O_MOVES_LEFT_ARM,
    "ID_8991a4a5-2dce-473d-b951-0621d3840839",
    "ID_1d695160-34dd-456d-baae-6c69119db808",
    "ID_aa89d450-b747-4998-b470-2a9e7b0009c6",
    "ID_6dd5ebfd-5234-45c1-9e10-a1d93f9a4984",
    "ID_6b299476-f87e-4798-b985-9e62a8f7de9e",
    "ID_d2faa05c-d9c0-47f9-916f-36d23658c127",
    "ID_aa248fd1-ad8f-4454-9135-5e214540017a",
    "ID_ea05b257-a80e-4427-a6e6-829d50c40582",
]

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

ORACLE_WORSEN_CHILD = ask(Q_WORSEN, WORSEN_CHILD_OPTIONS)
ORACLE_WORSEN_ADULT = ask(Q_WORSEN, WORSEN_ADULT_OPTIONS)
ORACLE_MOVES_TO = ask(Q_MOVES_TO, MOVES_TO_OPTIONS)
FOIL_HOW_FAST = ask(Q_HOW_FAST, [O_SUDDENLY, O_SLOWLY])
FOIL_MENSTRUAL_ONLY = ask(Q_WORSEN, [O_MENSTRUAL])
FOIL_WORSEN_OMIT_MENSTRUAL = ask(Q_WORSEN, WORSEN_CHILD_OPTIONS)
FOIL_NESTED = ask(Q_MOVES_TO, MOVES_TO_OPTIONS)

AGE_ANSWERS = [a for a in COMPLETE_ANSWERS if a["question_id"] != Q_WORSEN]
DEFAULT_ANSWERS = _replace_option(COMPLETE_ANSWERS, Q_ASSOCIATED, [O_COUGH])
ESCALATE_ANSWERS = copy.deepcopy(COMPLETE_ANSWERS)
NEST_INACTIVE_ANSWERS = copy.deepcopy(DEFAULT_ANSWERS)
NEST_ACTIVE_ANSWERS = _replace_option(DEFAULT_ANSWERS, Q_MOVE, [O_MOVE_YES])
INV_BETA_ANSWERS = list(reversed(DEFAULT_ANSWERS))


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
    report_slice: str,
) -> dict[str, Any]:
    policy_id = POLICY_ID if task_kind in {"one_shot_close", "one_shot_next", "rollout_intake"} else None
    if task_kind == "one_shot_next" and variant == "active":
        policy_id = None
    return {
        "case_id": case_id,
        "task_kind": task_kind,
        "suite": suite,
        "pair_id": pair_id,
        "variant": variant,
        "policy_id": policy_id,
        "close_disposition": close_disposition,
        "report_slice": report_slice,
        "age": age,
        "label": label,
        "answers": copy.deepcopy(answers),
        "oracle": copy.deepcopy(oracle),
        "patient_script": copy.deepcopy(patient_script),
        "patient_state": patient_state(age, answers, label),
    }


def iter_cases() -> list[dict[str, Any]]:
    return [
        _case(
            case_id="case-a10c2d",
            task_kind="one_shot_question",
            suite="age_eligibility",
            pair_id="pair-age-01",
            variant="ineligible",
            age=8,
            answers=AGE_ANSWERS,
            oracle=ORACLE_WORSEN_CHILD,
            close_disposition=None,
            report_slice="grammar",
        ),
        _case(
            case_id="case-b21d3e",
            task_kind="one_shot_question",
            suite="age_eligibility",
            pair_id="pair-age-01",
            variant="eligible",
            age=12,
            answers=AGE_ANSWERS,
            oracle=ORACLE_WORSEN_ADULT,
            close_disposition=None,
            report_slice="grammar",
        ),
        _case(
            case_id="case-c32e4f",
            task_kind="one_shot_next",
            suite="nested_branch",
            pair_id="pair-nest-01",
            variant="inactive",
            age=55,
            answers=NEST_INACTIVE_ANSWERS,
            oracle=close("local_management"),
            close_disposition="local_management",
            report_slice="both",
        ),
        _case(
            case_id="case-d43f50",
            task_kind="one_shot_next",
            suite="nested_branch",
            pair_id="pair-nest-01",
            variant="active",
            age=55,
            answers=NEST_ACTIVE_ANSWERS,
            oracle=ORACLE_MOVES_TO,
            close_disposition=None,
            report_slice="grammar",
        ),
        _case(
            case_id="case-e54061",
            task_kind="one_shot_close",
            suite="disposition",
            pair_id="pair-disp-01",
            variant="escalate",
            age=55,
            answers=ESCALATE_ANSWERS,
            oracle=close("urgent"),
            close_disposition="urgent",
            report_slice="disposition",
        ),
        _case(
            case_id="case-f65172",
            task_kind="one_shot_close",
            suite="disposition",
            pair_id="pair-disp-01",
            variant="default",
            age=55,
            answers=DEFAULT_ANSWERS,
            oracle=close("local_management"),
            close_disposition="local_management",
            report_slice="disposition",
        ),
        _case(
            case_id="case-061283",
            task_kind="one_shot_close",
            suite="invariance",
            pair_id="pair-inv-01",
            variant="alpha",
            age=55,
            answers=DEFAULT_ANSWERS,
            oracle=close("local_management"),
            close_disposition="local_management",
            label="fixture-alpha",
            report_slice="disposition",
        ),
        _case(
            case_id="case-172394",
            task_kind="one_shot_close",
            suite="invariance",
            pair_id="pair-inv-01",
            variant="beta",
            age=55,
            answers=INV_BETA_ANSWERS,
            oracle=close("local_management"),
            close_disposition="local_management",
            label="fixture-beta",
            report_slice="disposition",
        ),
        _case(
            case_id="case-2834a5",
            task_kind="rollout_intake",
            suite="rollout",
            pair_id="pair-roll-01",
            variant="escalate",
            age=55,
            answers=[],
            oracle=None,
            close_disposition="urgent",
            patient_script=answers_to_script(ESCALATE_ANSWERS),
            report_slice="disposition",
        ),
        _case(
            case_id="case-3945b6",
            task_kind="rollout_intake",
            suite="rollout",
            pair_id="pair-roll-01",
            variant="default",
            age=55,
            answers=[],
            oracle=None,
            close_disposition="local_management",
            patient_script=answers_to_script(DEFAULT_ANSWERS),
            report_slice="disposition",
        ),
    ]


def legal_question_ids(case: dict[str, Any], protocol: Protocol) -> list[str]:
    selected = selected_option_ids(case["answers"])
    answered = {a["question_id"] for a in case["answers"]}
    return [q.id for q in protocol.get_legal_next_questions(selected, answered, int(case["age"]))]


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
    for leaked in ("suite", "pair_id", "variant", "policy_id", "expected_disposition", "oracle", "report_slice"):
        if leaked in agent_patient:
            raise AssertionError(f"{case_id}: patient_state contains {leaked}")
    legal = legal_question_ids(case, protocol)
    if case["suite"] == "age_eligibility":
        if legal != [Q_WORSEN]:
            raise AssertionError(f"{case_id}: unique legal must be Q_WORSEN, got {legal}")
    if case["suite"] == "nested_branch" and case["variant"] == "active":
        if legal != [Q_MOVES_TO]:
            raise AssertionError(f"{case_id}: unique legal must be Q_MOVES_TO, got {legal}")
    if case["suite"] == "nested_branch" and case["variant"] == "inactive":
        if legal:
            raise AssertionError(f"{case_id}: inactive nest must have no legal questions, got {legal}")
        if O_MOVE_YES in selected_option_ids(answers):
            raise AssertionError(f"{case_id}: inactive nest selected move=Yes")
        if O_MOVE_NO not in selected_option_ids(answers):
            raise AssertionError(f"{case_id}: inactive nest missing move=No")
    if case["task_kind"] in {"one_shot_close", "rollout_intake"} or (
        case["task_kind"] == "one_shot_next" and case["variant"] == "inactive"
    ):
        if DEMO_RULES["escalation_disposition"] != "urgent":
            raise AssertionError("escalation_disposition must be urgent")
        if DEMO_RULES["default_disposition"] != "local_management":
            raise AssertionError("default_disposition must be local_management")
        if case["task_kind"] == "rollout_intake":
            final_answers = [
                _ans(qid, entry.get("option_ids") or [], entry.get("free_text"))
                for qid, entry in (case["patient_script"] or {}).items()
            ]
        else:
            final_answers = answers
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
            eligible = {
                o.id for o in protocol.options_for(qid) if protocol.is_age_eligible(o, age)
            }
            proposed = set(case["oracle"].get("option_ids") or [])
            if proposed != eligible:
                raise AssertionError(
                    f"{case_id}: oracle options {sorted(proposed)} != eligible {sorted(eligible)}"
                )
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
                "report_slice": case["report_slice"],
                "oracle": case["oracle"],
            }
        )
    return {
        "dataset": "intelehealth-verify-v3",
        "generated_by": "shared/build_v3_tasks.py",
        "protocol_file": "Chest pain.json",
        "policy_id": POLICY_ID,
        "validated_clinically": False,
        "note": (
            "Verifier-side fixture index. Grammar slices (age, nested ask) are protocol "
            "structure. Disposition slices use synthetic DEMO_POLICY: selected "
            "escalate_option_ids → urgent, else local_management. Not a clinical rule. "
            "Do not rank models on a blended mean of both slices."
        ),
        "cases": cases,
    }
