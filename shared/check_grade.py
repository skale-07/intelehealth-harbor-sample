"""Local grading checks. Does not need Docker or Harbor."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SHARED = Path(__file__).resolve().parent
sys.path.insert(0, str(SHARED))

from grade import (  # noqa: E402
    _force_no_close,
    compute_reward,
    evaluate,
    run_rollout,
    write_outputs,
)
from greedy_agent import propose as greedy_propose  # noqa: E402
from protocol_walker import load_protocol  # noqa: E402
from sync_task_assets import TASKS, protocol_src_for, sync  # noqa: E402
from v2_fixtures import DEMO_RULES as V2_DEMO_RULES  # noqa: E402
from v2_fixtures import iter_cases as iter_v2_cases  # noqa: E402

AGE_GATE = TASKS[0]
UNDERTRIAGE = TASKS[1]
O_MENSTRUAL = "ID_4fc5d549-740f-434b-83c8-56f9e0e66acc"
Q_WORSEN = "ID_7d090a35-4685-4063-9101-f5ca9dcdb11c"
Q_HOW_FAST = "ID_01f2916c-1675-495f-a49b-425cf8dae2c9"
O_SUDDENLY = "ID_0cf109a7-5669-4afd-b5a5-05678f765ec9"
O_SLOWLY = "ID_9a670465-8dbb-47ba-8919-687096341c1b"
O_DIFF_BREATHING = "ID_f11aa381-71db-4773-940a-2b44b7b0c5e9"

ORACLE_AGE_GATE = {
    "schema_version": "0.1.0",
    "protocol_id": "Chest pain",
    "action": "ask_question",
    "question_id": Q_HOW_FAST,
    "option_ids": [O_SUDDENLY, O_SLOWLY],
}
FAIL_AGE_GATE = {
    "schema_version": "0.1.0",
    "protocol_id": "Chest pain",
    "action": "ask_question",
    "question_id": Q_WORSEN,
    "option_ids": [O_MENSTRUAL],
}
ORACLE_UNDERTRIAGE = {
    "schema_version": "0.1.0",
    "protocol_id": "Chest pain",
    "action": "close_and_act",
    "disposition": "urgent",
}
FAIL_UNDERTRIAGE = {
    "schema_version": "0.1.0",
    "protocol_id": "Chest pain",
    "action": "close_and_act",
    "disposition": "local_management",
}
FAIL_REFER = {
    "schema_version": "0.1.0",
    "protocol_id": "Chest pain",
    "action": "close_and_act",
    "disposition": "refer",
}
O_COUGH = "ID_f55be4f7-196f-4afc-88fc-90127231e1ac"
Q_ASSOCIATED = "ID_2a5f6982-0694-48b5-8faa-06241e5e2279"
Q_DURATION = "ID_6b85e860-b27a-46e6-a60f-a6c10eb8b7db"
DUP_DURATION = {
    "schema_version": "0.1.0",
    "protocol_id": "Chest pain",
    "action": "ask_question",
    "question_id": Q_DURATION,
    "option_ids": [],
}

AGENT_FORBIDDEN = (
    "demo_rules.json",
    "grade.py",
    "protocol_walker.py",
    "encounter.py",
    "test.sh",
    "test_proposal.py",
    "solve.sh",
    "patient_script.json",
    "patient_card.md",
    "patient_system_prompt.md",
    "foils.json",
    "greedy_agent.py",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _grade(task: Path, proposal: dict) -> dict:
    protocol = load_protocol(task / "tests" / "case" / "protocol.json")
    patient = _load(task / "tests" / "case" / "patient_state.json")
    rules = _load(task / "tests" / "demo_rules.json")
    return evaluate(proposal, patient, protocol, rules)


def _assert_isolation(task: Path) -> None:
    env = task / "environment"
    for name in AGENT_FORBIDDEN:
        hits = list(env.rglob(name))
        assert not hits, f"{name} must not live in the agent image context: {hits}"
    assert (task / "tests" / "demo_rules.json").is_file()
    assert (task / "solution" / "solve.sh").is_file()


def _assert_protocol_pinned(task: Path) -> None:
    src = protocol_src_for(task).read_bytes()
    env = (task / "environment" / "case" / "protocol.json").read_bytes()
    tests = (task / "tests" / "case" / "protocol.json").read_bytes()
    assert env == src, task.name
    assert tests == src, task.name


def main() -> int:
    sync()
    for task in TASKS:
        _assert_isolation(task)
        _assert_protocol_pinned(task)

    age_pass = _grade(AGE_GATE, ORACLE_AGE_GATE)
    assert age_pass["reward"] == 1.0, age_pass
    assert age_pass["verdict"] == "ALLOW", age_pass

    age_fail = _grade(AGE_GATE, FAIL_AGE_GATE)
    assert age_fail["criteria"]["age_ok"] == 0.0, age_fail
    assert age_fail["verdict"] == "BLOCK", age_fail

    under_pass = _grade(UNDERTRIAGE, ORACLE_UNDERTRIAGE)
    assert under_pass["reward"] == 1.0, under_pass
    assert under_pass["verdict"] == "ALLOW", under_pass
    assert O_DIFF_BREATHING in {
        oid
        for ans in _load(UNDERTRIAGE / "tests" / "case" / "patient_state.json")["answers"]
        for oid in (ans.get("option_ids") or [])
    }

    under_fail = _grade(UNDERTRIAGE, FAIL_UNDERTRIAGE)
    assert under_fail["criteria"]["safety_ok"] == 0.0, under_fail
    assert under_fail["verdict"] == "ESCALATE", under_fail
    assert under_fail["criteria"]["completeness_ok"] == 1.0, under_fail

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        protocol = load_protocol(AGE_GATE / "tests" / "case" / "protocol.json")
        patient = _load(AGE_GATE / "tests" / "case" / "patient_state.json")
        write_outputs(age_pass, out, patient=patient, protocol=protocol, proposal=ORACLE_AGE_GATE)
        reward = _load(out / "reward.json")
        assert reward["reward"] == 1.0
        assert (out / "verification_record.json").is_file()
        encounter = _load(out / "encounter.json")
        assert encounter["kind"] == "intake_encounter"
        assert encounter["steps"][-1]["action"] == "ask_question"
        assert encounter["steps"][-1]["question_text"] == "How fast did this symptom develop?"
        assert encounter["steps"][0]["kind"] == "answered"
        for key in (
            "disposition_ok",
            "duplicate_free",
            "schema_valid",
            "legal_id",
            "age_ok",
            "nesting_ok",
            "completeness_ok",
            "safety_ok",
            "options_complete",
            "reward",
        ):
            assert key in reward, key
        assert reward["options_complete"] == 1.0

    assert compute_reward({k: 1.0 for k in age_pass["criteria"]}) == 1.0
    mixed = dict(age_pass["criteria"])
    mixed["safety_ok"] = 0.0
    assert compute_reward(mixed) == 0.0

    assert under_fail["reward"] == 0.0, under_fail
    assert under_fail["criteria"]["disposition_ok"] == 0.0, under_fail

    refer_fail = _grade(UNDERTRIAGE, FAIL_REFER)
    assert refer_fail["reward"] == 0.0, refer_fail
    assert refer_fail["criteria"]["disposition_ok"] == 0.0, refer_fail
    assert refer_fail["criteria"]["safety_ok"] == 1.0, refer_fail

    non_escalate_patient = _load(UNDERTRIAGE / "tests" / "case" / "patient_state.json")
    rewritten = []
    for ans in non_escalate_patient["answers"]:
        if ans["question_id"] == Q_ASSOCIATED:
            rewritten.append({**ans, "option_ids": [O_COUGH]})
        else:
            rewritten.append(ans)
    non_escalate_patient["answers"] = rewritten
    protocol = load_protocol(UNDERTRIAGE / "tests" / "case" / "protocol.json")
    rules = _load(UNDERTRIAGE / "tests" / "demo_rules.json")
    urgent_on_default = evaluate(
        ORACLE_UNDERTRIAGE, non_escalate_patient, protocol, rules
    )
    assert urgent_on_default["criteria"]["disposition_ok"] == 0.0, urgent_on_default
    assert urgent_on_default["reward"] == 0.0, urgent_on_default
    local_on_default = evaluate(FAIL_UNDERTRIAGE, non_escalate_patient, protocol, rules)
    assert local_on_default["reward"] == 1.0, local_on_default
    assert local_on_default["criteria"]["disposition_ok"] == 1.0, local_on_default

    forced = _force_no_close(age_pass)
    assert forced["criteria"]["completeness_ok"] == 0.0, forced
    assert forced["reward"] == 0.0, forced
    assert forced["verdict"] == "BLOCK", forced

    dup = _grade(AGE_GATE, DUP_DURATION)
    assert dup["criteria"]["duplicate_free"] == 0.0, dup
    assert dup["verdict"] == "BLOCK", dup
    assert dup["reward"] == 0.0, dup
    assert any(ev.get("repeated_question_id") == Q_DURATION for ev in dup["evidence"]), dup

    unanswered = _grade(AGE_GATE, ORACLE_AGE_GATE)
    assert unanswered["criteria"]["duplicate_free"] == 1.0, unanswered
    assert unanswered["reward"] == 1.0, unanswered
    assert unanswered["criteria"]["options_complete"] == 1.0, unanswered

    incomplete_how_fast = {
        "schema_version": "0.1.0",
        "protocol_id": "Chest pain",
        "action": "ask_question",
        "question_id": Q_HOW_FAST,
        "option_ids": [O_SUDDENLY],
    }
    incomplete = _grade(AGE_GATE, incomplete_how_fast)
    assert incomplete["criteria"]["options_complete"] == 0.0, incomplete
    assert incomplete["criteria"]["age_ok"] == 1.0, incomplete
    assert incomplete["reward"] == 0.0, incomplete
    assert incomplete["verdict"] == "BLOCK", incomplete

    protocol_src = protocol_src_for(AGE_GATE)
    v2_protocol = load_protocol(protocol_src)
    for case in iter_v2_cases():
        if case["task_kind"] == "rollout_intake":
            def _oracle(state: dict, proto: object, disposition: str = case["close_disposition"]) -> dict:
                proposal = greedy_propose(state, proto)
                if proposal.get("action") == "close_and_act":
                    proposal = dict(proposal)
                    proposal["disposition"] = disposition
                return proposal

            result, _, _, _ = run_rollout(
                _oracle,
                case["patient_state"],
                v2_protocol,
                V2_DEMO_RULES,
                case["patient_script"],
            )
        else:
            result = evaluate(case["oracle"], case["patient_state"], v2_protocol, V2_DEMO_RULES)
        assert result["reward"] == 1.0, (case["case_id"], result)
        assert result["criteria"]["options_complete"] == 1.0, (case["case_id"], result)

    intake = TASKS[2]
    start = _load(intake / "tests" / "case" / "patient_state.json")
    assert start.get("answers") == []
    script = _load(intake / "tests" / "case" / "patient_script.json")
    intake_protocol = load_protocol(intake / "tests" / "case" / "protocol.json")
    intake_rules = _load(intake / "tests" / "demo_rules.json")
    duration_option_ids = [
        o.id
        for o in intake_protocol.options_for(Q_DURATION)
        if intake_protocol.is_age_eligible(o, int(start["age"]))
    ]

    def repeat_duration(_state: dict, proto: object) -> dict:
        return {
            "schema_version": "0.1.0",
            "protocol_id": proto.name,  # type: ignore[attr-defined]
            "action": "ask_question",
            "question_id": Q_DURATION,
            "option_ids": duration_option_ids,
        }

    dup_rollout, final_patient, dup_steps, _ = run_rollout(
        repeat_duration, start, intake_protocol, intake_rules, script
    )
    duration_answers = [
        a for a in final_patient.get("answers") or [] if a.get("question_id") == Q_DURATION
    ]
    assert len(duration_answers) == 1, duration_answers
    assert dup_rollout["criteria"]["duplicate_free"] == 0.0, dup_rollout
    assert dup_rollout["verdict"] == "BLOCK", dup_rollout
    assert sum(1 for s in dup_steps if s.get("kind") == "answered") == 1

    print("grade checks passed")
    print("age-gate oracle ALLOW 1.0; menstrual option BLOCK age_ok=0")
    print("undertriage oracle ALLOW 1.0; local_management ESCALATE safety_ok=0")
    print("agent environment contexts do not contain demo_rules.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
