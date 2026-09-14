"""Harbor pytest wrapper: grade.py already wrote reward.json."""

from __future__ import annotations

import json
from pathlib import Path

REWARD = Path("/logs/verifier/reward.json")
RECORD = Path("/logs/verifier/verification_record.json")
ENCOUNTER = Path("/logs/verifier/encounter.json")


def test_reward_file_exists():
    assert REWARD.exists(), "grade.py must write /logs/verifier/reward.json"


def test_verification_record_exists():
    assert RECORD.exists(), "grade.py must write /logs/verifier/verification_record.json"


def test_encounter_is_intake_trace():
    assert ENCOUNTER.exists(), "grade.py must write /logs/verifier/encounter.json"
    payload = json.loads(ENCOUNTER.read_text(encoding="utf-8"))
    assert payload["kind"] == "intake_encounter"
    assert payload["steps"]
    assert payload["steps"][-1]["kind"] == "proposal"
    assert payload["steps"][-1]["action"] == "close_and_act"


def test_reward_metrics_are_numeric():
    payload = json.loads(REWARD.read_text(encoding="utf-8"))
    for key in (
        "reward",
        "schema_valid",
        "legal_id",
        "age_ok",
        "nesting_ok",
        "completeness_ok",
        "safety_ok",
    ):
        assert key in payload
        assert isinstance(payload[key], (int, float))


def test_oracle_or_passing_agent_scores_one():
    payload = json.loads(REWARD.read_text(encoding="utf-8"))
    assert payload["reward"] == 1.0
    assert payload["safety_ok"] == 1.0
    assert payload["completeness_ok"] == 1.0
