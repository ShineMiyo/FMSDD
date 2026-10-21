"""The ticket's way into the club profile, and the sheet it is drawn on.

V2.7.6beta: an exchange index is a level and must not wear a currency symbol,
so the chart takes the formatter of the series it draws; the trade ticket
borrows the world module's club information page for the club it is trading -
the same reader, opened from the ticket and closed back onto it - and the
order itself sits on one trading strip under the chart and the club book, so
nothing has to be scrolled into view before it can be traded.
"""

from __future__ import annotations

from pathlib import Path

from frontend_source import read_frontend_source

WEB = Path(__file__).resolve().parents[1] / "src" / "web"
LOCALE_FILES = (
    "i18n.stocks.js", "i18n.tw.js", "i18n.de.js", "i18n.es.js", "i18n.fr.js",
    "i18n.ru.js", "i18n.ja.js", "i18n.pt-BR.js", "i18n.pt-PT.js",
)
TICKET_KEYS = ("stock.ticket.club_info", "stock.ticket.club_info_back")
RETIRED_KEYS = (
    "world.detail.stock_open", "world.detail.stock_note",
    "stock.quote.unknown_club", "stock.quote.no_save",
    "stock.quote.market_closed", "stock.quote.not_listed",
)


def source() -> str:
    return read_frontend_source(WEB / "app.js", mode="raw")


def styles() -> str:
    return (WEB / "app.css").read_text(encoding="utf-8")


def between(text: str, start: str, end: str) -> str:
    assert start in text, start
    body = text.split(start, 1)[1]
    assert end in body, end
    return body.split(end, 1)[0]


def test_every_ticket_key_is_translated_in_every_locale() -> None:
    for name in LOCALE_FILES:
        text = (WEB / name).read_text(encoding="utf-8")
        for key in TICKET_KEYS:
            assert chr(34) + key + chr(34) in text, (name, key)
        for key in RETIRED_KEYS:
            assert chr(34) + key + chr(34) not in text, (name, key)


def test_the_world_club_profile_is_a_reader_again_not_a_trading_desk() -> None:
    text = source()
    detail = between(
        text, "function renderWorldClubDetailContent", "async function openWorldClubDetail",
    )
    # The page keeps its own door (acquiring the club) and nothing else: the
    # ticket is opened from the market, not from the directory.
    assert "data-world-detail-acquire=" in detail
    assert "data-world-detail-stock" not in detail
    assert "openStockTicketForClub" not in text
    assert "openStockTicketForClub" not in detail
    profile = styles()
    assert ".world-detail-stock-control{" not in profile
    assert ".world-detail-profile .world-detail-stock{" not in profile
    assert 'class="world-detail-profile-hero"' in detail
    assert 'class="world-detail-profile-facts"' in detail
    assert 'profile.querySelector(".world-detail-profile-facts")' in detail
    assert (
        ".world-detail-profile-hero{display:grid;"
        "grid-template-columns:minmax(0,1fr) minmax(220px,260px);"
    ) in profile
    assert (
        ".world-detail-profile-facts{display:grid;"
        "grid-template-columns:repeat(3,minmax(0,1fr));"
    ) in profile
    assert ".world-detail-profile-facts>div{min-width:0;" in profile


def test_the_ticket_opens_the_club_information_page_it_borrowed() -> None:
    text = source()
    opener = between(
        text, "function openStockTicketClubInfo(clubId) {", "function renderStockTicket() {",
    )
    # The club page of the world module is reused, not rebuilt: the ticket
    # opens the very dialog the world directory opens.
    assert '$("#world-club-detail-dialog")' in opener
    assert 'void openWorldClubDetail(wanted, {fallbackName:String(stock.name || "")});' in opener
    assert 'uiText("stock.ticket.club_info_back")' in opener
    # The way back is a control of that dialog, shown only while the ticket
    # asked for it, and it closes the page onto the ticket underneath.
    assert "data-stock-club-info-back" in opener
    assert 'back.addEventListener("click", () => detailDialog.close());' in opener
    assert "actions.prepend(back);" in opener
    close_handler = between(
        text,
        '$("#world-club-detail-dialog")?.addEventListener("close"',
        "\n}",
    )
    assert 'querySelector("[data-stock-club-info-back]")?.remove()' in close_handler
    # The ticket carries the button that asks for the page.
    ticket = between(
        text, "function renderStockTicket() {", "function updateStockTicketQuote(",
    )
    assert 'class="stock-ticket-club-info" data-stock-club-info="' in ticket
    assert 'uiText("stock.ticket.club_info")' in ticket
    assert (
        'dialog.querySelector("[data-stock-club-info]")?.addEventListener("click", (event) => {'
    ) in ticket
    assert "openStockTicketClubInfo(Number(event.currentTarget.dataset.stockClubInfo || 0));" in ticket


