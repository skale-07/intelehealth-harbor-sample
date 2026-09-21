"""Validate V3 fixtures, unique-legal contrasts, isolation, and oracle grades."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SHARED = Path(__file__).resolve().parent
ROOT = SHARED.parent
sys.path.insert(0, str(SHARED))

from build_v3_tasks import STUB_AGENT, V3_ROOT, build  # noqa: E402
from grade import evaluate, expected_disposition, run_rollout  # noqa: E402
from greedy_agent import propose as greedy_propose  # noqa: E402
from protocol_walker import load_protocol  # noqa: E402
from v3_fixtures import (  # noqa: E402
    DEMO_RULES,
    FOIL_HOW_FAST,
    FOIL_MENSTRUAL_ONLY,
    FOIL_NESTED,
    FOIL_WORSEN_OMIT_MENSTRUAL,
    O_COUGH,
    O_DIFF_BREATHING,
    O_MENSTRUAL,
    O_MOVE_NO,
    O_MOVE_YES,
    PROTOCOL_ID,
    Q_ASSOCIATED,
    Q_MOVE,
    Q_MOVES_TO,
    Q_WORSEN,
    iter_cases,
    legal_question_ids,
    validate_case,
)

PROTOCOL_SRC = ROOT / "data" / "Chest pain.json"

AGENT_FORBIDDEN_NAMES = (
    "demo_rules.json",
    "v2_manifest.json",
    "v3_manifest.json",
    "manifest.json",
    "meta.json",
    "oracle.json",
    "foils.json",
    "patient_script.json",
    "patient_card.md",
    "patient_system_prompt.md",
    "grade.py",
    "protocol_walker.py",
    "encounter.py",
    "test.sh",
    "test_proposal.py",
    "solve.sh",
    "greedy_agent.py",
    "v2_fixtures.py",
    "v3_fixtures.py",
    "build_v2_tasks.py",
    "build_v3_tasks.py",
    "check_shortcuts.py",
    "check_v3_shortcuts.py",
    "verification_record.json",
    "reward.json",
    "encounter.json",
)

LEAK_PHRASES = (
    "close urgent",
    "undertriage",
    "age_eligibility",
    "nested_branch",
    "pair-age-01",
    "pair-nest-01",
    "pair-disp-01",
    "pair-inv-01",
    "pair-roll-01",
    "demo-chest-pain-disposition-v2",
    "demo-chest-pain-disposition-v3",
    "expected_disposition",
    "escalation_disposition",
    "default_disposition",
    "escalate_option_ids",
    "local_management is blocked",
    "close_and_act + urgent",
    "validated_clinically",
    "policy_id",
    "suite",
    "pair_id",
    "report_slice",
    "Q_WORSEN",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _pair(cases: list[dict], pair_id: str) -> tuple[dict, dict]:
    matched = [c for c in cases if c["pair_id"] == pair_id]
    assert len(matched) == 2, pair_id
    return matched[0], matched[1]


def _answers_key(answers: list[dict]) -> list[tuple]:
    return sorted(
        (
            a["question_id"],
            tuple(a.get("option_ids") or []),
            a.get("free_text"),
        )
        for a in answers
    )


def _policy_oracle(disposition: str):
    def propose(state: dict, protocol: object) -> dict:
        proposal = greedy_propose(state, protocol)
        if proposal.get("action") == "close_and_act":
            proposal = dict(proposal)
            proposal["disposition"] = disposition
        return proposal

    return propose


def _assert_isolation(task: Path, kind: str) -> None:
    env = task / "environment"
    for name in AGENT_FORBIDDEN_NAMES:
        hits = list(env.rglob(name))
        assert not hits, f"{task.name}: forbidden {name} in agent image: {hits}"
    visible = [task / "instruction.md", task / "task.toml", env / "case" / "patient_state.json"]
    for path in visible:
        text = path.read_text(encoding="utf-8").lower()
        for phrase in LEAK_PHRASES:
            assert phrase.lower() not in text, f"{path}: leaked {phrase!r}"
    src = PROTOCOL_SRC.read_bytes()
    assert (task / "environment" / "case" / "protocol.json").read_bytes() == src
    assert (task / "tests" / "case" / "protocol.json").read_bytes() == src
    if kind == "rollout_intake":
        stub = (env / "agent.py").read_text(encoding="utf-8")
        assert stub == STUB_AGENT
        assert re.search(r'^CLOSE_DISPOSITION = ""', stub, re.M)
        oracle_agent = (task / "solution" / "agent.py").read_text(encoding="utf-8")
        assert stub != oracle_agent
        assert "CLOSE_DISPOSITION = \"urgent\"" not in stub
        assert "CLOSE_DISPOSITION = \"local_management\"" not in stub
    else:
        assert not (env / "agent.py").exists()


def main() -> int:
    build()
    protocol = load_protocol(PROTOCOL_SRC)
    cases = iter_cases()
    assert len(cases) == 10, len(cases)
    for case in cases:
        validate_case(case, protocol)

    ineligible, eligible = _pair(cases, "pair-age-01")
    assert ineligible["age"] == 8 and eligible["age"] == 12
    assert ineligible["answers"] == eligible["answers"]
    assert legal_question_ids(ineligible, protocol) == [Q_WORSEN]
    assert legal_question_ids(eligible, protocol) == [Q_WORSEN]
    how_fast_fail = evaluate(FOIL_HOW_FAST, ineligible["patient_state"], protocol, DEMO_RULES)
    assert how_fast_fail["criteria"]["duplicate_free"] == 0.0, how_fast_fail
    assert how_fast_fail["reward"] == 0.0, how_fast_fail
    inel = evaluate(FOIL_MENSTRUAL_ONLY, ineligible["patient_state"], protocol, DEMO_RULES)
    elig_menstrual = evaluate(FOIL_MENSTRUAL_ONLY, eligible["patient_state"], protocol, DEMO_RULES)
    assert inel["criteria"]["age_ok"] == 0.0, inel
    assert elig_menstrual["criteria"]["age_ok"] == 1.0, elig_menstrual
    assert elig_menstrual["criteria"]["options_complete"] == 0.0, elig_menstrual
    omit = evaluate(FOIL_WORSEN_OMIT_MENSTRUAL, eligible["patient_state"], protocol, DEMO_RULES)
    assert omit["criteria"]["options_complete"] == 0.0, omit
    assert omit["criteria"]["age_ok"] == 1.0, omit
    assert O_MENSTRUAL in eligible["oracle"]["option_ids"]
    assert O_MENSTRUAL not in ineligible["oracle"]["option_ids"]

    inactive, active = _pair(cases, "pair-nest-01")
    assert legal_question_ids(inactive, protocol) == []
    assert legal_question_ids(active, protocol) == [Q_MOVES_TO]
    move_inactive = [a for a in inactive["answers"] if a["question_id"] == Q_MOVE][0]
    move_active = [a for a in active["answers"] if a["question_id"] == Q_MOVE][0]
    assert move_inactive["option_ids"] == [O_MOVE_NO]
    assert move_active["option_ids"] == [O_MOVE_YES]
    rest_i = [a for a in inactive["answers"] if a["question_id"] != Q_MOVE]
    rest_a = [a for a in active["answers"] if a["question_id"] != Q_MOVE]
    assert rest_i == rest_a
    nest_off = evaluate(FOIL_NESTED, inactive["patient_state"], protocol, DEMO_RULES)
    nest_on = evaluate(FOIL_NESTED, active["patient_state"], protocol, DEMO_RULES)
    assert nest_off["criteria"]["nesting_ok"] == 0.0, nest_off
    assert nest_on["criteria"]["nesting_ok"] == 1.0, nest_on
    assert nest_on["reward"] == 1.0, nest_on
    close_active = evaluate(
        {"schema_version": "0.1.0", "protocol_id": "Chest pain", "action": "close_and_act", "disposition": "local_management"},
        active["patient_state"],
        protocol,
        DEMO_RULES,
    )
    assert close_active["criteria"]["completeness_ok"] == 0.0, close_active
    close_inactive = evaluate(inactive["oracle"], inactive["patient_state"], protocol, DEMO_RULES)
    assert close_inactive["reward"] == 1.0, close_inactive
    assert close_inactive["criteria"]["disposition_ok"] == 1.0, close_inactive
    assert close_inactive["criteria"]["nesting_ok"] == 1.0, close_inactive
    urgent_inactive = evaluate(
        {"schema_version": "0.1.0", "protocol_id": "Chest pain", "action": "close_and_act", "disposition": "urgent"},
        inactive["patient_state"],
        protocol,
        DEMO_RULES,
    )
    assert urgent_inactive["criteria"]["disposition_ok"] == 0.0, urgent_inactive
    assert urgent_inactive["criteria"]["nesting_ok"] == 1.0, urgent_inactive

    escalate, default = _pair(cases, "pair-disp-01")
    esc_sel = {oid for a in escalate["answers"] for oid in (a.get("option_ids") or [])}
    def_sel = {oid for a in default["answers"] for oid in (a.get("option_ids") or [])}
    assert O_DIFF_BREATHING in esc_sel and O_DIFF_BREATHING not in def_sel
    assert O_COUGH in def_sel and O_COUGH not in esc_sel
    esc_rest = [a for a in escalate["answers"] if a["question_id"] != Q_ASSOCIATED]
    def_rest = [a for a in default["answers"] if a["question_id"] != Q_ASSOCIATED]
    assert esc_rest == def_rest
    assert expected_disposition(escalate["patient_state"], DEMO_RULES) == "urgent"
    assert expected_disposition(default["patient_state"], DEMO_RULES) == "local_management"

    alpha, beta = _pair(cases, "pair-inv-01")
    assert expected_disposition(alpha["patient_state"], DEMO_RULES) == expected_disposition(
        beta["patient_state"], DEMO_RULES
    )
    assert expected_disposition(alpha["patient_state"], DEMO_RULES) == "local_management"
    assert _answers_key(alpha["answers"]) == _answers_key(beta["answers"])
    assert alpha["answers"] != beta["answers"]
    assert alpha["label"] != beta["label"]

    for case in cases:
        if case["task_kind"] == "rollout_intake":
            start = case["patient_state"]
            result, _, steps, last = run_rollout(
                _policy_oracle(case["close_disposition"]),
                start,
                protocol,
                DEMO_RULES,
                case["patient_script"],
            )
            assert result["reward"] == 1.0, (case["case_id"], result)
            assert last is not None and last.get("disposition") == case["close_disposition"]
            assert steps[-1]["action"] == "close_and_act"
            stub_result, _, _, stub_last = run_rollout(
                _policy_oracle(""),
                start,
                protocol,
                DEMO_RULES,
                case["patient_script"],
            )
            assert stub_result["reward"] == 0.0, (case["case_id"], stub_result)
            assert stub_result["criteria"]["schema_valid"] == 0.0, stub_result
            assert stub_last is not None and stub_last.get("disposition") == ""
        else:
            result = evaluate(case["oracle"], case["patient_state"], protocol, DEMO_RULES)
            assert result["reward"] == 1.0, (case["case_id"], result)
            assert result["criteria"]["options_complete"] == 1.0, result

        task = V3_ROOT / case["case_id"]
        _assert_isolation(task, case["task_kind"])
        patient = _load(task / "environment" / "case" / "patient_state.json")
        assert patient["protocol_id"] == PROTOCOL_ID
        env_text = json.dumps(patient)
        assert "urgent" not in env_text
        assert "local_management" not in env_text
        assert "refer" not in env_text

    print("v3 fixture checks passed")
    print(f"cases={len(cases)}")
    print("grammar: age pair + nested-active ask + nested-inactive nesting")
    print("disposition: closes + nested-inactive label + stub rollouts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
