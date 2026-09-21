"""Local rollout checks for all intake tasks. Does not need Docker or Harbor."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

SHARED = Path(__file__).resolve().parent
sys.path.insert(0, str(SHARED))

from grade import run_rollout, write_outputs  # noqa: E402
from greedy_agent import propose as greedy_propose  # noqa: E402
from protocol_walker import load_protocol  # noqa: E402
from sync_task_assets import INTAKE_TASKS, protocol_src_for, sync  # noqa: E402

O_DIFF_BREATHING = "ID_f11aa381-71db-4773-940a-2b44b7b0c5e9"
HIDDEN = (
    "patient_script.json",
    "patient_card.md",
    "patient_system_prompt.md",
    "demo_rules.json",
)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def close_immediately(state: dict[str, Any], protocol: Any) -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "protocol_id": protocol.name,
        "action": "close_and_act",
        "disposition": "urgent",
    }


def greedy_local_management(state: dict[str, Any], protocol: Any) -> dict[str, Any]:
    proposal = greedy_propose(state, protocol)
    if proposal.get("action") == "close_and_act":
        proposal = dict(proposal)
        proposal["disposition"] = "local_management"
    return proposal


def _check_intake(task: Path) -> None:
    env = task / "environment"
    for name in HIDDEN:
        hits = list(env.rglob(name))
        assert not hits, f"{task.name}: {name} must not live in the agent image: {hits}"
    src = protocol_src_for(task).read_bytes()
    assert (task / "environment" / "case" / "protocol.json").read_bytes() == src
    assert (task / "tests" / "case" / "protocol.json").read_bytes() == src

    protocol = load_protocol(task / "tests" / "case" / "protocol.json")
    patient = _load(task / "tests" / "case" / "patient_state.json")
    rules = _load(task / "tests" / "demo_rules.json")
    script = _load(task / "tests" / "case" / "patient_script.json")
    foils = _load(task / "tests" / "case" / "foils.json")
    assert patient.get("answers") == []
    assert (task / "tests" / "case" / "patient_card.md").is_file()
    assert (task / "tests" / "case" / "patient_system_prompt.md").is_file()

    oracle, final_patient, steps, last = run_rollout(
        greedy_propose, patient, protocol, rules, script
    )
    assert oracle["reward"] == foils["oracle"]["reward"], (task.name, oracle)
    assert oracle["verdict"] == "ALLOW", (task.name, oracle)
    assert last is not None and last.get("disposition") == foils["oracle"]["disposition"]
    assert len(steps) >= foils["oracle"]["min_steps"], (task.name, len(steps))
    assert steps[-1]["kind"] == "proposal"
    assert steps[-1]["action"] == "close_and_act"
    answered = [s for s in steps if s["kind"] == "answered"]
    assert answered
    assert all(s["source"] == "environment" for s in answered)

    immediate, _, _, _ = run_rollout(close_immediately, patient, protocol, rules, script)
    assert immediate["criteria"]["completeness_ok"] == foils["close_immediately"]["completeness_ok"], (
        task.name,
        immediate,
    )
    assert immediate["verdict"] == foils["close_immediately"]["verdict"], (task.name, immediate)

    if task.name == "chest-pain-intake":
        selected = {
            oid
            for ans in final_patient.get("answers") or []
            for oid in (ans.get("option_ids") or [])
        }
        assert O_DIFF_BREATHING in selected
        local, _, _, _ = run_rollout(greedy_local_management, patient, protocol, rules, script)
        assert local["criteria"]["completeness_ok"] == foils["greedy_local_management"]["completeness_ok"]
        assert local["criteria"]["safety_ok"] == foils["greedy_local_management"]["safety_ok"]
        assert local["verdict"] == foils["greedy_local_management"]["verdict"]

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        write_outputs(
            oracle, out, patient=patient, protocol=protocol, proposal=last, steps=steps
        )
        encounter = _load(out / "encounter.json")
        assert encounter["kind"] == "intake_encounter"
        assert encounter["steps"][-1]["action"] == "close_and_act"
        assert (out / "reward.json").is_file()

    print(f"  {task.name}: oracle ALLOW 1.0 steps={len(steps)}")


def main() -> int:
    sync()
    for task in INTAKE_TASKS:
        _check_intake(task)
    print("rollout checks passed")
    print("chest-pain-intake oracle ALLOW 1.0; close-immediately BLOCK completeness_ok=0")
    print("chest-pain greedy+local_management ESCALATE")
    print("patient_script.json / patient_card.md are not in agent environments")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