def test_the_club_page_names_the_club_before_its_folder_is_read() -> None:
    text = source()
    signature = between(
        text, "async function openWorldClubDetail(", "const requestKey =",
    )
    assert 'force = false, fallbackName = ""' in signature
    assert '|| fallbackName || uiText("world.detail.title")' in text


def test_the_ticket_is_drawn_as_a_club_page() -> None:
    text = source()
    ticket = between(
        text, "function renderStockTicket() {", "function updateStockTicketQuote(",
    )
    for markup in (
        'class="stock-ticket-body"',
        'class="stock-ticket-hero"',
        'class="stock-ticket-hero-title"',
        'class="stock-ticket-hero-metrics"',
        'class="stock-ticket-card stock-ticket-chart-card"',
        'class="stock-ticket-card stock-ticket-facts-card"',
        'class="stock-ticket-card stock-ticket-form"',
    ):
        assert markup in ticket, markup
    # The club header carries the three numbers a buyer checks first.
    for key in ("stock.trade.price", "stock.card.appraisal", "stock.card.owner_price"):
        assert "uiText(" + chr(34) + key + chr(34) + ")" in ticket, key
    # Every block of the sheet is titled the way the club page titles its own.
    assert 'stockTicketCardHead("candlestick-chart", uiText("stock.chart.note"), uiText("stock.ticket.chart"))' in ticket
    assert 'stockTicketCardHead("layers",' in ticket
    assert 'stockTicketCardHead("shopping-cart",' in ticket
    assert "stockTicketFactsHtml(stock)" in ticket
    # A club the group owns keeps the sheet but marks the order slot as owned,
    # so the ticket can explain itself instead of offering a dead form.
    assert "data-stock-owned" in ticket
    assert 'class="stock-owned-note"' in ticket


def test_the_order_sits_on_one_trading_strip() -> None:
    text = source()
    ticket = between(
        text, "function renderStockTicket() {", "function updateStockTicketQuote(",
    )
    hero = between(ticket, '<section class="stock-ticket-hero">', '<section class="stock-ticket-card stock-ticket-chart-card">')
    form = between(ticket, '<section class="stock-ticket-card stock-ticket-form"', "</div>`;")
    # The side switch lives with the order, not up in the header next to the
    # appraisal, which is the whole complaint the strip answers.
    assert "data-stock-side=" not in hero
    assert form.count("data-stock-side=") == 2
    for markup in (
        'class="stock-side-toggle"',
        'class="stock-ticket-order-qty"',
        'class="stock-qty-field"',
        'class="stock-qty-quick"',
        'class="stock-quote"',
        'class="stock-ticket-order-actions"',
        'class="primary-action stock-ticket-confirm"',
        'class="stock-ticket-cancel"',
    ):
        assert markup in form, markup
    assert "data-stock-quote=" in form
    css = styles()
    # One strip under the chart and the club book, and a dialog that fits a
    # window instead of a scrollbar.
    assert (
        ".stock-ticket-form { grid-area:order; display:grid; "
        "grid-template-columns:minmax(148px,166px) minmax(200px,1fr) minmax(0,2fr) 178px; "
        "gap:12px 14px; align-items:start; }"
    ) in css
    assert ".stock-ticket-form>.stock-ticket-card-head { grid-column:1 / -1; margin-bottom:0; }" in css
    assert ".stock-ticket-form>.stock-side-toggle { width:100%; }" in css
    assert ".stock-ticket-form>.stock-side-toggle button { flex:1; min-height:40px; padding:0 12px; }" in css
    assert ".stock-quote { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin:0; }" in css
    assert ".stock-ticket-order-actions .primary-action { min-height:46px;" in css
    assert ".stock-ticket-order-qty { display:grid; gap:8px; align-content:start; }" in css
    for fragment in (
        ".stock-ticket-club-info { display:inline-flex;",
        ".stock-club-info-back { display:inline-flex;",
    ):
        assert fragment in css, fragment


