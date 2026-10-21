from __future__ import annotations

import json
import re
import subprocess
from copy import deepcopy
from datetime import date
from pathlib import Path

import fm_odds_web as web
from tools import club_economy
from tools import life_interactions as interactions


ROOT = Path(__file__).resolve().parents[1] / "src"
LOCALES = (
    "en-GB", "zh-CN", "zh-TW", "ko-KR", "de-DE", "es-ES",
    "fr-FR", "ru-RU", "ja-JP", "pt-BR", "pt-PT",
)
DAY = date(2026, 1, 5).toordinal()
WEEK_LATER = date(2026, 1, 12).toordinal()


def player_row(player_id: int = 1001, *, name: str = "测试球员") -> dict:
    return {
        "id": player_id,
        "name": name,
        "age": 24,
        "female": True,
        "nationality_id": 200,
        "nationality": "英格兰",
        "team_id": 10,
        "team_name": "测试俱乐部",
        "positions": ["ST"],
        "ca": 140,
        "pa": 160,
        "world_reputation": 4000,
        "object_type": "player",
        "date_of_birth": "2002-03-04",
    }


def state_with_people(*rows: dict) -> dict:
    state = interactions.normalize_state({}, DAY)
    interactions.save_profile(state, {"surname": "测试", "given_name": "经理"}, DAY)
    for row in rows or (player_row(),):
        interactions.cache_search_row(state, row, DAY)
    return state


def _module_messages(filename: str) -> dict[str, dict[str, str]]:
    script = r'''
const fs = require("fs"), vm = require("vm");
const context = {window: {FMODDI18nModules: []}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), context);
console.log(JSON.stringify(context.window.FMODDI18nModules[0].messages));
'''
    result = subprocess.run(
        ["node", "-e", script, str(ROOT / "web" / filename)],
        check=True, capture_output=True, text=True, encoding="utf-8",
        stdin=subprocess.DEVNULL,
    )
    return json.loads(result.stdout)


