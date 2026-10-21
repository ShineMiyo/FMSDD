"""Frontend contract for the per-nation club stock market (V2.7.4beta, kept green by V2.7.6beta)."""

from __future__ import annotations

import re
from pathlib import Path

from tools.club_stock_market import SORT_KEYS

WEB = Path(__file__).resolve().parents[1] / "src" / "web"
LOCALE_FILES = (
    "i18n.stocks.js", "i18n.tw.js", "i18n.de.js", "i18n.es.js", "i18n.fr.js",
    "i18n.ru.js", "i18n.ja.js", "i18n.pt-BR.js", "i18n.pt-PT.js",
)
STOCK_KEY = re.compile(r'"(stock\.[A-Za-z0-9_.]+)"')
PAIR = re.compile(r'"(stock\.[A-Za-z0-9_.]+)"\s*:\s*"((?:[^"\\]|\\.)*)"')
ARRAY = re.compile(r'"(stock\.[A-Za-z0-9_.]+)"\s*:\s*\[([^\]]*)\]')
QUOTED = re.compile(r'"((?:[^"\\]|\\.)*)"')
PARAMETER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def stock_section() -> str:
    source = (WEB / "app.js").read_text(encoding="utf-8")
    return source[source.index(" * Club stock market (V2.7.6beta)"):]


def catalog() -> dict[str, dict[str, tuple[str, ...]]]:
    """Every stock template per locale file, read straight from the source."""
    files: dict[str, dict[str, tuple[str, ...]]] = {}
    for name in LOCALE_FILES:
        text = (WEB / name).read_text(encoding="utf-8")
        rows: dict[str, tuple[str, ...]] = {}
        for key, body in ARRAY.findall(text):
            rows[key] = tuple(QUOTED.findall(body))
        for key, value in PAIR.findall(text):
            rows.setdefault(key, (value,))
        files[name] = rows
    return files


def parameters(template: str) -> set[str]:
    return set(PARAMETER.findall(template))


def test_every_key_the_page_renders_exists_in_every_locale() -> None:
    section = stock_section()
    used = set(STOCK_KEY.findall(section))
    assert len(used) >= 75
    for name in LOCALE_FILES:
        available = set(STOCK_KEY.findall((WEB / name).read_text(encoding="utf-8")))
        missing = sorted(used - available)
        assert not missing, f"{name} is missing {missing}"


def test_stock_copy_keeps_the_same_parameters_in_every_locale() -> None:
    files = catalog()
    reference = {key: parameters(values[0]) for key, values in files["i18n.stocks.js"].items()}
    assert reference
    for name, rows in files.items():
        for key, values in rows.items():
            expected = reference.get(key)
            if expected is None:
                continue
            for value in values:
                assert parameters(value) == expected, (name, key, value)
            if name == "i18n.stocks.js":
                assert len(values) == 3, key


def test_market_requests_carry_the_selected_exchange_and_page() -> None:
    section = stock_section()
    builder = section.split("function stockMarketRequestPath", 1)[1].split("function loadStockMarket", 1)[0]
    for fragment in ('params.set("nation"', 'params.set("sort"', 'params.set("order"',
                     'params.set("page"', 'params.set("page_size"', 'params.set("watch"'):
        assert fragment in builder, fragment
    assert "return `/api/stock/market?${params.toString()}`;" in builder
    assert "await request(path);" in section
    assert "body:JSON.stringify({club_id:quote.stock.club_id, qty, ...stockViewPayload(state)})" in section


def test_the_board_offers_nation_selection_paging_and_watch_controls() -> None:
    section = stock_section()
    for marker in (
        'data-stock-nation="${escapeHtml(name)}"',
        'id="stock-nation-list"',
        'id="stock-nation-search"',
        'id="stock-nation-holdings"',
        'data-stock-order',
        'data-stock-watch-only',
        'data-stock-watch="${clubId}"',
        'data-stock-page="prev"',
        'data-stock-page="next"',
        'id="stock-page-size"',
        '"/api/stock/watch"',
    ):
        assert marker in section, marker


