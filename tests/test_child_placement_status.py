from __future__ import annotations

from datetime import date
from unittest.mock import patch

from tools import life_children, life_interactions
import fm_odds_web as web

DAY = date(2026, 1, 5).toordinal()


def test_completed_youth_plan_is_visible_to_child_sync() -> None:
    state = life_interactions.normalize_state({}, DAY)
    found = life_children.find_child(state, "missing")
    assert found is None
    # Build a placed child directly.
    relationship = life_interactions._normalize_relationship({
        "person_name": "测试", "romance_stage": "spouse",
        "children": [{
            "id": "child-000001", "name": "小明", "born_day": DAY - 15 * 365,
            "placement": {"status": "armed", "team_id": 42, "team_name": "测试俱乐部"},
        }],
    }, 1001)
    state["relationships"]["1001"] = relationship
    public_plan = {
        "status": "completed",
        "ability_result": {
            "player_id": 777, "player_name": "小明",
            "ca": 92, "pa": 168, "primary_position": "AML",
        },
        "last_message": "done",
    }
    with patch.object(web, "youth_plans_for_team", return_value={"academy_son": public_plan}):
        rows = web.LocalOddsState._child_placement_status_rows(None, "scope", state)
    assert rows["42"]["status"] == "completed"
    assert rows["42"]["player_id"] == 777
    assert rows["42"]["ca"] == 92
    assert rows["42"]["pa"] == 168
    assert rows["42"]["position"] == "AML"
    changed = life_interactions.sync_child_placements(state, rows, DAY)
    assert changed is True
    placement = state["relationships"]["1001"]["children"][0]["placement"]
    assert placement["status"] == "playing"
    assert placement["player_id"] == 777
    assert placement["player_name"] == "小明"
    assert placement["ca"] == 92
    assert placement["pa"] == 168
    assert placement["position"] == "AML"
    child = state["relationships"]["1001"]["children"][0]
    assert child["ca"] == 92
    assert child["pa"] == 168
    assert child["football_position"] == "AML"


def test_rejected_placement_is_retryable() -> None:
    state = life_interactions.normalize_state({}, DAY)
    relationship = life_interactions._normalize_relationship({
        "person_name": "测试", "romance_stage": "spouse",
        "children": [{
            "id": "child-000002", "name": "小红", "born_day": DAY - 15 * 365,
            "placement": {"status": "rejected", "team_id": 42},
        }],
    }, 1002)
    state["relationships"]["1002"] = relationship
    child = relationship["children"][0]
    assert life_children.eligibility(child, DAY)["ready"] is True
    assert life_children.eligibility(child, DAY)["placed"] is False


def test_completed_plan_without_player_uid_is_not_reported_as_in_fm() -> None:
    relationship = life_interactions._normalize_relationship({
        "person_name": "测试", "romance_stage": "spouse",
        "children": [{
            "id": "child-no-uid", "name": "小明", "born_day": DAY - 15 * 365,
            "placement": {"status": "armed", "team_id": 43},
        }],
    }, 1003)
    state = life_interactions.normalize_state({}, DAY)
    state["relationships"]["1003"] = relationship
    changed = life_interactions.sync_child_placements(
        state, {"43": {"status": "completed", "player_id": 0}}, DAY,
    )
    placement = relationship["children"][0]["placement"]
    assert changed is True
    assert placement["status"] == "pending"
    assert placement["player_id"] == 0
    assert "UID" in placement["message"]


def test_legacy_training_with_uid_migrates_to_playing() -> None:
    child = life_children.normalize_child({
        "id": "legacy-playing", "name": "小明",
        "born_day": DAY - 15 * 365,
        "placement": {"status": "training", "team_id": 44, "player_id": 778},
    }, DAY)
    assert child["placement"]["status"] == "playing"
    assert life_children.eligibility(child, DAY)["placed"] is True


def test_legacy_trial_training_status_migrates_without_fm_player() -> None:
    child = life_children.normalize_child({
        "id": "legacy-trial", "name": "小明",
        "born_day": DAY - 15 * 365,
        "placement": {"status": "training", "team_id": 42},
    }, DAY)
    assert child["placement"]["status"] == "trial_passed"
    assert life_children.eligibility(child, DAY)["placed"] is False
    assert life_children.can_start_trial(child, DAY) is False


def test_managed_club_target_recovers_name_and_address_from_context() -> None:
    import threading
    from unittest.mock import patch

    state = web.LocalOddsState.__new__(web.LocalOddsState)
    state.lock = threading.RLock()
    state.output = {"club": {}}
    state.club_contexts = {
        42: {"team": {"id": 42, "name": "测试俱乐部", "address": "0x1234"}},
    }
    state.club_context = state.club_contexts[42]

    with patch.object(
        web.LocalOddsState, "_life_context",
        return_value=("scope", "2026-01-05", DAY, 1),
    ), patch.object(
        web.LocalOddsState, "_life_manager_team_id", return_value=42,
    ), patch.object(
        web.LocalOddsState, "_world_club_native_cache", return_value={},
    ):
        _, output, club = state._managed_club_target(42)

    assert output["game_date"] == "2026-01-05"
    assert club["name"] == "测试俱乐部"
    assert club["address"] == "0x1234"
    assert club["team_id"] == 42
