"""Local checks for protocol_walker against Chest pain.json. No Docker."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

from protocol_walker import load_protocol  # noqa: E402

PROTOCOL_PATH = ROOT / "data" / "Chest pain.json"
PROTOCOL_ID = "ID_c492cec3-f0e8-4ab1-8b31-fd2f3b557e0b"
Q_DURATION = "ID_6b85e860-b27a-46e6-a60f-a6c10eb8b7db"
Q_WORSEN = "ID_7d090a35-4685-4063-9101-f5ca9dcdb11c"
O_MENSTRUAL = "ID_4fc5d549-740f-434b-83c8-56f9e0e66acc"
Q_MOVE = "ID_8acf327f-18e6-48db-aba5-f9052276ed0c"
O_MOVE_YES = "ID_ab8419e3-3590-4916-8fa4-bfc101a63217"
Q_MOVES_TO = "ID_e9a1aaab-f1e9-4dbd-8c58-3c7e77995b3e"
O_DIFF_BREATHING = "ID_f11aa381-71db-4773-940a-2b44b7b0c5e9"


def main() -> int:
    protocol = load_protocol(PROTOCOL_PATH)
    assert protocol.protocol_id == PROTOCOL_ID
    assert protocol.name == "Chest pain"
    assert protocol.engine_version == "3.0"
    assert len(protocol.top_level_questions()) == 16
    assert protocol.has_node(Q_DURATION)
    menstrual = protocol.get_node(O_MENSTRUAL)
    assert menstrual is not None and menstrual.age_min == 10
    assert protocol.age_violation(O_MENSTRUAL, 8) is menstrual
    assert protocol.age_violation(O_MENSTRUAL, 12) is None
    assert protocol.is_branch_active(Q_MOVES_TO, set()) is False
    assert protocol.is_branch_active(Q_MOVES_TO, {O_MOVE_YES}) is True
    assert protocol.get_node(O_DIFF_BREATHING) is not None
    worsen = protocol.get_node(Q_WORSEN)
    assert worsen is not None and worsen.is_required
    print("protocol_walker checks passed")
    print(f"nodes={len(protocol.nodes)} questions={len(protocol.questions())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
