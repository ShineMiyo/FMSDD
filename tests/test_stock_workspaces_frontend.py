from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = (Path(__file__).resolve().parents[1] / "src")
STOCK_PAGES = ("stocks", "stock-holdings", "stock-trades", "stock-notices")
WORKSPACE_PAGES = STOCK_PAGES[1:]
LOCALES = (
    "en-GB", "zh-CN", "ko-KR", "zh-TW", "de-DE", "es-ES", "fr-FR", "ru-RU",
    "ja-JP", "pt-BR", "pt-PT",
)
WORKSPACE_COPY_KEYS = (
    "nav.stock_exchange",
    "nav.stock_holdings",
    "nav.stock_trades",
    "nav.stock_notices",
    "stock.holdings.eyebrow",
    "stock.holdings.title",
    "stock.holdings.group",
    "stock.trades.eyebrow",
    "stock.trades.title",
    "stock.trades.count",
    "stock.notices.eyebrow",
    "stock.notices.title",
    "stock.notices.count",
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


def sources() -> tuple[str, str, str]:
    return (
        (ROOT / "web" / "app.js").read_text(encoding="utf-8"),
        (ROOT / "web" / "index.html").read_text(encoding="utf-8"),
        (ROOT / "web" / "app.css").read_text(encoding="utf-8"),
    )


def _catalog() -> dict[str, dict[str, str]]:
    script = (
        CATALOG_SCRIPT.replace("__LOCALES__", json.dumps(list(LOCALES)))
        .replace("__KEYS__", json.dumps(list(WORKSPACE_COPY_KEYS)))
    )
    result = subprocess.run(
        ["node", "-e", script, str(ROOT)], capture_output=True, check=True, text=True
    )
    return json.loads(result.stdout)


def sidebar_html() -> str:
    _, html, _ = sources()
    sidebar = html.split('<aside class="main-sidebar"', 1)[1].split("</aside>", 1)[0]
    return sidebar


def test_stock_sidebar_group_exposes_four_sections() -> None:
    sidebar = sidebar_html()
    toggle = (
        '<button type="button" class="sidebar-group-toggle" id="stocks-toggle" '
        'data-page="stocks" aria-controls="stocks-subnav" aria-expanded="false">'
    )
    assert toggle in sidebar, "the stocks entry keeps the shared sidebar group markup"
    subnav = sidebar.split('id="stocks-subnav"', 1)[1].split("</div>", 1)[0]
    assert re.findall(r'data-page="([a-z-]+)"', subnav) == list(STOCK_PAGES), (
        "the subnav opens on the exchange and keeps the four sections in order"
    )
    labels = {
        "stocks": "nav.stock_exchange",
        "stock-holdings": "nav.stock_holdings",
        "stock-trades": "nav.stock_trades",
        "stock-notices": "nav.stock_notices",
    }
    for page in STOCK_PAGES:
        assert f'data-i18n="{labels[page]}"' in subnav


def test_stock_group_toggle_only_speaks_for_the_stocks_pages() -> None:
    script, _, _ = sources()
    setup = script.split('document.querySelectorAll("[data-page]").forEach', 1)[1].split(
        "document.addEventListener(\"visibilitychange\"", 1
    )[0]
    assert 'button.id==="stocks-toggle"' in setup
    assert 'setSidebarGroupOpen("stocks",nextOpen,{exclusive:nextOpen});' in setup
    assert '$("#stocks-toggle").classList.toggle("active", stockPage);' in script


def test_stock_workspace_pages_own_a_content_root_and_refresh_control() -> None:
    _, html, _ = sources()
    for page in WORKSPACE_PAGES:
        marker = f'id="page-{page}"'
        assert marker in html
        block = html.split(marker, 1)[1].split("</section>", 1)[0]
        assert f'id="{page}-content"' in block
        assert f'id="{page}-refresh"' in block
        assert "data-stock-refresh" in block
    exchange = html.split('id="page-stocks"', 1)[1].split("</section>", 1)[0]
    assert 'id="stock-content"' in exchange
    assert 'id="stock-refresh-button"' in exchange
    assert "stock-workspace-page" not in exchange, "the exchange keeps its existing layout"


def test_stock_workspace_pages_are_registered_as_renderers() -> None:
    script, _, _ = sources()
    renderers = script.split("function renderCurrentPage(", 1)[1].split("renderers[page]?.();", 1)[0]
    for page in WORKSPACE_PAGES:
        assert f'"{page}": () => render' in renderers


def test_show_page_declares_the_stock_group_flag_once_in_function_scope() -> None:
    script, _, _ = sources()
    navigation = script.split("function showPage(page", 1)[1].split(
        "function showInitialUsageNotice", 1
    )[0]
    declaration = (
        'const stockPage = ["stocks", "stock-holdings", "stock-trades", '
        '"stock-notices"].includes(page);'
    )
    assert navigation.count(declaration) == 1, (
        "one declaration per call: a block scoped flag breaks the later loadStockMarket branch"
    )
    assert navigation.index(declaration) < navigation.index(
        "app.navigationRenderSignature !== navigationSignature"
    )
    assert navigation.index(declaration) < navigation.index("if (stockPage) {")
    assert 'setSidebarGroupOpen(activeSidebarGroup, true, {exclusive:true});' in navigation


def test_stock_board_repaints_the_workspaces_before_its_own_early_return() -> None:
    script, _, _ = sources()
    board = script.split("function renderStockMarket()", 1)[1].split(
        "function stockUpdateFilterBadge", 1
    )[0]
    assert "renderStockWorkspaces();" in board
    assert board.index("renderStockWorkspaces();") < board.index('app.page !== "stocks"'), (
        "a board repaint must reach the three workspace pages as well"
    )
    fanout = script.split("function renderStockWorkspaces()", 1)[1].split(
        "function stockWorkspaceRender", 1
    )[0]
    for renderer in ("renderStockHoldings()", "renderStockTrades()", "renderStockNotices()"):
        assert renderer in fanout


def test_stock_workspace_signatures_stay_per_page() -> None:
    script, _, _ = sources()
    render = script.split("function stockWorkspaceRender(", 1)[1].split(
        "function stockBindWorkspace", 1
    )[0]
    assert "stockWorkspaceSignature(view) === signature" in render
    assert "stockWorkspaceSignature(view, signature);" in render
    assert "app.stockWorkspaceSignatures[view]" in script


def test_refresh_covers_the_board_and_every_workspace_control() -> None:
    script, _, _ = sources()
    refresh = script.split("function refreshStockMarket()", 1)[1].split(
        "async function autoReadStockData", 1
    )[0]
    assert '$("#stock-refresh-button")' in refresh
    assert 'document.querySelectorAll("[data-stock-refresh]")' in refresh


def test_stock_workspace_copy_resolves_in_every_locale() -> None:
    catalog = _catalog()
    assert set(catalog) == set(LOCALES)
    for locale in LOCALES:
        for key in WORKSPACE_COPY_KEYS:
            value = catalog[locale][key]
            assert value and value != key, f"{locale} is missing {key}"
