"""Contract for the V2.7.6beta share capital display and order rules.

Covers the capital sentence the board and the holdings quote, the ticket
facts that show the club's book, the per-order and club-book limits the
ticket enforces before the server does, and the issue notice on the tape.
"""

from __future__ import annotations

import re
from pathlib import Path

from frontend_source import read_frontend_source

WEB = Path(__file__).resolve().parents[1] / "src" / "web"
LOCALE_FILES = (
    "i18n.stocks.js", "i18n.tw.js", "i18n.de.js", "i18n.es.js", "i18n.fr.js",
    "i18n.ru.js", "i18n.ja.js", "i18n.pt-BR.js", "i18n.pt-PT.js",
)
CAPITAL_KEYS = (
    "stock.card.capital_line", "stock.card.shares", "stock.card.shares_note",
    "stock.card.club_shares", "stock.card.split_price", "stock.card.split_note",
    "stock.trade.max_order", "stock.trade.order_cap", "stock.trade.club_limit",
    "stock.trade.club_empty", "stock.notice.split", "stock.notice.capital",
)


def source() -> str:
    return read_frontend_source(WEB / "app.js", mode="raw")


def between(text: str, start: str, end: str) -> str:
    assert start in text, start
    body = text.split(start, 1)[1]
    assert end in body, end
    return body.split(end, 1)[0]


def test_every_capital_key_is_translated_in_every_locale() -> None:
    for name in LOCALE_FILES:
        text = (WEB / name).read_text(encoding="utf-8")
        for key in CAPITAL_KEYS:
            assert f'"{key}"' in text, (name, key)


def test_share_counts_use_the_same_unit_ladder_as_money() -> None:
    text = source()
    helper = between(text, "function stockShares(value) {", "\nfunction stockCandleBars(")
    assert "stockShareVolume(value)" in helper


def test_the_holding_card_quotes_the_capital_after_the_pie_took_the_row() -> None:
    text = source()
    counter = between(text, "function stockCapitalText(stock) {", "\nfunction stockRankText(")
    for fragment in (
        'uiText("stock.card.capital_line"',
        "shares:stockShares(stock?.shares)",
        "club:stockShares(stock?.club_shares)",
        "count:Number(stock?.split_count || 0)",
    ):
        assert fragment in counter, fragment
    row = between(text, "function stockRowHtml(", "\nfunction stockPaginationHtml(")
    # The row hands its register column to the holder pie, so the capital
    # sentence and the split title stay on the holding card alone.
    assert "${stockPieHtml(stock)}" in row
    assert "stockCapitalText(stock)" not in row
    assert "stockSplitTitle(stock)" not in row
    holding = between(text, "function stockHoldingHtml(", "\nfunction stockTradeHtml(")
    assert "stockCapitalText(stock)" in holding


def test_the_ticket_facts_show_the_club_book_and_the_next_issue_price() -> None:
    text = source()
    facts = between(text, "function stockTicketFactsHtml(", "\nfunction renderStockTicket(")
    for key in ("stock.card.shares", "stock.card.club_shares", "stock.card.split_price"):
        assert f'uiText("{key}")' in facts, key
    assert "stockShares(stock.shares)" in facts
    assert "stockShares(stock.club_shares)" in facts
    assert 'uiText("stock.card.shares_note", {initial:stockShares(stock.initial_shares)})' in facts
    assert 'uiText("stock.trade.max_order", {qty:stockShares(stock.max_order)})' in facts
    assert 'uiText("stock.card.split_note"' in facts


def test_the_ticket_checks_the_club_book_before_the_order_cap() -> None:
    text = source()
    quote = between(text, "function stockTicketQuote() {", "\nfunction stockAffordableQty(")
    assert "Math.floor(Number(stock.club_shares || 0))" in quote
    assert "stockDirectCap(stock)" in quote
    assert "stockBlockCap(stock)" in quote
    book = quote.index('uiText("stock.trade.club_limit"')
    empty = quote.index('uiText("stock.trade.club_empty")')
    cap = quote.index('uiText("stock.block.cap"')
    over = quote.index('uiText("stock.block.over"')
    stake = quote.index('uiText("stock.limit.stake"')
    cash = quote.index('uiText("stock.trade.insufficient"')
    # What is not for sale cannot be bought at any size, so the club's own
    # book is reported before the board caps, the stake ceiling and the wallet.
    assert empty < book < cap < over < stake < cash