def _parameters(value: str) -> set[str]:
    return set(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", value))


def test_schema_five_migration_preserves_existing_people_and_points() -> None:
    legacy = {
        "schema_version": 4,
        "people": {"1001": player_row()},
        "relationships": {
            "1001": {
                "person_name": "测试球员", "familiarity": 44,
                "affection": 35, "trust": 22, "attraction": 18,
                "respect": 17, "social_stage": "friend",
            },
        },
        "action_points": {"current": 5, "week_ordinal": DAY, "week_key": "2026-W02"},
    }
    state = interactions.normalize_state(deepcopy(legacy), DAY)
    assert state["schema_version"] == 8
    assert state["people"]["1001"]["name"] == "测试球员"
    assert state["relationships"]["1001"]["familiarity"] == 44
    assert state["action_points"]["current"] == 5
    assert state["action_point_ledger"] == []


def test_action_point_ledger_records_chat_recovery_cdk_and_cap() -> None:
    state = state_with_people()
    interactions.chat_plan(state, 1001, DAY, "football")
    points = interactions.action_points(state, DAY)
    assert points["current"] == 11
    assert points["ledger"][0]["reason"] == "chat"
    assert points["ledger"][0]["amount"] == -1
    assert points["ledger"][0]["person_name"] == "测试球员"
    assert points["ledger"][0]["balance_after"] == 11

    state = interactions.normalize_state({}, DAY)
    state["action_points"]["current"] = 5
    assert interactions.refresh_action_points(state, WEEK_LATER)
    recovery = interactions.action_points(state, WEEK_LATER)["ledger"][0]
    assert recovery["reason"] == "weekly_recovery"
    assert recovery["amount"] == 6
    assert recovery["balance_after"] == 11

    state = interactions.normalize_state({}, DAY)
    interactions.activate_cdk_perk(
        state, "action_points", code="日理万机", day=DAY,
    )
    cdk = interactions.action_points(state, DAY)["ledger"][0]
    assert cdk["reason"] == "cdk_action_points"
    assert cdk["amount"] == 12
    assert cdk["balance_after"] == 24

    state["action_points"]["current"] = 23
    assert interactions.refresh_action_points(state, WEEK_LATER)
    capped = interactions.action_points(state, WEEK_LATER)["ledger"][0]
    assert interactions.action_points(state, WEEK_LATER)["current"] == 24
    assert capped["amount"] == 1


def test_relationship_progress_explains_every_social_and_romance_gate() -> None:
    state = state_with_people()
    relationship = state["relationships"]["1001"]
    relationship.update({
        "familiarity": 100.0, "affection": 0.0, "trust": 0.0,
        "attraction": 0.0, "respect": 0.0,
        "social_stage": "acquaintance", "romance_stage": "none",
    })

    progress = interactions.relationship_progress(state, relationship)
    social = progress["social"]
    assert social["next"] == "friend"
    assert social["ready"] is False
    requirements = {row["key"]: row for row in social["requirements"]}
    assert requirements["familiarity"]["met"] is True
    assert requirements["affection"]["met"] is False
    assert requirements["trust"]["met"] is False
    assert requirements["affection"]["required"] == 30.0

    relationship.update({"affection": 30.0, "trust": 20.0})
    progress = interactions.relationship_progress(state, relationship)
    assert progress["social"]["ready"] is True
    relationship["social_stage"] = "friend"
    progress = interactions.relationship_progress(state, relationship)
    assert progress["romance"]["next"] == "ambiguous"
    romance = {row["key"]: row for row in progress["romance"]["requirements"]}
    assert romance["social_stage"]["met"] is True
    assert romance["attraction"]["required"] == 35.0
    assert romance["affection"]["required"] == 30.0


def test_owned_assets_projection_is_grouped_and_exposed_per_person() -> None:
    state = state_with_people()
    state["gifted_assets"] = [
        {
            "person_id": 1001, "asset_type": "property",
            "asset_id": "home-1", "asset_name": "测试住宅",
            "value": 1_200_000, "day": DAY,
        },
        {
            "person_id": 1001, "asset_type": "vehicle",
            "asset_id": "car-1", "asset_name": "测试跑车",
            "value": 500_000, "day": DAY,
        },
        {
            "person_id": 1002, "asset_type": "property",
            "asset_id": "home-2", "asset_name": "其他人的住宅",
            "value": 900_000, "day": DAY,
        },
    ]
    owned = interactions.person_owned_assets(state, 1001)
    assert owned["count"] == 2
    assert owned["total_value"] == 1_700_000
    assert [row["asset_id"] for row in owned["properties"]] == ["home-1"]
    assert [row["asset_id"] for row in owned["vehicles"]] == ["car-1"]
    assert owned["permanent"] is True

    view = interactions.public_view(state, day=DAY)
    relationship = view["relationships"][0]["relationship"]
    assert relationship["owned_assets"]["count"] == 2
    assert relationship["social_progress"]["social"]["next"] == "friend"


def test_residence_rows_project_occupant_identity_and_relationship_badges() -> None:
    state = state_with_people()
    state["residences"] = {"1001": "home-1"}
    state["relationships"]["1001"].update({
        "social_stage": "close_friend",
        "romance_stage": "partner",
    })
    life = {
        "properties": {
            "home-1": {
                "id": "home-1", "kind": "residential", "tenure": "owned",
                "mode": "self", "area_sqm": 96, "level": 2,
                "name_zh": "东城住宅", "name_en": "East Home",
                "city_name_zh": "北京", "city_name_en": "Beijing",
                "district_name_zh": "东城", "district_name_en": "Dongcheng",
                "city_id": "beijing", "base_price": 1_000_000,
            },
        },
        "vehicles": {}, "garages": {},
    }

    rows = interactions.residence_rows(life, state, DAY)
    assert len(rows) == 1
    assert rows[0]["occupied"] == 1
    assert rows[0]["resident_ids"] == ["1001"]
    occupant = rows[0]["occupants"][0]
    assert occupant["person"]["id"] == 1001
    assert occupant["person"]["name"] == "测试球员"
    assert occupant["person"]["team_name"] == "测试俱乐部"
    assert occupant["relationship"]["social_stage"] == "close_friend"
    assert occupant["relationship"]["romance_stage"] == "partner"


def test_contact_removal_clears_cached_history_but_keeps_permanent_gifts() -> None:
    state = state_with_people()
    state["residences"] = {"1001": "home-1"}
    state["gifted_assets"] = [{
        "person_id": 1001, "asset_type": "property",
        "asset_id": "home-1", "asset_name": "测试住宅",
        "value": 1_200_000, "day": DAY,
    }]
    state["timeline"] = [
        {"id": "timeline-1", "person_id": 1001, "kind": "chat"},
        {"id": "timeline-2", "person_id": 1002, "kind": "chat"},
    ]

    result = interactions.remove_person(state, 1001)
    assert result["removed"] is True
    assert result["preserved_permanent_gifts"] == 1
    assert result["removed_timeline_entries"] == 1
    assert "1001" not in state["people"]
    assert "1001" not in state["relationships"]
    assert "1001" not in state["residences"]
    assert [row["person_id"] for row in state["timeline"]] == [1002]
    assert state["gifted_assets"][0]["asset_id"] == "home-1"


def test_gift_catalog_maps_every_relationship_gift_category() -> None:
    gift_skus = [sku for sku in club_economy.SHOP_SKUS if sku.startswith("gift_")]
    assert len(gift_skus) == len(interactions.GIFT_CATEGORIES)
    for sku in gift_skus:
        product = club_economy.PRODUCTS[sku]
        assert product["family"] == "gift"
        assert product["gift_category"] in interactions.GIFT_CATEGORIES
        assert web.LocalOddsState._life_interaction_item_category(sku, product) == product[
            "gift_category"
        ]


def test_new_gift_and_interaction_copy_cover_all_eleven_locales() -> None:
    for filename in ("i18n.gifts.js", "i18n.interactions.beta.js"):
        messages = _module_messages(filename)
        assert set(messages) == set(LOCALES)
        baseline = set(messages["en-GB"])
        for locale in LOCALES:
            assert set(messages[locale]) == baseline, (filename, locale)
            for key in baseline:
                assert messages[locale][key].strip(), (filename, locale, key)
                assert _parameters(messages[locale][key]) == _parameters(
                    messages["en-GB"][key]
                ), (filename, locale, key)


def test_people_workspace_delete_progress_ledger_and_network_contract() -> None:
    page = (ROOT / "web" / "interactions_page.js").read_text(encoding="utf-8")
    css = (ROOT / "web" / "interactions.css").read_text(encoding="utf-8")
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    gift = (ROOT / "web" / "gift_shop_page.js").read_text(encoding="utf-8")

    assert 'data-interaction-remove="${id}"' in page
    assert '"/api/life/interactions/remove"' in page
    assert 'life.interactions.relationship.delete_confirm_body' in page
    assert 'life.interactions.people_tabs.owned' in page
    assert 'renderOwnedAssets(data, row)' in page
    assert 'life.interactions.interaction_tabs.progress' in page
    assert 'data-interaction-mode-tab="progress"' in page
    assert 'interaction-progress-requirements' in page
    assert 'data-interaction-action="open-ap-ledger"' in page
    assert 'id="life-interactions-ap-ledger-dialog"' in html
    assert 'renderRelationshipNetwork(data)' in page
    assert 'interaction-network-grid' in page
    assert '.interaction-network-grid' in css
    assert '.interaction-action-grid--three' in css
    assert '.interaction-people-detail,\n.interaction-people-content,' in css
    assert 'width: 100%; min-width: 0;' in css
    assert 'data-page="gift-shop"' in html
    assert 'data-i18n="nav.gifts"' in html
    assert 'id="page-gift-shop"' in html
    assert '"gift-shop": () => window.FMSDDGiftShop?.render()' in app
    assert 'bridge().request("/api/shop/buy-batch"' in gift


def test_visual_relationship_pickers_and_residence_cards_contract() -> None:
    page = (ROOT / "web" / "interactions_page.js").read_text(encoding="utf-8")
    css = (ROOT / "web" / "interactions.css").read_text(encoding="utf-8")
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

    assert 'id="life-interactions-gift-dialog"' in html
    assert 'id="life-interactions-date-dialog"' in html
    assert 'data-interaction-gift-choice="${esc(item.id)}"' in page
    assert 'data-interaction-date-choice="${esc(activity.id)}"' in page
    assert 'function giftGroups(data)' in page
    assert 'existing.count += 1' in page
    assert 'const gifts = giftGroups(data);' in page
    assert 'portraitMarkup(row.person, {small: true})' in page
    assert 'tone-${affectionTone(affection)}' in page
    assert 'life.interactions.residence.occupants' in page
    assert 'residenceOccupantsMarkup(residence)' in page
    assert 'grid-template-columns: repeat(2, minmax(0, 1fr));' in css
    assert 'minmax(310px, 350px)' in css
    assert '.interaction-relation-affection.tone-devoted' in css
    assert '.interaction-choice-dialog' in css
