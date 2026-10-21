from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_is_295beta() -> None:
    api = (ROOT / "src" / "fm_odds_web.py").read_text(encoding="utf-8")
    host = (ROOT / "src" / "desktop" / "WebViewHost.csproj").read_text(encoding="utf-8")
    title = (ROOT / "src" / "web" / "index.html").read_text(encoding="utf-8")
    assert 'PRODUCT_VERSION = "V2.9.6cBeta"' in api
    assert '"76-dev"' in api
    assert "<Version>2.9.6.3</Version>" in host
    assert "FMSDD V2.9.6cBeta" in title


def test_asset_group_toggle_closes_child_groups_when_city_opens() -> None:
    script = (ROOT / "src" / "web" / "life_page.js").read_text(encoding="utf-8")
    assert "childPrefix" in script
    assert "closed:${groupKey}" in script
    assert "state.assetExpanded.clear()" in script
    interactions = (ROOT / "src" / "web" / "interactions_page.js").read_text(encoding="utf-8")
    assert "cityPrefix" in interactions
    assert "districtPrefix" in interactions


def test_direct_inventory_actions_and_new_shop_items() -> None:
    app = (ROOT / "src" / "web" / "app.js").read_text(encoding="utf-8")
    products = (ROOT / "src" / "tools" / "club_economy.py").read_text(encoding="utf-8")
    assert "data-gift-direct" in app
    assert "data-use-child-elixir" in app
    assert "inventoryTargetDialog" in app
    for sku in ("growth_elixir", "wedding_ring", "intimate_condoms", "intimate_pills", "gift_roses"):
        assert f'"{sku}"' in products


def test_pregnancy_window_and_child_football_contracts() -> None:
    interactions = (ROOT / "src" / "tools" / "life_interactions.py").read_text(encoding="utf-8")
    children = (ROOT / "src" / "tools" / "life_children.py").read_text(encoding="utf-8")
    assert "PREGNANCY_EARLY_DAYS = 252" in interactions
    assert "PREGNANCY_LATE_DAYS = 301" in interactions
    assert 'kind="child_football"' in interactions
    assert "def training_event_day" in children
    assert "def apply_elixir_years" in children
    assert "child_football" in (ROOT / "src" / "web" / "i18n.v294.js").read_text(encoding="utf-8")


def test_shop_category_tabs_gift_cart_and_family_timeline_contracts() -> None:
    app = (ROOT / "src" / "web" / "app.js").read_text(encoding="utf-8")
    gift = (ROOT / "src" / "web" / "gift_shop_page.js").read_text(encoding="utf-8")
    family = (ROOT / "src" / "web" / "interactions_page.js").read_text(encoding="utf-8")
    products = (ROOT / "src" / "tools" / "club_economy.py").read_text(encoding="utf-8")
    assert "shopCategory" in app and "data-shop-category" in app
    assert "gift-shop-cart" in gift and "data-gift-add" in gift and "checkout" in gift
    assert "interaction-child-steps" in family and "data-child-trial" in family
    assert "intimate_dice" in products and "gift_poetry" in products
    assert "start_academy_trial" in (ROOT / "src" / "tools" / "life_children.py").read_text(encoding="utf-8")


def test_family_parent_portrait_growth_event_rename_and_avatar_contracts() -> None:
    script = (ROOT / "src" / "web" / "interactions_page.js").read_text(encoding="utf-8")
    children = (ROOT / "src" / "tools" / "life_children.py").read_text(encoding="utf-8")
    assert "portraitMarkup({ id: parent.id" in script
    assert "interaction-family-workspace" in script
    assert "growthEventCta" in script and "data-child-avatar" in script
    assert "rename_locked" in script and "renameChild" in script
    assert "street" in children and "risky" in children
    assert "write_player_portrait" in (ROOT / "src" / "tools" / "player_portraits.py").read_text(encoding="utf-8")


def test_family_workspace_sections_and_academy_status_contracts() -> None:
    script = (ROOT / "src" / "web" / "interactions_page.js").read_text(encoding="utf-8")
    html = (ROOT / "src" / "web" / "index.html").read_text(encoding="utf-8")
    styles = (ROOT / "src" / "web" / "interactions.css").read_text(encoding="utf-8")
    family_i18n = (ROOT / "src" / "web" / "i18n.family.v294.js").read_text(encoding="utf-8")
    for section in ("overview", "children", "growth", "academy"):
        assert f'"{section}"' in script
        assert f'data-family-section="${{key}}"' in script
    assert "familySection" in script
    assert "refresh-family-academy" in script
    assert "interaction-family-academy-uid" in script
    assert "interaction-family-child-chip" in script
    assert "data-family-child" in script
    assert "familyChild(selectedChild)" in script
    assert "data-family-child-view" in script
    assert "child_view.profile" in family_i18n
    assert "interaction-family-sections" in styles
    assert "/i18n.family.v294.js" in html
    for key in (
        "life.interactions.family.section.overview",
        "life.interactions.family.section.children",
        "life.interactions.family.section.growth",
        "life.interactions.family.section.academy",
        "life.interactions.family.academy_note",
    ):
        assert family_i18n.count(f'"{key}"') == 11
