from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from tools import life_children
from tools.player_portraits import write_player_portrait

DAY = date(2026, 1, 5).toordinal()


def test_portrait_writer_creates_uid_config_idempotently() -> None:
    with TemporaryDirectory() as folder:
        root = Path(folder)
        write_player_portrait(root, 98765, b"one", "png")
        write_player_portrait(root, 98765, b"two", "png")
        xml = (root / "FMSDD" / "config.xml").read_text(encoding="utf-8")
        assert xml.count('to="graphics/pictures/person/98765/portrait"') == 1
        assert (root / "FMSDD" / "faces" / "98765.png").read_bytes() == b"two"


def test_child_avatar_sync_uses_native_player_uid() -> None:
    child = life_children.normalize_child({
        "id": "child-avatar", "name": "张小明", "born_day": DAY - 15 * 365,
        "placement": {"status": "training", "team_id": 10, "player_id": 98765},
    }, DAY)
    life_children.set_child_avatar(child, "cG5n", "png", DAY)
    with TemporaryDirectory() as folder:
        assert life_children.sync_child_avatar(child, folder, DAY) is True
        assert child["avatar"]["synced_uid"] == 98765
        assert (Path(folder) / "FMSDD" / "faces" / "98765.png").read_bytes() == b"png"


def test_child_rename_is_blocked_at_fifteen() -> None:
    state = {"profile": {"surname": "张", "name": "张三"}}
    relationship = {"children": [{
        "id": "child-rename", "name": "张小明", "surname": "张", "given_name": "小明",
        "born_day": DAY - 15 * 365,
    }]}
    state["relationships"] = {"1": relationship}
    try:
        life_children.name_child(state, "child-rename", "张大明", DAY)
    except ValueError as error:
        assert "15" in str(error)
    else:
        raise AssertionError("rename at 15 should be blocked")
