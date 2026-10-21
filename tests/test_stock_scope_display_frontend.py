"""Contract for the V2.7.4beta exchange-filter display fixes.

Covers the restored restart state (league club counts without a manual
per-nation read), league-level selections counting their nation on the board
chip and the filter badge, the pinyin ordering with the shared bucket last,
and the translated shared bucket label.
"""

from __future__ import annotations

from pathlib import Path

from frontend_source import read_frontend_source

WEB = Path(__file__).resolve().parents[1] / "src" / "web"
LOCALE_FILES = (
    "i18n.stocks.js", "i18n.tw.js", "i18n.de.js", "i18n.es.js", "i18n.fr.js",
    "i18n.ru.js", "i18n.ja.js", "i18n.pt-BR.js", "i18n.pt-PT.js",
)


def source() -> str:
    return read_frontend_source(WEB / "app.js", mode="raw")


def between(text: str, start: str, end: str) -> str:
    assert start in text, start
    body = text.split(start, 1)[1]
    assert end in body, end
    return body.split(end, 1)[0]


def test_league_club_counts_survive_a_restart() -> None:
    text = source()
    league_clubs = between(text, "function stockFilterLeagueClubs(", "\nfunction ")
    assert "filter.tables[nation]" in league_clubs
    assert "scope_leagues" in league_clubs
    assert "suggestions" in league_clubs
    pending = between(text, "function stockFilterPendingStats(", "\nfunction ")
    assert "clubs += stockFilterLeagueClubs(nation, competition);" in pending
    assert "Number(filter.tables" not in pending


def test_league_level_selections_count_their_nation() -> None:
    text = source()
    covered = between(text, "function stockScopeCoveredNations(", "\nfunction ")
    assert "new Set()" in covered
    assert "nations" in covered and "leagues" in covered
    assert "pair?.[0]" in covered
    assert "nations:stockScopeCoveredNations(scope).size" in text
    assert (
        "const total = stockScopeCoveredNations(scope).size + (scope.leagues || []).length;"
        in text
    )


def test_nations_sort_by_pinyin_and_the_shared_bucket_stays_last() -> None:
    text = source()
    assert 'const stockNationCollator = new Intl.Collator("zh-Hans", {usage:"sort"});' in text
    compare = between(text, "function stockNationCompare(", "\nfunction ")
    assert "stockNationBucket(first) - stockNationBucket(second)" in compare
    assert "stockNationCollator.compare(first, second)" in compare
    assert "const all = [...(filter.data?.nations || [])].sort(stockNationCompare);" in text
    rail = between(text, "function stockNationRowsHtml(", "\nfunction ")
    assert (
        ".sort((left, right) => stockNationBucket(left?.name) - stockNationBucket(right?.name))"
        in rail
    )


def test_shared_bucket_uses_one_translated_label() -> None:
    text = source()
    assert 'const STOCK_NATION_OTHER_KEY = "\u672a\u5206\u7c7b";' in text
    label = between(text, "function stockNationLabel(", "\nfunction ")
    assert 'return key === STOCK_NATION_OTHER_KEY ? uiText("stock.nation.other") : key;' in label
    for fragment in (
        '<span class="stock-filter-nation-name">${escapeHtml(stockNationLabel(name))}</span>',
        '<span class="stock-nation-name">${escapeHtml(stockNationLabel(name))}</span>',
        "`${stockNationLabel(nation)} \u00b7 ${uiText(\"stock.index.title\")}`",
        "`${stockNationLabel(nation)} \u00b7 ${uiText(\"stock.board.title\")}`",
        "stock.competition || stockNationLabel(stock.nation)",
    ):
        assert fragment in text, fragment


def test_search_accepts_the_stored_key_and_the_label() -> None:
    text = source()
    search = between(text, "function stockNationSearchText(", "\nfunction ")
    assert "stockNationLabel(name)" in search
    dialog = between(text, "function stockFilterRowsHtml(", "\nfunction ")
    assert "stockNationSearchText(row?.name).includes(query)" in dialog
    rail = between(text, "function stockNationRowsHtml(", "\nfunction ")
    assert "stockNationSearchText(row.name).includes(query)" in rail


def test_every_locale_ships_the_shared_bucket_label() -> None:
    for name in LOCALE_FILES:
        assert '"stock.nation.other"' in read_frontend_source(WEB / name, mode="raw"), name
    stocks = read_frontend_source(WEB / "i18n.stocks.js", mode="raw")
    assert (
        '"stock.nation.other": ["Other leagues worldwide", "\u5168\u7403\u5176\u4ed6\u8054\u8d5b", "\uc804 \uc138\uacc4 \uae30\ud0c0 \ub9ac\uadf8"]'
        in stocks
    )
