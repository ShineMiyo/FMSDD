from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from tools import life_interactions as interactions
from tools import life_system

ROOT = Path(__file__).resolve().parents[1]
DAY = date(2026, 1, 5).toordinal()


def state_and_life() -> tuple[dict, dict]:
    state = interactions.normalize_state({}, DAY)
    life = life_system._empty_state()
    life["properties"]["property-rich"] = {
        "id": "property-rich", "kind": "commercial",
        "tenure": "owned", "market_value": 900_000_000,
    }
    return state, life


def test_new_asset_level_cars_and_storage_first_claim() -> None:
    state, life = state_and_life()
    interactions.sync_asset_level_rewards(state, life, DAY)
    expected = {
        2: "car-462", 3: "car-339", 4: "car-120",
        5: "car-383", 6: "car-124", 7: "car-71", 11: "car-816",
    }
    assert {
        int(row["level"]): row["vehicle"]["catalog_id"]
        for row in interactions._asset_level_snapshot(state, life, DAY)["levels"]
        if row["vehicle"]
    } == expected
    assert not life["vehicles"]
    for level in (2, 3, 4, 5, 6, 7):
        claimed = interactions.claim_asset_level_vehicle(state, life, level, DAY)
        assert claimed["vehicle"]["catalog_id"] == expected[level]
        assert claimed["vehicle"]["garage_id"] == "storage"


def test_claim_falls_back_to_another_garage_then_fails_when_all_full() -> None:
    state, life = state_and_life()
    interactions.sync_asset_level_rewards(state, life, DAY)
    life["garages"]["storage"]["capacity"] = 0
    life["garages"]["club"]["capacity"] = 1
    claimed = interactions.claim_asset_level_vehicle(state, life, 2, DAY)
    assert claimed["vehicle"]["garage_id"] == "club"

    state, life = state_and_life()
    interactions.sync_asset_level_rewards(state, life, DAY)
    for garage in life["garages"].values():
        if isinstance(garage, dict):
            garage["capacity"] = 0
    with pytest.raises(ValueError, match="所有车库"):
        interactions.claim_asset_level_vehicle(state, life, 2, DAY)


def test_storage_capacity_is_10000_for_new_and_legacy_saves() -> None:
    assert life_system.STORAGE_GARAGE["capacity"] == 10000
    state = life_system.normalize_state({})
    assert state["garages"]["storage"]["capacity"] == 10000
    legacy = life_system.normalize_state({
        "garages": {"storage": {"id": "storage", "kind": "storage", "capacity": 100}},
    })
    assert legacy["garages"]["storage"]["capacity"] == 10000


def test_reputation_is_a_costed_profile_attribute() -> None:
    assert interactions.PROFILE_REPUTATION_COST == 5
    state = interactions.normalize_state({}, DAY)
    assert state["profile"]["points_available"] == 191
    saved = interactions.save_profile(state, {
        "surname": "测试", "given_name": "经理",
        "appearance": 2, "ability": 2, "charisma": 2, "eq": 2, "reputation": 5,
    }, DAY)
    assert saved["reputation"] == 5
    assert saved["points_spent"] == 2 + 2 + 2 + 2 + 5 * interactions.PROFILE_REPUTATION_COST
    assert saved["points_available"] == 200 - saved["points_spent"]


