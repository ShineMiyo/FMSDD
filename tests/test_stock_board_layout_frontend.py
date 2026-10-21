"""Contract for the market board column widths (V2.7.7beta board rebalance).

The player asked for one specific internal rebalance of the quote board: the
identity and candle columns keep their width, price and market cap shrink,
the volume/capital column and the holdings column grow, and the match line
(form, league rank, reputation) moves under the club name so the two money
columns stop crowding each other. The outer board width must not change.
"""

from __future__ import annotations

import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "src" / "web"


def css() -> str:
    return (WEB / "app.css").read_text(encoding="utf-8")


def source() -> str:
    return (WEB / "app.js").read_text(encoding="utf-8")


def market_css() -> str:
    text = css()
    return text[text.index("/* Club stock market ("):]


def tracks(text: str) -> list[str]:
    """The track list of the first ``.stock-row`` rule inside ``text``."""
    body = text[text.index(".stock-row {"):]
    body = body.split("grid-template-columns:", 1)[1]
    return body.split(";", 1)[0].split()


def between(text: str, start: str, end: str) -> str:
    assert start in text, start
    body = text.split(start, 1)[1]
    assert end in body, end
    return body.split(end, 1)[0]


def row_html() -> str:
    return between(source(), "function stockRowHtml(stock) {", "\nfunction stockPaginationHtml(")


def test_the_identity_and_candle_tracks_keep_their_width() -> None:
    row = tracks(market_css())
    assert row[0] == "minmax(148px,1.45fr)", row[0]
    assert row[1] == "104px", row[1]


def test_price_and_market_cap_are_capped_instead_of_sharing_the_slack() -> None:
    row = tracks(market_css())
    # Both used to be fr tracks, so every extra pixel of window went into two
    # columns that only hold a short number and a short label.
    assert row[2] == "minmax(96px,132px)", row[2]
    assert row[3] == "minmax(88px,118px)", row[3]
    price_max = int(row[2].split(",")[1].removesuffix("px)"))
    cap_max = int(row[3].split(",")[1].removesuffix("px)"))
    assert price_max <= 132 and cap_max <= 118


def test_the_volume_and_holdings_columns_grow() -> None:
    row = tracks(market_css())
    assert row[4] == "minmax(150px,1.55fr)", row[4]
    assert row[5] == "minmax(140px,1.4fr)", row[5]
    volume_flex = float(row[4].split(",")[1].removesuffix("fr)"))
    holding_flex = float(row[5].split(",")[1].removesuffix("fr)"))
    # The two money columns must outweigh the price/cap pair they take from.
    assert volume_flex + holding_flex > 2.9


def test_every_responsive_tier_keeps_the_capped_price_tracks() -> None:
    market = market_css()
    narrow = market[market.index("@media(max-width:1440px) {"):]
    tiers = [narrow.split("@media(max-width:1180px) {", 1)[0]]
    deepest = narrow.split("@media(max-width:1180px) {", 1)[1]
    tiers.append(deepest[: deepest.index("@media(max-width:900px) {")])
    # 5 tracks at 1440px (candles and the volume column are hidden) and 3 at
    # 1180px (price and market cap are the only money cells left).
    assert [len(tracks(tier)) for tier in tiers] == [5, 3]
    assert tracks(tiers[0])[1] == "minmax(96px,132px)"
    assert tracks(tiers[1])[1] == "minmax(96px,132px)"


def test_the_match_line_moves_under_the_club_name() -> None:
    identity = between(row_html(), 'class="stock-row-identity"', "</button>")
    for fragment in (
        "stock-row-meta", "stock-form", "stockFormText(stock.fundamentals)",
        "escapeHtml(formNote)",
    ):
        assert fragment in identity, fragment
    note = between(row_html(), "const formNote = [", "].filter(Boolean).join")
    assert "rank" in note
    assert 'uiText("stock.card.reputation")' in note


def test_the_price_line_keeps_the_turnover_and_the_pie_takes_the_register() -> None:
    row = row_html()
    price = between(row, 'class="stock-row-price"', "</div>")
    assert 'uiText("stock.summary.turnover")' in price
    assert 'class="stock-row-turnover"' in price
    assert "${stockPieHtml(stock)}" in row
    # The register column is the holder pie now, so the capital sentence and
    # the split title live on the holding card alone.
    assert "stockCapitalText(stock)" not in row
    assert "stockSplitTitle(stock)" not in row


def test_the_holdings_column_keeps_the_holding_capital_and_the_cost() -> None:
    holding = between(row_html(), "const holdingHtml = holding", "\n  return `")
    for fragment in (
        "stock.row.holding", "stockMoney(stock.holding_value)",
        'uiText("stock.holding.own"', 'uiText("stock.holding.sellable"',
    ):
        assert fragment.replace("stock.row.holding", "stock-row-holding") in holding, fragment
    assert "cost:stockMoney(stock.avg_cost)" in holding


def test_the_row_actions_are_left_alone() -> None:
    actions = between(row_html(), '<div class="stock-row-actions">', "</div>")
    for fragment in (
        'class="stock-watch-action', 'class="stock-buy-action"', 'class="stock-sell-action"',
    ):
        assert fragment in actions, fragment


def test_the_moved_line_wraps_instead_of_being_clipped() -> None:
    body = market_css()
    rule = between(body, ".stock-row-name small.stock-row-meta {", "}")
    assert "white-space:normal" in rule
    assert "text-overflow:clip" in rule
    assert "flex-wrap:wrap" in rule
    assert "overflow:visible" in rule


def test_the_board_type_stays_at_or_above_the_house_minimum() -> None:
    sizes = [float(value) for value in re.findall(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", market_css())]
    assert sizes and min(sizes) >= 13


def test_the_outer_board_width_is_untouched() -> None:
    body = market_css()
    rail = between(body, ".stock-shell {", "}")
    assert "grid-template-columns:" in rail
    assert ".stock-board { display:grid; }" in body


def test_a_group_club_keeps_both_moves_in_the_row() -> None:
    row = row_html()
    actions = between(row, '<div class="stock-row-actions">', "</div>")
    # 集团全资俱乐部在行情看板上既能卖回俱乐部，也能回收集团卖出的股份。
    assert "stock.buyback_room" in row
    assert 'class="stock-buy-action" data-stock-trade="buy" data-stock-id="${clubId}" ${recoverable > 0 ? "" : "disabled"}' in actions
    assert 'uiText("stock.owned.recover")' in actions
    # 行内的王冠只留图标，两个按钮才不会把这一列撑宽。
    assert 'class="stock-owned-badge is-compact"' in actions
    style = css()
    assert (
        ".stock-row-actions .stock-owned-badge.is-compact "
        "{ justify-content:center; width:32px; padding:0; }"
    ) in style
    assert ".stock-row-actions .stock-owned-badge.is-compact span { display:none; }" in style
