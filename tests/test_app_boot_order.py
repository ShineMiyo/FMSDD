"""Guards for the boot order of src/web/app.js.

The shell boots on the last line of the script:
``initializeCustomSelects(); bindEvents(); ...``.  Everything the boot line
reaches synchronously — the announcement board constants, the stock market
tables, the shell helpers — must already be evaluated by then.  In
V2.8.0beta the boot line sat above those declarations, ``bindEvents()`` read
the announcement board inside its temporal dead zone, and the thrown
ReferenceError aborted every module level statement after it: home icons,
the top bar listeners and the stock loader all went dead (28th round).
"""

from __future__ import annotations

import re
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "src" / "web" / "app.js"
BOOT_ANCHOR = "initializeCustomSelects(); bindEvents();"
BOOT_TAIL = (
    "checkForUpdates({silent:true});",
    'showPage("home");',
    "showInitialUsageNotice();",
    'document.addEventListener("DOMContentLoaded", () => maybePreloadLifeData({announce:true}), {once:true});',
)


def read_script() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def is_comment(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith(("//", "/*", "*", "*/"))


def test_boot_line_is_the_final_statement_of_the_shell_script() -> None:
    script = read_script()
    assert script.count(BOOT_ANCHOR) == 1, "the boot line must stay unique"
    body = script[script.index(BOOT_ANCHOR):].splitlines()[1:]
    statements = [
        line for line in body
        if line.strip() and not is_comment(line)
    ]
    assert statements == list(BOOT_TAIL), (
        "the boot block must be the last statement of the file"
    )


def test_every_top_level_binding_precedes_the_boot_line() -> None:
    script = read_script()
    tail = script[script.index(BOOT_ANCHOR):]
    declared = [
        match.group(1)
        for match in re.finditer(r"(?m)^(?:const|let|class)\s+([A-Za-z_$][\w$]*)", tail)
    ]
    assert declared == [], (
        "a const/let/class declared after the boot line would sit in its "
        f"temporal dead zone when bootstrap runs: {declared}"
    )


def test_announcement_boot_dependencies_are_declared_before_boot() -> None:
    script = read_script()
    boot = script.index(BOOT_ANCHOR)
    for declaration in (
        'const ANNOUNCEMENT_SEEN_STORAGE_KEY = "fmodd-announcements-seen";',
        'const ANNOUNCEMENT_VIEW_STORAGE_KEY = "fmsdd-announcements-view";',
        'const ANNOUNCEMENT_PERMANENT_TOP_KEY = "announce.entry.open_source";',
        "const ANNOUNCEMENT_SEARCH_DELAY = 120;",
        "const announcementExpandedIds = new Set();",
        "let announcementViewCache = null;",
        "let announcementSearchTimer = 0;",
        "const STOCK_SORT_KEYS = Object.freeze([",
    ):
        assert script.index(declaration) < boot, declaration
    assert "bindAnnouncementBoard();" in script