def test_v293_static_contracts() -> None:
    api = (ROOT / "src/fm_odds_web.py").read_text(encoding="utf-8")
    host = (ROOT / "src/desktop/WebViewHost.csproj").read_text(encoding="utf-8")
    title = (ROOT / "src/desktop/WebViewHost.cs").read_text(encoding="utf-8")
    page = (ROOT / "src/web/life_page.js").read_text(encoding="utf-8")
    interactions_js = (ROOT / "src/web/interactions_page.js").read_text(encoding="utf-8")
    life_css = (ROOT / "src/web/life.css").read_text(encoding="utf-8")
    i18n = (ROOT / "src/web/i18n.interactions.v293.js").read_text(encoding="utf-8")

    assert 'PRODUCT_VERSION = "V2.9.6cBeta"' in api
    assert "76-dev" in api
    assert "<Version>2.9.6.3</Version>" in host
    assert "FMSDD V2.9.6cBeta" in title
    assert '"/api/life/interactions/asset-level/claim": "claim_life_asset_level"' in api
    assert "availableLifeFunds" in page
    assert "bulk_shortfall" in page
    assert '#life-garage-bulk-content { height: 0' in life_css
    assert "claim-asset-level" in interactions_js
    assert "ledger_reference.asset_level" in interactions_js
    assert "profileAttributeWeight" in interactions_js
    assert "is-reputation" in interactions_js
    assert "manager_reputation_reason_unsupported" not in interactions_js
    assert i18n.count('"life.interactions.asset_level.claim_vehicle"') == 11
    assert i18n.count('"life.map.bulk_insufficient"') == 11
    assert i18n.count('"life.interactions.profile.ledger_source.asset_level"') == 11
    assert i18n.count('"life.interactions.profile.reputation_cost"') == 11


def test_asset_grouping_and_children_static_contracts() -> None:
    page = (ROOT / "src/web/life_page.js").read_text(encoding="utf-8")
    interactions_js = (ROOT / "src/web/interactions_page.js").read_text(encoding="utf-8")
    app_js = (ROOT / "src/web/app.js").read_text(encoding="utf-8")
    children_i18n = (ROOT / "src/web/i18n.children.v293.js").read_text(encoding="utf-8")
    round73_i18n = (ROOT / "src/web/i18n.round73.js").read_text(encoding="utf-8")
    api = (ROOT / "src/fm_odds_web.py").read_text(encoding="utf-8")
    html = (ROOT / "src/web/index.html").read_text(encoding="utf-8")

    # Asset portfolio groups by city then district with expand/collapse.
    assert 'data-life-action="asset-toggle-group"' in page
    assert 'data-life-action="asset-toggle-all"' in page
    assert "life-asset-city" in page and "life-asset-district" in page
    assert "assetExpanded" in page
    # Bulk purchase now prices through the server before charging.
    assert "/api/life/property/buy-batch/prepare" in page
    assert '"/api/life/property/buy-batch/prepare": "prepare_life_property_batch"' in api
    # Children workspace.
    assert '["family", "life.interactions.tabs.family"' in interactions_js
    assert "/api/life/interactions/children/name" in interactions_js
    assert "/api/life/interactions/children/elixir" in interactions_js
    assert "data-child-club" in interactions_js
    assert "manager_identity?.team_id" in interactions_js
    assert "/api/life/interactions/children/academy" in interactions_js
    for route in (
        "/api/life/interactions/children/name",
        "/api/life/interactions/children/elixir",
        "/api/life/interactions/children/academy",
    ):
        assert f'"{route}"' in api
    assert "/i18n.children.v293.js" in html
    assert children_i18n.count('"settings.cdk.success.refill_action_points"') == 11
    assert 'effect === "refill_action_points"' in app_js
    for token in (
        'data-interaction-gift-toggle', 'function giftPropertyGroups',
        'function giftVehicleGroups', 'data-interaction-gift-filter',
        'interaction-intimacy-subtabs', 'pregnancy_possible',
    ):
        assert token in interactions_js
    assert '"spouse"' in interactions_js
    for key in (
        "life.interactions.relationship.pregnancy_possible",
        "life.interactions.intimacy.tabs.history",
        "life.interactions.asset.filter_city",
        "life.interactions.asset.unknown_garage",
    ):
        assert round73_i18n.count(f'"{key}"') == 11
    for key in (
        "life.interactions.tabs.family",
        "life.interactions.family.name_label",
        "life.interactions.family.elixir_confirm",
        "life.interactions.family.place_own",
        "life.interactions.family.elixir_name.apprentice",
        "life.interactions.family.elixir_name.immortal",
        "life.properties.grouped_by_city",
        "life.map.bulk_preparing",
    ):
        assert children_i18n.count(f'"{key}"') == 11
