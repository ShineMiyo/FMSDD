from __future__ import annotations

import threading
from datetime import date
from unittest.mock import patch

from tools import life_system
import fm_odds_web as web

DAY = date(2026, 1, 5).toordinal()


def _test_pack() -> dict:
    return {
        "city_id": "test-city", "city_name_zh": "测试城", "city_name_en": "Test City",
        "parcels": [
            {
                "id": "test-parcel-1", "city_id": "test-city", "kind": "residential",
                "district_id": "d1", "district_name_zh": "一区", "district_name_en": "One",
                "name_zh": "测试地块一", "name_en": "Test One", "area_sqm": 120,
                "base_price": 1_000_000, "lat": 39.9, "lng": 116.4,
                "monthly_rent": 0.0, "monthly_operating_net": 0.0,
            },
        ],
    }


def _fake_state(state: dict):
    """Minimal LocalOddsState surface with the real pricing/charge methods."""

    class Fake:
        lock = threading.RLock()
        output = {"game_date": "2025-01-01", "selected_manager_id": 1}
        _life_context = web.LocalOddsState._life_context
        _plan_life_property_batch = web.LocalOddsState._plan_life_property_batch
        prepare_life_property_batch = web.LocalOddsState.prepare_life_property_batch
        buy_life_properties = web.LocalOddsState.buy_life_properties

        def _has_verified_save(self):
            return True

        def _data_scope_id(self, _output):
            return "scope"

        def _life_state(self, _scope, _ordinal):
            return state

        def _life_view(self, _state, **_kwargs):
            return {"properties": list(_state.get("properties", {}).values())}

    return Fake()


def test_batch_purchase_charge_details_do_not_shadow_kind() -> None:
    state = life_system.normalize_state({})
    calls = []

    def charge(amount, kind, **details):
        calls.append((amount, kind, details))
        return {"bank": amount, "wallet": 0.0, "total": amount, "transaction_id": "t1"}

    with patch.object(web, "charge_combined_funds", side_effect=charge), \
            patch.object(web, "public_economy", return_value={}), \
            patch.object(web, "refund_combined_funds"), \
            patch.object(life_system, "load_city_pack", return_value=_test_pack()), \
            patch.object(life_system, "save_state", lambda *_a, **_k: None):
        result = _fake_state(state).buy_life_properties(
            {"city_id": "test-city", "kind": "all"},
        )

    assert result["count"] == 1
    assert result["total"] > 0
    assert len(calls) == 1
    assert calls[0][1] == "life_property_batch_buy"
    assert calls[0][2]["property_kind"] == "all"


def test_batch_prepare_prices_without_charging() -> None:
    state = life_system.normalize_state({})
    calls = []

    def charge(amount, kind, **details):  # pragma: no cover - must not run
        calls.append((amount, kind, details))
        return {}

    with patch.object(web, "charge_combined_funds", side_effect=charge), \
            patch.object(life_system, "load_city_pack", return_value=_test_pack()):
        plan = _fake_state(state).prepare_life_property_batch(
            {"city_id": "test-city", "kind": "all"},
        )

    assert not calls
    assert plan["count"] == 1
    assert plan["total"] > 0
    assert plan["items"][0]["parcel_id"] == "test-parcel-1"
