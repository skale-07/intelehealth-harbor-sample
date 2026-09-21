"""Validate V2 fixtures, pair contrasts, isolation, and oracle grades."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SHARED = Path(__file__).resolve().parent
ROOT = SHARED.parent
sys.path.insert(0, str(SHARED))

from build_v2_tasks import V2_ROOT, build  # noqa: E402
from grade import evaluate, expected_disposition, run_rollout  # noqa: E402
from greedy_agent import propose as greedy_propose  # noqa: E402
from protocol_walker import load_protocol  # noqa: E402
from v2_fixtures import (  # noqa: E402
    DEMO_RULES,
    FOIL_MENSTRUAL,
    FOIL_NESTED,
    O_COUGH,
    O_DIFF_BREATHING,
    O_MENSTRUAL,
    O_MOVE_NO,
    O_MOVE_YES,
    PROTOCOL_ID,
    Q_ASSOCIATED,
    Q_MOVE,
    iter_cases,
    validate_case,
)

PROTOCOL_SRC = ROOT / "data" / "Chest pain.json"

AGENT_FORBIDDEN_NAMES = (
    "demo_rules.json",
    "v2_manifest.json",
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
    "build_v2_tasks.py",
    "check_shortcuts.py",
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


def _assert_isolation(task: Path) -> None:
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


def main() -> int:
    build()
    protocol = load_protocol(PROTOCOL_SRC)
    cases = iter_cases()
    assert len(cases) >= 6, len(cases)
    for case in cases:
        validate_case(case, protocol)

    ineligible, eligible = _pair(cases, "pair-age-01")
    assert ineligible["age"] == 8 and eligible["age"] == 12
    assert ineligible["answers"] == eligible["answers"]
    assert ineligible["patient_state"]["label"] == eligible["patient_state"]["label"]
    assert FOIL_MENSTRUAL["option_ids"] == [O_MENSTRUAL]
    inel = evaluate(FOIL_MENSTRUAL, ineligible["patient_state"], protocol, DEMO_RULES)
    elig = evaluate(FOIL_MENSTRUAL, eligible["patient_state"], protocol, DEMO_RULES)
    assert inel["criteria"]["age_ok"] == 0.0, inel
    assert elig["criteria"]["age_ok"] == 1.0, elig
    assert elig["reward"] == 1.0, elig

    inactive, active = _pair(cases, "pair-nest-01")
    assert inactive["answers"][:2] == active["answers"][:2]
    assert inactive["answers"][2]["question_id"] == Q_MOVE
    assert active["answers"][2]["question_id"] == Q_MOVE
    assert inactive["answers"][2]["option_ids"] == [O_MOVE_NO]
    assert active["answers"][2]["option_ids"] == [O_MOVE_YES]
    assert len(inactive["answers"]) == len(active["answers"]) == 3
    nest_off = evaluate(FOIL_NESTED, inactive["patient_state"], protocol, DEMO_RULES)
    nest_on = evaluate(FOIL_NESTED, active["patient_state"], protocol, DEMO_RULES)
    assert nest_off["criteria"]["nesting_ok"] == 0.0, nest_off
    assert nest_on["criteria"]["nesting_ok"] == 1.0, nest_on
    assert nest_on["reward"] == 1.0, nest_on

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
        if case["task_kind"] == "one_shot_question":
            result = evaluate(case["oracle"], case["patient_state"], protocol, DEMO_RULES)
            assert result["reward"] == 1.0, (case["case_id"], result)
        elif case["task_kind"] == "one_shot_close":
            result = evaluate(case["oracle"], case["patient_state"], protocol, DEMO_RULES)
            assert result["reward"] == 1.0, (case["case_id"], result)
            assert result["criteria"]["disposition_ok"] == 1.0, result
        else:
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

        task = V2_ROOT / case["case_id"]
        _assert_isolation(task)
        patient = _load(task / "environment" / "case" / "patient_state.json")
        assert patient["protocol_id"] == PROTOCOL_ID
        env_text = json.dumps(patient)
        assert "urgent" not in env_text
        assert "local_management" not in env_text
        assert "refer" not in env_text

    print("v2 fixture checks passed")
    print(f"cases={len(cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
