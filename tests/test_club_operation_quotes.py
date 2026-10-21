from __future__ import annotations

import pytest

from tools.club_operation_quotes import (
    owned_club_brand_quote,
    owned_club_brand_quotes,
    owned_club_facility_upgrade_price,
    owned_club_facility_upgrade_quote,
    owned_club_record_sale_metrics,
    owned_club_sale_price,
)


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (1, 1_500_000),
        ("10", 3_750_000),
        (19, 6_000_000),
    ],
)
def test_facility_upgrade_price_accepts_valid_current_levels(level, expected):
    assert owned_club_facility_upgrade_price(level) == expected


@pytest.mark.parametrize("level", [None, "unknown", 0, 20, 21])
def test_facility_upgrade_price_rejects_invalid_current_levels(level):
    assert owned_club_facility_upgrade_price(level) is None


def test_facility_upgrade_quote_totals_each_level_and_duration():
    assert owned_club_facility_upgrade_quote(10, 3) == {
        "before": 10,
        "after": 13,
        "levels": 3,
        "price": 12_000_000,
        "days": 36,
    }


@pytest.mark.parametrize(
    ("level", "levels", "message"),
    [
        ("unknown", 1, "设施等级或升级级数无效"),
        (10, "unknown", "设施等级或升级级数无效"),
        (0, 1, "无法读取该项俱乐部设施等级"),
        (21, 1, "无法读取该项俱乐部设施等级"),
        (10, 0, "请选择 1 至 10 级"),
        (19, 2, "请选择 1 至 1 级"),
        (20, 1, "请选择 1 至 0 级"),
    ],
)
def test_facility_upgrade_quote_preserves_invalid_boundary_errors(
    level, levels, message,
):
    with pytest.raises(ValueError, match=f"^{message}$"):
        owned_club_facility_upgrade_quote(level, levels)


def test_sale_price_does_not_discount_the_competition_premium():
    assert owned_club_sale_price({
        "current_valuation": 1_000,
        "competition_premium": 200,
    }) == 984


def test_sale_price_caps_the_competition_premium_at_valuation():
    assert owned_club_sale_price({
        "current_valuation": 1_000,
        "competition_premium": 2_000,
    }) == 1_000


@pytest.mark.parametrize(
    "metrics",
    [
        {},
        {"current_valuation": 0},
        {"current_valuation": "unknown"},
        {"current_valuation": 1_000, "competition_premium": "unknown"},
        {"current_valuation": 1_000, "unavailable": True},
    ],
)
def test_sale_price_rejects_missing_or_unusable_valuation(metrics):
    assert owned_club_sale_price(metrics) is None


def test_record_sale_metrics_prefer_portfolio_values_and_cap_premium():
    assert owned_club_record_sale_metrics({
        "portfolio_metrics": {
            "current_valuation": 1_200,
            "competition_premium": 1_500,
        },
        "current_valuation": 1_100,
        "competition_premium": 300,
        "acquisition_valuation": {
            "price": 1_000,
            "competition_premium": 200,
        },
        "acquisition_price": 900,
    }) == {
        "current_valuation": 1_200,
        "competition_premium": 1_200,
        "market_factor": 1.0,
    }


