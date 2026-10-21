"""Contract for the share register, the order rules and financing (V2.7.7beta).

The player asked for four things in one round: the turnover leaves the
register column and rides under the market factor, the register itself becomes
a pie that names every holder on hover, one click may take two percent of a
club while anything larger is an application the club delivers the next game
day (and never more than ten percent, never past a quarter of the club), and a
financing pays the club for new shares at today's quote up to 49% of it.
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
ORDER_KEYS = (
    "stock.pie.title", "stock.pie.mine", "stock.pie.club", "stock.pie.empty",
    "stock.pie.stake", "stock.pie.segment", "stock.pie.hint",
    "stock.limit.title", "stock.limit.direct", "stock.limit.block",
    "stock.limit.stake", "stock.limit.room", "stock.limit.impact",
    "stock.limit.missing",
    "stock.mode.market", "stock.mode.block", "stock.mode.limit",
    "stock.block.action", "stock.block.note", "stock.block.cap",
    "stock.block.over", "stock.block.switch",
    "stock.trade.limit_price", "stock.trade.limit_note",
    "stock.trade.confirm_limit", "stock.trade.impact",
    "stock.order.title", "stock.order.slots", "stock.order.empty",
    "stock.order.kind.block", "stock.order.kind.limit", "stock.order.line",
    "stock.order.waiting", "stock.order.cancel", "stock.order.escrow",
    "stock.finance.action", "stock.finance.title", "stock.finance.subtitle",
    "stock.finance.qty", "stock.finance.min", "stock.finance.max",
    "stock.finance.cap", "stock.finance.cost", "stock.finance.after",
    "stock.finance.stake", "stock.finance.confirm", "stock.finance.note",
    "stock.finance.insufficient", "stock.finance.blocked",
    "stock.finance.appetite", "stock.finance.appetite_note",
    "stock.finance.reason.gap", "stock.finance.reason.debt",
    "stock.finance.reason.slump", "stock.finance.reason.none",
    "stock.trade.daily", "stock.limit.daily", "stock.pie.holder",
    "stock.receipt.kicker", "stock.receipt.block_title",
    "stock.receipt.limit_title", "stock.receipt.qty", "stock.receipt.price",
    "stock.receipt.cost", "stock.receipt.capital", "stock.receipt.stake",
    "stock.receipt.quote", "stock.receipt.move", "stock.receipt.dropped",
    "stock.receipt.close", "stock.receipt.note",
    "stock.toast.block", "stock.toast.limit_sell", "stock.toast.cancelled",
    "stock.toast.financed",
    "stock.notice.order", "stock.notice.order_fill",
    "stock.notice.order_fill_drop", "stock.notice.order_cancel",
    "stock.notice.finance", "stock.trade.side.finance",
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


def test_every_new_key_is_translated_in_every_locale() -> None:
    for name in LOCALE_FILES:
        text = (WEB / name).read_text(encoding="utf-8")
        for key in ORDER_KEYS:
            assert chr(34) + key + chr(34) in text, (name, key)


def test_the_turnover_rides_under_the_market_factor() -> None:
    row = between(source(), "function stockRowHtml(", "\nfunction stockPaginationHtml(")
    price = between(row, 'class="stock-row-price"', "</div>")
    assert 'uiText("stock.trade.factor")' in price
    assert 'uiText("stock.summary.turnover")' in price
    assert "stockShareVolume(stock.turnover || 0)" in price
    assert price.index('uiText("stock.trade.factor")') < price.index('uiText("stock.summary.turnover")')
    # The register column no longer reads the capital out as a sentence.
    assert "${stockPieHtml(stock)}" in row
    assert "stockCapitalText" not in row
    assert "stockSplitTitle" not in row


def test_the_register_is_a_pie_that_names_every_holder_on_hover() -> None:
    text = source()
    slices = between(text, "function stockHoldingSlices(stock) {", "\nfunction stockPieLabel(")
    assert 'slices.push({key:"mine"' in slices
    assert 'slices.push({key:"club"' in slices
    assert "stock?.club_shares ?? Math.max(0, capital - mine)" in slices
    pie = between(text, "function stockPieHtml(stock) {", "\nfunction stockPieTooltipNode(")
    for markup in (
        'class="stock-pie-ring"',
        'class="stock-pie-slice stock-pie-',
        'class="stock-pie-dot stock-pie-',
        'class="stock-pie-legend"',
        'pathLength="100"',
        'data-stock-pie-segment="',
    ):
        assert markup in pie, markup
    # The ring carries no figure of its own any more: the share of every
    # holder sits on its legend line, named after the holder it belongs to.
    assert 'class="stock-pie-center"' not in pie
    assert 'stockPieLabel(slice.key, stock)' in pie
    assert 'data-stock-pie-club="' in pie
    assert 'stockShares(Number(qty))' not in pie
    label = between(text, "function stockPieLabel(key, stock) {", "\nfunction stockPieHtml(")
    assert 'app.worldClubs?.group_name' in label
    assert 'uiText("stock.pie.holder", {name:named})' in label
    tooltip = between(text, "function stockPieHoverStart(segment) {", "\nfunction stockPieHoverTarget(")
    assert 'uiText("stock.pie.stake")' in tooltip
    assert 'uiText("stock.card.shares")' in tooltip
    assert 'dataset.stockPieSegment || "").split("|")' in tooltip
    assert "stockPieTooltipNode(host)" in tooltip
    # One pointer listener drives both the candles and the ring.
    listener = between(text, 'document.addEventListener("pointermove"', "{passive:true});")
    assert "stockCandleHoverTarget(target);" in listener
    assert "stockPieHoverTarget(target);" in listener
    assert "app.stockPieHover" in text


def test_the_daily_limits_come_from_the_document_not_from_the_page() -> None:
    text = source()
    limits = between(text, "function stockMarketLimits() {", "\nfunction stockRatioText(")
    for fragment in (
        "stockMarketState().data?.limits",
        "direct: ratio(stored.direct, 0.02)",
        "block: ratio(stored.block, 0.10)",
        "stake: ratio(stored.stake, 0.25)",
        "financeMax: ratio(stored.finance_max, 0.10)",
        "financeStake: ratio(stored.finance_stake, 0.499)",
    ):
        assert fragment in limits, fragment
    # The caps of one click and of one application are the server's own
    # numbers, read off the row the ticket was opened on.
    direct = between(text, "function stockDirectCap(stock) {", "\nfunction stockBlockCap(")
    assert "stock?.max_order" in direct
    assert "Math.floor(capital * stockMarketLimits().direct)" in direct
    block = between(text, "function stockBlockCap(stock) {", "\nfunction stockStakeRoom(")
    assert "stock?.block_order" in block
    assert "Math.floor(capital * stockMarketLimits().block)" in block
    room = between(text, "function stockStakeRoom(stock) {", "\nfunction stockAffordableQty(")
    assert "stock?.buy_room" in room
    assert "Math.floor(capital * stockMarketLimits().stake) - held" in room


def test_one_click_is_direct_and_anything_larger_is_an_application() -> None:
    text = source()
    quote = between(text, "function stockTicketQuote() {", "\nfunction stockDirectCap(")
    assert 'const kind = buying ? (mode === "block" ? "block" : "direct")' in quote
    assert 'suggest = "block";' in quote
    assert 'uiText("stock.block.over"' in quote
    assert 'uiText("stock.block.cap"' in quote
    assert 'uiText("stock.limit.stake"' in quote
    ticket = between(text, "function renderStockTicket() {", "\nfunction updateStockTicketQuote(")
    assert ticket.count("data-stock-side=") == 2
    assert 'data-stock-mode="${mode}"' in ticket
    assert 'data-stock-block-switch' in ticket
    assert 'uiText("stock.block.switch")' in ticket
    # The suggestion is a button, and clicking it retypes the order.
    assert 'ticket.mode = "block";' in ticket
    assert 'ticket.mode = String(button.dataset.stockMode || "market");' in ticket


def test_the_ticket_confirms_every_mode_with_its_own_words() -> None:
    text = source()
    ticket = between(text, "function renderStockTicket() {", "\nfunction updateStockTicketQuote(")
    for key in ("stock.block.action", "stock.trade.confirm_limit", "stock.trade.confirm_buy"):
        assert f'"{key}"' in ticket, key
    assert 'uiText("stock.trade.limit_price")' in ticket
    assert 'id="stock-limit-input"' in ticket
    assert 'ticket.limit = limitInput.value;' in ticket
    assert 'stockAffordableQty(stock, quote.kind)' in ticket


def test_an_application_is_the_same_order_with_a_kind_on_it() -> None:
    text = source()
    payload = between(text, "function stockTicketPayload(quote, state) {", "\nasync function submitStockTicket(")
    assert 'if (quote.kind === "block") body.kind = "block";' in payload
    assert 'body.kind = "limit";' in payload
    assert "body.limit = quote.limitPrice;" in payload
    submit = between(text, "async function submitStockTicket() {", "\nasync function cancelStockOrder(")
    assert '? "/api/stock/orders"' in submit
    assert ': side === "sell" ? "/api/stock/sell" : "/api/stock/buy",' in submit
    assert "body:JSON.stringify(stockTicketPayload(quote, state))," in submit
    for key in ("stock.toast.block", "stock.toast.limit_sell"):
        assert f'uiText("{key}"' in submit, key


def test_the_queue_lists_every_open_application_and_takes_it_back() -> None:
    text = source()
    row = between(text, "function stockOrderRowHtml(order) {", "\nfunction stockOrderStripHtml(")
    assert 'class="stock-order-row"' in row
    assert 'data-stock-order-cancel="' in row
    assert 'uiText("stock.order.line", {' in row
    assert 'uiText("stock.order.cancel")' in row
    assert 'uiText("stock.order.escrow"' in row
    strip = between(text, "function stockOrderStripHtml(stock) {", "\nfunction renderStockTicket() {")
    assert 'uiText("stock.order.slots", {count:slots, max:limits.orders})' in strip
    assert 'uiText("stock.order.empty")' in strip
    assert "stock.orders || []" in strip
    ticket = between(text, "function renderStockTicket() {", "\nfunction updateStockTicketQuote(")
    assert "${stockOrderStripHtml(stock)}" in ticket
    assert 'data-stock-order-cancel]").forEach' in ticket
    cancel = between(text, "async function cancelStockOrder(orderId) {", "\n/* ------")
    assert '"/api/stock/orders/cancel"' in cancel
    assert "order_id:String(orderId)" in cancel
    assert 'uiText("stock.toast.cancelled"' in cancel


def test_the_quote_says_what_the_order_is_about_to_do_to_the_price() -> None:
    text = source()
    impact = between(text, "function stockImpactPreview(qty, stock, kind, side) {", "\nfunction stockTicketState(")
    assert "limits.impactK * ratio * weight" in impact
    assert 'limits.blockWeight' in impact
    assert 'String(side) === "sell" ? -magnitude : magnitude' in impact
    quote = between(text, "function stockTicketQuote() {", "\nfunction stockDirectCap(")
    # The estimate belongs to the order the server will actually see: a size
    # past the day's direct budget is priced as the application it becomes, so
    # the reading never depends on which mode the tab happens to show.
    assert "const impactKind = buying" in quote
    assert '(kind === "block" || qty > directRoom ? "block" : "direct") : kind;' in quote
    assert 'impact: stockImpactPreview(qty, stock, impactKind, buying ? "buy" : "sell"),' in quote
    ticket = between(text, "function renderStockTicket() {", "\nfunction updateStockTicketQuote(")
    assert 'class="stock-quote-impact' in ticket
    assert 'uiText("stock.trade.impact"' in ticket
    update = between(text, "function updateStockTicketQuote() {", "\nasync function submitStockTicket(")
    assert 'uiText("stock.trade.impact"' in update
    # The row keeps its place: an empty size reads zero instead of erasing it.
    assert "impact.hidden = true;" not in update


def test_financing_pays_the_club_for_new_shares_it_issues() -> None:
    text = source()
    room = between(text, "function stockFinanceRoom(stock) {", "\nfunction stockFinanceQuote(")
    # An issue grows the capital as well as the lot, so the room solves the
    # ceiling instead of subtracting the lot from it.
    assert "((limits.financeStake * capital) - held) / (1 - limits.financeStake)" in room
    assert "stock?.finance_room" in room
    quote = between(text, "function stockFinanceQuote() {", "\nfunction stockFinanceFactsHtml(")
    for key in ("stock.finance.blocked", "stock.finance.min", "stock.finance.max", "stock.finance.insufficient"):
        assert f'uiText("{key}"' in quote, key
    assert "Math.min(perRound, room)" in quote
    assert "const stakeAfter = after > 0 ? (held + qty) / after : 0;" in quote
    facts = between(text, "function stockFinanceFactsHtml(quote) {", "\nfunction ensureStockFinanceDialog(")
    for name in ("qty", "amount", "after", "stake"):
        assert f'data-stock-finance-quote="{name}"' in facts, name
    for key in ("stock.finance.min", "stock.finance.max", "stock.finance.cap"):
        assert f'uiText("{key}"' in facts, key
    submit = text[text.index("async function submitStockFinance() {"):]
    assert '"/api/stock/finance"' in submit
    assert "body:JSON.stringify({club_id:quote.stock.club_id, qty, ...stockViewPayload(state)})," in submit
    assert 'uiText("stock.toast.financed"' in submit
    # The door to it sits on the club book, next to the capital it changes.
    book = between(text, "function stockTicketFactsHtml(stock) {", "\nfunction stockTicketCardHead(")
    assert 'class="stock-finance-action"' in book
    assert 'data-stock-finance="' in book
    assert 'uiText("stock.finance.action")' in book
    ticket = between(text, "function renderStockTicket() {", "\nfunction updateStockTicketQuote(")
    assert 'dialog.querySelector("[data-stock-finance]")?.addEventListener("click", (event) => {' in ticket
    assert "openStockFinance(Number(event.currentTarget.dataset.stockFinance || 0));" in ticket


def test_the_exchange_talks_about_its_own_applications_and_issues() -> None:
    text = source()
    kinds = between(text, "const STOCK_NOTICE_KINDS = Object.freeze({", "});")
    for line in (
        'order: ["clipboard-list", "stock.notice.order", "stock-flat"],',
        'order_fill: ["check-circle-2", "stock.notice.order_fill", "stock-up"],',
        'order_cancel: ["undo-2", "stock.notice.order_cancel", "stock-down"],',
        'finance: ["landmark", "stock.notice.finance", "stock-up"],',
    ):
        assert line in kinds, line
    picker = between(text, "function stockNoticeKey(kind, notice) {", "\nfunction stockNoticeHtml(")
    assert 'return "stock.notice.order_fill_drop";' in picker
    assert "Number(notice?.dropped || 0) > 0" in picker
    notice = between(text, "function stockNoticeHtml(notice) {", "\nfunction stockPortfolioHtml(")
    for fragment in ("kind:stockOrderKindText(notice?.order_kind)", "qty:stockShares(notice?.qty)",
                     "dropped:stockShares(notice?.dropped)", "price:stockMoney(notice?.price || 0)"):
        assert fragment in notice, fragment
    tape = between(text, "function stockTradeHtml(trade) {", "\nconst STOCK_NOTICE_KINDS")
    assert 'raw === "finance" ? uiText("stock.trade.side.finance")' in tape


def test_the_new_controls_keep_the_house_type_and_the_strip_layout() -> None:
    css = styles()
    block = css[css.index("/* Club stock market ("):]
    for selector in (
        ".stock-row-pie {", ".stock-row-turnover {", ".stock-pie-slice {",
        ".stock-pie-tooltip {", ".stock-mode-toggle {", ".stock-limit-strip {",
        ".stock-order-row {", ".stock-order-cancel {", ".stock-finance-action {",
        ".stock-finance-dialog {", ".stock-quote-impact {",
        ".stock-finance-appetite {", ".stock-receipt-dialog {",
    ):
        assert selector in block, selector
    assert ".stock-row-fundamentals" not in block
    # The strip keeps its four columns and the new rows span all of them.
    assert (
        ".stock-ticket-form>.stock-limit-strip,\n"
        ".stock-ticket-form>.stock-order-strip,\n"
        ".stock-ticket-form>.stock-quote-error { grid-column:1 / -1; }"
    ) in block
    sizes = [float(value) for value in re.findall(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", block)]
    assert sizes and min(sizes) >= 13
    dark = (WEB / "dark-theme.css").read_text(encoding="utf-8")
    assert '.stock-pie-tooltip' in dark
    assert '.stock-pie-track' in dark


def test_the_direct_budget_of_the_day_is_the_exchanges_own_number() -> None:
    text = source()
    room = between(text, "function stockDirectRoom(stock) {", "\nfunction stockBlockCap(")
    assert "stock?.direct_room" in room
    assert "stock?.direct_used" in room
    assert "stockDirectCap(stock) - used" in room
    quote = between(text, "function stockTicketQuote() {", "\nfunction stockDirectCap(")
    assert "const directRoom = stockDirectRoom(stock);" in quote
    assert 'uiText("stock.trade.daily", {qty:stockShares(directRoom)})' in quote
    assert 'suggest = "block";' in quote
    all_qty = between(text, 'function stockAffordableQty(stock, kind = "direct") {', "\nfunction ensureStockTicketDialog(")
    assert 'const cap = kind === "block" ? stockBlockCap(stock) : stockDirectRoom(stock);' in all_qty
    strip = between(text, "function stockLimitStripHtml(quote) {", "\nfunction stockOrderKindText(")
    assert 'uiText("stock.limit.daily", {qty:stockShares(quote.directRoom)})' in strip


def test_a_filled_application_comes_back_as_a_settlement_slip() -> None:
    text = source()
    feed = between(text, "function stockReceiptFeed(state, data) {", "\n/* The board the player is looking at")
    assert "state.receiptSeen" in feed
    assert "openStockReceipt(fresh[0])" in feed
    assert text.count("stockReceiptFeed(state, state.data);") == 2
    dialog = between(text, "function stockReceiptHtml(slip) {", "\nfunction openStockReceipt(")
    for key in (
        "stock.receipt.qty", "stock.receipt.price", "stock.receipt.cost",
        "stock.receipt.capital", "stock.receipt.stake", "stock.receipt.quote",
        "stock.receipt.move", "stock.receipt.dropped", "stock.receipt.note",
        "stock.receipt.close", "stock.receipt.block_title",
        "stock.receipt.limit_title", "stock.receipt.kicker",
    ):
        assert f'uiText("{key}"' in dialog, key
    assert 'dialog.id = "stock-receipt-dialog";' in text
    assert 'data-stock-receipt-close' in dialog


def test_financing_asks_the_club_first_and_says_why() -> None:
    text = source()
    reasons = between(text, "function stockFinanceReasonText(reason) {", "\n/* What the club thinks about the offer")
    for key in (
        "stock.finance.reason.gap", "stock.finance.reason.debt",
        "stock.finance.reason.slump", "stock.finance.reason.none",
    ):
        assert f'uiText("{key}")' in reasons, key
    appetite = between(text, "function stockFinanceAppetiteHtml(appetite) {", "\nfunction stockFinanceFactsHtml(")
    assert 'uiText("stock.finance.appetite", {ratio:' in appetite
    assert 'uiText("stock.finance.appetite_note")' in appetite
    assert "stockFinanceReasonText(reason)" in appetite
    assert 'data-stock-finance-quote="appetite"' in appetite
    quote = between(text, "function stockFinanceQuote() {", "\nfunction stockFinanceReasonText(")
    assert "appetite:stock?.appetite || null," in quote
    render = between(text, "function renderStockFinance() {", "\nfunction updateStockFinanceQuote() {")
    assert "${stockFinanceAppetiteHtml(quote.appetite)}" in render
    update = between(text, "function updateStockFinanceQuote() {", "\nasync function submitStockFinance(")
    assert 'write("appetite", uiText("stock.finance.appetite", {ratio:' in update
