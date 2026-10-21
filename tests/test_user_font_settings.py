from __future__ import annotations

from pathlib import Path


ROOT = (Path(__file__).resolve().parents[1] / "src")


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_settings_dialog_exposes_font_refresh_and_user_folders() -> None:
    index = _read("web/index.html")
    assert 'id="refresh-fonts"' in index
    assert 'data-i18n="settings.font.refresh"' in index
    assert 'id="user-font-folders"' in index
    assert 'id="user-font-folder-chinese"' in index
    assert 'id="user-font-folder-latin"' in index
    assert 'data-i18n="settings.font.user_chinese_folder"' in index
    assert 'data-i18n="settings.font.user_latin_folder"' in index


def test_app_loads_user_font_catalog_and_injects_font_faces() -> None:
    app = _read("web/app.js")
    assert 'request("/api/fonts"' in app
    assert 'style.id = USER_FONT_FACE_STYLE_ID;' in app
    assert 'const USER_FONT_FACE_STYLE_ID = "fmodd-user-font-faces";' in app
    assert "return `user-${font.id}`;" in app
    assert 'if (locale === "zh-CN") return [...config.keys, ...userFontKeysForScope("chinese")];' in app
    assert 'if (locale === "en-GB") return [...config.keys, ...userFontKeysForScope("latin")];' in app
    assert 'settings.font.refreshed' in app
    assert 'settings.font.refresh_failed' in app


def test_settings_font_refresh_button_is_wired() -> None:
    app = _read("web/app.js")
    assert '$("#refresh-fonts")?.addEventListener("click"' in app
    assert "localeFontAvailabilityCache.clear();" in app


def test_cjk_font_selections_render_through_a_unicode_range_face() -> None:
    app = _read("web/app.js")
    assert 'const CJK_LOCALE_FACE_STYLE_ID = "fmodd-cjk-locale-face";' in app
    assert "function syncCjkLocaleFace(fontKey)" in app
    assert "unicode-range:${CJK_LOCALE_FACE_RANGES};" in app
    assert 'return `url("${font.url}")${format}`;' in app
    assert 'return `local("${String(source).replace' in app
    assert 'const cjkFamily = CJK_FONT_LOCALES.has(locale) ? syncCjkLocaleFace(normalized) : "";' in app
    assert 'root.style.fontFamily = "var(--fmodd-locale-font), var(--fmodd-english-render-font' in app
    assert "U+4E00-9FFF" in app
