from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import date
from unittest.mock import patch

from tools import account_application, life_interactions
from tools.club_economy import new_economy_state, resolve_cdk_code

DAY = date(2026, 1, 5).toordinal()


def test_internal_code_resolves_to_a_refill_effect() -> None:
    descriptor = resolve_cdk_code(" 10086 ")
    assert descriptor["code"] == "10086"
    assert descriptor["effect"] == "refill_action_points"
    assert descriptor["amount"] == 0


def test_refill_can_be_used_repeatedly_without_entitlement() -> None:
    state = life_interactions.normalize_state({}, DAY)
    state["action_points"]["current"] = 1
    first = life_interactions.refill_action_points(state, code="10086", day=DAY)
    assert first["before"] == 1
    assert state["action_points"]["current"] == state["action_points"]["maximum"]
    assert not state["entitlements"]
    state["action_points"]["current"] = 3
    second = life_interactions.refill_action_points(state, code="10086", day=DAY)
    assert second["current"] == state["action_points"]["maximum"]
    assert second["amount"] == 0
    assert state["action_points"]["current"] == state["action_points"]["maximum"]
    assert not state["entitlements"]


def test_redeem_service_bypasses_one_shot_redemption_for_10086() -> None:
    state = life_interactions.normalize_state({}, DAY)
    state["action_points"]["current"] = 2
    captured: dict = {}

    def fake_update_documents(initial, mutate, scope_id, legacy_path=None):
        nonlocal state
        documents = deepcopy(initial)
        documents["life_interactions"] = deepcopy(state)
        record = mutate(documents)
        state = documents["life_interactions"]
        captured["documents"] = documents
        captured["record"] = record
        return record

    class Operation:
        scope_id = "internal-cdk-test"
        game_date = "2026-01-05"

        @staticmethod
        def economy_patch(payload, **_kwargs):
            return payload

    @contextmanager
    def operation(_scope):
        yield Operation()

    service = account_application.AccountApplicationService(operation)
    with patch.object(account_application, "update_documents", fake_update_documents), \
            patch.object(account_application, "public_economy", lambda: {"bank_balance": 0}):
        first = service.redeem_cdk({"code": "10086"})
        second = service.redeem_cdk({"code": "10086"})
    assert first["cdk"]["effect"] == "refill_action_points"
    assert second["cdk"]["effect"] == "refill_action_points"
    assert state["action_points"]["current"] == state["action_points"]["maximum"]
    assert not captured["documents"].get("economy", {}).get("cdk_redemptions")
    assert not state["entitlements"]
