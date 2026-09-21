"""Deterministic Harbor grader.

One-shot tasks: grade `/app/proposal.json`.
Rollout tasks: import `/app/agent.py` and step it against a hidden patient_script.

Reward is a hard gate: min(criteria) so any failed criterion yields 0.0.
Disposition scoring uses a verifier-only synthetic DEMO_POLICY. Chest pain.json
does not encode diagnoses or dispositions. Non-applicable criteria stay 1.0.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

from encounter import answered_turn, build_encounter, build_rollout_encounter, _proposal_turn
from protocol_walker import Protocol, load_protocol

VERIFIER_VERSION = "0.3.0"
ACTION_ASK = "ask_question"
ACTION_CLOSE = "close_and_act"
ALLOWED_DISPOSITIONS = {"local_management", "refer", "urgent"}
PHASE1_ESCALATION_DISPOSITION = "urgent"
PHASE1_DEFAULT_DISPOSITION = "local_management"

ALLOW = "ALLOW"
WARN = "WARN"
BLOCK = "BLOCK"
ESCALATE = "ESCALATE"
_SEVERITY = {ALLOW: 0, WARN: 1, ESCALATE: 2, BLOCK: 3}

CRITERIA_KEYS = (
    "schema_valid",
    "legal_id",
    "age_ok",
    "nesting_ok",
    "completeness_ok",
    "safety_ok",
    "disposition_ok",
    "duplicate_free",
    "options_complete",
)


def initial_criteria() -> dict[str, float]:
    return {key: 1.0 for key in CRITERIA_KEYS}


def compute_reward(criteria: dict[str, float]) -> float:
    """Hard gate: every criterion 1.0 → 1.0; any 0.0 → 0.0."""
    if not criteria:
        return 0.0
    return float(min(criteria.values()))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _selected_option_ids(patient: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for answer in patient.get("answers") or []:
        ids.update(answer.get("option_ids") or [])
    return ids


def _answered_question_ids(patient: dict[str, Any]) -> set[str]:
    return {a["question_id"] for a in (patient.get("answers") or []) if a.get("question_id")}


def age_eligible_option_ids(protocol: Protocol, question_id: str, age: int) -> list[str]:
    return [o.id for o in protocol.options_for(question_id) if protocol.is_age_eligible(o, age)]


def expected_disposition(patient: dict[str, Any], demo_rules: dict[str, Any]) -> str:
    """Synthetic demo mapping. Not a protocol field."""
    escalate_ids = set(demo_rules.get("escalate_option_ids") or [])
    selected = _selected_option_ids(patient)
    if selected & escalate_ids:
        return str(demo_rules.get("escalation_disposition") or PHASE1_ESCALATION_DISPOSITION)
    return str(demo_rules.get("default_disposition") or PHASE1_DEFAULT_DISPOSITION)


def _evidence(protocol: Protocol, node_id: str, note: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    node = protocol.get_node(node_id)
    item = {
        "source": protocol.source_file,
        "path": node_id,
        "field": "id",
        "value": node.text if node else None,
        "note": note,
        "source_kind": "protocol_grammar",
        "validated_clinically": False,
    }
    if extra:
        item.update(extra)
    return item


def _demo_evidence(note: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "source": "demo_rules.json",
        "source_kind": "DEMO_POLICY",
        "note": note,
        "validated_clinically": False,
    }
    if extra:
        item.update(extra)
    return item


def evaluate(
    proposal: dict[str, Any] | None,
    patient: dict[str, Any],
    protocol: Protocol,
    demo_rules: dict[str, Any],
) -> dict[str, Any]:
    criteria = initial_criteria()
    reasons: list[str] = []
    evidence: list[dict[str, Any]] = []
    rules_checked = list(CRITERIA_KEYS)
    verdict = ALLOW

    def fail(metric: str, next_verdict: str, reason: str, ev: dict[str, Any] | None = None) -> None:
        nonlocal verdict
        criteria[metric] = 0.0
        reasons.append(reason)
        if ev:
            evidence.append(ev)
        if _SEVERITY[next_verdict] > _SEVERITY[verdict]:
            verdict = next_verdict

    if not isinstance(proposal, dict):
        fail("schema_valid", BLOCK, "Proposal is missing or not a JSON object.")
        return _pack(criteria, verdict, reasons, evidence, rules_checked, protocol)

    action = proposal.get("action")
    protocol_id = proposal.get("protocol_id")
    schema_version = proposal.get("schema_version")
    if schema_version != "0.1.0":
        fail("schema_valid", BLOCK, f"schema_version must be 0.1.0, got {schema_version!r}.")
    if action not in {ACTION_ASK, ACTION_CLOSE}:
        fail("schema_valid", BLOCK, f"action must be ask_question or close_and_act, got {action!r}.")
    if not protocol_id:
        fail("schema_valid", BLOCK, "protocol_id is required.")
    elif protocol_id not in {protocol.name, protocol.protocol_id}:
        fail("schema_valid", BLOCK, f"protocol_id {protocol_id!r} does not match {protocol.name}.")
    if action == ACTION_ASK and not proposal.get("question_id"):
        fail("schema_valid", BLOCK, "ask_question requires question_id.")
    if action == ACTION_CLOSE and proposal.get("disposition") not in ALLOWED_DISPOSITIONS:
        fail("schema_valid", BLOCK, "close_and_act requires disposition local_management|refer|urgent.")

    if criteria["schema_valid"] != 1.0:
        return _pack(criteria, verdict, reasons, evidence, rules_checked, protocol)

    age = int(patient["age"])
    selected = _selected_option_ids(patient)
    answered = _answered_question_ids(patient)

    if action == ACTION_ASK:
        qid = proposal["question_id"]
        if qid in answered:
            fail(
                "duplicate_free",
                BLOCK,
                f"Question {qid} was already answered. Repeated questions are blocked.",
                {
                    "source": "patient_state.answers",
                    "path": qid,
                    "field": "question_id",
                    "value": qid,
                    "repeated_question_id": qid,
                    "note": "duplicate_free fails when ask_question repeats an answered ID.",
                    "validated_clinically": False,
                },
            )
            return _pack(criteria, verdict, reasons, evidence, rules_checked, protocol)

        option_ids = list(proposal.get("option_ids") or [])
        node = protocol.get_node(qid)
        if node is None:
            fail(
                "legal_id",
                BLOCK,
                f"question_id {qid} does not exist in {protocol.source_file}.",
                {
                    "source": protocol.source_file,
                    "path": qid,
                    "field": "id",
                    "value": None,
                    "note": "No node with this ID exists in the protocol.",
                    "validated_clinically": False,
                },
            )
        elif not node.is_question:
            fail(
                "legal_id",
                BLOCK,
                f"{qid} exists but is not a question node.",
                _evidence(protocol, qid, "Node exists but is not a question."),
            )
        else:
            for oid in option_ids:
                opt = protocol.get_node(oid)
                if opt is None:
                    fail(
                        "legal_id",
                        BLOCK,
                        f"option_id {oid} does not exist in the protocol.",
                        {
                            "source": protocol.source_file,
                            "path": oid,
                            "field": "id",
                            "value": None,
                            "note": "Option ID is not in the protocol.",
                            "validated_clinically": False,
                        },
                    )
                elif opt.parent_id != qid:
                    fail(
                        "legal_id",
                        BLOCK,
                        f"option_id {oid} is not an option of {qid}.",
                        _evidence(protocol, oid, "Option does not belong to the proposed question."),
                    )

        referenced = [qid, *option_ids]
        for nid in referenced:
            if not protocol.has_node(nid):
                continue
            offender = protocol.age_violation(nid, age)
            if offender is not None:
                bound = (
                    f"age_min={offender.age_min}" if offender.age_min is not None
                    else f"age_max={offender.age_max}"
                )
                fail(
                    "age_ok",
                    BLOCK,
                    f"Patient age {age} violates {bound} on \"{offender.text}\" ({offender.id}).",
                    {
                        "source": protocol.source_file,
                        "path": offender.id,
                        "field": "age_min" if offender.age_min is not None else "age_max",
                        "value": offender.age_min if offender.age_min is not None else offender.age_max,
                        "patient_age": age,
                        "note": "Age restriction is declared verbatim in the protocol JSON.",
                        "validated_clinically": False,
                    },
                )

        if node is not None and node.is_question:
            eligible = set(age_eligible_option_ids(protocol, qid, age))
            missing_eligible = eligible - set(option_ids)
            if missing_eligible:
                fail(
                    "options_complete",
                    BLOCK,
                    (
                        f"option_ids omit {len(missing_eligible)} age-eligible option(s) of "
                        f"\"{node.text}\" ({qid})."
                    ),
                    _evidence(
                        protocol,
                        qid,
                        "Ask must list every age-eligible option of the question.",
                        extra={"missing_option_ids": sorted(missing_eligible)},
                    ),
                )
            gate = protocol.activating_option(qid)
            if gate is not None and not protocol.is_branch_active(qid, selected):
                fail(
                    "nesting_ok",
                    BLOCK,
                    f"Nested question \"{node.text}\" is not reachable because parent option "
                    f"\"{gate.text}\" is not selected.",
                    _evidence(protocol, gate.id, "Required activating option is not selected."),
                )

    elif action == ACTION_CLOSE:
        applicable = protocol.get_applicable_required_questions(selected, age)
        missing = [q for q in applicable if q.id not in answered]
        if missing:
            preview = ", ".join(f'"{q.text}"' for q in missing[:3])
            more = f" (+{len(missing) - 3} more)" if len(missing) > 3 else ""
            fail(
                "completeness_ok",
                BLOCK,
                f"{len(missing)} applicable isRequired questions are unanswered: {preview}{more}.",
                _evidence(protocol, missing[0].id, "isRequired=true in the protocol, unanswered."),
            )
            for q in missing[:8]:
                evidence.append(_evidence(protocol, q.id, "isRequired=true, unanswered."))

        blocked = demo_rules.get("blocks_dispositions") or ["local_management"]
        escalate_ids = set(demo_rules.get("escalate_option_ids") or [])
        disposition = proposal.get("disposition")
        triggered = sorted(selected & escalate_ids)
        if disposition in blocked and triggered:
            fail(
                "safety_ok",
                ESCALATE,
                (
                    f"Disposition {disposition!r} is blocked by demo policy because selected "
                    f"option IDs {triggered} are listed in demo_rules.json. "
                    "This is demo policy, not a protocol red-flag field."
                ),
                _demo_evidence(
                    "INTERPRETATION: demo policy, not encoded in Chest pain.json.",
                    {
                        "path": "escalate_option_ids",
                        "field": "escalate_option_ids",
                        "value": triggered,
                    },
                ),
            )

        expected = expected_disposition(patient, demo_rules)
        if disposition != expected:
            fail(
                "disposition_ok",
                ESCALATE,
                (
                    f"Submitted disposition {disposition!r} does not match synthetic demo "
                    f"expected {expected!r} (source=DEMO_POLICY, validated_clinically=false). "
                    f"Policy: escalate_option_ids present → {demo_rules.get('escalation_disposition') or PHASE1_ESCALATION_DISPOSITION}; "
                    f"else → {demo_rules.get('default_disposition') or PHASE1_DEFAULT_DISPOSITION}. "
                    "Chest pain.json does not define this mapping."
                ),
                _demo_evidence(
                    "Disposition compared to DEMO_POLICY after close_and_act. Expected value is not shown to the agent before grading.",
                    {
                        "path": "expected_disposition",
                        "field": "disposition",
                        "submitted": disposition,
                        "expected": expected,
                        "triggered_option_ids": triggered,
                        "policy_id": demo_rules.get("policy_id"),
                    },
                ),
            )

    return _pack(criteria, verdict, reasons, evidence, rules_checked, protocol)


def _pack(
    criteria: dict[str, float],
    verdict: str,
    reasons: list[str],
    evidence: list[dict[str, Any]],
    rules_checked: list[str],
    protocol: Protocol,
) -> dict[str, Any]:
    return {
        "reward": compute_reward(criteria),
        "criteria": criteria,
        "verdict": verdict,
        "reasons": reasons,
        "evidence": evidence,
        "rules_checked": rules_checked,
        "verifier_version": VERIFIER_VERSION,
        "protocol_id": protocol.protocol_id,
        "protocol_name": protocol.name,
        "engine_version": protocol.engine_version,
        "ground_truth_version": protocol.source_file,
    }


def write_outputs(
    result: dict[str, Any],
    out_dir: Path,
    *,
    patient: dict[str, Any],
    protocol: Protocol,
    proposal: dict[str, Any] | None,
    steps: list[dict[str, Any]] | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    criteria = result["criteria"]
    reward = {"reward": float(result["reward"])}
    for key in CRITERIA_KEYS:
        reward[key] = float(criteria[key])
    (out_dir / "reward.json").write_text(
        json.dumps(reward, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    failed = [key for key, value in criteria.items() if value != 1.0]
    record = {
        "verdict": result["verdict"],
        "reasons": result["reasons"],
        "evidence": result["evidence"],
        "rules_checked": result["rules_checked"],
        "criteria": criteria,
        "failed_criteria": failed,
        "reward": result["reward"],
        "verifier_version": result["verifier_version"],
        "protocol_id": result["protocol_id"],
        "protocol_name": result["protocol_name"],
        "engine_version": result["engine_version"],
        "ground_truth_version": result["ground_truth_version"],
        "disposition_policy": {
            "source": "DEMO_POLICY",
            "validated_clinically": False,
            "note": "Disposition mapping is synthetic demo policy, not encoded in the protocol.",
        },
    }
    (out_dir / "verification_record.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if steps is not None:
        encounter = build_rollout_encounter(patient, protocol, steps, result)
    else:
        encounter = build_encounter(patient, protocol, proposal, result)
    (out_dir / "encounter.json").write_text(
        json.dumps(encounter, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _load_agent(path: Path) -> Callable[..., dict[str, Any]] | None:
    spec = importlib.util.spec_from_file_location("submitted_agent", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    propose = getattr(module, "propose", None)
    return propose if callable(propose) else None


def _chart_answer(script: dict[str, Any], question_id: str) -> dict[str, Any] | None:
    entry = script.get(question_id)
    if not isinstance(entry, dict):
        return None
    return {
        "question_id": question_id,
        "option_ids": list(entry.get("option_ids") or []),
        "free_text": entry.get("free_text"),
    }


def _force_no_close(result: dict[str, Any]) -> dict[str, Any]:
    criteria = dict(result["criteria"])
    reasons = list(result["reasons"])
    verdict = result["verdict"]
    if criteria.get("completeness_ok") == 1.0:
        criteria["completeness_ok"] = 0.0
        reasons.append("Episode ended without close_and_act.")
        if _SEVERITY[BLOCK] > _SEVERITY[verdict]:
            verdict = BLOCK
    packed = dict(result)
    packed["criteria"] = criteria
    packed["reasons"] = reasons
    packed["verdict"] = verdict
    packed["reward"] = compute_reward(criteria)
    return packed


def run_rollout(
    propose: Callable[..., Any],
    start_patient: dict[str, Any],
    protocol: Protocol,
    demo_rules: dict[str, Any],
    patient_script: dict[str, Any],
    max_steps: int = 40,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]:
    patient = copy.deepcopy(start_patient)
    patient["answers"] = list(patient.get("answers") or [])
    steps: list[dict[str, Any]] = []
    last_result: dict[str, Any] | None = None
    last_proposal: dict[str, Any] | None = None
    closed = False
    t = 0
    for _ in range(max_steps):
        try:
            proposal = propose(copy.deepcopy(patient), protocol)
        except Exception as exc:
            last_proposal = None
            last_result = evaluate(None, patient, protocol, demo_rules)
            last_result["reasons"] = list(last_result["reasons"]) + [f"propose() raised: {exc}"]
            steps.append(_proposal_turn(None, protocol, t))
            break
        if not isinstance(proposal, dict):
            proposal = None
        last_proposal = proposal
        last_result = evaluate(proposal, patient, protocol, demo_rules)
        turn = _proposal_turn(proposal, protocol, t)
        turn["verdict"] = last_result["verdict"]
        steps.append(turn)
        t += 1
        if proposal is None or last_result["verdict"] == BLOCK:
            break
        if proposal.get("action") == ACTION_CLOSE:
            closed = True
            break
        if proposal.get("action") == ACTION_ASK:
            answer = _chart_answer(patient_script, proposal["question_id"])
            if answer is not None:
                patient["answers"].append(answer)
                steps.append(
                    answered_turn(
                        answer["question_id"],
                        list(answer["option_ids"]),
                        protocol,
                        t,
                        free_text=answer.get("free_text"),
                        source="environment",
                    )
                )
                t += 1
    if last_result is None:
        last_result = evaluate(None, patient, protocol, demo_rules)
    if not closed:
        last_result = _force_no_close(last_result)
    return last_result, patient, steps, last_proposal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal", default="/app/proposal.json")
    parser.add_argument("--agent", default="/app/agent.py")
    parser.add_argument("--patient", default="/tests/case/patient_state.json")
    parser.add_argument("--protocol", default="/tests/case/protocol.json")
    parser.add_argument("--rules", default="/tests/demo_rules.json")
    parser.add_argument("--script", default="/tests/case/patient_script.json")
    parser.add_argument("--out", default="/logs/verifier")
    args = parser.parse_args(argv)

    protocol = load_protocol(args.protocol)
    patient = _load_json(Path(args.patient))
    demo_rules = _load_json(Path(args.rules))
    agent_path = Path(args.agent)
    script_path = Path(args.script)

    if agent_path.exists() and script_path.exists():
        propose = _load_agent(agent_path)
        if propose is None:
            result = evaluate(None, patient, protocol, demo_rules)
            result["reasons"] = list(result["reasons"]) + ["agent.py has no callable propose()."]
            write_outputs(result, Path(args.out), patient=patient, protocol=protocol, proposal=None)
            print(json.dumps({"verdict": result["verdict"], "reward": result["reward"], "reasons": result["reasons"]}))
            return 1
        script = _load_json(script_path)
        result, patient, steps, proposal = run_rollout(
            propose, patient, protocol, demo_rules, script
        )
        write_outputs(
            result, Path(args.out), patient=patient, protocol=protocol, proposal=proposal, steps=steps
        )
        print(json.dumps({"verdict": result["verdict"], "reward": result["reward"], "reasons": result["reasons"]}))
        return 0 if result["reward"] == 1.0 else 1

    proposal_path = Path(args.proposal)
    proposal: dict[str, Any] | None = None
    if proposal_path.exists():
        try:
            loaded = json.loads(proposal_path.read_text(encoding="utf-8"))
            proposal = loaded if isinstance(loaded, dict) else None
        except json.JSONDecodeError:
            proposal = None

    result = evaluate(proposal, patient, protocol, demo_rules)
    write_outputs(result, Path(args.out), patient=patient, protocol=protocol, proposal=proposal)
    print(json.dumps({"verdict": result["verdict"], "reward": result["reward"], "reasons": result["reasons"]}))
    return 0 if result["reward"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
