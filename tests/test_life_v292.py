from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from tools import life_system

ROOT = Path(__file__).resolve().parents[1]
DAY = date(2026, 1, 5).toordinal()


def make_state() -> dict:
    state = life_system.normalize_state({})
    state["garages"]["lot"] = {
        "id": "lot", "kind": "standalone", "category": "standalone",
        "capacity": 20, "name_zh": "Test garage", "name_en": "Test garage",
    }
    return state


def add_vehicle(state: dict, vehicle_id: str, catalog_id: str, value: int) -> None:
    state["vehicles"][vehicle_id] = {
        "id": vehicle_id,
        "catalog_id": catalog_id,
        "name": f"Car {catalog_id}",
        "manufacturer": "Test",
        "class": "A",
        "rarity": "rare",
        "year": 2020,
        "base_price": value,
        "condition": 1.0,
        "purchase_day": DAY,
        "garage_id": "lot",
        "market_value": value,
        "image": "",
    }


def test_duplicate_sale_keeps_the_highest_value_copy() -> None:
    state = make_state()
    add_vehicle(state, "v-low", "car-a", 100_000)
    add_vehicle(state, "v-high", "car-a", 300_000)
    add_vehicle(state, "v-mid", "car-a", 200_000)
    add_vehicle(state, "v-unique", "car-b", 50_000)

    plan = life_system.duplicate_vehicle_sales(state, "lot", DAY)
    assert plan["count"] == 2
    assert [row["id"] for row in plan["kept"]] == ["v-high"]
    assert [row["vehicle"]["id"] for row in plan["plans"]] == ["v-low", "v-mid"]
    assert plan["total_net"] > 0

    for sale in plan["plans"]:
        life_system.commit_sell_vehicle(state, sale, DAY)
    assert set(state["vehicles"]) == {"v-high", "v-unique"}


def test_duplicate_sale_rejects_unknown_garage() -> None:
    state = make_state()
    with pytest.raises(ValueError, match="车库"):
        life_system.duplicate_vehicle_sales(state, "", DAY)


def test_gacha_accepts_arbitrary_counts_for_multiplier_buttons() -> None:
    state = make_state()
    tier = life_system.gacha_tiers()[0]
    plan = life_system.gacha_plan(state, tier["id"], 3, "lot", DAY, "seed")
    assert plan["draws"] == 3
    assert plan["cost"] == int(tier["ticket_price"]) * 3
    assert len(plan["records"]) == 3
    with pytest.raises(ValueError):
        life_system.gacha_plan(state, tier["id"], 1001, "lot", DAY, "seed")


def test_v292_static_controls_and_version() -> None:
    api = (ROOT / "src/fm_odds_web.py").read_text(encoding="utf-8")
    host = (ROOT / "src/desktop/WebViewHost.csproj").read_text(encoding="utf-8")
    title = (ROOT / "src/desktop/WebViewHost.cs").read_text(encoding="utf-8")
    page = (ROOT / "src/web/life_page.js").read_text(encoding="utf-8")
    interactions = (ROOT / "src/web/interactions_page.js").read_text(encoding="utf-8")
    css = (ROOT / "src/web/interactions.css").read_text(encoding="utf-8")
    life_css = (ROOT / "src/web/life.css").read_text(encoding="utf-8")
    i18n = (ROOT / "src/web/i18n.interactions.v292.js").read_text(encoding="utf-8")

    assert 'PRODUCT_VERSION = "V' in api
    assert "APP_VERSION = PRODUCT_VERSION if FROZEN" in api
    assert '"/api/life/vehicle/sell-duplicates": "sell_duplicate_life_vehicles"' in api
    assert "<Version>" in host
    assert "FMSDD V" in title
    assert "life-gacha-tier-title-row" in page
    assert 'data-draws="${singleDraws}"' in page
    assert 'data-draws="${tenDraws}"' in page
    assert "life-garage-bulk-footer" in page
    assert "life-garage-bulk-list-scroll" in page
    assert "sell-duplicates" in page
    assert "refreshStorageSelectionUi" in page
    assert "interaction-asset-pass" in interactions
    assert "data-asset-pass-rail" in interactions
    assert "assetPassCarArt" in interactions
    assert "user-select: none" in css
    assert "interaction-asset-pass-card" in css
    assert "life-garage-bulk-footer" in life_css
    assert i18n.count('"life.garage.duplicate_sell"') == 11
    assert i18n.count('"life.interactions.asset_level.pass_hint"') == 11
