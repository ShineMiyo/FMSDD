"""Regression guard for the settings dialog DOM contract.

The settings enhancement functions in ``src/web/app.js`` insert new rows
relative to anchors such as ``.storage-setting`` and ``.support-setting``
with ``insertBefore``, which requires those anchors to be direct children
of ``.settings-content``. An unclosed ``</div>`` once nested every later
section inside ``.font-settings``; the resulting ``NotFoundError`` aborted
the whole frontend bootstrap (dead buttons, missing icons).
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path


ROOT = (Path(__file__).resolve().parents[1] / "src")
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}
SECTION_CLASSES = (
    "font-settings", "font-user-folders", "cheat-setting", "storage-setting",
    "operation-log-setting",
)


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _marker(tag: str, classes: set[str]) -> str:
    if "settings-content" in classes:
        return "settings-content"
    for name in SECTION_CLASSES:
        if name in classes:
            return name
    if tag == "a" and "author-update-note" in classes:
        return "author-update-note"
    return ""


class _SettingsLayout(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, str]] = []
        self.parent_of: dict[str, str] = {}

    def handle_starttag(self, tag, attrs) -> None:
        attributes = dict(attrs)
        marker = _marker(tag, set(attributes.get("class", "").split()))
        if marker and marker != "settings-content" and marker not in self.parent_of:
            self.parent_of[marker] = self.stack[-1][1] if self.stack else ""
        if tag not in VOID_ELEMENTS:
            self.stack.append((tag, marker))

    def handle_endtag(self, tag) -> None:
        if tag in VOID_ELEMENTS:
            return
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                return


def test_settings_sections_are_direct_children_of_settings_content() -> None:
    layout = _SettingsLayout()
    layout.feed(_read("web/index.html"))
    for marker in (
        "font-settings", "cheat-setting", "storage-setting",
        "author-update-note", "operation-log-setting",
    ):
        assert layout.parent_of.get(marker) == "settings-content", (
            f"{marker} must be a direct child of .settings-content; "
            f"found parent {layout.parent_of.get(marker)!r}"
        )
    assert layout.parent_of.get("font-user-folders") == "font-settings"


def test_settings_rows_never_insert_before_unguarded_anchors() -> None:
    app = _read("web/app.js")
    for anchor in ("fontSettings", "storage"):
        assert f"settings.insertBefore(row, {anchor} || null)" not in app