def test_the_filter_lists_the_saves_own_leagues_and_recovers_from_no_data() -> None:
    section = stock_section()
    for marker in (
        "function stockFilterSaveOnly()",
        "function stockFilterNationVisible(row)",
        "function stockFilterLeagueVisible(row)",
        "function stockFilterAwaitingHtml(filter)",
        "async function stockFilterScanClubs()",
        "data-stock-filter-save-only",
        "data-stock-filter-scan",
        "data-stock-filter-retry",
        "data-stock-filter-show-all",
        "await ensureWorldDataScan();",
        'uiText("stock.filter.save_only_count"',
        'uiText("stock.filter.no_save_leagues")',
        'uiText("stock.filter.awaiting")',
    ):
        assert marker in section, marker
    # A search miss and an unread save must not share one message.
    assert 'uiText("stock.filter.empty")' in section
    assert "!all.length) return stockFilterAwaitingHtml(filter)" in section


def test_ticking_a_row_keeps_the_filter_scroll_and_focus() -> None:
    section = stock_section()
    for marker in (
        "function stockFilterScrollSnapshot(dialog)",
        "function stockFilterFocusTarget(dialog, focus)",
        "function stockFilterRestoreScroll(dialog, snapshot)",
        "target.focus({preventScroll:true})",
    ):
        assert marker in section, marker
    refresh = section.split("function stockRefreshFilterList()", 1)[1].split("\n}", 1)[0]
    assert "stockFilterScrollSnapshot(dialog)" in refresh
    assert "stockFilterRestoreScroll(dialog, snapshot)" in refresh
    render = section.split("function renderStockFilter()", 1)[1].split(
        "async function stockFilterScanClubs", 1,
    )[0]
    assert "stockFilterScrollSnapshot(dialog)" in render
    assert "stockFilterRestoreScroll(dialog, snapshot)" in render
    # Ticking a nation or a league refreshes the list only, so the long dialog
    # keeps its place instead of jumping back to the top.
    change = section.split('dialog.addEventListener("change"', 1)[1].split(
        'dialog.addEventListener("input"', 1,
    )[0]
    toggles = change.split("const nation =", 1)[1]
    assert "[data-stock-filter-nation]" in toggles
    assert "[data-stock-filter-league]" in toggles
    # The nation branch cycles (and refreshes inside the cycle), the league one refreshes.
    assert "void stockFilterCycleNation(" in toggles
    assert toggles.count("stockRefreshFilterList();") == 1
    assert "renderStockFilter();" not in toggles
    chip = section.split(
        'const chip = event.target.closest("[data-stock-filter-chip]");', 1,
    )[1].split("\n    }", 1)[0]
    assert "stockRefreshFilterList();" in chip
    assert "renderStockFilter();" not in chip


def test_one_click_picks_the_leagues_and_the_next_the_whole_nation() -> None:
    section = stock_section()
    for marker in (
        "async function stockFilterCycleNation(name)",
        "async function stockFilterLoadLeagues(nation)",
        "function stockFilterListedLeagues(nation)",
        "function stockFilterAllListedLeagues(nation)",
    ):
        assert marker in section, marker
    cycle = section.split("async function stockFilterCycleNation(name)", 1)[1].split("\n}", 1)[0]
    # Already on the whole country: the click switches everything off again.
    assert "if (stockFilterNationSelected(key)) {" in cycle
    assert "delete filter.nations[key];" in cycle
    assert "delete filter.leagues[key];" in cycle
    # Otherwise the first click lists every league, the second the whole nation.
    assert "const table = filter.leagues[key] || (filter.leagues[key] = {});" in cycle
    assert "listed.forEach((league) => { table[league] = true; });" in cycle
    assert "if (stockFilterAllListedLeagues(key)) {" in cycle
    assert "filter.nations[key] = true;" in cycle
    assert cycle.index("stockFilterAllListedLeagues(key)") < cycle.index("listed.forEach(")
    # A country without a single league still has to be selectable in one click.
    assert "if (!listed || !listed.length) {" in cycle
    # The nation checkbox must not write `checked` straight into the model.
    change = section.split('dialog.addEventListener("change"', 1)[1].split(
        'dialog.addEventListener("input"', 1,
    )[0]
    nation_branch = change.split("const nation =", 1)[1].split("const league =", 1)[0]
    assert "stockFilterCycleNation(" in nation_branch
    assert "stockFilterToggleNation(" not in nation_branch
    # The row says which of the two picked states it is in.
    assert 'data-stock-filter-nation-state="${state}"' in section
    assert '"stock.filter.selected_all"' in section
    assert '"stock.filter.cycle_hint"' in section


