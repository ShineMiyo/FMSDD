from __future__ import annotations

from datetime import date
from unittest.mock import patch

from tools import life_interactions as interactions
from tools import life_system

DAY = date(2026, 1, 5).toordinal()


def _state() -> dict:
    state = interactions.normalize_state({}, DAY)
    interactions.save_profile(state, {"name": "玩家", "age": 30, "gender": "male"}, DAY)
    interactions.cache_search_row(state, {
        "id": 1001, "name": "测试球员", "age": 25, "female": True,
        "nationality_id": 200, "nationality": "England", "team_id": 10,
        "team_name": "测试俱乐部", "positions": ["ST"], "ca": 140, "pa": 160,
        "world_reputation": 4000, "object_type": "player",
        "date_of_birth": "2001-03-04",
    }, DAY)
    return state


def _spouse(state: dict, intimacy: float = 80) -> dict:
    relationship = state["relationships"]["1001"]
    relationship.update({
        "familiarity": 90, "affection": 90, "trust": 90, "attraction": 80,
        "respect": 90, "romance_stage": "spouse", "intimacy": intimacy,
        "social_stage": "acquaintance",
    })
    return relationship


def test_spouse_can_date_even_when_social_stage_is_behind() -> None:
    state = _state()
    _spouse(state)
    result = interactions.date_plan(state, 1001, DAY, "cafe")
    assert result["kind"] == "date"
    assert result["action_cost"] == 2


def test_pregnancy_chance_rises_with_intimacy() -> None:
    state = _state()
    relationship = _spouse(state, 10)
    low = interactions._pregnancy_chance(state, relationship)
    relationship["intimacy"] = 50
    middle = interactions._pregnancy_chance(state, relationship)
    relationship["intimacy"] = 95
    high = interactions._pregnancy_chance(state, relationship)
    assert low < middle < high
    assert high > low * 2


def test_possible_pregnancy_chip_and_due_event() -> None:
    state = _state()
    relationship = _spouse(state, 90)
    state["action_points"]["current"] = 12
    with patch.object(interactions, "_stable_unit", return_value=0.0):
        interactions.intimacy_plan(state, 1001, DAY, "stay_close")
    assert relationship["pregnancy"]["status"] == "expecting"
    pregnancy = relationship["pregnancy"]
    assert pregnancy["due_early"] - DAY == interactions.PREGNANCY_EARLY_DAYS
    assert pregnancy["due_late"] - DAY == interactions.PREGNANCY_LATE_DAYS
    assert pregnancy["due_early"] <= pregnancy["due_day"] <= pregnancy["due_late"]
    view = interactions.public_view(state, day=DAY)
    pregnancy_view = view["relationships"][0]["relationship"]["pregnancy"]
    assert pregnancy_view["possible"] is True
    assert pregnancy_view["revealed"] is False
    assert "due_day" not in pregnancy_view
    assert "days_remaining" not in pregnancy_view
    assert not view["pending_events"]
    discovered = interactions.public_view(
        state, day=DAY + interactions.PREGNANCY_DISCOVERY_DAYS,
    )
    revealed_view = discovered["relationships"][0]["relationship"]["pregnancy"]
    assert revealed_view["revealed"] is True
    assert 220 <= revealed_view["days_remaining"] <= 272
    event = discovered["pending_events"][0]
    assert event["kind"] == "pregnancy"
    assert event["available_day"] == DAY + interactions.PREGNANCY_DISCOVERY_DAYS
    interactions.event_plan(
        state, event["id"], "keep_child", DAY + interactions.PREGNANCY_DISCOVERY_DAYS,
    )
    assert not relationship["children"]
    born = interactions.public_view(state, day=pregnancy["due_day"])
    assert born["relationships"][0]["relationship"]["pregnancy"]["status"] == "born"
    assert len(relationship["children"]) == 1
    assert relationship["children"][0]["born_day"] == pregnancy["due_day"]


def test_no_conception_means_no_chip_and_no_event() -> None:
    state = _state()
    relationship = _spouse(state, 30)
    state["action_points"]["current"] = 12
    with patch.object(interactions, "_stable_unit", return_value=1.0):
        interactions.intimacy_plan(state, 1001, DAY, "stay_close")
    assert "pregnancy" not in relationship or not relationship["pregnancy"]
    view = interactions.public_view(
        state, day=DAY + interactions.PREGNANCY_LATE_DAYS,
    )
    assert not view["relationships"][0]["relationship"].get("pregnancy")
    assert not view["pending_events"]


def test_gift_assets_expose_location_and_garage_identity() -> None:
    state = _state()
    life = life_system._empty_state()
    life["properties"]["property-1"] = {
        "id": "property-1", "kind": "residential", "city_id": "beijing",
        "city_name_zh": "北京", "city_name_en": "Beijing",
        "district_id": "dongcheng", "district_name_zh": "东城",
        "district_name_en": "Dongcheng", "name_zh": "东城住宅 A",
        "name_en": "Dongcheng Home A", "tenure": "owned", "mode": "self",
        "area_sqm": 120, "level": 1, "base_price": 1_000_000,
    }
    life["garages"]["club"] = {
        "id": "club", "name_zh": "俱乐部车库", "name_en": "Club Garage",
        "capacity": 10, "category": "club",
    }
    life["vehicles"]["vehicle-1"] = {
        "id": "vehicle-1", "name": "Test Car", "manufacturer": "Test",
        "class": "A", "rarity": "legendary", "garage_id": "club",
        "catalog_id": "car-1", "image": "assets/life/cars/test.webp",
    }
    with patch.object(life_system, "parcel_quote", return_value=1_200_000), \
            patch.object(life_system, "vehicle_market_value", return_value=500_000):
        options = interactions.asset_gift_options(life, state, DAY)
    property_row = options["properties"][0]
    assert property_row["city_id"] == "beijing"
    assert property_row["district_id"] == "dongcheng"
    assert property_row["district_name_zh"] == "东城"
    vehicle_row = options["vehicles"][0]
    assert vehicle_row["garage_id"] == "club"
    assert vehicle_row["garage_name_zh"] == "俱乐部车库"
    assert vehicle_row["image"] == "assets/life/cars/test.webp"
