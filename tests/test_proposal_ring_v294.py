from __future__ import annotations

from datetime import date
from unittest.mock import patch

from tools import life_interactions as interactions

DAY = date(2026, 1, 5).toordinal()


def _state() -> dict:
    state = interactions.normalize_state({}, DAY)
    interactions.save_profile(state, {"name": "玩家", "age": 30, "gender": "male"}, DAY)
    interactions.cache_search_row(state, {
        "id": 1001, "name": "测试球员", "age": 27, "female": True,
        "nationality_id": 200, "nationality": "England", "team_id": 10,
        "team_name": "测试俱乐部", "positions": ["ST"], "ca": 140, "pa": 160,
        "object_type": "player", "date_of_birth": "1999-03-04",
    }, DAY)
    relationship = state["relationships"]["1001"]
    relationship.update({
        "familiarity": 95, "affection": 95, "trust": 95, "attraction": 90,
        "respect": 95, "romance_stage": "partner", "intimacy": 75,
        "social_stage": "close_friend",
    })
    state["action_points"]["current"] = 12
    return state


def test_ring_raises_proposal_chance_and_missing_ring_penalises_failure() -> None:
    with_ring_state = _state()
    without_ring_state = _state()
    with patch.object(interactions, "_stable_unit", return_value=0.99):
        ring_result = interactions.relationship_plan(
            with_ring_state, 1001, DAY, "spouse", has_ring=True,
        )
        no_ring_result = interactions.relationship_plan(
            without_ring_state, 1001, DAY, "spouse", has_ring=False,
        )
    assert ring_result["chance"] > no_ring_result["chance"]
    assert ring_result["success"] is False and no_ring_result["success"] is False
    assert no_ring_result["deltas"]["affection"] < 0
    assert ring_result["ring_used"] is True
