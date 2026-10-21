from __future__ import annotations

import io
from http import HTTPStatus

import fm_odds_web as web
from tools import user_fonts


def _isolated_folders(monkeypatch, tmp_path):
    folders = {
        "chinese": tmp_path / "fonts" / "chinese",
        "latin": tmp_path / "fonts" / "latin",
    }
    monkeypatch.setattr(user_fonts, "USER_FONT_FOLDERS", folders)
    return folders


def test_scan_creates_folders_and_lists_supported_files(monkeypatch, tmp_path):
    folders = _isolated_folders(monkeypatch, tmp_path)
    folders["chinese"].mkdir(parents=True)
    (folders["chinese"] / "SourceHanSansSC.ttf").write_bytes(b"\x00\x01\x00\x00")
    (folders["chinese"] / "readme.txt").write_text("not a font", encoding="utf-8")
    folders["latin"].mkdir(parents=True)
    (folders["latin"] / "Inter.OTF").write_bytes(b"OTTO")
    (folders["latin"] / "nested").mkdir()

    payload = user_fonts.scan_user_fonts()

    assert payload["folders"] == {scope: str(path) for scope, path in folders.items()}
    assert [(font["scope"], font["name"], font["suffix"]) for font in payload["fonts"]] == [
        ("chinese", "SourceHanSansSC", "ttf"),
        ("latin", "Inter", "otf"),
    ]
    assert payload["fonts"][0]["css_format"] == "truetype"
    assert payload["fonts"][1]["css_format"] == "opentype"
    assert payload["fonts"][0]["url"] == f"/api/font-file?id={payload['fonts'][0]['id']}"


def test_scan_creates_missing_folders(monkeypatch, tmp_path):
    folders = _isolated_folders(monkeypatch, tmp_path)
    assert not folders["chinese"].exists()
    user_fonts.scan_user_fonts()
    assert folders["chinese"].is_dir()
    assert folders["latin"].is_dir()


def test_resolve_user_font_round_trips_scanned_ids(monkeypatch, tmp_path):
    folders = _isolated_folders(monkeypatch, tmp_path)
    folders["latin"].mkdir(parents=True)
    target = folders["latin"] / "Inter.ttf"
    target.write_bytes(b"\x00\x01\x00\x00")

    font_id = user_fonts.scan_user_fonts()["fonts"][0]["id"]

    assert user_fonts.resolve_user_font(font_id) == target


def test_resolve_user_font_rejects_unknown_and_malformed_ids(monkeypatch, tmp_path):
    folders = _isolated_folders(monkeypatch, tmp_path)
    folders["latin"].mkdir(parents=True)
    (folders["latin"] / "Inter.ttf").write_bytes(b"\x00\x01\x00\x00")

    assert user_fonts.resolve_user_font("latin-00000000000000000000") is None
    assert user_fonts.resolve_user_font("chinese-../latin/Inter.ttf") is None
    assert user_fonts.resolve_user_font("") is None
    assert user_fonts.resolve_user_font(None) is None


def _recording_handler(path):
    handler = web.Handler.__new__(web.Handler)
    handler.command = "GET"
    handler.path = path
    handler.headers = {}
    handler.rfile = io.BytesIO(b"")
    handler._bind_request_scope = lambda: None
    events = []
    handler._json = lambda status, payload: events.append(("json", status, payload))
    handler.send_response = lambda status, *args: events.append(("status", status))
    handler.send_header = lambda key, value: events.append(("header", key, value))
    handler.end_headers = lambda: events.append(("end",))
    handler.wfile = io.BytesIO()
    return handler, events


def test_font_file_endpoint_serves_scanned_font_bytes(monkeypatch, tmp_path):
    folders = _isolated_folders(monkeypatch, tmp_path)
    folders["latin"].mkdir(parents=True)
    content = b"\x00\x01\x00\x00font-bytes"
    (folders["latin"] / "Inter.ttf").write_bytes(content)
    font_id = user_fonts.scan_user_fonts()["fonts"][0]["id"]

    handler, events = _recording_handler(f"/api/font-file?id={font_id}")
    handler._do_GET()

    assert handler.wfile.getvalue() == content
    assert ("header", "Content-Type", "font/ttf") in events
    assert ("status", HTTPStatus.OK) in events
    assert not any(event[0] == "json" for event in events)


def test_font_file_endpoint_rejects_unknown_ids(monkeypatch, tmp_path):
    _isolated_folders(monkeypatch, tmp_path)

    handler, events = _recording_handler("/api/font-file?id=chinese-00000000000000000000")
    handler._do_GET()

    assert events == [("json", HTTPStatus.NOT_FOUND, {"error": "未找到自定义字体"})]


def test_font_catalog_route_is_registered():
    assert web.API_ROUTES.resolve("GET", "/api/fonts") is not None
