from __future__ import annotations

from datetime import date

from tools import life_children, life_interactions

DAY = date(2026, 1, 5).toordinal()


def _state_with_child(age: int = 3) -> dict:
    state = life_interactions.normalize_state({}, DAY)
    life_interactions.save_profile(
        state, {"name": "张三", "surname": "张", "given_name": "三", "age": 30}, DAY,
    )
    relationship = life_interactions._normalize_relationship({
        "person_name": "测试", "romance_stage": "spouse",
        "children": [{
            "id": "child-000001", "name": "",
            "born_day": DAY - age * 365,
        }],
    }, 1001)
    state["people"]["1001"] = {"id": 1001, "name": "测试", "age": 30}
    state["relationships"]["1001"] = relationship
    return state


def test_child_surname_comes_from_player_and_only_given_name_is_entered() -> None:
    child = life_children.name_child(
        _state_with_child(), "child-000001", "小明", DAY, preferred_position="ST",
    )
    assert child["surname"] == "张"
    assert child["given_name"] == "小明"
    assert child["name"] == "张小明"
    assert child["preferred_position"] == "ST"


def test_growth_elixir_years_cap_at_fifteen() -> None:
    child = life_children.find_child(_state_with_child(10), "child-000001")[1]
    result = life_children.apply_elixir_years(child, 3, DAY)
    assert result["age"] == 13
    result = life_children.apply_elixir_years(child, 2, DAY)
    assert result["age"] == 15
    try:
        life_children.apply_elixir_years(child, 1, DAY)
    except ValueError as error:
        assert "成年" in str(error)
    else:
        raise AssertionError("adult elixir should be rejected")


def test_child_football_event_raises_ca_and_pa() -> None:
    state = _state_with_child(3)
    child = state["relationships"]["1001"]["children"][0]
    view = life_interactions.public_view(state, day=DAY + 120)
    events = [row for row in view["pending_events"] if row["kind"] == "child_football"]
    assert events
    child_row = view["children"][0]
    assert child_row["growth_event"]["id"] == events[0]["id"]
    event = events[0]
    assert 3 <= len(event["options"]) <= 5
    before = (int(child["ca"]), int(child["pa"]))
    result = life_interactions.event_plan(state, event["id"], event["options"][0], DAY + 120)
    assert (result["detail"]["training"]["ca"], result["detail"]["training"]["pa"]) != before
    assert int(child["ca"]) != before[0] or int(child["pa"]) != before[1]
    assert event["data"]["milestone"] == 3


def test_child_ca_pa_are_seeded_and_growth_events_are_age_bound() -> None:
    state = _state_with_child(0)
    child = state["relationships"]["1001"]["children"][0]
    seeded = life_children.seed_child_football(child, state, state["relationships"]["1001"])
    assert 10 <= int(seeded["ca"]) <= 120
    assert int(seeded["ca"]) + 18 <= int(seeded["pa"]) <= 199
    assert life_children.training_due(seeded, DAY) == 0
    seeded["born_day"] = DAY - 3 * 365
    assert life_children.training_due(seeded, DAY + 120) == 3
    seeded["born_day"] = DAY - 4 * 365
    assert life_children.training_due(seeded, DAY + 120) == 0
    penalty = life_children.apply_neglect_penalty(seeded, 3, DAY + 120)
    assert penalty["ca_change"] < 0
    assert 3 in seeded["neglected_milestones"]