def test_the_all_shortcut_stops_at_the_club_the_board_and_the_stake() -> None:
    text = source()
    affordable = between(
        text, 'function stockAffordableQty(stock, kind = "direct") {', "\nfunction ensureStockTicketDialog",
    )
    # A direct buy stops at what the day still allows, an application at the
    # size the club will deliver: both are the server's own numbers.
    assert "stockDirectRoom(stock)" in affordable
    assert "stockBlockCap(stock)" in affordable
    assert "stockStakeRoom(stock)" in affordable
    assert "capped(stock?.club_shares)" in affordable
    # An unknown cap must not turn the button into a zero.
    assert "amount > 0 ? amount : Infinity" in affordable


def test_an_issue_reads_as_a_notice_of_its_own() -> None:
    text = source()
    kinds = between(text, "const STOCK_NOTICE_KINDS = Object.freeze({", "});")
    assert 'split: ["split", "stock.notice.split", "stock-up"],' in kinds
    notice = between(text, "function stockNoticeHtml(notice) {", "\nfunction stockPortfolioHtml(")
    for fragment in (
        "issue:Number(notice?.issue || 0)",
        "ratio:Number(notice?.ratio || 0)",
        "before:stockShares(notice?.before)",
        "after:stockShares(notice?.after)",
        "base:stockMoney(notice?.base || 0)",
    ):
        assert fragment in notice, fragment


def test_a_rebased_lot_reads_as_a_notice_of_its_own() -> None:
    text = source()
    kinds = between(text, "const STOCK_NOTICE_KINDS = Object.freeze({", "});")
    assert 'capital: ["split", "stock.notice.capital", "stock-flat"],' in kinds


def test_the_ticket_merges_the_board_and_the_holdings() -> None:
    text = source()
    lookup = between(text, "function stockById(clubId) {", "\nfunction stockTicketState(")
    assert "(state.data?.stocks || [])" in lookup
    assert "(state.data?.holdings || [])" in lookup


def test_the_ticket_is_a_wide_sheet_and_stacks_on_narrow_windows() -> None:
    css = (WEB / "app.css").read_text(encoding="utf-8")
    assert (
        ".stock-ticket-dialog { width:min(1180px,calc(100vw - 40px)); "
        "max-width:1180px; max-height:calc(100vh - 28px); overflow-y:auto; }"
    ) in css
    # The sheet trades without a scrollbar: the club header across the top,
    # the chart and the club book side by side, and the order strip under
    # both of them, filling the width the chart and the book leave.
    assert (
        ".stock-ticket-body { display:grid; "
        "grid-template-columns:minmax(0,1.42fr) minmax(330px,0.9fr); "
        'grid-template-areas:"hero hero" "chart facts" "order order"; '
        "gap:13px; align-items:start; padding:15px; background:#fff; }"
    ) in css
    for fragment in (
        ".stock-ticket-hero { grid-area:hero;",
        ".stock-ticket-chart-card { grid-area:chart;",
        ".stock-ticket-facts-card { grid-area:facts;",
        ".stock-ticket-form { grid-area:order;",
        ".stock-candle-dialog { height:220px; }",
    ):
        assert fragment in css, fragment
    market = css[css.index("/* Club stock market ("):]
    narrow = market[market.index("@media(max-width:1180px) {"):]
    narrow = narrow[: narrow.index("@media(max-width:900px) {")]
    assert (
        '.stock-ticket-body { grid-template-columns:minmax(0,1fr); '
        'grid-template-areas:"hero" "chart" "facts" "order"; }'
    ) in narrow


def test_the_ticket_draws_the_wide_candle_series() -> None:
    text = source()
    ticket = between(text, "function renderStockTicket() {", "\nfunction updateStockTicketQuote(")
    assert (
        'stockCandleChart(stockCandleBars(stock.history), '
        '{width:640, height:220, className:"stock-candle-chart stock-candle-dialog", '
        "volume:true, interactive:true, axes:true, marks:true, moving:true})"
    ) in ticket


def test_the_pie_legend_keeps_the_house_type() -> None:
    css = (WEB / "app.css").read_text(encoding="utf-8")
    assert ".stock-pie-legend b { font-variant-numeric:tabular-nums; }" in css
    block = css[css.index("/* Club stock market ("):]
    sizes = [float(value) for value in re.findall(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", block)]
    assert sizes and min(sizes) >= 13
