from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from tools import app_settings
from tools import player_portraits


def _write_settings(tmp_path: Path, payload: dict) -> None:
    (tmp_path / "settings.json").write_text(
        json.dumps(payload), encoding="utf-8",
    )


def test_multi_folder_uid_offset_without_config_xml(tmp_path: Path) -> None:
    first = tmp_path / "pack-a"
    second = tmp_path / "pack-b"
    first.mkdir()
    second.mkdir()
    (first / "face_1003.png").write_bytes(b"png-a")
    (second / "face_2000.webp").write_bytes(b"webp-b")
    settings_path = tmp_path / "settings.json"
    _write_settings(tmp_path, {})
    with patch.object(app_settings, "SETTINGS_PATH", settings_path), patch.object(
        app_settings, "DATA_ROOT", tmp_path,
    ):
        app_settings.set_portrait_source_rows([
            {"path": str(first), "offset": 2},
            {"path": str(second), "offset": 0},
        ])
        player_portraits.clear_portrait_cache()
        first_path = player_portraits.portrait_path(1001)
        second_path = player_portraits.portrait_path(2000)
    assert first_path == (first / "face_1003.png").resolve()
    assert second_path == (second / "face_2000.webp").resolve()


def test_portrait_source_rows_reject_missing_folder(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    _write_settings(tmp_path, {})
    with patch.object(app_settings, "SETTINGS_PATH", settings_path), patch.object(
        app_settings, "DATA_ROOT", tmp_path,
    ):
        try:
            app_settings.set_portrait_source_rows([
                {"path": str(tmp_path / "missing"), "offset": 0},
            ])
        except ValueError as error:
            assert "不存在" in str(error)
        else:
            raise AssertionError("missing folder was accepted")


def test_defaults_expose_empty_portrait_sources(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    with patch.object(app_settings, "SETTINGS_PATH", settings_path):
        payload = app_settings.load_settings()
    assert payload["portrait_sources"] == []


def test_portrait_settings_use_independent_folders_not_xml() -> None:
    from pathlib import Path as _Path
    root = _Path(__file__).resolve().parents[1]
    app = (root / "src" / "web" / "app.js").read_text(encoding="utf-8")
    html = (root / "src" / "web" / "index.html").read_text(encoding="utf-8")
    api = (root / "src" / "fm_odds_web.py").read_text(encoding="utf-8")
    assert '"/api/player-portraits/sources"' in app
    assert "portrait-source-row" in app
    assert "portrait-source-offset-input" in app
    assert "choose-portrait-xml" not in app
    assert "config.xml" not in app
    assert "/i18n.v296a.js" in html
    assert "/api/player-portraits/sources" in api
    assert "def set_portrait_source_rows" in (root / "src" / "tools" / "app_settings.py").read_text(encoding="utf-8")
