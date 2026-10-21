from __future__ import annotations

import copy

import pytest

import fm_odds_web as web
import tools.club_economy as club_economy
from tools import life_interactions
from tools.money import to_minor, write_minor


def cdk_economy(monkeypatch, balance: float = 0.0):
    """Bind one in-memory economy document plus its committed snapshots."""
    state = club_economy._new_state()
    write_minor(state, "general_balance", to_minor(balance))
    saved: list[dict] = []
    monkeypatch.setattr(club_economy, "load_economy", lambda: state)
    monkeypatch.setattr(club_economy, "save_economy", lambda payload: saved.append(copy.deepcopy(payload)))
    monkeypatch.setattr(club_economy, "available_balance", lambda: 0.0)
    monkeypatch.setattr(club_economy, "load_wallet", lambda: {"transactions": []})
    return state, saved


def test_a_built_in_code_credits_the_bank_once_per_save(monkeypatch):
    state, saved = cdk_economy(monkeypatch)

    result = club_economy.redeem_cdk("\u540d\u53d6\u65e9\u8036\u9999")

    assert state["general_balance"] == 15_000_000_000_000_000.0
    assert result["bank_balance"] == 15_000_000_000_000_000.0
    assert result["cdk"]["code"] == "\u540d\u53d6\u65e9\u8036\u9999"
    assert result["cdk"]["amount"] == 15_000_000_000_000_000.0
    assert state["transactions"][-1]["type"] == "cdk_redeem"
    assert state["transactions"][-1]["source"] == "cdk"
    assert state["cdk_redemptions"]["\u540d\u53d6\u65e9\u8036\u9999"]["amount"] == 15_000_000_000_000_000.0
    assert saved

    with pytest.raises(ValueError, match=r"^cdk\.redeemed$"):
        club_economy.redeem_cdk("\u540d\u53d6\u65e9\u8036\u9999")
    assert state["general_balance"] == 15_000_000_000_000_000.0
    assert len(saved) == 1


def test_the_code_ignores_spacing_and_rejects_unknown_text(monkeypatch):
    state, _saved = cdk_economy(monkeypatch)

    with pytest.raises(ValueError, match=r"^cdk\.empty$"):
        club_economy.redeem_cdk("   ")
    with pytest.raises(ValueError, match=r"^cdk\.invalid$"):
        club_economy.redeem_cdk("not-a-code")

    embedded = club_economy.redeem_cdk(" \u3000\u540d\u53d6\u65e9\u8036\u9999 ")
    assert embedded["cdk"]["amount"] == 15_000_000_000_000_000.0
    assert state["general_balance"] == 15_000_000_000_000_000.0


def test_an_alias_spends_the_same_single_use_code(monkeypatch):
    state, saved = cdk_economy(monkeypatch)

    result = club_economy.redeem_cdk("natori   sayaka")

    assert result["cdk"]["code"] == "\u540d\u53d6\u65e9\u8036\u9999"
    assert state["cdk_redemptions"]["\u540d\u53d6\u65e9\u8036\u9999"]["amount"] == 15_000_000_000_000_000.0
    assert saved

    with pytest.raises(ValueError, match=r"^cdk\.redeemed$"):
        club_economy.redeem_cdk("\u540d\u53d6\u65e9\u8036\u9999")


def test_every_built_in_code_has_a_positive_grant_or_interaction_effect():
    assert club_economy.CDK_CODES
    for code, entry in club_economy.CDK_CODES.items():
        if "amount" in entry:
            assert to_minor(entry["amount"]) > 0, code
        else:
            assert entry.get("effect") in life_interactions.CDK_PERK_EFFECTS, code
    assert club_economy.TRANSACTION_LABELS["cdk_redeem"]
    for code, entry in club_economy.CDK_CODES.items():
        for alias in entry.get("aliases") or ():
            assert club_economy._cdk_key(alias) != club_economy._cdk_key(code), (code, alias)


def test_interaction_perk_codes_are_claimed_once_without_bank_credit(monkeypatch):
    state, saved = cdk_economy(monkeypatch)

    result = club_economy.redeem_cdk("\u65e5\u7406\u4e07\u673a")

    assert result["cdk"]["code"] == "\u65e5\u7406\u4e07\u673a"
    assert result["cdk"]["effect"] == "action_points"
    assert result["cdk"]["amount"] == 0.0
    assert not state["transactions"]
    assert state["cdk_redemptions"]["\u65e5\u7406\u4e07\u673a"]["effect"] == "action_points"
    assert saved

    with pytest.raises(ValueError, match=r"^cdk\.redeemed$"):
        club_economy.redeem_cdk("\u65e5\u7406\u4e07\u673a")
    assert len(saved) == 1


def test_the_cdk_route_is_registered():
    routes = {path: name for _method, path, name in web.API_ROUTES.describe()}
    assert routes["/api/cdk/redeem"] == "redeem_cdk"
