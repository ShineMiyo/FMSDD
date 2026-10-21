from __future__ import annotations

from datetime import date

import pytest

from tools import life_interactions as interactions


DAY = date(2026, 1, 5).toordinal()


def _state() -> dict:
    state = interactions.normalize_state({}, DAY)
    interactions.save_profile(state, {"name": "玩家", "age": 30}, DAY)
    interactions.cache_search_row(state, {
        "id": 1001, "name": "测试球员", "age": 24, "female": True,
        "nationality_id": 200, "nationality": "英格兰",
        "team_id": 10, "team_name": "测试俱乐部",
        "positions": ["ST"], "ca": 140, "pa": 160,
        "world_reputation": 4000, "object_type": "player",
        "date_of_birth": "2002-03-04",
    }, DAY)
    return state


def _person_with_traits(state: dict, *, values: list[str], personality: list[str]) -> None:
    person = state["people"]["1001"]
    person["traits"]["values"] = values
    person["traits"]["personality"] = personality


def test_money_gift_rewards_value_fit_and_has_diminishing_returns() -> None:
    generous = _state()
    _person_with_traits(generous, values=["stability"], personality=["driven"])
    first = interactions.money_gift_plan(generous, 1001, DAY, 10_000_000)
    first_affection = first["deltas"]["affection"]
    second = interactions.money_gift_plan(generous, 1001, DAY, 10_000_000)
    assert first_affection > 0
    assert second["deltas"]["affection"] < first_affection
    assert generous["relationships"]["1001"]["gifted_value_total"] == 20_000_000

    honest = _state()
    _person_with_traits(honest, values=["honesty"], personality=["reserved"])
    honest_result = interactions.money_gift_plan(honest, 1001, DAY, 10_000_000)
    assert honest_result["deltas"]["affection"] < first_affection


def test_money_gift_rejects_tiny_amounts_and_requires_ap() -> None:
    state = _state()
    with pytest.raises(ValueError):
        interactions.money_gift_plan(state, 1001, DAY, 999)
    state["action_points"]["current"] = 0
    with pytest.raises(ValueError):
        interactions.money_gift_plan(state, 1001, DAY, 1_000_000)


def test_buy_action_points_at_configured_price_and_cap() -> None:
    state = _state()
    state["action_points"]["current"] = 4
    state["action_points"]["maximum"] = 12
    result = interactions.purchase_action_points(state, DAY, 3)
    assert result["points"] == 3
    assert result["cost"] == 3 * interactions.ACTION_POINT_PURCHASE_PRICE
    assert result["current"] == 7
    assert interactions.action_points(state, DAY)["purchase_price"] == interactions.ACTION_POINT_PURCHASE_PRICE
    state["action_points"]["current"] = 12
    with pytest.raises(ValueError):
        interactions.purchase_action_points(state, DAY, 1)


def test_measurement_ranges_are_asymmetric_and_contain_the_true_value() -> None:
    state = _state()
    relationship = state["relationships"]["1001"]
    relationship.update({"familiarity": 55, "trust": 50, "social_stage": "close_friend"})
    person = state["people"]["1001"]
    visible = interactions._visible_person_for_relationship(person, relationship)
    traits = visible["traits"]
    assert traits["measurement_exact"] is False
    assert traits["measurement_ranges"]
    for key, bounds in traits["measurement_ranges"].items():
        true_value = person["traits"]["measurements"][key]
        assert bounds["minimum"] <= true_value <= bounds["maximum"]
        assert bounds["minimum"] < bounds["maximum"]
        # A symmetric range would let the midpoint reveal the exact number.
        assert bounds["minimum"] + bounds["maximum"] != true_value * 2
    again = interactions._visible_person_for_relationship(person, relationship)
    assert again["traits"]["measurement_ranges"] == traits["measurement_ranges"]


def test_money_and_action_point_ui_and_routes_are_wired() -> None:
    from pathlib import Path as _Path
    root = _Path(__file__).resolve().parents[1]
    page = (root / "src" / "web" / "interactions_page.js").read_text(encoding="utf-8")
    api = (root / "src" / "fm_odds_web.py").read_text(encoding="utf-8")
    polish = (root / "src" / "web" / "i18n.interactions.polish.js").read_text(encoding="utf-8")
    assert "open-money-gift" in page
    assert 'life-collection-dialog interaction-money-dialog' in page
    assert 'life-collection-dialog interaction-ap-dialog' in page
    assert 'life-icon-button" data-interaction-action="close-money-gift' in page
    assert "/api/life/interactions/money-gift" in page
    assert "open-ap-purchase" in page
    assert "/api/life/interactions/action-points/purchase" in page
    assert "/api/life/interactions/money-gift" in api
    assert "/api/life/interactions/action-points/purchase" in api
    assert "±{cm}" not in polish


def test_instant_birth_pill_is_expensive_and_only_works_on_pregnancy() -> None:
    from tools import club_economy
    product = club_economy.PRODUCTS["instant_birth_pill"]
    assert product["price"] == 1_000_000_000
    assert product["category"] == "子女"

    state = _state()
    relationship = state["relationships"]["1001"]
    with pytest.raises(ValueError):
        interactions.use_birth_pill(state, 1001, DAY)
    relationship["pregnancy"] = {
        "status": "expecting", "decision": "pending",
        "conceived_day": DAY - 20, "due_day": DAY + 100,
        "due_early": DAY + 80, "due_late": DAY + 120,
    }
    result = interactions.use_birth_pill(state, 1001, DAY)
    assert result["child"]["id"]
    assert relationship["children"][-1]["id"] == result["child"]["id"]
    assert relationship["pregnancy"]["status"] == "born"
    assert relationship["pregnancy"]["born_day"] == DAY
    assert relationship["pregnancy"]["decision"] == "kept"


def test_birth_pill_route_and_ui_are_wired() -> None:
    from pathlib import Path as _Path
    root = _Path(__file__).resolve().parents[1]
    api = (root / "src" / "fm_odds_web.py").read_text(encoding="utf-8")
    app = (root / "src" / "web" / "app.js").read_text(encoding="utf-8")
    assert "/api/life/interactions/children/birth-pill" in api
    assert "use_life_birth_pill" in api
    assert "instant_birth_pill" in app
    assert "useBirthPillFromInventory" in app
    assert "no_pregnant_target" in app
