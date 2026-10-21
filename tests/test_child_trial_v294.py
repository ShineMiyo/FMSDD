from __future__ import annotations

from datetime import date

from tools import life_children

DAY = date(2026, 1, 5).toordinal()


def _child(age: int = 15, pa: int = 160) -> dict:
    return life_children.normalize_child({
        "id": "child-trial-1", "name": "张小明", "surname": "张", "given_name": "小明",
        "born_day": DAY - age * 365, "ca": 80, "pa": pa,
    }, DAY)


def test_trial_rejects_before_fifteen_and_allows_high_potential_at_low_level_club() -> None:
    young = _child(age=14)
    assert life_children.can_start_trial(young, DAY) is False
    try:
        life_children.start_academy_trial(young, DAY, team_id=10, team_name="低级别俱乐部", club_level=1)
    except ValueError as error:
        assert "15" in str(error)
    else:
        raise AssertionError("underage trial should fail")

    child = _child(age=15, pa=170)
    placement = life_children.start_academy_trial(
        child, DAY, team_id=10, team_name="低级别俱乐部", club_level=1,
    )
    assert placement["status"] == "trial_passed"
    assert child["academy"]["team_id"] == 10
    assert life_children.can_start_trial(child, DAY) is False