def test_a_league_only_selection_counts_its_nation() -> None:
    section = stock_section()
    stats = section.split("function stockFilterPendingStats()", 1)[1].split("\n}", 1)[0]
    assert "const nations = new Set(selection.nations);" in stats
    assert "nations.add(nation);" in stats
    # The league a parked exchange waits for is counted as waiting, not as a
    # listed league: the country it belongs to still counts as picked.
    assert "const parked = stockFilterParkedKeys();" in stats
    assert "leagues:selection.leagues.length - waiting, clubs," in stats
    assert "waiting," in stats


def test_the_scope_toggle_styles_stay_readable() -> None:
    css = (WEB / "app.css").read_text(encoding="utf-8")
    block = css[css.index("/* Club stock market (V2.7.6beta)"):]
    for selector in (
        ".stock-filter-scope-toggle", ".stock-filter-in-save",
        ".stock-filter-awaiting", ".stock-filter-awaiting-actions",
        ".stock-filter-empty .stock-filter-show-all",
    ):
        assert selector in block, selector
    sizes = [float(value) for value in re.findall(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", block)]
    assert sizes and min(sizes) >= 13


def test_sort_keys_cover_every_field_the_server_can_order_by() -> None:
    section = stock_section()
    declared = section.split("const STOCK_SORT_KEYS = Object.freeze([", 1)[1].split("]);", 1)[0]
    rendered = set(re.findall(r'\["([a-z_]+)", "stock\.sort\.', declared))
    assert rendered == set(SORT_KEYS)


def test_stylesheet_keeps_the_exchange_layout_and_readable_type() -> None:
    css = (WEB / "app.css").read_text(encoding="utf-8")
    block = css[css.index("/* Club stock market (V2.7.6beta)"):]
    for selector in (
        ".stock-shell", ".stock-exchange-rail", ".stock-nation-row", ".stock-rail-list",
        ".stock-pagination", ".stock-portfolio", ".stock-watch-action", ".stock-banner",
    ):
        assert selector in block, selector
    sizes = [float(value) for value in re.findall(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", block)]
    assert sizes and min(sizes) >= 13
def test_candles_normalise_ohlc_so_a_wick_never_sits_inside_the_body() -> None:
    section = stock_section()
    bars = section.split("function stockCandleBars(history) {", 1)[1].split("\n}", 1)[0]
    for field in ("o", "h", "l", "c", "v"):
        assert f"row?.{field}" in bars, field
    assert "high: Math.max(bar.high, bar.open, bar.close)," in bars
    assert "low: Math.min(bar.low, bar.open, bar.close)," in bars


def test_every_candle_draws_body_wick_volume_and_hit_area() -> None:
    section = stock_section()
    chart = section.split("function stockCandleChart(bars, {", 1)[1].split(
        "function stockCandleTooltipNode", 1,
    )[0]
    for markup in (
        'class="stock-candle-wick"',
        'class="stock-candle-body"',
        'class="stock-candle-volume stock-candle-${tone}"',
        'class="stock-candle-hit"',
        'class="stock-candle-guide"',
    ):
        assert markup in chart, markup
    assert "stock-candle-interactive" in chart
    for attribute in (
        "data-stock-candle-bar=", "data-stock-candle-center=", "data-stock-candle-close=",
    ):
        assert attribute in chart, attribute
    # Non-interactive charts (the board rows) keep a native title per bar.
    assert "<title>" in chart


def test_the_hover_tooltip_reads_the_bar_under_the_pointer() -> None:
    section = stock_section()
    tooltip = section.split("function stockCandleTooltipHtml(", 1)[1].split(
        "\nfunction ", 1,
    )[0]
    for key in (
        "stock.candle.open", "stock.candle.high", "stock.candle.low",
        "stock.candle.close", "stock.candle.volume",
    ):
        assert f'uiText("{key}")' in tooltip, key
    assert "stockToneClass(change)" in tooltip
    assert 'document.addEventListener("pointermove"' in section
    assert "app.stockCandleHover" in section


def test_candle_colours_follow_the_profit_loss_setting() -> None:
    css = (WEB / "app.css").read_text(encoding="utf-8")
    block = css[css.index("/* Club stock market (V2.7.6beta)"):]
    assert ".stock-candle-chart .stock-candle-up { color:var(--profit-solid); }" in block
    assert ".stock-candle-chart .stock-candle-down { color:var(--loss-solid); }" in block
    assert ".stock-candle-interactive { cursor:crosshair; }" in block
    tooltip = block.split(".stock-candle-tooltip {", 1)[1].split("}", 1)[0]
    assert "font-size:13px" in tooltip
    dark = (WEB / "dark-theme.css").read_text(encoding="utf-8")
    assert "[data-reverse-profit-loss-colors] .stock-candle-chart .stock-candle-up" in dark


def test_the_exchange_rail_clips_its_own_overflow() -> None:
    css = (WEB / "app.css").read_text(encoding="utf-8")
    block = css[css.index("/* Club stock market (V2.7.6beta)"):]
    rail = block.split("\n.stock-exchange-rail {", 1)[1].split("}", 1)[0]
    assert "grid-template-columns:minmax(0,1fr)" in rail
    assert "min-width:0" in rail
    assert "overflow:hidden" in rail
    assert ".stock-exchange-rail > * { min-width:0; }" in block
    rail_list = block.split(".stock-rail-list {", 1)[1].split("}", 1)[0]
    assert "min-width:0" in rail_list
    assert "overflow-x:hidden" in rail_list



def test_the_worldwide_row_writes_real_nations_and_leagues() -> None:
    """The fix for the V2.7.9beta world-wide counter drift.

    The worldwide row is a real write onto the listed countries - every
    league first, the whole country second, nothing third - so the panel and
    the board count the same clubs and a stored worldwide code is rewritten
    as the entries it stood for.
    """
    section = stock_section()
    for marker in (
        "function stockScopeWorldNext(state)",
        "function stockScopeWorldRows(filter, visible)",
        "async function stockFilterEnsureTables()",
        "function stockFilterWorldApply(mode)",
        "async function stockFilterCycleWorld()",
        "async function stockFilterAdoptWorld()",
        "/api/stock/scope/leagues?nation=*",
    ):
        assert marker in section, marker
    next_state = section.split("function stockScopeWorldNext(state)", 1)[1].split("\n}", 1)[0]
    assert next_state.index('return "none";') < next_state.index('return "world";')
    assert next_state.index('return "world";') < next_state.index('return "leagues";')
    cycle = section.split("async function stockFilterCycleWorld()", 1)[1].split("\n}", 1)[0]
    assert "stockScopeWorldNext(stockFilterWorldState())" in cycle
    assert "await stockFilterEnsureTables();" in cycle
    assert "stockFilterWorldApply(mode);" in cycle
    assert "stockRefreshFilterList();" in cycle
    # The state is written as the very entries a click per country would leave.
    apply = section.split("function stockFilterWorldApply(mode)", 1)[1].split("\n}", 1)[0]
    assert "stockScopeWorldRows(filter, stockFilterNationVisible)" in apply
    assert "listed.forEach((league) => { table[league] = true; });" in apply
    assert "if (mode === \"none\") return;" in apply
    # A worldwide code of an older scope is adopted on open, pending the save.
    load = section.split("async function loadStockScope(", 1)[1].split("async function ", 1)[0]
    assert "await stockFilterAdoptWorld();" in load
    adopt = section.split("async function stockFilterAdoptWorld()", 1)[1].split("\n}", 1)[0]
    assert 'stockFilterWorldApply(world.world ? "world" : "leagues");' in adopt
    # The worldwide note counts the pending selection itself.
    row = section.split("function stockFilterWorldRowHtml()", 1)[1].split("\nfunction ", 1)[0]
    assert "stockFilterPendingStats()" in row
    assert 'uiText("stock.filter.world_leagues", {leagues:stats.leagues})' in row
    assert 'uiText("stock.filter.world_all", {clubs:stats.clubs})' in row


def test_the_exchange_rail_rebinds_its_rows_after_a_repaint() -> None:
    section = stock_section()
    refresh = section.split("function stockRefreshNationList(root)", 1)[1].split("\n}", 1)[0]
    # The rail is repainted by the search box and the holdings toggle, so the
    # fresh buttons must get listeners again or no exchange can be clicked.
    assert "bindStockNationRows(root);" in refresh
    binder = section.split("function bindStockNationRows(root)", 1)[1].split("\n}", 1)[0]
    assert 'root.querySelectorAll("[data-stock-nation]")' in binder
    assert "void loadStockMarket();" in binder
    board = section.split("function bindStockBoard(root)", 1)[1].split("\n}", 1)[0]
    assert "bindStockNationRows(root);" in board
    assert 'root.querySelectorAll("[data-stock-nation]")' not in board
    holdings = section.split('id="stock-nation-holdings"', 1)[1].split('id="stock-nation-list"', 1)[0]
    assert "stockRefreshNationList(root);" in section.split('root.querySelector("#stock-nation-holdings")', 1)[1].split("\n}", 1)[0]
    assert holdings
