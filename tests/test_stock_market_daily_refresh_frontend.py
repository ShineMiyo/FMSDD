"""Contract for the V2.7.4beta daily market refresh and its settings switch.

Covers the enabled-club chip counting the whole scope, the new setting that
decides whether connecting a save reads the club data by itself, the board
refresh on a game-day change and the server-side pricing the page renders.
"""

from __future__ import annotations

from pathlib import Path

from frontend_source import read_frontend_source

WEB = Path(__file__).resolve().parents[1] / "src" / "web"
LOCALE_FILES = (
    "i18n.settings.js", "i18n.tw.js", "i18n.de.js", "i18n.es.js", "i18n.fr.js",
    "i18n.ru.js", "i18n.ja.js", "i18n.pt-BR.js", "i18n.pt-PT.js",
)


def source() -> str:
    return read_frontend_source(WEB / "app.js", mode="raw")


def html() -> str:
    return read_frontend_source(WEB / "index.html", mode="raw")


def between(text: str, start: str, end: str) -> str:
    assert start in text, start
    body = text.split(start, 1)[1]
    assert end in body, end
    return body.split(end, 1)[0]


def test_the_scope_chip_counts_every_enabled_club() -> None:
    text = source()
    hero = between(text, "function stockHeroHtml(", "function stockInitBannerHtml(")
    assert "const clubs = (data.nations || []).reduce((sum, row) => sum + Number(row.clubs || 0), 0);" in hero
    assert "clubs:clubs || Number(summary.clubs || 0)," in hero
    # The init banner always read the whole scope; the chip must agree with it
    # and with the exchange filter instead of quoting one exchange.
    banner = between(text, "function stockInitBannerHtml(", "function stockToolbarHtml(")
    assert "(data.nations || []).reduce((sum, row) => sum + Number(row.clubs || 0), 0)" in banner


def test_the_settings_switch_exists_in_every_locale() -> None:
    markup = html()
    assert 'id="stock-auto-read"' in markup
    assert 'data-i18n="settings.stock_auto_read"' in markup
    assert 'data-i18n="settings.stock_auto_read_note"' in markup
    assert 'class="setting-toggle stock-auto-read-setting"' in markup
    for name in LOCALE_FILES:
        catalog = read_frontend_source(WEB / name, mode="raw")
        assert '"settings.stock_auto_read"' in catalog, name
        assert '"settings.stock_auto_read_note"' in catalog, name


def test_the_switch_lives_in_the_markets_tab_and_repaints_with_it() -> None:
    text = source()
    markets = between(text, 'key:"markets"', "},")
    assert ".stock-auto-read-setting" in markets
    signature = between(text, "function settingsRenderStateSignature(", "app.fontSizeStep")
    assert "app.stockAutoRead," in signature
    controls = between(text, "function renderSettingsControls(", "app.fontSizeStep")
    assert '$("#stock-auto-read").checked = app.stockAutoRead;' in controls


def test_the_switch_persists_and_triggers_the_auto_read() -> None:
    text = source()
    assert 'const STOCK_AUTO_READ_STORAGE_KEY = "fm-odds-stock-auto-read";' in text
    stored = between(text, "function storedStockAutoRead(", "const moneyUnitTable")
    assert "localStorage.getItem(STOCK_AUTO_READ_STORAGE_KEY)" in stored
    assert "return true;" in stored
    assert "stockAutoRead: storedStockAutoRead()," in text
    assert 'stockAutoReadScope: "",' in text
    listener = between(text, '$("#stock-auto-read").addEventListener("change"', "});")
    assert "localStorage.setItem(STOCK_AUTO_READ_STORAGE_KEY, String(app.stockAutoRead));" in listener
    assert 'app.stockAutoReadScope = "";' in listener
    assert "maybeAutoReadStockData();" in listener


def test_the_auto_read_waits_for_a_connected_save_and_reads_the_scope() -> None:
    text = source()
    auto = between(text, "async function autoReadStockData(", "function maybeAutoReadStockData(")
    assert "const scope = stockMarketScope();" in auto
    assert "app.stockAutoReadScope === scope" in auto
    assert "await ensureWorldDataScan();" in auto
    assert "await loadStockScope({force:true});" in auto
    assert "await loadStockMarket({force:true});" in auto
    guard = between(text, "function maybeAutoReadStockData(", "/* ---")
    assert "if (!app.stockAutoRead) return;" in guard
    assert "isSaveConnected()" in guard and "isWalletReady()" in guard
    # Connecting a save and the first wallet-ready tick both trigger it.
    assert "maybeAutoReadStockData();" in between(
        text, "if (accountScopeChanged) {", "app.mailRecords = null;",
    )
    assert "maybeAutoReadStockData();" in between(
        text, "if (!walletWasReady && isWalletReady()) {", "}\n",
    )


def test_a_new_game_day_repaints_the_board() -> None:
    text = source()
    clock = between(text, "async function loadGameClock(", "async function pollRefreshStatus(")
    assert "if (previousDate !== clock.date) {" in clock
    assert 'if (app.page === "stocks") loadStockMarket({force:true});' in clock


def test_the_page_renders_the_server_quotes_unmodified() -> None:
    text = source()
    # The daily swing belongs to the market model, so the frontend must not
    # re-derive it while drawing a quote.
    assert "stockDailySwing" not in text
