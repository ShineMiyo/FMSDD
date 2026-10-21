from __future__ import annotations

import threading
from datetime import date
from unittest.mock import patch

from tools import life_children, life_interactions, life_system

DAY = date(2026, 1, 5).toordinal()


def _state_with_child(age: int, name: str = "") -> dict:
    state = life_interactions.normalize_state({}, DAY)
    state["people"]["1001"] = {"id": 1001, "name": "测试", "age": 30}
    state["relationships"]["1001"] = life_interactions._normalize_relationship({
        "person_name": "测试", "romance_stage": "spouse",
        "children": [{
            "id": "child-000001", "name": name,
            "born_day": DAY - age * life_children.CHILD_AGE_DAYS,
        }],
    }, 1001)
    return state


def test_named_child_is_projectable_and_starts_unnamed() -> None:
    state = _state_with_child(3)
    view = life_interactions.public_view(
        state, life_state=life_system._empty_state(), day=DAY,
    )
    assert view["children"][0]["age"] == 3
    assert view["children"][0]["named"] is False
    assert view["children"][0]["ready_for_academy"] is False
    assert [row["id"] for row in view["children_rules"]["elixirs"]][0] == "apprentice"


def test_child_naming_and_elixir_growth_cross_the_adult_age() -> None:
    state = _state_with_child(3)
    child = life_children.name_child(state, "child-000001", "小明", DAY, preferred_position="ST")
    assert child["name"] == "小明"
    quote = life_children.elixir_quote(child, "immortal", DAY)
    assert quote["current_age"] == 3
    assert quote["target_age"] >= 15
    assert quote["crosses_adult_age"] is True
    result = life_children.apply_elixir(state, "child-000001", "immortal", DAY)
    assert result["child"]["growth_source"] == "elixir"
    assert result["child"]["elixirs_used"][0]["tier"] == "immortal"
    assert life_children.eligibility(result["child"], DAY)["ready"] is True


def test_child_needs_a_name_before_an_elixir() -> None:
    state = _state_with_child(3)
    try:
        life_children.elixir_quote({"id": "x", "born_day": DAY - 3 * 365}, "apprentice", DAY)
    except ValueError:
        pass
    quote = life_children.elixir_quote({"born_day": DAY - 3 * 365}, "apprentice", DAY)
    assert quote["target_age"] == 4


def test_placement_sync_reflects_native_youth_plan_status() -> None:
    state = _state_with_child(15, name="小明")
    found = life_children.find_child(state, "child-000001")
    assert found is not None
    life_children.apply_child_placement_plan(
        found[1], DAY, team_id=42, team_name="测试俱乐部", mode="own",
    )
    changed = life_interactions.sync_child_placements(state, {
        "42": {"status": "completed", "player_id": 777, "player_name": "明 小"},
    }, DAY)
    assert changed is True
    placement = found[1]["placement"]
    assert placement["status"] == "playing"
    assert placement["player_id"] == 777
    assert life_interactions.sync_child_placements(state, {}, DAY) is False


def test_child_academy_config_is_accepted_by_the_native_planner() -> None:
    from tools import youth_intake

    config = life_children.child_academy_plan_config(
        {"name": "小明", "preferred_position": "ST"}, "",
    )
    normalized = youth_intake.normalize_youth_plan_config("academy_son", config)
    assert normalized["count"] == 1
    assert normalized["name"] == "小明"
    assert normalized["primary_position"] == "ST"
