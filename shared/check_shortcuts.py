"""Shortcut-policy QC across V2 fixtures. Not shipped into agent containers."""

from __future__ import annotations

import sys
from collections import defaultdict
from typing import Any, Callable

from pathlib import Path

SHARED = Path(__file__).resolve().parent
ROOT = SHARED.parent
sys.path.insert(0, str(SHARED))

from build_v2_tasks import build  # noqa: E402
from grade import evaluate, run_rollout  # noqa: E402
from greedy_agent import propose as greedy_propose  # noqa: E402
from protocol_walker import load_protocol  # noqa: E402
from v2_fixtures import DEMO_RULES, PROTOCOL_NAME, iter_cases  # noqa: E402

PROTOCOL_SRC = ROOT / "data" / "Chest pain.json"
Propose = Callable[..., dict[str, Any]]


def _close(disposition: str) -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "protocol_id": PROTOCOL_NAME,
        "action": "close_and_act",
        "disposition": disposition,
    }


def always_close(disposition: str) -> Propose:
    def propose(_state: dict[str, Any], _protocol: Any) -> dict[str, Any]:
        return _close(disposition)

    return propose


def duplicate_question(state: dict[str, Any], protocol: Any) -> dict[str, Any]:
    answers = state.get("answers") or []
    if answers:
        qid = answers[0]["question_id"]
        return {
            "schema_version": "0.1.0",
            "protocol_id": PROTOCOL_NAME,
            "action": "ask_question",
            "question_id": qid,
            "option_ids": list(answers[0].get("option_ids") or []),
        }
    age = int(state["age"])
    legal = protocol.get_legal_next_questions(set(), set(), age)
    question = legal[0]
    option_ids = [
        o.id for o in protocol.options_for(question.id) if protocol.is_age_eligible(o, age)
    ]
    return {
        "schema_version": "0.1.0",
        "protocol_id": PROTOCOL_NAME,
        "action": "ask_question",
        "question_id": question.id,
        "option_ids": option_ids,
    }


def oracle_for(case: dict[str, Any]) -> Propose:
    if case["task_kind"] != "rollout_intake":
        def propose(_state: dict[str, Any], _protocol: Any) -> dict[str, Any]:
            return dict(case["oracle"])

        return propose

    disposition = case["close_disposition"]

    def propose(state: dict[str, Any], protocol: Any) -> dict[str, Any]:
        proposal = greedy_propose(state, protocol)
        if proposal.get("action") == "close_and_act":
            proposal = dict(proposal)
            proposal["disposition"] = disposition
        return proposal

    return propose


def _grade_case(case: dict[str, Any], protocol: Any, propose: Propose) -> dict[str, Any]:
    patient = case["patient_state"]
    if case["task_kind"] == "rollout_intake":
        result, _, _, _ = run_rollout(
            propose, patient, protocol, DEMO_RULES, case["patient_script"]
        )
        return result
    return evaluate(propose(patient, protocol), patient, protocol, DEMO_RULES)


def _failed_criteria(result: dict[str, Any]) -> list[str]:
    return [key for key, value in result["criteria"].items() if value != 1.0]


def main() -> int:
    build()
    protocol = load_protocol(PROTOCOL_SRC)
    cases = iter_cases()
    policies: list[tuple[str, Propose]] = [
        ("always_urgent", always_close("urgent")),
        ("always_local_management", always_close("local_management")),
        ("always_refer", always_close("refer")),
        ("close_immediately", always_close("urgent")),
        ("duplicate_question", duplicate_question),
        ("oracle", oracle_for),  # placeholder, handled per case
    ]

    rows: list[dict[str, Any]] = []
    by_policy: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for policy_name, factory in policies:
        for case in cases:
            propose = factory(case) if policy_name == "oracle" else factory
            result = _grade_case(case, protocol, propose)
            row = {
                "policy": policy_name,
                "case_id": case["case_id"],
                "suite": case["suite"],
                "variant": case["variant"],
                "task_kind": case["task_kind"],
                "reward": result["reward"],
                "verdict": result["verdict"],
                "failed": _failed_criteria(result),
            }
            rows.append(row)
            by_policy[policy_name].append(row)

    print("policy\tcases attempted\tcases passed\tpass rate\tfailures by criterion")
    warnings: list[str] = []
    for policy_name, _ in policies:
        group = by_policy[policy_name]
        passed = [r for r in group if r["reward"] == 1.0]
        fail_counts: dict[str, int] = defaultdict(int)
        suite_pass: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for row in group:
            suite_pass[row["suite"]][1] += 1
            if row["reward"] == 1.0:
                suite_pass[row["suite"]][0] += 1
            for key in row["failed"]:
                fail_counts[key] += 1
        rate = len(passed) / len(group) if group else 0.0
        fail_txt = ",".join(f"{k}:{v}" for k, v in sorted(fail_counts.items())) or "none"
        print(f"{policy_name}\t{len(group)}\t{len(passed)}\t{rate:.2f}\t{fail_txt}")
        print("  by suite: " + ", ".join(
            f"{suite} {ok}/{n}" for suite, (ok, n) in sorted(suite_pass.items())
        ))
        if policy_name != "oracle" and passed:
            ids = ", ".join(r["case_id"] for r in passed)
            warnings.append(f"{policy_name} passes {ids}")

    def _row(policy: str, case_id: str) -> dict[str, Any]:
        matches = [r for r in rows if r["policy"] == policy and r["case_id"] == case_id]
        assert len(matches) == 1, (policy, case_id)
        return matches[0]

    assert _row("always_urgent", "case-56a8c4")["reward"] == 0.0
    assert "disposition_ok" in _row("always_urgent", "case-56a8c4")["failed"]
    assert _row("always_local_management", "case-45f7b3")["reward"] == 0.0
    assert "disposition_ok" in _row("always_local_management", "case-45f7b3")["failed"]
    for case_id in ("case-45f7b3", "case-56a8c4"):
        assert _row("always_refer", case_id)["reward"] == 0.0
        assert "disposition_ok" in _row("always_refer", case_id)["failed"]
    for case_id in ("case-89d1f7", "case-90e2a8"):
        immediate = _row("close_immediately", case_id)
        assert immediate["reward"] == 0.0
        assert "completeness_ok" in immediate["failed"]
    dup_failed = any(
        r["reward"] == 0.0 and "duplicate_free" in r["failed"]
        for r in by_policy["duplicate_question"]
    )
    assert dup_failed, by_policy["duplicate_question"]
    oracle_fail = [r for r in by_policy["oracle"] if r["reward"] != 1.0]
    assert not oracle_fail, oracle_fail

    if warnings:
        print("WARNING: shortcut policies pass some fixtures (expected on matching labels):")
        for line in warnings:
            print(f"  {line}")

    print("shortcut checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