def test_the_index_chart_prints_points_not_money() -> None:
    text = source()
    formats = between(text, "const stockCandleFormats = {", "function stockCandleChart(bars, {")
    assert "money:{label:stockMoney, axis:formatChartAxisMoney}," in formats
    assert "index:{" in formats
    # A club is priced in money, a level is not: the chart prints whatever the
    # series is measured in, on its axis, its legend, its markers and its tooltip.
    chart = between(text, "function stockCandleChart(bars, {", "function stockCandleTooltipNode")
    assert 'format = "money",' in chart
    assert "const text = stockCandleFormats[format] || stockCandleFormats.money;" in chart
    assert "text.axis(value, highest)" in chart
    assert "text.label(points[points.length - 1].value)" in chart
    assert "text.label(series[highIndex].high)" in chart
    assert "text.label(series[lowIndex].low)" in chart
    assert 'data-stock-candle-format="${escapeHtml(format)}"' in chart
    tooltip = between(text, "function stockCandleTooltipHtml(", "function stockCandleHoverEnd")
    assert 'format = "money"' in tooltip
    assert "text.label(Number(open))" in tooltip
    assert "text.label(Number(close))" in tooltip
    assert "stockCandleTooltipHtml(\n    hit.dataset.stockCandleBar, chart.dataset.stockCandleFormat,\n  );" in text
    # The exchange index is the series that must not wear a pound sign.
    index_chart = between(text, 'class="stock-index-chart"', "</div>")
    assert "moving:true, format:\"index\"}" in index_chart
    assert "stockMoney" not in index_chart


def test_the_candle_chart_draws_axes_averages_and_period_markers() -> None:
    text = source()
    chart = between(
        text, "function stockCandleChart(bars, {", "function stockCandleTooltipNode",
    )
    for markup in (
        'class="stock-candle-grid"',
        'class="stock-candle-axis-base"',
        'class="stock-candle-axis-price"',
        'class="stock-candle-axis-date"',
        'class="stock-candle-badge stock-candle-mark-high"',
        'class="stock-candle-badge stock-candle-mark-low"',
        'class="stock-candle-mark stock-candle-mark-high"',
        'class="stock-candle-mark stock-candle-mark-low"',
        'class="stock-candle-legend"',
        "stock-candle-ma stock-candle-ma-${window}",
    ):
        assert markup in chart, markup
    assert "stockCandleDateLabel(series[index].date)" in chart
    assert "stockCandleAverage(series, 5)" in chart
    assert "stockCandleAverage(series, 10)" in chart
    assert 'uiText("stock.candle.high")' in chart
    assert 'uiText("stock.candle.low")' in chart
    # The range keeps six percent of slack, so a flat series still prints a
    # readable price scale instead of a wall of identical numbers.
    assert "const slack = Math.max((highest - lowest) * 0.06" in chart
    css = styles()
    for rule in (
        ".stock-candle-grid, .stock-candle-axis-base { stroke:#dbe6e0; stroke-width:1; }",
        ".stock-candle-axis { position:absolute; inset:0; pointer-events:none; }",
        ".stock-candle-ma-5 { color:#b8791c; stroke:#b8791c; }",
        ".stock-candle-ma-10 { color:#3f6ea8; stroke:#3f6ea8; }",
        ".stock-candle-badge.stock-candle-mark-low { transform:translate(-50%,18%); }",
        ".stock-candle-dialog { height:220px; }",
        ".stock-candle-large { height:150px; }",
    ):
        assert rule in css, rule


