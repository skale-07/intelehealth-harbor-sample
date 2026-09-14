"""Pin Chest pain.json into the three Harbor task trees."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_DIR = ROOT / "data"
SHARED = ROOT / "shared"

TASK_PROTOCOLS = {
    "chest-pain-age-gate": "Chest pain.json",
    "chest-pain-undertriage": "Chest pain.json",
    "chest-pain-intake": "Chest pain.json",
}

TASKS = [ROOT / "datasets" / "intelehealth-verify" / name for name in TASK_PROTOCOLS]
INTAKE_TASKS = [t for t in TASKS if t.name.endswith("-intake")]
GRADER_FILES = ("protocol_walker.py", "grade.py", "encounter.py", "proposal_schema.json")


def protocol_src_for(task: Path) -> Path:
    path = PROTOCOL_DIR / TASK_PROTOCOLS[task.name]
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def sync() -> None:
    for task in TASKS:
        src = protocol_src_for(task)
        protocol_bytes = src.read_bytes()
        env_case = task / "environment" / "case"
        tests_case = task / "tests" / "case"
        tests_case.mkdir(parents=True, exist_ok=True)
        env_case.mkdir(parents=True, exist_ok=True)
        (env_case / "protocol.json").write_bytes(protocol_bytes)
        (tests_case / "protocol.json").write_bytes(protocol_bytes)
        patient = env_case / "patient_state.json"
        if not patient.is_file():
            raise FileNotFoundError(patient)
        shutil.copy2(patient, tests_case / "patient_state.json")
        for name in GRADER_FILES:
            shutil.copy2(SHARED / name, task / "tests" / name)
        if task in INTAKE_TASKS:
            solution = task / "solution"
            solution.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SHARED / "greedy_agent.py", solution / "agent.py")
        print(f"synced {task.name} <- {src.name}")


if __name__ == "__main__":
    sync()