@pytest.mark.parametrize(
    ("ownership", "expected"),
    [
        (
            {
                "current_valuation": 1_100,
                "competition_premium": 300,
                "acquisition_valuation": {
                    "price": 1_000,
                    "competition_premium": 200,
                },
                "acquisition_price": 900,
            },
            {"current_valuation": 1_100, "competition_premium": 300, "market_factor": 1.0},
        ),
        (
            {
                "current_valuation": 0,
                "competition_premium": 0,
                "acquisition_valuation": {
                    "price": 1_000,
                    "competition_premium": 200,
                },
                "acquisition_price": 900,
            },
            {"current_valuation": 1_000, "competition_premium": 200, "market_factor": 1.0},
        ),
        (
            {"acquisition_valuation": "invalid", "acquisition_price": 900},
            {"current_valuation": 900, "competition_premium": 0, "market_factor": 1.0},
        ),
        (
            {
                "acquisition_valuation": {"price": 1_000, "competition_premium": 0},
                "acquisition_market_factor": 1.25,
            },
            {"current_valuation": 1_000, "competition_premium": 0, "market_factor": 1.25},
        ),
        (
            {
                "acquisition_valuation": {"price": 1_000, "competition_premium": 0},
                "acquisition_market_factor": "unknown",
            },
            {"current_valuation": 1_000, "competition_premium": 0, "market_factor": 1.0},
        ),
        ({}, {"current_valuation": 0, "competition_premium": 0, "market_factor": 1.0}),
    ],
)
def test_record_sale_metrics_follow_the_documented_fallback_order(
    ownership, expected,
):
    assert owned_club_record_sale_metrics(ownership) == expected


@pytest.mark.parametrize(
    ("reputation", "expected_price"),
    [
        (0, 4_000_000),
        (2_500, 8_000_000),
        (4_000, 16_000_000),
        (5_500, 30_000_000),
        (7_000, 60_000_000),
        (8_500, 100_000_000),
        (9_000, 160_000_000),
        (9_500, 240_000_000),
    ],
)
def test_brand_quote_uses_the_band_at_each_threshold(
    reputation, expected_price,
):
    assert owned_club_brand_quote(reputation, 50)["price"] == expected_price


def test_brand_quote_caps_applied_reputation_and_price_at_ten_thousand():
    assert owned_club_brand_quote(9_990, 300) == {
        "before": 9_990,
        "requested": 300,
        "after": 10_000,
        "applied": 10,
        "price": 48_000_000,
    }
    assert [quote["requested"] for quote in owned_club_brand_quotes(9_990)] == [
        50, 100, 300,
    ]
    assert {quote["after"] for quote in owned_club_brand_quotes(9_990)} == {10_000}
    assert owned_club_brand_quotes(10_000) == []


@pytest.mark.parametrize(
    ("reputation", "delta", "message"),
    [
        ("unknown", 50, "俱乐部声望或推广规格无效"),
        (7_000, "unknown", "俱乐部声望或推广规格无效"),
        (7_000, 20, "请选择已有的品牌推广规格"),
        (10_000, 50, "俱乐部声望已经达到 10000"),
    ],
)
def test_brand_quote_preserves_invalid_specification_errors(
    reputation, delta, message,
):
    with pytest.raises(ValueError, match=f"^{message}$"):
        owned_club_brand_quote(reputation, delta)


def test_sale_price_follows_the_stock_market_factor():
    """A club bought while its shares were cheap sells cheap as well."""
    base = {"current_valuation": 1_000, "competition_premium": 200}
    assert owned_club_sale_price({**base, "market_factor": 1.0}) == 984
    assert owned_club_sale_price({**base, "market_factor": 1.25}) == 1_230
    assert owned_club_sale_price({**base, "market_factor": 0.75}) == 738
    assert owned_club_sale_price({**base, "market_factor": "unknown"}) == 984


def test_sale_price_keeps_the_market_factor_inside_its_band():
    base = {"current_valuation": 1_000_000, "competition_premium": 0}
    assert owned_club_sale_price({**base, "market_factor": 99.0}) == 1_960_000
    assert owned_club_sale_price({**base, "market_factor": -3.0}) == 490_000
    assert owned_club_sale_price({**base, "market_factor": 3.0}) == 1_960_000


def test_record_sale_metrics_scale_with_the_stored_market_factor():
    ownership = {
        "acquisition_valuation": {"price": 1_000, "competition_premium": 200},
        "acquisition_market_factor": 1.25,
    }
    metrics = owned_club_record_sale_metrics(ownership)
    assert metrics == {
        "current_valuation": 1_000,
        "competition_premium": 200,
        "market_factor": 1.25,
    }
    assert owned_club_sale_price(metrics) == 1_230