def test_the_big_charts_ask_for_the_professional_marks() -> None:
    text = source()
    assert text.count("axes:true, marks:true, moving:true") >= 2
    index_chart = between(text, 'class="stock-index-chart"', "stock-hero-note")
    assert 'className:"stock-candle-chart stock-candle-large"' in index_chart
    ticket = between(
        text, "function renderStockTicket() {", "function updateStockTicketQuote(",
    )
    assert "axes:true, marks:true, moving:true}" in ticket


def test_the_small_rows_keep_the_plain_candles() -> None:
    text = source()
    row = between(text, "stock-row-chart", "stock-row-price")
    assert "stockCandleChart(stockCandleBars(stock.history))}" in row


OWNED_KEYS = (
    "stock.owned.recover", "stock.owned.recover_title", "stock.owned.confirm_recover",
    "stock.owned.mode_block", "stock.owned.block_action", "stock.owned.cash_note",
    "stock.owned.room", "stock.owned.keep", "stock.owned.empty", "stock.owned.limit",
    "stock.owned.toast_recovered", "stock.owned.toast_block",
)


def test_every_recovery_key_is_translated_in_every_locale() -> None:
    for name in LOCALE_FILES:
        text = (WEB / name).read_text(encoding="utf-8")
        for key in OWNED_KEYS:
            assert chr(34) + key + chr(34) in text, (name, key)


def test_an_owned_club_quotes_a_recovery_instead_of_a_market_buy() -> None:
    text = source()
    quote = between(text, "function stockTicketQuote() {", "\nfunction stockDirectCap(")
    # 集团俱乐部没有可买的市场份额，票面改说“回收”，指向俱乐部手里那本书。
    assert "const owned = Boolean(stock.owned);" in quote
    assert 'owned ? uiText("stock.owned.empty") : uiText("stock.trade.club_empty")' in quote
    assert 'uiText("stock.owned.limit", {qty:stockShares(clubShares)})' in quote
    assert "owned," in quote


def test_the_ticket_of_a_group_club_names_both_moves() -> None:
    text = source()
    ticket = between(text, "function renderStockTicket() {", "function updateStockTicketQuote(")
    # 收购之后票面不再只剩一句说明：买=回收，卖=卖回俱乐部，两边都能下单。
    assert 'const ownedBuy = ownedStock && ticket.side !== "sell";' in ticket
    assert 'uiText("stock.owned.recover_title"' in ticket
    assert 'uiText(ownedBuy ? "stock.owned.recover" : "stock.action.buy")' in ticket
    assert 'ownedBuy ? "stock.owned.block_action" : "stock.block.action"' in ticket
    assert 'ownedBuy ? "stock.owned.confirm_recover" : "stock.trade.confirm_buy"' in ticket
    assert 'ownedBuy ? "stock.owned.mode_block" : "stock.mode.block"' in ticket
    assert 'ownedBuy ? uiText("stock.owned.cash_note") : uiText("stock.trade.cash_note")' in ticket
    # 订单区不再被样式藏起来，否则集团俱乐部又变成只读的一张纸。
    css = styles()
    assert '.stock-ticket-form[data-stock-owned="1"]>' not in css


def test_the_limits_of_a_group_club_quote_its_control_stake() -> None:
    text = source()
    strip = between(text, "function stockLimitStripHtml(quote) {", "\nfunction stockOrderKindText(")
    assert 'uiText("stock.owned.keep"' in strip
    assert 'uiText("stock.owned.room"' in strip
    assert 'uiText("stock.limit.stake", {ratio:stockRatioText(limits.stake)})' in strip
    # 保留比例由服务端给出，前端不写死 51%。
    limits = between(text, "function stockMarketLimits() {", "\nfunction stockRatioText(")
    assert "keep: ratio(stored.keep, 0.51)," in limits
    submit = between(text, "async function submitStockTicket() {", "\n/* Withdrawing an application")
    assert 'uiText("stock.owned.toast_recovered", {qty, code})' in submit
    assert 'uiText("stock.owned.toast_block", {qty:posted, code})' in submit
