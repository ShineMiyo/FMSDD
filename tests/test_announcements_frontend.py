"""Contract tests for the shell announcement board.

The board data, Markdown renderer and ordering live in ``web/announcement_board.js``;
``web/app.js`` keeps only the reader's view state, the unread marker and the DOM
binding.  These tests read the shipped source, evaluate the browser module in a
Node context, and check that every locale still resolves the copy.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = (Path(__file__).resolve().parents[1] / "src")
MODULE = ROOT / "web" / "announcement_board.js"
LOCALES = (
    "en-GB", "zh-CN", "ko-KR", "zh-TW", "de-DE", "es-ES", "fr-FR", "ru-RU",
    "ja-JP", "pt-BR", "pt-PT",
)
BASE_KEYS = (
    "top.announcements",
    "announce.title",
    "announce.subtitle",
    "announce.author",
    "announce.pinned",
    "announce.expand",
    "announce.collapse",
    "announce.empty",
    "announce.unread",
    "announce.mute",
    "announce.search",
    "announce.search_clear",
    "announce.sort_label",
    "announce.sort.pinned",
    "announce.sort.newest",
    "announce.filter_label",
    "announce.filter.all",
    "announce.results",
    "announce.no_results",
    "announce.tag.release",
    "announce.tag.feature",
    "announce.tag.improvement",
    "announce.tag.fix",
    "announce.tag.important",
    "announce.tag.notice",
    "announce.tag.event",
    "announce.tag.guide",
)
CATALOG_SCRIPT = r'''
const fs = require("fs"), vm = require("vm"), root = process.argv[1];
const html = fs.readFileSync(root + "/web/index.html", "utf8");
const sources = [...html.matchAll(/<script\s+src="([^"]+)"/g)].map((match) => match[1]);
const context = {
  window:{FMODDI18nModules:[], FMODDLocalePacks:{}},
  document:{documentElement:{dataset:{}}, querySelector:()=>null, dispatchEvent:()=>{}},
  NodeFilter:{SHOW_TEXT:4}, CustomEvent:class CustomEvent {},
};
vm.createContext(context);
for (const source of sources) {
  if (!source.startsWith("/i18n") || source === "/i18n.js") continue;
  vm.runInContext(fs.readFileSync(root + "/web" + source, "utf8"), context, {filename:source});
}
vm.runInContext(fs.readFileSync(root + "/web/i18n.js", "utf8"), context, {filename:"/i18n.js"});
const locales = __LOCALES__;
const keys = __KEYS__;
const out = {};
for (const locale of locales) {
  context.window.FMODDI18n.setLocale(locale, {persist:false, root:null});
  out[locale] = Object.fromEntries(keys.map((key) => [key, context.window.FMODDI18n.t(key)]));
}
console.log(JSON.stringify(out));
'''
BOARD_HARNESS = r'''
const fs = require("fs"), vm = require("vm");
const context = {window:{}, document:{}, NodeFilter:{SHOW_TEXT:4}, CustomEvent:class CustomEvent {}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1] + "/web/announcement_board.js", "utf8"), context);
const board = context.window.FMSDDAnnouncements;
const input = JSON.parse(process.argv[2] || "{}");
const out = (() => { __EXPRESSION__ })();
console.log(JSON.stringify(out));
'''


def sources() -> tuple[str, str, str]:
    return (
        (ROOT / "web" / "app.js").read_text(encoding="utf-8"),
        (ROOT / "web" / "index.html").read_text(encoding="utf-8"),
        (ROOT / "web" / "app.css").read_text(encoding="utf-8"),
    )


def _node_module(expression: str, payload: dict[str, object] | None = None) -> object:
    script = BOARD_HARNESS.replace("__EXPRESSION__", expression)
    result = subprocess.run(
        ["node", "-e", script, str(ROOT), json.dumps(payload or {})],
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        stdin=subprocess.DEVNULL,
    )
    return json.loads(result.stdout)


def _catalog(keys: list[str]) -> dict[str, dict[str, str]]:
    script = (
        CATALOG_SCRIPT.replace("__LOCALES__", json.dumps(list(LOCALES)))
        .replace("__KEYS__", json.dumps(keys))
    )
    result = subprocess.run(
        ["node", "-e", script, str(ROOT)],
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        stdin=subprocess.DEVNULL,
    )
    return json.loads(result.stdout)


def test_announcement_button_opens_a_board_left_of_mail() -> None:
    _, html, _ = sources()
    actions = html.split('<div class="top-actions">', 1)[1].split("</div>", 1)[0]
    assert 'id="announcement-button"' in actions
    assert actions.index('id="announcement-button"') < actions.index('id="mail-button"'), (
        "the announcement entry sits left of mail"
    )
    button = actions.split('id="announcement-button"', 1)[1].split("</button>", 1)[0]
    assert 'aria-haspopup="dialog"' in button
    assert 'aria-controls="announcement-dialog"' in button
    assert 'id="announcement-dot" hidden' in button
    assert 'data-i18n="top.announcements"' in button


def test_announcement_dialog_offers_sort_filter_and_search() -> None:
    _, html, _ = sources()
    assert 'id="mail-dialog"' in html
    dialog = html.split('id="announcement-dialog"', 1)[1].split("</dialog>", 1)[0]
    assert 'id="announcement-subtitle"' in dialog
    assert 'id="announcement-content"' in dialog
    assert 'data-i18n="announce.title"' in dialog
    assert 'id="announcement-filters"' in dialog
    assert 'id="announcement-search"' in dialog
    assert 'data-i18n-placeholder="announce.search"' in dialog
    assert 'id="announcement-search-clear"' in dialog
    assert 'id="announcement-mute"' in dialog
    assert 'data-i18n="announce.mute"' in dialog
    assert dialog.index('announcement-mute') < dialog.index('close-dialog')
    assert 'data-announcement-sort="pinned"' in dialog
    assert 'data-announcement-sort="newest"' in dialog
    assert dialog.index('announcement-toolbar') < dialog.index('announcement-content')
    assert html.index('id="mail-dialog"') < html.index('id="announcement-dialog"'), (
        "the board keeps the utility dialogs together"
    )


def test_board_module_loads_before_the_shell() -> None:
    _, html, _ = sources()
    sources_list = re.findall(r'<script\s+src="([^"]+)"', html)
    assert "/announcement_board.js" in sources_list
    assert sources_list.index("/announcement_board.js") < sources_list.index("/app.js")
    assert "/announcement_board.js" in sources_list
    assert MODULE.is_file()


def test_board_entries_carry_stable_identity_tags_and_pin_state() -> None:
    entries = _node_module("return board.BOARD")
    assert len(entries) == 7
    ids = [entry["id"] for entry in entries]
    assert len(set(ids)) == len(ids)
    known_tags = {"release", "feature", "improvement", "fix", "important", "notice", "event", "guide"}
    for entry in entries:
        assert entry["id"], "every entry needs a stable id for the seen marker"
        assert entry["key"].startswith("announce.entry."), entry
        assert re.match(r"\d{4}-\d{2}-\d{2}", entry["date"]), entry
        assert re.match(r"\d{2}:\d{2}", entry["time"]), entry
        assert isinstance(entry["pinned"], bool), entry
        assert entry["tags"], entry
        assert set(entry["tags"]) <= known_tags, entry
    newest = entries[0]
    assert newest["id"] == "2026-10-21-v296-update"
    assert newest["key"] == "announce.entry.v296_update"
    assert newest["version"] == "V2.9.6cBeta"
    assert newest["pinned"] is True
    assert "release" in newest["tags"]
    v290 = next(entry for entry in entries if entry["id"] == "2026-10-19-v290-update")
    assert v290["pinned"] is False, "the V2.9.0 notice is no longer pinned"
    previous = next(entry for entry in entries if entry["id"] == "2026-10-18-v285-launch")
    assert previous["pinned"] is False, "the V2.8.5 notice is no longer pinned"
    community = next(entry for entry in entries if entry["id"] == "2026-10-19-community")
    assert community["key"] == "announce.entry.community"
    assert community["pinned"] is True
    assert community["alwaysOpen"] is True, "the two codes must stay visible without expanding"
    assert community["tags"] == ["notice", "event"]


def test_permanent_notice_precedes_every_other_entry() -> None:
    script, _, _ = sources()
    assert 'const ANNOUNCEMENT_PERMANENT_TOP_KEY = "announce.entry.open_source";' in script
    result = _node_module(
        "return board.orderedEntries(input.entries, {mode:'pinned', permanentKey:input.key})",
        {
            "key": "announce.entry.open_source",
            "entries": [
                {"id": "future", "key": "announce.entry.future", "date": "2026-12-01", "time": "10:00", "pinned": True, "tags": ["release"]},
                {"id": "v285", "key": "announce.entry.v285_launch", "date": "2026-10-18", "time": "02:00", "pinned": False, "tags": ["release"]},
                {"id": "v290", "key": "announce.entry.v290_update", "date": "2026-10-19", "time": "13:00", "pinned": True, "tags": ["release"]},
                {"id": "open", "key": "announce.entry.open_source", "date": "2026-10-17", "time": "09:00", "pinned": True, "tags": ["notice"]},
                {"id": "guide", "key": "announce.entry.feature_guide", "date": "2026-10-16", "time": "21:00", "pinned": False, "tags": ["guide"]},
            ],
        },
    )
    assert [entry["id"] for entry in result] == ["open", "future", "v290", "v285", "guide"]


def test_newest_sort_overrides_pinning_but_keeps_the_permanent_notice() -> None:
    payload = {
        "key": "announce.entry.open_source",
        "entries": [
            {"id": "pinned-old", "key": "announce.entry.old", "date": "2026-10-10", "time": "10:00", "pinned": True, "tags": ["release"]},
            {"id": "fresh", "key": "announce.entry.fresh", "date": "2026-11-02", "time": "09:00", "pinned": False, "tags": ["release"]},
            {"id": "open", "key": "announce.entry.open_source", "date": "2026-09-01", "time": "09:00", "pinned": True, "tags": ["notice"]},
        ],
    }
    pinned = _node_module(
        "return board.orderedEntries(input.entries, {mode:'pinned', permanentKey:input.key})",
        payload,
    )
    newest = _node_module(
        "return board.orderedEntries(input.entries, {mode:'newest', permanentKey:input.key})",
        payload,
    )
    assert [entry["id"] for entry in pinned] == ["open", "pinned-old", "fresh"]
    assert [entry["id"] for entry in newest] == ["open", "fresh", "pinned-old"]


def test_newest_stamp_is_computed_from_dates_not_array_order() -> None:
    entries = [
        {"id": "old", "date": "2026-10-01", "time": "09:00"},
        {"id": "new", "date": "2026-10-21", "time": "08:30"},
        {"id": "middle", "date": "2026-10-18", "time": "23:00"},
    ]
    assert _node_module("return board.newestId(input)", entries) == "new"


def test_filters_and_search_use_tags_and_copy() -> None:
    payload = {
        "entries": [
            {"id": "a", "title": "Alpha release", "plain": "vehicle garage", "version": "V2.8.6Beta", "tags": ["release", "feature"], "key": "a", "date": "2026-10-01", "time": "00:00", "pinned": False},
            {"id": "b", "title": "Beta fixes", "plain": "dialog stability", "version": "V2.8.7Beta", "tags": ["fix"], "key": "b", "date": "2026-10-02", "time": "00:00", "pinned": False},
        ],
        "labels": {"release": "Release", "feature": "New", "fix": "Fixed"},
    }
    by_tag = _node_module(
        "return board.filterEntries(input.entries, {tag:'fix', tagLabel:(id)=>input.labels[id]||id}).map((e)=>e.id)",
        payload,
    )
    by_query = _node_module(
        "return board.filterEntries(input.entries, {query:'garage', tagLabel:(id)=>input.labels[id]||id}).map((e)=>e.id)",
        payload,
    )
    by_label = _node_module(
        "return board.filterEntries(input.entries, {query:'fixed', tagLabel:(id)=>input.labels[id]||id}).map((e)=>e.id)",
        payload,
    )
    assert by_tag == ["b"]
    assert by_query == ["a"]
    assert by_label == ["b"]


def test_markdown_renders_headings_lists_tables_quotes_and_code() -> None:
    html = _node_module(
        "return board.renderMarkdown(input).html",
        "# One\n## Two\n### Three\n- a\n- b\n\n1. first\n2. second\n\n> quoted\n\n---\n\n| h1 | h2 |\n|---|---|\n| 1 | 2 |\n\n```\ncode\n```",
    )
    assert '<h4 class="announcement-md-heading" data-md-level="1">One</h4>' in html
    assert '<h5 class="announcement-md-heading" data-md-level="2">Two</h5>' in html
    assert '<h6 class="announcement-md-heading" data-md-level="3">Three</h6>' in html
    assert "<ul><li>a</li><li>b</li></ul>" in html
    assert "<ol><li>first</li><li>second</li></ol>" in html
    assert "<blockquote><p>quoted</p></blockquote>" in html
    assert "<hr>" in html
    assert "<th>h1</th>" in html and "<td>2</td>" in html
    assert "<pre class=\"announcement-md-code\"><code>code</code></pre>" in html


def test_markdown_supports_the_legacy_section_marker() -> None:
    html = _node_module("return board.renderMarkdown(input).html", "【Before you begin】Back up first.")
    assert '<h5 class="announcement-md-heading" data-md-level="2">Before you begin</h5>' in html
    assert "<p>Back up first.</p>" in html
    assert "【" not in html


def test_markdown_escapes_html_and_rejects_unsafe_links() -> None:
    html = _node_module(
        "return board.renderMarkdown(input).html",
        '<img src=x onerror=alert(1)> **bold** `code` [ok](https://example.com/a) [bad](javascript:alert(1))',
    )
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "<strong>bold</strong>" in html
    assert "<code>code</code>" in html
    assert '<a href="https://example.com/a" target="_blank" rel="noreferrer noopener">ok</a>' in html
    assert "javascript:" not in html
    assert ">bad</a>" not in html


def test_cards_expose_tags_status_and_a_scoped_expand_toggle() -> None:
    card = _node_module(
        "return board.cardHtml(input.entry, {t:(key)=>key, expanded:false})",
        {
            "entry": {
                "id": "2026-10-19-v290-update", "key": "announce.entry.v290_update",
                "date": "2026-10-19", "time": "13:00", "stamp": "2026-10-19 13:00",
                "pinned": True, "version": "V2.9.0Beta", "tags": ["release", "feature"],
                "title": "Change log", "author": "Natori Sayaka",
                "body": "A long notice body that keeps going so the card has to collapse: " + ("detail " * 40), "rendered": None,
            },
        },
    )
    assert '<article class="announcement-card is-pinned"' in card
    assert 'data-announcement-id="2026-10-19-v290-update"' in card
    assert 'aria-labelledby="announcement-title-2026-10-19-v290-update"' in card
    assert "announcement-pinned" in card
    assert "announcement-version" in card
    assert 'data-tag-tone="green"' in card and 'data-tag-tone="blue"' in card
    assert "data-announcement-body" in card
    assert 'aria-controls="announcement-body-2026-10-19-v290-update"' in card
    assert 'aria-expanded="' in card


def test_collapsed_cards_share_one_preview_height() -> None:
    _, _, css = sources()
    assert "--announcement-collapsed-height:220px" in css
    assert "max-height:var(--announcement-collapsed-height)" in css
    assert ".announcement-body.is-collapsed > *:nth-child(n+4)" not in css


def test_always_open_cards_never_collapse() -> None:
    card = _node_module(
        "return board.cardHtml(input.entry, {t:(key)=>key, expanded:false})",
        {
            "entry": {
                "id": "2026-10-19-community", "key": "announce.entry.community",
                "date": "2026-10-19", "time": "12:00", "stamp": "2026-10-19 12:00",
                "pinned": True, "version": "", "tags": ["notice"], "alwaysOpen": True,
                "title": "Community", "author": "Natori Sayaka",
                "body": "A long body that would normally collapse. " * 20,
                "rendered": None,
            },
        },
    )
    assert "is-collapsed" not in card
    assert "data-announcement-toggle" not in card


def test_filter_chips_report_counts_for_present_tags_only() -> None:
    chips = _node_module(
        "return board.filtersHtml(input.entries, {tag:'all', t:(key)=>key})",
        {
            "entries": [
                {"tags": ["release", "feature"]},
                {"tags": ["release"]},
                {"tags": ["guide"]},
            ],
        },
    )
    assert 'data-announcement-filter="all"' in chips
    assert "announcement-filter-count" in chips
    assert re.search(r'data-announcement-filter="all"[^>]*>.*?>3<', chips), "the all chip counts every notice"
    assert 'data-announcement-filter="release"' in chips
    assert 'data-announcement-filter="feature"' in chips
    assert 'data-announcement-filter="guide"' in chips
    assert 'data-announcement-filter="fix"' not in chips
    assert 'aria-pressed="true"' in chips


def test_shell_keeps_view_state_and_marks_the_newest_notice() -> None:
    script, _, _ = sources()
    assert 'const ANNOUNCEMENT_SEEN_STORAGE_KEY = "fmodd-announcements-seen";' in script
    assert 'const ANNOUNCEMENT_VIEW_STORAGE_KEY = "fmsdd-announcements-view";' in script
    assert "board.newestId(entries)" in script
    assert 'localStorage.setItem(ANNOUNCEMENT_SEEN_STORAGE_KEY, newest);' in script
    bind = script.split("function bindAnnouncementBoard(", 1)[1].split(
        "function bindStockNationRows", 1
    )[0]
    assert "data-announcement-filter" in bind
    assert "data-announcement-sort" in bind
    assert "announcementSearchTimer" in bind
    assert "updateAnnouncementView" in bind
    assert "toggleAnnouncementCard" in bind


def test_announcement_cards_expand_and_collapse_from_the_board() -> None:
    script, _, _ = sources()
    toggle = script.split("function toggleAnnouncementCard(", 1)[1].split(
        "function bindAnnouncementBoard", 1
    )[0]
    assert "is-collapsed" in toggle
    assert 'toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");' in toggle
    assert 'uiText(collapsed ? "announce.expand" : "announce.collapse")' in toggle
    assert "announcementExpandedIds.add(id)" in toggle
    assert "announcementExpandedIds.delete(id)" in toggle


def test_startup_announcements_open_after_the_welcome_notice() -> None:
    script, _, _ = sources()
    notice = script.split("function showInitialUsageNotice()", 1)[1].split(
        "function lotteryData()", 1
    )[0]
    assert notice.count("showStartupAnnouncements();") == 2, (
        "both early exits of the welcome notice hand over to the board"
    )
    confirm = script.split('$("#usage-notice-confirm").addEventListener', 1)[1].split(
        '$("#manager-select").addEventListener', 1
    )[0]
    assert "showStartupAnnouncements();" in confirm
    handout = script.split("function showStartupAnnouncements()", 1)[1].split(
        "function bindAnnouncementBoard", 1
    )[0]
    assert "const entries = announcementEntries();" in handout
    assert "if (announcementMuted() && !announcementUnread(entries)) return;" in handout
    assert "if (!announcementUnread()) return;" not in handout
    assert 'if ($("#usage-notice-dialog")?.open) return;' in handout
    assert "openAnnouncements();" in handout


def test_announcement_mute_preference_controls_the_startup_popup() -> None:
    script, _, _ = sources()
    assert 'const ANNOUNCEMENT_MUTE_STORAGE_KEY = "fmsdd-announcements-mute";' in script
    assert "function announcementMuted()" in script
    assert "function setAnnouncementMuted(muted)" in script
    assert "function syncAnnouncementMute()" in script
    assert 'localStorage.getItem(ANNOUNCEMENT_MUTE_STORAGE_KEY) === "1";' in script
    assert 'localStorage.setItem(ANNOUNCEMENT_MUTE_STORAGE_KEY, muted ? "1" : "0");' in script
    bind = script.split("function bindAnnouncementBoard(", 1)[1].split(
        "function bindStockNationRows", 1
    )[0]
    assert '"#announcement-mute"' in bind
    assert "setAnnouncementMuted(Boolean(event.target.checked));" in bind
    opener = script.split("function openAnnouncements()", 1)[1].split(
        "function showStartupAnnouncements", 1
    )[0]
    assert "syncAnnouncementMute();" in opener
    assert "const ANNOUNCEMENT_MUTE_STORAGE_KEY" in script[:script.index("function announcementMuted")]


def test_announcement_board_is_wired_into_the_shell() -> None:
    script, _, _ = sources()
    assert "bindAnnouncementBoard();" in script
    shell = script.split("bindAnnouncementBoard();", 1)[1][:200]
    assert '$("#mail-button").addEventListener' in shell, (
        "the board is bound next to the other top bar entries"
    )


def test_markdown_renders_packaged_images_and_rejects_unsafe_sources() -> None:
    figure = _node_module(
        "return board.renderMarkdown(input).html",
        "![Official FMSDD QQ group QR code](/assets/community/qq-group.png)",
    )
    assert '<figure class="announcement-figure">' in figure
    assert 'src="/assets/community/qq-group.png"' in figure
    assert 'alt="Official FMSDD QQ group QR code"' in figure
    assert "<figcaption>Official FMSDD QQ group QR code</figcaption>" in figure

    inline = _node_module(
        "return board.renderMarkdown(input).html",
        "Scan ![QR](/assets/community/qq-group.png) to join.",
    )
    assert '<img class="announcement-image"' in inline
    assert "<figure" not in inline

    unsafe = _node_module(
        "return board.renderMarkdown(input).html",
        "![a](javascript:alert(1)) ![b](../../secret.png) ![c](data:image/png;base64,AA)",
    )
    assert "<img" not in unsafe
    assert "javascript:" not in unsafe
    assert "data:image" not in unsafe


def test_markdown_renders_two_images_in_one_row() -> None:
    html = _node_module(
        "return board.renderMarkdown(input).html",
        "![Group](/assets/community/qq-group.png) ![App icon](/assets/app-icon.png)",
    )
    assert '<div class="announcement-media-row">' in html
    assert html.count("<figure") == 2
    assert 'src="/assets/community/qq-group.png"' in html
    assert 'src="/assets/app-icon.png"' in html
    assert "<figcaption>Group</figcaption>" in html
    assert "<figcaption>App icon</figcaption>" in html

    unsafe_pair = _node_module(
        "return board.renderMarkdown(input).html",
        "![a](javascript:alert(1)) ![b](/assets/app-icon.png)",
    )
    assert "announcement-media-row" not in unsafe_pair


def test_community_qr_asset_and_group_number_ship_with_the_board() -> None:
    community_qr = ROOT / "web" / "assets" / "community" / "qq-group.png"
    assert community_qr.is_file()
    assert community_qr.stat().st_size > 10_000
    catalog = _catalog(["announce.entry.community.body"])
    for locale in LOCALES:
        body = catalog[locale]["announce.entry.community.body"]
        assert "/assets/community/qq-group.png" in body, locale
        assert "/assets/author-support.png" not in body, locale
        assert "fmodd.com/donate" not in body, locale
        assert "1131124119" in body, locale


def test_announcement_titles_are_localized_instead_of_falling_back_to_english() -> None:
    entries = _node_module("return board.BOARD")
    title_keys = [f'{entry["key"]}.title' for entry in entries]
    catalog = _catalog(title_keys)
    english = catalog["en-GB"]
    for locale in LOCALES:
        if locale == "en-GB":
            continue
        for key in title_keys:
            assert catalog[locale][key] != english[key], (
                f"{locale} falls back to the English title for {key}"
            )
    for key in title_keys:
        assert re.search(r"[\u4e00-\u9fff]", catalog["zh-CN"][key]), (
            f"the zh-CN title is not Chinese: {catalog['zh-CN'][key]}"
        )
        assert not catalog["zh-CN"][key].startswith("FMSDD V"), (
            "the product/version prefix belongs in the version chip, not the title"
        )


def test_announcement_copy_resolves_in_every_locale() -> None:
    entries = _node_module("return board.BOARD")
    keys = list(BASE_KEYS)
    for entry in entries:
        keys.append(f'{entry["key"]}.title')
        keys.append(f'{entry["key"]}.body')
    catalog = _catalog(keys)
    assert set(catalog) == set(LOCALES)
    for locale in LOCALES:
        for key in keys:
            value = catalog[locale][key]
            assert value and value != key, f"{locale} is missing {key}"
        assert "{count}" in catalog[locale]["announce.subtitle"]
        assert "{visible}" in catalog[locale]["announce.results"]
        assert "{total}" in catalog[locale]["announce.results"]
        for entry in entries:
            body = catalog[locale][f'{entry["key"]}.body']
            if entry["key"] in {
                "announce.entry.v296_update",
                "announce.entry.v290_update",
                "announce.entry.v285_launch",
                "announce.entry.v280_launch",
                "announce.entry.feature_guide",
            }:
                assert "## " in body, f"{locale} body lost its Markdown headings"
            assert "【" not in body, f"{locale} still uses the legacy section marker"
            if entry["key"] == "announce.entry.v296_update":
                assert "CDK" not in body, f"{locale} still mentions the internal CDK"
                assert "2.9.6a" not in body and "2.9.6b" not in body, f"{locale} still splits 2.9.6a/b"


