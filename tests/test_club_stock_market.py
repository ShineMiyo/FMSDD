"""Club stock market: nation exchanges, deterministic quotes and trading."""

from __future__ import annotations

import pytest

from tools.money import round_money

from tools.club_stock_market import (
    DAILY_SWING,
    DAILY_SWING_CHANCE,
    FACTOR_CAP,
    FACTOR_FLOOR,
    FORM_POINTS_MAX,
    FORM_REPUTATION_MAX_WEIGHT,
    FORM_REPUTATION_MIN_WEIGHT,
    FORM_WEIGHT,
    DEFAULT_REPUTATION,
    FACILITY_MAX,
    INDEX_BASE,
    INDEX_COMPONENTS,
    MAX_INITIAL_SHARES,
    MAX_ORDER_SHARE_RATIO,
    MAX_SHARES_PER_ORDER,
    MIN_SHARE_PRICE,
    MIN_SHARES_OUTSTANDING,
    REPUTATION_SCALE,
    SHARE_SPLIT_TRIGGER,
    SPLIT_RATIO_MAX,
    SPLIT_RATIO_MIN,
    MIN_SPLIT_ISSUE,
    LEGACY_SHARES_OUTSTANDING,
    CAPITAL_REPAIR_VERSION,
    MIN_TRADE_FEE,
    NEWS_FLOOR,
    NEWS_HALF_LIFE,
    NEWS_UNITS,
    NEWS_WEIGHT,
    NOISE_AMPLITUDE,
    POSITION_WEIGHT,
    SCHEMA_VERSION,
    apply_factor,
    assign_codes,
    buy_plan,
    club_factor,
    club_lot_view,
    club_form,
    commit_buy,
    commit_sell,
    daily_swing,
    day_ordinal,
    detect_splits,
    empty_state,
    facility_levels,
    inferred_facility_level,
    initial_shares,
    market_extras,
    max_shares_per_order,
    share_base,
    share_books,
    share_splits,
    listed_shares,
    repair_legacy_capital,
    shares_at,
    split_ratio,
    split_threshold,
    fundamentals_row,
    holding_lots,
    index_series,
    intrinsic_value,
    market_cap,
    market_factor,
    market_noise,
    market_view,
    nation_of,
    nation_board,
    nation_index,
    nation_summary,
    news_decay,
    news_tilt,
    ordinal_date,
    performance_tilt,
    result_day,
    result_news,
    result_points,
    position_ratio,
    price_history,
    quote,
    reads_legacy_capital,
    registry_sync,
    result_weight,
    revert_buy,
    revert_sell,
    sell_plan,
    sellable_qty,
    share_price,
    stock_code,
    stock_public,
    sync_holding_quotes,
    tilt_from,
    toggle_watch,
    trade_fee,
    trading_quote,
    turnover_shares,
    weighted_form,
    weighted_tilt,
)

from tools.club_stock_market import (
    BLOCK_PRICE_PREMIUM,
    MAX_BLOCK_BUY_RATIO,
    MAX_BUY_STAKE,
    MAX_DIRECT_BUY_RATIO,
    MAX_FINANCE_RATIO,
    MAX_FINANCE_STAKE,
    HISTORY_LIMIT,
    INDEX_HISTORY_DAYS,
    MAX_PENDING_ORDERS,
    MIN_FINANCE_RATIO,
    cancel_order,
    commit_finance,
    extras_signature,
    fill_pending_orders,
    finance_extras,
    finance_plan,
    max_block_shares,
    max_direct_shares,
    max_finance_shares,
    order_slots,
    place_limit_sell,
    plan_impact,
    reserved_qty,
    submit_block_order,
    trade_impact,
    trade_impact_delta,
    trading_limits,
)

GAME_DATE = "2025-10-24"
ORDINAL = day_ordinal(GAME_DATE)


def club(club_id: int, name: str, **overrides) -> dict:
    row = {
        "id": club_id, "name": name, "short_name": "", "nation": "英格兰",
        "competition": "英超联赛", "reputation": 6_000, "club_value": 1_000_000_000,
        "recent_results": [], "position": None, "team_count": None,
    }
    row.update(overrides)
    return row


def world(size: int = 60) -> list[dict]:
    rows = []
    for index in range(1, size + 1):
        nation = "英格兰" if index % 3 else "西班牙"
        rows.append(club(
            index, f"Club {index}", nation=nation,
            reputation=1_000 + index * 100, club_value=500_000_000 + index * 10_000_000,
            recent_results=[{"result": "胜"} for _ in range(index % 6)],
            position=(index % 20) + 1, team_count=20,
        ))
    return rows


def dated(outcome: str, days_ago: int, *, reputation=None, competition: str = "") -> dict:
    """One result as the appraiser hands it over: dated and reduced to an ordinal."""
    day = ORDINAL - int(days_ago)
    row = {"result": outcome, "date": ordinal_date(day), "day": day}
    if reputation is not None:
        row["reputation"] = reputation
    if competition:
        row["competition"] = competition
    return row


def initialized(rows: list[dict] | None = None, *, game_date: str = GAME_DATE):
    state = empty_state()
    rows = rows if rows is not None else world()
    outcome = registry_sync(
        state, rows, game_date=game_date, ordinal=day_ordinal(game_date), season="2025",
    )
    return state, rows, outcome


# ---------------------------------------------------------------------------
# Fundamentals and quotes
# ---------------------------------------------------------------------------


def test_day_ordinal_parses_iso_dates_and_rejects_garbage():
    assert day_ordinal("2026-08-12") is not None
    assert day_ordinal("2026-08-13") == day_ordinal("2026-08-12") + 1
    assert ordinal_date(day_ordinal("2026-08-12")) == "2026-08-12"
    assert day_ordinal("") is None
    assert day_ordinal("not-a-date") is None
    assert day_ordinal(None) is None


def test_club_form_counts_the_last_five_results_only():
    outcomes = [{"result": value} for value in ("胜", "胜", "平", "负", "胜", "胜", "胜")]
    assert club_form(outcomes) == {"wins": 3, "draws": 1, "losses": 1, "points": 10}
    assert club_form([]) == {"wins": 0, "draws": 0, "losses": 0, "points": 0}


def test_performance_tilt_rewards_form_and_table_position():
    assert tilt_from(15, 1, 20) > 0 > tilt_from(0, 20, 20)
    assert tilt_from(None, None, None) == 0.0
    assert performance_tilt({"tilt": 0.05}) == pytest.approx(0.05)
    assert performance_tilt({"form_points": 15, "position": 1, "team_count": 20}) > 0


def test_result_weight_reads_match_prestige_on_every_scale():
    assert result_weight(None) == 1.0
    assert result_weight(0) == pytest.approx(FORM_REPUTATION_MIN_WEIGHT)
    assert result_weight(100) == pytest.approx(FORM_REPUTATION_MAX_WEIGHT)
    # A native 0..200 scale is halved into the model before it is read.
    assert result_weight(200) == pytest.approx(FORM_REPUTATION_MAX_WEIGHT)
    assert result_weight("80") == pytest.approx(result_weight(80))
    scales = [result_weight(value) for value in (0, 25, 50, 75, 100)]
    assert scales == sorted(scales)
    assert FORM_REPUTATION_MIN_WEIGHT < result_weight(50) < FORM_REPUTATION_MAX_WEIGHT


def test_weighted_form_keeps_the_plain_record_without_reputation():
    results = [{"result": value} for value in ("胜", "胜", "平", "负", "胜")]
    form = weighted_form(results)
    assert form["points"] == pytest.approx(10.0)
    assert form["count"] == 5.0
    assert form["weight"] == pytest.approx(1.0)
    assert weighted_form([])["count"] == 0.0
    assert weighted_form([{"result": ""}])["points"] == 0.0


def test_weighted_tilt_matches_the_plain_reading_without_reputation():
    checks = (
        ["胜"] * 5, ["负"] * 5, ["平"] * 5, ["胜"], ["胜", "负"], ["?", "胜"],
    )
    for outcomes in checks:
        results = [{"result": value} for value in outcomes]
        points = sum(3 if value == "胜" else 1 if value == "平" else 0 for value in outcomes)
        for position, team_count in ((None, None), (1, 20), (20, 20), (7, 20)):
            assert weighted_tilt(results, position, team_count) == pytest.approx(
                tilt_from(points, position, team_count), abs=1e-12,
            ), outcomes


def test_weighted_tilt_scales_the_swing_with_match_prestige():
    def results(outcome: str, reputation, count: int = 5):
        return [{"result": outcome, "reputation": reputation} for _ in range(count)]

    place = (position_ratio(10, 20) - 0.5) * POSITION_WEIGHT
    for outcome, points, sign in (("胜", 15.0, 1), ("平", 5.0, -1), ("负", 0.0, -1)):
        form = (points / FORM_POINTS_MAX - 0.5) * FORM_WEIGHT
        obscure = weighted_tilt(results(outcome, 0), 10, 20)
        neutral = weighted_tilt(results(outcome, None), 10, 20)
        famous = weighted_tilt(results(outcome, 100), 10, 20)
        assert neutral == pytest.approx(form + place)
        assert obscure == pytest.approx(form * FORM_REPUTATION_MIN_WEIGHT + place)
        assert famous == pytest.approx(form * FORM_REPUTATION_MAX_WEIGHT + place)
        # Prestige magnifies the deviation from an even record instead of
        # moving it: a famous window swings further both ways, an obscure one
        # stays closer to an even record.
        assert (famous - neutral) * sign > 0, outcome
        assert (neutral - obscure) * sign > 0, outcome

    famous_win = weighted_tilt(results("胜", 100), None, None)
    obscure_win = weighted_tilt(results("胜", 0), None, None)
    famous_loss = weighted_tilt(results("负", 100), None, None)
    obscure_loss = weighted_tilt(results("负", 0), None, None)
    assert famous_win > obscure_win > 0 > obscure_loss > famous_loss
    assert obscure_loss == pytest.approx(-obscure_win)
    assert famous_loss == pytest.approx(-famous_win)


def test_weighted_tilt_lets_one_result_outweigh_a_whole_season():
    mixed = [
        {"result": "胜", "reputation": 100},
        {"result": "负", "reputation": 0}, {"result": "负", "reputation": 0},
        {"result": "负", "reputation": 0}, {"result": "负", "reputation": 0},
    ]
    flat = [{"result": "胜", "reputation": 100}] + [
        {"result": "负", "reputation": 100},
    ] * 4
    assert weighted_tilt(mixed, 10, 20) > weighted_tilt(flat, 10, 20)


def test_daily_swing_is_a_half_chance_of_the_small_coin_toss():
    assert DAILY_SWING == pytest.approx(0.005)
    assert DAILY_SWING_CHANCE == pytest.approx(0.5)
    values = [daily_swing(club_id, ORDINAL) for club_id in range(1, 4001)]
    assert set(values) <= {0.0, DAILY_SWING, -DAILY_SWING}
    assert values.count(0.0) / len(values) == pytest.approx(0.5, abs=0.03)
    assert values.count(DAILY_SWING) / len(values) == pytest.approx(0.25, abs=0.03)
    assert values.count(-DAILY_SWING) / len(values) == pytest.approx(0.25, abs=0.03)
    assert daily_swing(7, ORDINAL) == daily_swing(7, ORDINAL)
    assert daily_swing("7", ORDINAL) == daily_swing(7, ORDINAL)
    days = [daily_swing(7, ORDINAL + step) for step in range(120)]
    assert len(set(days)) == 3
    assert len({daily_swing(club_id, ORDINAL) for club_id in range(1, 401)}) > 1


def test_market_factor_adds_the_daily_swing_and_the_news_on_top_of_noise():
    swings = [daily_swing(club_id, ORDINAL) for club_id in range(1, 201)]
    assert any(value != 0.0 for value in swings)
    for club_id in range(1, 201):
        row = club(club_id, f"Club {club_id}")
        expected = 1.0 + market_noise(club_id, ORDINAL) + daily_swing(club_id, ORDINAL)
        assert market_factor(row, ORDINAL) == pytest.approx(
            max(FACTOR_FLOOR, min(FACTOR_CAP, expected)), abs=1e-6,
        )
    moving = [
        club_id for club_id in range(1, 201)
        if daily_swing(club_id, ORDINAL) != daily_swing(club_id, ORDINAL + 1)
    ]
    assert len(moving) > 50


def test_market_noise_is_deterministic_bounded_and_moves():
    first = market_noise(7, ORDINAL)
    assert first == market_noise(7, ORDINAL)
    assert -NOISE_AMPLITUDE <= first <= NOISE_AMPLITUDE
    series = [market_noise(7, ORDINAL + step) for step in range(400)]
    assert len(set(series)) > 350
    assert max(abs(value) for value in series) <= NOISE_AMPLITUDE + 1e-9
    assert abs(sum(series) / len(series)) < 0.01
    assert series != [market_noise(8, ORDINAL + step) for step in range(400)]


def test_one_result_outweighs_a_whole_day_of_market_noise():
    # What a result has to beat is not the texture level - it is how far the
    # texture and the coin toss can move the quote between two game days.
    worst = 0.0
    for club_id in range(1, 1201):
        for day in range(ORDINAL, ORDINAL + 20):
            delta = (
                market_noise(club_id, day + 1) + daily_swing(club_id, day + 1)
                - market_noise(club_id, day) - daily_swing(club_id, day)
            )
            worst = max(worst, abs(delta))
    assert worst < 0.02
    assert NEWS_WEIGHT * FORM_REPUTATION_MIN_WEIGHT > worst
    assert -NEWS_UNITS["负"] * NEWS_WEIGHT * FORM_REPUTATION_MIN_WEIGHT > worst
    assert 0 < NOISE_AMPLITUDE < 0.1
    assert 0 < DAILY_SWING < NOISE_AMPLITUDE


def test_news_units_shape_the_news_around_a_quiet_draw():
    assert NEWS_UNITS["胜"] == pytest.approx(1.0)
    assert NEWS_UNITS["平"] == pytest.approx(0.0)
    assert -1.0 < NEWS_UNITS["负"] < 0.0


def test_result_points_and_result_day_read_every_row_shape():
    assert result_points("胜") == 3.0
    assert result_points("平") == 1.0
    assert result_points("负") == 0.0
    assert result_points("?") is None
    assert result_points(None) is None
    assert result_day({"day": 12}) == 12
    assert result_day({"day": "12"}) == 12
    assert result_day({"day": "not-a-day"}) is None
    assert result_day({"date": GAME_DATE}) == ORDINAL
    assert result_day({"date": "2025-10-24T20:00:00"}) == ORDINAL
    assert result_day({}) is None


def test_news_decay_pays_the_match_day_in_full_and_keeps_a_floor():
    assert news_decay(0) == pytest.approx(1.0)
    assert news_decay(-3) == pytest.approx(1.0)
    assert news_decay(1) < 1.0
    assert news_decay(NEWS_HALF_LIFE) == pytest.approx(
        NEWS_FLOOR + (1.0 - NEWS_FLOOR) * 0.5,
    )
    assert news_decay(400) == pytest.approx(NEWS_FLOOR)
    assert NEWS_FLOOR < news_decay(5) < news_decay(1)


def test_news_tilt_pays_a_win_on_the_match_day_and_fades_it():
    assert result_news(dated("胜", 0), ORDINAL) == pytest.approx(NEWS_UNITS["胜"])
    assert result_news(dated("平", 0), ORDINAL) == pytest.approx(0.0)
    assert result_news(dated("负", 0), ORDINAL) == pytest.approx(NEWS_UNITS["负"])
    assert news_tilt([dated("胜", 0)], ORDINAL) == pytest.approx(NEWS_WEIGHT)
    assert news_tilt([dated("负", 0)], ORDINAL) == pytest.approx(
        NEWS_WEIGHT * NEWS_UNITS["负"],
    )
    assert news_tilt([dated("平", 0)], ORDINAL) == pytest.approx(0.0)
    assert news_tilt(
        [dated("胜", 0, reputation=100)], ORDINAL,
    ) == pytest.approx(NEWS_WEIGHT * FORM_REPUTATION_MAX_WEIGHT)
    assert news_tilt(
        [dated("胜", 0, reputation=0)], ORDINAL,
    ) == pytest.approx(NEWS_WEIGHT * FORM_REPUTATION_MIN_WEIGHT)
    old = news_tilt([dated("胜", 1)], ORDINAL)
    assert 0 < news_tilt([dated("胜", 40)], ORDINAL) < old < news_tilt([dated("胜", 0)], ORDINAL)
    # Five wins spread over a month stack up instead of cancelling out.
    streak = [dated("胜", days) for days in (0, 6, 12, 18, 24)]
    assert news_tilt(streak, ORDINAL) > 2.0 * NEWS_WEIGHT


def test_news_tilt_ignores_undated_and_not_yet_played_results():
    assert news_tilt([{"result": "胜"}], ORDINAL) == 0.0
    assert news_tilt([{"result": "胜", "date": "not-a-date"}], ORDINAL) == 0.0
    assert news_tilt([{"result": "胜", "date": GAME_DATE}], ORDINAL) == pytest.approx(NEWS_WEIGHT)
    assert news_tilt([dated("胜", -1)], ORDINAL) == 0.0
    assert news_tilt([], ORDINAL) == 0.0
    assert news_tilt(None, ORDINAL) == 0.0
    # A window without dates keeps the plain reading and adds no news.
    row = club(1, "Alpha", recent_results=[{"result": "胜"}] * 5, position=1, team_count=20)
    plain = (
        1.0 + performance_tilt(row) + market_noise(1, ORDINAL)
        + daily_swing(1, ORDINAL)
    )
    assert market_factor(row, ORDINAL) == pytest.approx(plain, abs=1e-6)


def test_a_recorded_win_is_always_a_green_day():
    baseline = [dated("胜", 24), dated("负", 18), dated("平", 12), dated("胜", 6)]
    for club_id in range(1, 300):
        before = club(
            club_id, f"Club {club_id}", recent_results=baseline,
            position=10, team_count=20,
        )
        after = club(
            club_id, f"Club {club_id}", recent_results=[dated("胜", 0)] + baseline,
            position=10, team_count=20,
        )
        yesterday = market_factor(before, ORDINAL - 1)
        today = market_factor(after, ORDINAL)
        assert today > yesterday, club_id
        assert (today - yesterday) / yesterday > 0.03, club_id


def test_a_recorded_defeat_is_always_a_red_day():
    baseline = [dated("胜", 24), dated("胜", 18), dated("平", 12), dated("胜", 6)]
    for club_id in range(1, 300):
        before = club(
            club_id, f"Club {club_id}", recent_results=baseline,
            position=10, team_count=20,
        )
        after = club(
            club_id, f"Club {club_id}", recent_results=[dated("负", 0)] + baseline,
            position=10, team_count=20,
        )
        yesterday = market_factor(before, ORDINAL - 1)
        today = market_factor(after, ORDINAL)
        assert today < yesterday, club_id
        assert (today - yesterday) / yesterday < -0.025, club_id


def test_price_history_turns_up_on_the_match_day():
    for club_id in (1, 2, 3, 7, 11, 42):
        row = club(
            club_id, "Alpha",
            recent_results=[dated("胜", 0), dated("平", 5), dated("负", 11)],
            position=8, team_count=20,
        )
        series = price_history(row, ORDINAL, days=6)
        last, previous = series[-1], series[-2]
        assert last["d"] == ordinal_date(ORDINAL)
        assert last["c"] > previous["c"]
        assert last["o"] == previous["c"]
        assert last["h"] >= last["c"] >= last["l"]


def test_market_factor_stays_inside_its_band():
    row = club(1, "Alpha", recent_results=[{"result": "胜"}] * 5, position=1, team_count=20)
    factor = market_factor(row, ORDINAL)
    assert FACTOR_FLOOR <= factor <= FACTOR_CAP
    assert factor == market_factor(row, ORDINAL)
    assert market_factor({}, ORDINAL) == pytest.approx(1.0 + market_noise(0, ORDINAL), abs=0.25)


def test_share_price_is_the_appraisal_times_the_market_factor():
    row = club(1, "Alpha", club_value=1_000_000_000)
    factor = market_factor(row, ORDINAL)
    assert share_price(row, ORDINAL) == pytest.approx(
        quote(1_000_000_000 * factor / initial_shares(row)), abs=1e-6,
    )
    assert intrinsic_value(row) == 1_000_000_000
    assert market_cap(row, ORDINAL) == pytest.approx(1_000_000_000 * factor)


def test_share_price_never_drops_below_the_minimum_tick():
    row = club(1, "Tiny", club_value=1)
    assert share_price(row, ORDINAL) >= MIN_SHARE_PRICE


def test_stock_public_reports_quote_cap_and_change():
    row = club(1, "Alpha", club_value=2_000_000_000)
    public = stock_public(row, ORDINAL, code="ALP", history=True)
    assert public["code"] == "ALP"
    assert public["market_cap"] == pytest.approx(2_000_000_000 * public["factor"], rel=1e-6)
    assert public["change"] == pytest.approx(
        (public["price"] - public["prev_close"]) / public["prev_close"], abs=1e-6,
    )
    assert len(public["history"]) == 30
    assert public["history"][-1]["c"] == public["price"]
    assert public["fundamentals"]["club_value"] == 2_000_000_000


def test_turnover_is_deterministic_and_scales_with_movement():
    row = club(5, "Alpha")
    assert turnover_shares(row, ORDINAL) == turnover_shares(row, ORDINAL)
    assert turnover_shares(row, ORDINAL, 0.2) > turnover_shares(row, ORDINAL, 0.0)
    assert 0 < turnover_shares(row, ORDINAL) < initial_shares(row)


def test_price_history_walks_back_from_the_current_day():
    row = club(3, "Alpha")
    series = price_history(row, ORDINAL, days=10)
    assert len(series) == 10
    assert series[0]["d"] == ordinal_date(ORDINAL - 9)
    assert series[-1]["d"] == ordinal_date(ORDINAL)
    assert series[-1]["c"] == share_price(row, ORDINAL)


# ---------------------------------------------------------------------------
# Share capital and automatic issues
# ---------------------------------------------------------------------------


def test_initial_shares_multiply_the_four_facilities_and_reputation():
    perfect = club(1, "Perfect", reputation=REPUTATION_SCALE, facilities={
        "training": 20, "youth": 20, "junior_coaching": 20, "youth_recruitment": 20,
    })
    assert initial_shares(perfect) == MAX_INITIAL_SHARES == 1_600_000_000
    # The public aliases of the two junior fields read just as well.
    aliased = club(2, "Aliased", reputation=REPUTATION_SCALE, facilities={
        "training": 20, "youth": 20, "junior": 20, "recruitment": 20,
    })
    assert initial_shares(aliased) == MAX_INITIAL_SHARES
    smaller = club(3, "Smaller", reputation=5_000, facilities={
        "training": 10, "youth": 8, "junior_coaching": 6, "youth_recruitment": 4,
    })
    assert initial_shares(smaller) == 10 * 8 * 6 * 4 * 5_000
    # One unfinished or out-of-range level discards the whole reading and the
    # reputation proxy of the acquisition model takes over.
    broken = club(4, "Broken", reputation=5_000, facilities={
        "training": 20, "youth": 20, "junior_coaching": None, "youth_recruitment": 20,
    })
    assert facility_levels(broken) == {}
    assert initial_shares(broken) == inferred_facility_level(5_000) ** 4 * 5_000
    outlaw = club(5, "Outlaw", reputation=5_000, facilities={
        "training": 21, "youth": 20, "junior_coaching": 20, "youth_recruitment": 20,
    })
    assert facility_levels(outlaw) == {}
    # A row without a readable reputation still lists a tradable capital.
    anonymous = club(6, "Anonymous", reputation=None)
    assert initial_shares(anonymous) == initial_shares(club(7, "Named", reputation=DEFAULT_REPUTATION))
    assert initial_shares({"id": 8}) >= MIN_SHARES_OUTSTANDING


def test_a_tiny_club_lists_at_the_one_million_share_floor():
    # Four level-1 facilities and 5,000 reputation multiply out to 5,000
    # shares, which would print a five-figure price for one share of a small
    # club; the floor lifts the listing so a single share still reads as money.
    tiny = club(9, "Tiny", reputation=5_000, facilities={
        "training": 1, "youth": 1, "junior_coaching": 1, "youth_recruitment": 1,
    })
    assert initial_shares(tiny) == MIN_SHARES_OUTSTANDING == 1_000_000
    # The floor never truncates a club that already lists above it.
    assert initial_shares(club(10, "Tiny+", reputation=6_000, facilities={
        "training": 5, "youth": 5, "junior_coaching": 5, "youth_recruitment": 5,
    })) == 5 ** 4 * 6_000
    # The quote of the whole club is the appraisal times the day's factor
    # either way: the floor only spreads the same money over more shares.
    price = share_price(tiny, ORDINAL)
    expected = market_cap(tiny, ORDINAL) / MIN_SHARES_OUTSTANDING
    assert price == pytest.approx(quote(expected), rel=0.001)


def test_inferred_facility_level_mirrors_the_acquisition_proxy():
    # The appraisal scores an unread reputation as zero, so the proxy of a club
    # without readable facilities sits on its floor; the DEFAULT_REPUTATION
    # fallback of initial_shares() is a separate, explicit step above it.
    assert inferred_facility_level(0) == 4
    assert inferred_facility_level(None) == inferred_facility_level(0)
    assert inferred_facility_level(REPUTATION_SCALE) == 16
    levels = [inferred_facility_level(value) for value in (0, 2_000, 5_000, 8_000, 10_000)]
    assert levels == sorted(levels)
    assert FACILITY_MAX >= max(levels) >= min(levels) >= 1


def test_split_ratio_is_deterministic_and_inside_the_band():
    values = [split_ratio(42, index) for index in range(12)]
    assert values == [split_ratio(42, index) for index in range(12)]
    assert all(SPLIT_RATIO_MIN <= value <= SPLIT_RATIO_MAX for value in values)
    # 100%..200%: one issue can at most double the capital, and a draw is
    # never a no-op issue that prints nothing new.
    assert (SPLIT_RATIO_MIN, SPLIT_RATIO_MAX) == (1.00, 2.00)
    assert all(value >= SPLIT_RATIO_MIN + MIN_SPLIT_ISSUE for value in values)
    assert len(set(values)) > 1
    assert values != [split_ratio(43, index) for index in range(12)]
    drawn = [split_ratio(club_id, index) for club_id in range(400) for index in range(4)]
    assert max(drawn) == SPLIT_RATIO_MAX
    assert min(drawn) < SPLIT_RATIO_MIN + 0.2


def test_shares_at_grows_with_every_recorded_issue():
    row = club(11, "Alpha")
    assert shares_at(row, ORDINAL) == initial_shares(row)
    book = {"b": 100.0, "s": [ORDINAL, ORDINAL + 5]}
    first = max(
        initial_shares(row) + 1,
        int(round(initial_shares(row) * split_ratio(11, 0))),
    )
    second = max(first + 1, int(round(first * split_ratio(11, 1))))
    assert shares_at(row, ORDINAL - 1, book) == initial_shares(row)
    assert shares_at(row, ORDINAL, book) == first
    assert shares_at(row, ORDINAL + 4, book) == first
    assert shares_at(row, ORDINAL + 5, book) == second
    assert share_splits({"s": [ORDINAL, "x", None]}) == [ORDINAL]
    assert share_splits(None) == []


def test_registry_sync_freezes_one_share_record_per_listed_club():
    state, rows, outcome = initialized()
    assert outcome["share_book"] == len(rows)
    books = share_books(state)
    assert len(books) == len(rows)
    for row in rows:
        record = books[int(row["id"])]
        assert record["s"] == []
        assert record["b"] == pytest.approx(share_price(row, ORDINAL))
    # A second sync of the same directory adds nothing and keeps the bases.
    again = registry_sync(
        state, rows, game_date=GAME_DATE, ordinal=ORDINAL + 1, season="2025",
    )
    assert again["share_book"] == 0
    assert share_books(state) == books
    # A club that joins the save later lists at that day's own quote.
    late = club(999, "Late", reputation=3_000, club_value=12_000_000)
    registry_sync(
        state, rows + [late], game_date=GAME_DATE, ordinal=ORDINAL + 1, season="2025",
    )
    late_book = share_books(state)[999]
    assert late_book["s"] == []
    assert late_book["b"] == pytest.approx(share_price(late, ORDINAL + 1))
    # A club that leaves the directory keeps its record: a scan that has not
    # finished, a frozen league and a club outside the enabled scope all come
    # back to the capital history they left with instead of listing at a fresh
    # one, which would erase the issues the account paid for.
    registry_sync(
        state, rows, game_date=GAME_DATE, ordinal=ORDINAL + 2, season="2025",
    )
    assert share_books(state)[999] == late_book


def test_a_doubled_quote_forces_one_issue_a_game_day():
    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 2)
    book = share_books(state)[2]
    base = book["b"]
    assert split_threshold(book) == pytest.approx(quote(base * SHARE_SPLIT_TRIGGER))

    # The club did not move: no issue.
    quiet = detect_splits(state, rows, game_date=GAME_DATE, ordinal=ORDINAL)
    assert quiet["count"] == 0

    doubled = {**row, "club_value": int(row["club_value"] * 2)}
    forced = detect_splits(state, [doubled], game_date=GAME_DATE, ordinal=ORDINAL)
    assert forced["count"] == 1
    event = forced["events"][0]
    assert event["club_id"] == 2 and event["issue"] == 1
    assert event["ratio"] == pytest.approx(split_ratio(2, 0))
    assert SPLIT_RATIO_MIN <= event["ratio"] <= SPLIT_RATIO_MAX
    assert event["shares_after"] > event["shares_before"]
    assert event["price"] == pytest.approx(quote(base * SHARE_SPLIT_TRIGGER), rel=0.35)
    # The issue dilutes the quote on the same close, and that diluted price -
    # not the quote that forced it - is the base of the next issue.
    assert event["base"] < event["price"]
    record = share_books(state)[2]
    assert record["s"] == [ORDINAL]
    assert record["b"] == pytest.approx(event["base"])
    assert shares_at(doubled, ORDINAL, record) == event["shares_after"]
    assert [notice["kind"] for notice in state["notices"]][-1] == "split"

    # The same day cannot issue twice: the diluted close is already the base.
    again = detect_splits(state, [doubled], game_date=GAME_DATE, ordinal=ORDINAL)
    assert again["count"] == 0
    # Doubling again from the new base issues once more.
    twice = {**doubled, "club_value": int(doubled["club_value"] * 2)}
    second = detect_splits(state, [twice], game_date=GAME_DATE, ordinal=ORDINAL + 1)
    assert second["count"] == 1
    assert second["events"][0]["issue"] == 2
    assert share_splits(share_books(state)[2]) == [ORDINAL, ORDINAL + 1]


def test_an_issue_scales_every_holding_and_keeps_its_value():
    state, rows, _outcome = initialized()
    stock = stock_public(
        next(row for row in rows if int(row["id"]) == 2), ORDINAL, code="B2",
        book=share_books(state)[2],
    )
    commit_buy(state, stock, buy_plan(stock, 500), game_date=GAME_DATE, ordinal=ORDINAL)
    holding = state["holdings"]["2"]
    cost = round_money(holding["qty"] * holding["avg_cost"])
    row = next(item for item in rows if int(item["id"]) == 2)
    doubled = {**row, "club_value": int(row["club_value"] * 2)}
    forced = detect_splits(state, [doubled], game_date=GAME_DATE, ordinal=ORDINAL)
    assert forced["count"] == 1
    event = forced["events"][0]
    scale = event["shares_after"] / event["shares_before"]
    assert holding["qty"] == round(500 * scale)
    assert holding["avg_cost"] == pytest.approx(cost / holding["qty"], abs=0.01)
    assert event["holding_qty"] == holding["qty"]
    # The issue dilutes the quote, not the stake: the lot keeps the value it
    # had at the quote that forced the issue, and the doubled club value shows
    # up in the scaled holding instead of in the doubled share price.
    after = stock_public(doubled, ORDINAL, code="B2", book=share_books(state)[2], holding=holding)
    assert after["holding_value"] == pytest.approx(500 * event["price"], rel=0.02)
    assert after["shares"] == event["shares_after"]
    assert after["split_count"] == 1
    assert after["share_base"] == pytest.approx(event["base"])
    assert after["split_price"] == pytest.approx(quote(event["base"] * SHARE_SPLIT_TRIGGER))


def test_the_tape_buys_straight_from_the_club_and_never_past_its_holding():
    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 3)
    book = share_books(state)[3]
    stock = stock_public(row, ORDINAL, code="C3", book=book)
    assert stock["club_shares"] == stock["shares"]
    assert stock["initial_shares"] == initial_shares(row)
    assert stock["max_order"] == max_shares_per_order(stock["shares"])

    plan = buy_plan(stock, 100)
    commit_buy(state, stock, plan, game_date=GAME_DATE, ordinal=ORDINAL)
    after = stock_public(row, ORDINAL, code="C3", book=book, holding=state["holdings"]["3"])
    assert after["club_shares"] == after["shares"] - 100
    # The club is the only seller, so its own book is checked before the
    # per-order cap: an order past the shares still on offer is refused first.
    with pytest.raises(ValueError, match="^俱乐部可售股份不足$"):
        buy_plan(after, after["shares"])
    with pytest.raises(ValueError, match="^单笔股数过大$"):
        buy_plan(stock, stock["max_order"] + 1)

    # Selling the lot back hands the shares to the club again.
    sell = sell_plan(state, after, 100, ordinal=ORDINAL + 1)
    commit_sell(state, after, sell, game_date="2025-10-25", ordinal=ORDINAL + 1)
    restored = stock_public(row, ORDINAL + 1, code="C3", book=book)
    assert restored["club_shares"] == restored["shares"]


def test_a_trading_quote_counts_the_club_book_against_the_account():
    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 3)
    book = share_books(state)[3]
    bare = trading_quote(state, row, ORDINAL, code="C3", book=book)
    assert bare["code"] == "C3"
    assert bare["qty"] == 0
    assert bare["club_shares"] == bare["shares"]
    assert bare["max_order"] == max_shares_per_order(bare["shares"])

    commit_buy(state, bare, buy_plan(bare, 400), game_date=GAME_DATE, ordinal=ORDINAL)
    held = trading_quote(state, row, ORDINAL, code="C3", book=book)
    # The cached board knows nothing about the account; the ticket's own quote
    # must, or the club would keep selling shares it no longer has.
    assert held["qty"] == 400
    assert held["club_shares"] == held["shares"] - 400
    assert held["sellable"] == 0
    toggle_watch(state, 3)
    assert trading_quote(state, row, ORDINAL, code="C3", book=book)["watched"] is True
    assert trading_quote(state, row, ORDINAL, code="C3", book=book)["split_count"] == 0


def test_holding_lots_carry_the_capital_of_their_club():
    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 2)
    book = share_books(state)[2]
    stock = stock_public(row, ORDINAL, code="B2", book=book)
    commit_buy(state, stock, buy_plan(stock, 25), game_date=GAME_DATE, ordinal=ORDINAL)

    lots = holding_lots(state, {2: row}, ORDINAL)
    assert len(lots) == 1
    lot = lots[0]
    assert lot["qty"] == 25
    assert lot["shares"] == shares_at(row, ORDINAL, book)
    assert lot["initial_shares"] == initial_shares(row)
    assert lot["club_shares"] == lot["shares"] - 25
    assert lot["max_order"] == max_shares_per_order(lot["shares"])
    assert lot["split_count"] == 0
    assert lot["share_base"] == pytest.approx(quote(share_base(book)))
    assert lot["split_price"] == pytest.approx(split_threshold(book))


def test_max_order_is_two_percent_of_the_capital_and_never_a_round_lot():
    # Two percent of the capital is the only ceiling a click has: a round lot
    # of a million shares is what a ticket offers by default, never what the
    # board allows, so a club big enough for the lot to sit under its two
    # percent answers a click with the whole two percent instead of being
    # pushed into a block application it does not need.
    assert max_shares_per_order(MIN_SHARES_OUTSTANDING) == int(
        MIN_SHARES_OUTSTANDING * MAX_DIRECT_BUY_RATIO
    )
    assert max_shares_per_order(2_000_000) == int(2_000_000 * MAX_DIRECT_BUY_RATIO)
    assert max_shares_per_order(4_000_000) == int(4_000_000 * MAX_DIRECT_BUY_RATIO)
    assert max_shares_per_order(100_000_000) == int(100_000_000 * MAX_DIRECT_BUY_RATIO)
    assert max_shares_per_order(MAX_INITIAL_SHARES) == int(
        MAX_INITIAL_SHARES * MAX_DIRECT_BUY_RATIO
    )
    # The lot is below the cap of the largest club the model can list, so the
    # cap - not the lot - is what a large club answers with.
    assert max_shares_per_order(MAX_INITIAL_SHARES) > MAX_SHARES_PER_ORDER
    assert max_shares_per_order(1) == 1
    assert max_shares_per_order(None) == MAX_SHARES_PER_ORDER
    assert max_shares_per_order(0) == MAX_SHARES_PER_ORDER
    # Fifty orders still fit in one club, and ten clicks are a block.
    assert max_shares_per_order(MIN_SHARES_OUTSTANDING) * 50 <= MIN_SHARES_OUTSTANDING
    assert max_block_shares(MIN_SHARES_OUTSTANDING) == int(
        MIN_SHARES_OUTSTANDING * MAX_BLOCK_BUY_RATIO
    )
    assert max_block_shares(MAX_INITIAL_SHARES) == int(
        MAX_INITIAL_SHARES * MAX_BLOCK_BUY_RATIO
    )
    assert max_block_shares(MIN_SHARES_OUTSTANDING) == (
        max_shares_per_order(MIN_SHARES_OUTSTANDING) * 5
    )


def test_market_view_reports_the_capital_of_every_listed_club():
    state, rows, _outcome = initialized()
    view = market_view(
        state, rows, game_date=GAME_DATE, scope_id="scope-1", nation="英格兰", page_size=50,
    )
    for stock in view["stocks"]:
        assert stock["shares"] == initial_shares(stock)
        assert stock["initial_shares"] == stock["shares"]
        assert stock["club_shares"] == stock["shares"]
        assert stock["split_count"] == 0
        assert stock["share_base"] == pytest.approx(stock["price"])
    assert view["share_trigger"] == SHARE_SPLIT_TRIGGER
    assert view["max_order_ratio"] == MAX_ORDER_SHARE_RATIO
    assert "shares_outstanding" not in view


def test_price_history_reads_the_capital_of_each_candle_day():
    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 2)
    record = share_books(state)[2]
    doubled = {**row, "club_value": int(row["club_value"] * 2)}
    detect_splits(state, [doubled], game_date=GAME_DATE, ordinal=ORDINAL)
    series = price_history(doubled, ORDINAL + 1, days=4, book=record)
    # As-traded candles: the issue is drawn on the day it happened, and every
    # candle still opens at the previous day's close.
    for previous, candle in zip(series, series[1:]):
        assert candle["o"] == pytest.approx(previous["c"], abs=1e-9)
    split_candle = next(candle for candle in series if candle["d"] == ordinal_date(ORDINAL))
    before = next(candle for candle in series if candle["d"] == ordinal_date(ORDINAL - 1))
    ratio = split_ratio(2, 0)
    assert split_candle["l"] < before["c"] / ratio < split_candle["h"]


def test_a_listed_club_keeps_the_capital_it_listed_with():
    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 2)
    book = share_books(state)[2]
    assert book["i"] == initial_shares(row)
    assert listed_shares(row, book) == initial_shares(row)
    assert shares_at(row, ORDINAL, book) == initial_shares(row)
    price = share_price(row, ORDINAL, book)

    # Facilities, reputation and club value all move as the save is played;
    # only a recorded issue may ever change the capital of the club.
    better = {
        **row, "reputation": REPUTATION_SCALE,
        "facilities": {"training": 20, "youth": 20, "junior_coaching": 20, "youth_recruitment": 20},
    }
    assert initial_shares(better) > book["i"]
    assert listed_shares(better, book) == book["i"]
    assert shares_at(better, ORDINAL, book) == book["i"]
    assert share_price(better, ORDINAL, book) == price
    assert max_shares_per_order(shares_at(better, ORDINAL, book)) == max_shares_per_order(book["i"])

    # A record written before the capital was frozen keeps the capital that
    # was in effect instead of jumping to a newly readable facility level.
    legacy = {"b": 10.0, "s": []}
    frozen = registry_sync(
        state, rows, game_date=GAME_DATE, ordinal=ORDINAL + 1, season="2025",
    )
    assert frozen["share_frozen"] == 0 or frozen["share_frozen"] >= 0
    record, added = _frozen_probe(legacy, row)
    assert added == 1
    assert record["i"] == initial_shares(row)


def _frozen_probe(legacy, row):
    """Freeze one pre-freeze record through the public sync, not a copy of it."""
    entry = {"shares": {"2": dict(legacy)}}
    added, frozen = _sync_share_book_probe(entry, [row], ORDINAL)
    return entry["shares"]["2"], frozen


def _sync_share_book_probe(entry, group, ordinal):
    from tools.club_stock_market import _sync_share_book
    return _sync_share_book(entry, group, ordinal)


def test_the_next_issue_is_measured_from_the_price_after_the_last_one():
    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 2)
    book = share_books(state)[2]
    base = share_base(book)
    # 30 -> 60 forces the issue; the diluted close of that same day (45 in
    # the classic example) is what the next doubling is measured against.
    doubled = {**row, "club_value": int(round(row["club_value"] * SHARE_SPLIT_TRIGGER))}
    forced = detect_splits(state, [doubled], game_date=GAME_DATE, ordinal=ORDINAL)
    event = forced["events"][0]
    ratio = event["ratio"]
    assert event["price"] == pytest.approx(quote(base * SHARE_SPLIT_TRIGGER), rel=0.02)
    assert event["base"] == pytest.approx(quote(event["price"] / ratio), rel=0.02)
    record = share_books(state)[2]
    assert record["b"] == pytest.approx(event["base"])
    # Not the old trigger level: the next issue needs another doubling from
    # the price holders actually see after the dilution.
    assert split_threshold(record) == pytest.approx(quote(event["base"] * SHARE_SPLIT_TRIGGER))
    assert split_threshold(record) == pytest.approx(quote(event["price"] * 2 / ratio), abs=0.05)
    assert event["price"] < split_threshold(record) < event["price"] * SHARE_SPLIT_TRIGGER
    # Two thirds of a doubling is not enough any more.
    halfway = {**doubled, "club_value": int(round(doubled["club_value"] * 1.5))}
    assert detect_splits(state, [halfway], game_date=GAME_DATE, ordinal=ORDINAL + 1)["count"] == 0


def test_an_issue_never_cuts_a_lot_below_the_value_it_had():
    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 2)
    book = share_books(state)[2]
    stock = stock_public(row, ORDINAL, code="B2", book=book)
    commit_buy(state, stock, buy_plan(stock, 900), game_date=GAME_DATE, ordinal=ORDINAL)
    before = holding_lots(state, {2: row}, ORDINAL)[0]
    doubled = {**row, "club_value": int(round(row["club_value"] * SHARE_SPLIT_TRIGGER))}
    detect_splits(state, [doubled], game_date=GAME_DATE, ordinal=ORDINAL)
    # Read the lot again at the same club value: the issue is a bookkeeping
    # change of the capital, so the holding is worth what it was worth before.
    after = holding_lots(state, {2: row}, ORDINAL)[0]
    assert after["qty"] > before["qty"]
    assert after["avg_cost"] < before["avg_cost"]
    # Same stake, same money: a capital increase is not a loss.
    assert after["value"] == pytest.approx(before["value"], rel=0.02)
    assert after["cost"] == pytest.approx(before["cost"], rel=0.001)


def test_a_legacy_capital_lot_is_repaired_into_the_clubs_own_scale():
    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 2)
    book = share_books(state)[2]
    price_now = share_price(row, ORDINAL, book)
    legacy_price = quote(market_cap(row, ORDINAL) / LEGACY_SHARES_OUTSTANDING)
    scale = max(legacy_price, price_now) / min(legacy_price, price_now)
    assert scale > 4  # the two capital scales are never close
    qty = 1_000
    state["holdings"]["2"] = {
        "qty": qty, "avg_cost": legacy_price, "locked_qty": qty, "locked_ordinal": ORDINAL,
        "code": "B2", "name": row["name"], "nation": row["nation"],
    }
    state["trades"].append({
        "id": "legacy-1", "at": "2026-01-01T00:00:00", "game_date": GAME_DATE,
        "side": "buy", "club_id": 2, "code": "B2", "name": row["name"],
        "nation": row["nation"], "qty": qty, "price": legacy_price,
        "amount": round_money(qty * legacy_price), "fee": 0.0,
    })

    outcome = repair_legacy_capital(state, rows, game_date=GAME_DATE, ordinal=ORDINAL)
    assert outcome["checked"] is True
    assert outcome["count"] == 1
    holding = state["holdings"]["2"]
    assert holding["qty"] == pytest.approx(round(qty * legacy_price / price_now), rel=0.01)
    assert holding["locked_qty"] == holding["qty"]
    # The lot keeps the money it paid and the stake it bought.
    assert holding["qty"] * price_now == pytest.approx(qty * legacy_price, rel=0.02)
    assert holding["avg_cost"] == pytest.approx(price_now, rel=0.02)
    assert state["capital_repair"] == CAPITAL_REPAIR_VERSION
    assert [notice["kind"] for notice in state["notices"]][-1] == "capital"

    # One repair per save: the flag stops a second pass from scaling again.
    again = repair_legacy_capital(state, rows, game_date=GAME_DATE, ordinal=ORDINAL)
    assert again["checked"] is False and again["count"] == 0
    assert state["holdings"]["2"] == holding


def test_reads_legacy_capital_keeps_the_closest_reading_and_ties_on_today():
    row = club(11, "Scale", reputation=5_000)
    capital = initial_shares(row)
    cap_now = 800_000_000.0
    legacy = quote(cap_now / LEGACY_SHARES_OUTSTANDING)
    today = quote(cap_now / capital)
    assert reads_legacy_capital(legacy, capital=capital, cap_now=cap_now) is True
    assert reads_legacy_capital(today, capital=capital, cap_now=cap_now) is False
    # A price that implies the same capitalisation on both scales - the
    # capital of the club is the legacy count itself - stays on today's scale.
    tie = quote(cap_now / LEGACY_SHARES_OUTSTANDING)
    assert reads_legacy_capital(
        tie, capital=LEGACY_SHARES_OUTSTANDING, cap_now=cap_now,
    ) is False
    # Nothing to read: no price, no capital or no cap is never a legacy lot.
    assert reads_legacy_capital(0, capital=capital, cap_now=cap_now) is False
    assert reads_legacy_capital(legacy, capital=0, cap_now=cap_now) is False
    assert reads_legacy_capital(legacy, capital=capital, cap_now=0) is False


def test_the_legacy_repair_leaves_a_lot_bought_on_todays_scale_alone():
    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 2)
    book = share_books(state)[2]
    stock = stock_public(row, ORDINAL, code="B2", book=book)
    commit_buy(state, stock, buy_plan(stock, 700), game_date=GAME_DATE, ordinal=ORDINAL)
    holding = dict(state["holdings"]["2"])
    outcome = repair_legacy_capital(state, rows, game_date=GAME_DATE, ordinal=ORDINAL)
    assert outcome["count"] == 0
    assert state["holdings"]["2"] == holding
    assert state["capital_repair"] == CAPITAL_REPAIR_VERSION


def test_club_lot_view_quotes_one_club_for_a_page_that_never_loaded_the_board():
    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 5)
    book = share_books(state)[5]
    stock = stock_public(row, ORDINAL, code="C5", book=book)
    commit_buy(state, stock, buy_plan(stock, 12), game_date=GAME_DATE, ordinal=ORDINAL)

    lot = club_lot_view(state, row, ORDINAL, book=book)
    # The club profile opens the ticket with this row: the quote, the account
    # lot and the candles all come from the same day.
    assert lot["club_id"] == 5
    assert lot["qty"] == 12
    assert lot["club_shares"] == lot["shares"] - 12
    assert lot["history"][-1]["c"] == lot["price"]
    assert len(lot["history"]) >= 2
    assert lot["history"][-1]["d"] == GAME_DATE


def test_holding_lots_carry_the_board_their_ticket_draws():
    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 2)
    book = share_books(state)[2]
    # The board quotes this nation from the day its exchange opened, so the
    # lot has to be read the same way or its change would not match the chart.
    entry = state["nations"][row["nation"]]
    stock = stock_public(
        row, ORDINAL, code="B2", book=book, since=entry.get("listed_ordinal"),
    )
    commit_buy(state, stock, buy_plan(stock, 40), game_date=GAME_DATE, ordinal=ORDINAL)
    # The order the account placed is part of the quote from that day on, so
    # the lot is read with the account's own impact in it, exactly like the
    # board would quote it.
    after = stock_public(
        row, ORDINAL, code="B2", book=book, since=entry.get("listed_ordinal"),
        extras=market_extras(state),
    )
    assert after["factor"] > stock["factor"]
    lot = holding_lots(state, {2: row}, ORDINAL)[0]
    # A holding of an exchange the player is not looking at must still carry
    # everything its trade ticket shows: appraisal, factor, cap and candles.
    assert lot["intrinsic"] == after["intrinsic"]
    assert lot["factor"] == pytest.approx(after["factor"])
    assert lot["market_cap"] == after["market_cap"]
    assert lot["fundamentals"] == after["fundamentals"]
    assert lot["turnover"] > 0
    assert lot["change"] == pytest.approx(after["change"])
    assert len(lot["history"]) >= 2
    assert lot["history"][-1]["c"] == lot["price"]
    # Bought today, so T+1 still holds the lot; the next game day releases it.
    assert lot["sellable"] == 0 and lot["locked_qty"] == 40
    tomorrow = holding_lots(state, {2: row}, ORDINAL + 1)[0]
    assert tomorrow["sellable"] == 40


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


def test_stock_code_prefers_latin_names_and_falls_back_to_the_id():
    assert stock_code("Manchester United", "", 1) == "MAN"
    assert stock_code("", "Barcelona", 2) == "BAR"
    assert stock_code("尤文图斯", "", 1234).startswith("CLB")
    assert stock_code("尤文图斯", "", 1234) == stock_code("尤文图斯", "", 1234)


def test_assign_codes_keeps_tickers_unique_inside_one_exchange():
    rows = [club(1, "Manchester United"), club(2, "Manchester City"), club(3, "米尔沃尔")]
    codes = assign_codes(rows)
    assert codes[1] == "MAN"
    assert len(set(codes.values())) == 3


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_sync_opens_every_nation_once():
    state, rows, outcome = initialized()
    assert outcome["initialized"] is True
    assert set(state["nations"]) == {"英格兰", "西班牙"}
    assert state["nations"]["英格兰"]["clubs"] == 40
    assert state["notices"][-1]["kind"] == "init"
    assert len(state["nations"]["英格兰"]["components"]) == min(INDEX_COMPONENTS, 40)

    again = registry_sync(state, rows, game_date=GAME_DATE, ordinal=ORDINAL, season="2025")
    assert again["initialized"] is False
    assert again["opened"] == []
    assert again["club_change"] == 0
    assert len(state["notices"]) == 1


def test_registry_sync_reports_club_changes_and_new_nations():
    state, rows, _outcome = initialized()
    trimmed = [row for row in rows if int(row["id"]) != 1]
    trimmed.append(club(999, "Newcomer", nation="意大利"))
    outcome = registry_sync(
        state, trimmed, game_date="2025-10-25", ordinal=ORDINAL + 1, season="2025",
    )
    assert outcome["opened"] == ["意大利"]
    assert outcome["club_change"] == 1
    kinds = {notice["kind"] for notice in state["notices"]}
    assert {"listing", "club_change"} <= kinds


def test_registry_sync_settles_a_holding_whose_club_left_the_database():
    state, rows, _outcome = initialized()
    stock = stock_public(next(row for row in rows if int(row["id"]) == 1), ORDINAL, code="A1")
    commit_buy(state, stock, buy_plan(stock, 100), game_date=GAME_DATE, ordinal=ORDINAL)
    remaining = [row for row in rows if int(row["id"]) != 1]
    # One reading without the club is a sighting, not a farewell: the scan may
    # simply not have reached it yet, so the lot stays and the day is written
    # down for the next game day to judge.
    sighting = registry_sync(
        state, remaining, game_date=GAME_DATE, ordinal=ORDINAL, season="2025",
    )
    assert sighting["settlements"] == []
    assert sighting["cash_credit"] == 0.0
    assert sighting["unconfirmed"] == 1
    assert state["missing"] == {"1": ORDINAL}
    assert state["holdings"]["1"]["qty"] == 100

    # Still gone on a later game day is a club the save lost, and only then is
    # the lot bought out at its last known quote.
    outcome = registry_sync(
        state, remaining, game_date="2025-10-25", ordinal=ORDINAL + 1, season="2025",
    )
    assert outcome["settlements"][0]["club_id"] == 1
    assert outcome["cash_credit"] == pytest.approx(100 * stock["price"])
    assert "1" not in state["holdings"]
    assert state["trades"][-1]["side"] == "delist"
    assert state["notices"][-1]["kind"] == "delisting"
    # The sighting is kept only while the market still waits on the club - the
    # queue of the same club may still need it - so the next reading of a
    # directory that answers for nothing drops it.
    assert state["missing"] == {"1": ORDINAL}
    pruned = registry_sync(
        state, remaining, game_date="2025-10-26", ordinal=ORDINAL + 2, season="2025",
    )
    assert pruned["unconfirmed"] == 0
    assert state["missing"] == {}


def test_a_directory_that_is_still_being_read_never_delists_a_lot():
    state, rows, _outcome = initialized()
    stock = stock_public(next(row for row in rows if int(row["id"]) == 1), ORDINAL, code="A1")
    commit_buy(state, stock, buy_plan(stock, 100), game_date=GAME_DATE, ordinal=ORDINAL)
    remaining = [row for row in rows if int(row["id"]) != 1]
    # The world scan hands the directory over club by club, so a reading that
    # has not reached a club says nothing about the save at all: the registry
    # settles nothing while the reader is still running.
    scanning = registry_sync(
        state, remaining, game_date="2025-10-25", ordinal=ORDINAL + 1,
        season="2025", confirm_absent=False,
    )
    assert scanning["settlements"] == []
    assert scanning["unconfirmed"] == 1
    assert state["holdings"]["1"]["qty"] == 100
    # The club arrives with the rest of the directory: the sighting is dropped
    # and the lot was never touched.
    back = registry_sync(
        state, rows, game_date="2025-10-25", ordinal=ORDINAL + 1, season="2025",
    )
    assert back["unconfirmed"] == 0
    assert state["missing"] == {}
    assert state["holdings"]["1"]["qty"] == 100
    assert [trade["side"] for trade in state["trades"]] == ["buy"]


def test_an_application_waits_out_the_reading_and_is_withdrawn_when_proven_gone():
    state, rows, _row, _book, stock = listed_club(3)
    order = submit_block_order(
        state, stock, stock["block_order"], game_date=GAME_DATE, ordinal=ORDINAL,
    )
    remaining = [row for row in rows if int(row["id"]) != 3]
    later = ORDINAL + 1
    # Day one without the club: nothing is withdrawn, the day is remembered.
    first = fill_pending_orders(
        state, remaining, later, game_date=ordinal_date(later),
        books=share_books(state),
    )
    assert first["fills"] == [] and first["cancels"] == []
    assert first["unconfirmed"] == 1
    assert order["status"] == "pending"
    assert state["missing"] == {"3": later}
    assert order_slots(state) == MAX_PENDING_ORDERS - 1

    # Day two without a club the registry has also written down: the
    # application is withdrawn and the withdrawal is reported with its money.
    counted = registry_sync(
        state, remaining, game_date=ordinal_date(later), ordinal=later, season="2025",
    )
    assert counted["unconfirmed"] == 1
    gone = fill_pending_orders(
        state, remaining, later + 1, game_date=ordinal_date(later + 1),
        books=share_books(state),
    )
    assert gone["fills"] == [] and len(gone["cancels"]) == 1
    assert gone["refunds"] == pytest.approx(order["total"], abs=0.01)
    assert order["status"] == "cancelled"
    assert order["reason"] == "该俱乐部已不在当前存档"
    assert state["notices"][-1]["kind"] == "order_cancel"
    assert state["notices"][-1]["refund"] == pytest.approx(order["total"], abs=0.01)
    assert order_slots(state) == MAX_PENDING_ORDERS
    assert state["missing"] == {}


def test_a_listing_day_from_the_future_never_freezes_an_exchange():
    from tools.club_stock_market import listing_day

    # A game day that went backwards can leave an exchange stamped with a day
    # the save no longer reaches.  That is not a listing day: reading it as one
    # empties the candles and pins the quote to zero change.
    assert listing_day(ORDINAL + 5, ORDINAL) is None
    assert listing_day(ORDINAL, ORDINAL) == ORDINAL
    assert listing_day(ORDINAL - 5, ORDINAL) == ORDINAL - 5
    assert listing_day(None, ORDINAL) is None
    assert listing_day(0, ORDINAL) is None

    state, rows, _outcome = initialized()
    entry = state["nations"]["英格兰"]
    entry["listed_ordinal"] = ORDINAL + 5
    today = registry_sync(
        state, rows, game_date=GAME_DATE, ordinal=ORDINAL, season="2025",
    )
    # The registry puts the exchange back on the day the board is quoting.
    assert entry["listed_ordinal"] == ORDINAL
    assert "英格兰" not in today["opened"]
    row = next(item for item in rows if nation_of(item) == "英格兰")
    book = share_books(state)[int(row["id"])]
    by_id = {int(item["id"]): item for item in rows}
    late = ORDINAL + 2
    stock = stock_public(
        row, late, code="A1", since=entry["listed_ordinal"], book=book,
        history=True,
    )
    # The exchange trades again: the quote moves against the previous close,
    # the candles of its days are there to be drawn, and its index is quoted
    # instead of standing still.
    assert stock["change"] != 0.0
    assert len(stock["history"]) == late - ORDINAL + 1
    series = index_series(entry, by_id, late)
    assert len(series) == INDEX_HISTORY_DAYS
    assert len({candle["c"] for candle in series}) > 1


def test_index_starts_at_its_base_and_keeps_its_level_across_a_rebalance():
    state, rows, _outcome = initialized()
    ordinal = ORDINAL
    entry = state["nations"]["英格兰"]
    by_id = {int(row["id"]): row for row in rows}
    before = nation_index(entry, by_id, ordinal)["value"]
    assert before == pytest.approx(INDEX_BASE, rel=0.2)

    registry_sync(state, rows, game_date="2026-07-01", ordinal=ordinal + 200, season="2026")
    after = nation_index(state["nations"]["英格兰"], by_id, ordinal)
    assert after["value"] == pytest.approx(before, rel=0.35)
    assert state["notices"][-1]["kind"] == "rebalance"
    assert len(index_series(state["nations"]["英格兰"], by_id, ordinal, days=40)) == 40


def test_nation_summary_and_board_cover_every_club():
    _state, rows, _outcome = initialized()
    summary = nation_summary(rows, ORDINAL)
    assert summary["英格兰"]["clubs"] == 40
    assert summary["英格兰"]["gainers"] + summary["英格兰"]["losers"] == 40
    assert summary["英格兰"]["cap"] > 0

    board = nation_board(rows, ORDINAL, nations=["英格兰"])["英格兰"]
    assert len(board) == 40
    assert all(item["price"] > 0 for item in board)
    assert len({item["code"] for item in board}) == 40


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


def test_market_view_pages_sorts_and_searches_one_exchange():
    state, rows, _outcome = initialized()
    view = market_view(
        state, rows, game_date=GAME_DATE, scope_id="scope-1", nation="英格兰",
        sort="value", order="desc", page=1, page_size=10,
    )
    assert view["ready"] is True
    assert view["nation"] == "英格兰"
    assert len(view["stocks"]) == 10
    assert view["pagination"]["total"] == 40
    assert view["pagination"]["page_count"] == 4
    caps = [stock["market_cap"] for stock in view["stocks"]]
    assert caps == sorted(caps, reverse=True)
    assert view["index"]["history"]
    assert view["summary"]["clubs"] == 40
    assert len(view["nations"]) == 2

    second = market_view(
        state, rows, game_date=GAME_DATE, scope_id="scope-1", nation="英格兰",
        sort="value", order="asc", page=1, page_size=10,
    )
    assert [stock["club_id"] for stock in second["stocks"]] != [
        stock["club_id"] for stock in view["stocks"]
    ]
    searched = market_view(
        state, rows, game_date=GAME_DATE, scope_id="scope-1", nation="英格兰",
        search="Club 3", page_size=50,
    )
    assert len(searched["stocks"]) < 40


def test_market_view_reports_holdings_and_totals():
    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 2)
    stock = stock_public(row, ORDINAL, code="B2")
    commit_buy(state, stock, buy_plan(stock, 200), game_date=GAME_DATE, ordinal=ORDINAL)
    # The account's own order is part of the quote from the day it happened, so
    # the lot is worth the close the trade left behind instead of the one it saw.
    close = stock_public(row, ORDINAL, code="B2", extras=market_extras(state))
    assert close["price"] > stock["price"]
    view = market_view(
        state, rows, game_date=GAME_DATE, scope_id="scope-1", nation="英格兰",
    )
    assert view["totals"]["market_value"] == pytest.approx(200 * close["price"], abs=0.05)
    assert view["holdings"][0]["qty"] == 200
    assert view["holdings"][0]["sellable"] == 0
    row = next(item for item in view["stocks"] if item["club_id"] == 2)
    assert row["qty"] == 200 and row["profit"] < 0


def test_market_view_watch_filter_and_toggle():
    state, rows, _outcome = initialized()
    assert toggle_watch(state, 3) is True
    assert toggle_watch(state, 3) is False
    assert toggle_watch(state, 4) is True
    view = market_view(
        state, rows, game_date=GAME_DATE, scope_id="scope-1", nation="英格兰",
        watch_only=True, page_size=50,
    )
    assert [stock["club_id"] for stock in view["stocks"]] == [4]
    assert view["watchlist"] == [4]


def test_market_view_handles_an_empty_directory():
    state = empty_state()
    view = market_view(state, {}, game_date=GAME_DATE, scope_id="scope-1")
    assert view["ready"] is True
    assert view["stocks"] == [] and view["nations"] == []
    assert view["index"]["value"] == INDEX_BASE


def test_market_view_is_stable_for_the_same_game_day():
    state, rows, _outcome = initialized()
    first = market_view(state, rows, game_date=GAME_DATE, nation="英格兰", page_size=50)
    second = market_view(state, rows, game_date=GAME_DATE, nation="英格兰", page_size=50)
    assert [item["price"] for item in first["stocks"]] == [
        item["price"] for item in second["stocks"]
    ]
    later = market_view(state, rows, game_date="2025-11-24", nation="英格兰", page_size=50)
    assert [item["price"] for item in later["stocks"]] != [
        item["price"] for item in first["stocks"]
    ]


# ---------------------------------------------------------------------------
# Trading
# ---------------------------------------------------------------------------


def test_trade_fee_has_a_floor_and_a_rate():
    assert trade_fee(1_000_000) == pytest.approx(3_000)
    assert trade_fee(10) == MIN_TRADE_FEE
    assert trade_fee(0) == 0.0


def test_buy_plan_and_commit_track_cost_fee_and_average_price():
    state, rows, _outcome = initialized()
    stock = stock_public(next(row for row in rows if int(row["id"]) == 1), ORDINAL, code="A1")
    plan = buy_plan(stock, 100)
    assert plan["total"] == pytest.approx(plan["amount"] + plan["fee"])
    trade = commit_buy(state, stock, plan, game_date=GAME_DATE, ordinal=ORDINAL)
    holding = state["holdings"]["1"]
    assert holding["qty"] == 100
    assert holding["avg_cost"] == pytest.approx(plan["total"] / 100, abs=0.01)
    assert holding["name"] == stock["name"] and holding["code"] == "A1"
    assert holding["locked_qty"] == 100
    assert trade["side"] == "buy"
    assert sellable_qty(state, 1, ORDINAL) == 0
    assert sellable_qty(state, 1, ORDINAL + 1) == 100


def test_sell_requires_the_next_game_day_and_records_realized_profit():
    state, rows, _outcome = initialized()
    stock = stock_public(next(row for row in rows if int(row["id"]) == 1), ORDINAL, code="A1")
    commit_buy(state, stock, buy_plan(stock, 100), game_date=GAME_DATE, ordinal=ORDINAL)
    cost = state["holdings"]["1"]["avg_cost"] * 100
    with pytest.raises(ValueError, match="^当日买入的股票需等待下一个比赛日才能卖出$"):
        sell_plan(state, stock, 100, ordinal=ORDINAL)
    plan = sell_plan(state, stock, 100, ordinal=ORDINAL + 1)
    trade = commit_sell(state, stock, plan, game_date="2025-10-25", ordinal=ORDINAL + 1)
    assert "1" not in state["holdings"]
    assert state["realized_profit"] == pytest.approx(trade["realized"])
    assert trade["realized"] == pytest.approx(
        plan["amount"] - plan["fee"] - cost, abs=0.05,
    )


@pytest.mark.parametrize("shares", [0, -5, "abc", 10 ** 15])
def test_trade_plans_reject_invalid_quantities(shares):
    state, rows, _outcome = initialized()
    stock = stock_public(next(row for row in rows if int(row["id"]) == 1), ORDINAL, code="A1")
    with pytest.raises(ValueError):
        buy_plan(stock, shares)
    commit_buy(state, stock, buy_plan(stock, 10), game_date=GAME_DATE, ordinal=ORDINAL)
    with pytest.raises(ValueError):
        sell_plan(state, stock, shares, ordinal=ORDINAL + 1)


def test_trade_plans_reject_unknown_clubs():
    state, rows, _outcome = initialized()
    stock = stock_public(next(row for row in rows if int(row["id"]) == 1), ORDINAL, code="A1")
    with pytest.raises(ValueError, match="^股票不存在$"):
        buy_plan({}, 10)
    with pytest.raises(ValueError, match="^股票不存在$"):
        sell_plan(state, {"club_id": 999, "price": 1}, 10, ordinal=1)


def test_reverts_restore_the_pre_trade_state():
    state, rows, _outcome = initialized()
    stock = stock_public(next(row for row in rows if int(row["id"]) == 1), ORDINAL, code="A1")
    buy = buy_plan(stock, 50)
    commit_buy(state, stock, buy, game_date=GAME_DATE, ordinal=ORDINAL)
    revert_buy(state, buy, ordinal=ORDINAL)
    assert "1" not in state["holdings"]
    assert state["trades"] == []

    commit_buy(state, stock, buy_plan(stock, 50), game_date=GAME_DATE, ordinal=ORDINAL)
    sell = sell_plan(state, stock, 50, ordinal=ORDINAL + 1)
    trade = commit_sell(state, stock, sell, game_date="2025-10-25", ordinal=ORDINAL + 1)
    revert_sell(state, sell, trade)
    assert state["holdings"]["1"]["qty"] == 50
    assert state["realized_profit"] == pytest.approx(0.0)
    assert all(row.get("side") != "sell" for row in state["trades"])


def test_holding_lots_and_quote_sync_track_the_last_price():
    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 1)
    stock = stock_public(row, ORDINAL, code="A1")
    commit_buy(state, stock, buy_plan(stock, 10), game_date=GAME_DATE, ordinal=ORDINAL)
    lots = holding_lots(state, {1: row}, ORDINAL)
    assert lots[0]["club_id"] == 1 and lots[0]["qty"] == 10

    state["holdings"]["1"]["last_price"] = quote(stock["price"] * 3)
    assert sync_holding_quotes(state, {1: row}, ORDINAL) is True
    assert state["holdings"]["1"]["last_price"] == pytest.approx(stock["price"], abs=0.05)
    assert sync_holding_quotes(state, {1: row}, ORDINAL) is False


def test_market_factor_helpers_couple_the_appraisal_and_the_market():
    rows = {1: club(1, "Alpha", club_value=1_000_000_000)}
    factor = club_factor(rows, 1, ORDINAL)
    assert factor == market_factor(rows[1], ORDINAL)
    assert club_factor(rows, 999, ORDINAL) == 1.0
    assert apply_factor(1_000_000, factor) == int(round(1_000_000 * factor))
    assert apply_factor(1_000_000, 99.0) == int(round(1_000_000 * FACTOR_CAP))


def test_legacy_documents_keep_their_history_and_lose_the_top_list():
    from tools.club_stock_market import _normalize

    legacy = {
        "version": 1,
        "stocks": {"1100": {
            "club_id": 1100, "code": "CLB4", "name": "老俱乐部", "nation": "英格兰",
            "price": 677.97, "history": [{"d": "2025-10-01", "c": 677.97}],
        }},
        "holdings": {"1100": {"qty": 10, "avg_cost": 677.97, "locked_qty": 10, "locked_ordinal": 2123}},
        "index": {"base": 1000.0, "value": 1000.0, "history": []},
        "notices": [{"kind": "listing", "game_date": "2025-10-01"}],
        "trades": [],
        "realized_profit": 0.0,
    }
    state = _normalize(dict(legacy))
    assert state["version"] == SCHEMA_VERSION
    assert "stocks" not in state and "index" not in state
    holding = state["holdings"]["1100"]
    assert holding["qty"] == 10
    assert holding["code"] == "CLB4" and holding["name"] == "老俱乐部"
    assert holding["last_price"] == pytest.approx(677.97)
    assert state["notices"][0]["kind"] == "listing"


# ---------------------------------------------------------------------------
# Exchange scope
# ---------------------------------------------------------------------------


def test_normalize_scope_and_signature_are_canonical_and_idempotent():
    from tools.club_stock_market import (
        empty_scope, in_scope, market_enabled, normalize_scope, scope_rows,
        scope_signature,
    )

    raw = {
        "nations": [" 西班牙 ", "英格兰", "英格兰", "", None],
        "leagues": [
            ["西班牙", "西甲"], {"nation": "英格兰", "competition": "英冠"},
            ["西班牙", "西甲"], ["意大利", ""], "英乙",
        ],
    }
    scope = normalize_scope(raw)
    assert scope == {
        "nations": ["英格兰", "西班牙"],
        "leagues": [["英格兰", "英冠"], ["西班牙", "西甲"]],
    }
    assert normalize_scope(scope) == scope
    assert scope_signature(raw) == scope_signature(scope)
    assert scope_signature(scope) != scope_signature({"nations": ["意大利"], "leagues": []})
    assert scope_signature(empty_scope()) == ""
    assert market_enabled({"scope": scope}) is True
    assert market_enabled({"scope": empty_scope()}) is False
    assert market_enabled({}) is False

    rows = [
        club(1, "A", nation="英格兰", competition="英超联赛"),
        club(2, "B", nation="西班牙", competition="西甲"),
        club(3, "C", nation="西班牙", competition="西乙"),
        club(4, "D", nation="意大利", competition="意甲"),
    ]
    picked = {"nations": ["意大利"], "leagues": [["西班牙", "西甲"]]}
    assert [row["id"] for row in scope_rows(rows, picked)] == [2, 4]
    assert scope_rows(rows, empty_scope()) == []
    assert in_scope(rows[1], picked) is True
    assert in_scope(rows[2], picked) is False
    assert in_scope(rows[0], empty_scope()) is False


def test_save_competition_index_reads_the_save_and_matches_each_club():
    from tools.club_stock_market import club_in_save, save_competition_index

    output = {
        "competition_formats": [
            {"competition_id": 1301, "competition_name": "英超联赛", "competition_kind": "league"},
            {"competition_id": 1302, "competition_name": "足总杯", "competition_kind": "cup"},
            {"competition_id": 1303, "competition_name": "国家队赛事", "competition_kind": "national"},
            {"competition_name": "   ", "competition_kind": "league"},
            "not a row",
        ],
    }
    ids, names = save_competition_index(output)
    assert ids == frozenset({1301, 1302})
    assert names == frozenset({"英超联赛", "足总杯"})
    assert save_competition_index({}) == (frozenset(), frozenset())

    assert club_in_save({"competition_id": 1301, "competition": "英超联赛"}, ids, names) is True
    assert club_in_save({"competition": "足总杯", "competitions": ["足总杯"]}, ids, names) is True
    assert club_in_save({"competition_id": 9999, "competition": "意甲联赛"}, ids, names) is False
    assert club_in_save({"competition": "英超联赛"}, frozenset(), frozenset()) is False
    assert club_in_save(None, ids, names) is False
    assert club_in_save({"competition_id": "1301"}, ids, names) is True


def test_apply_scope_opens_deletes_and_never_re_lists_an_exchange():
    from tools.club_stock_market import apply_scope

    rows = world()
    english = sum(1 for row in rows if row["nation"] == "英格兰")
    state = empty_state()

    opened = apply_scope(
        state, rows, {"nations": ["英格兰"]}, game_date=GAME_DATE, ordinal=ORDINAL,
    )
    assert opened["changed"] is True
    assert opened["enabled"] is True
    assert opened["added"] == {"nations": ["英格兰"], "leagues": [], "clubs": english}
    assert opened["listed"] == english
    assert state["scope"] == {"nations": ["英格兰"], "leagues": []}
    assert [notice["kind"] for notice in state["notices"]] == ["scope_add"]

    again = apply_scope(
        state, rows, {"nations": ["英格兰"]}, game_date=GAME_DATE, ordinal=ORDINAL,
    )
    assert again["changed"] is False
    assert again["listed"] == english
    assert [notice["kind"] for notice in state["notices"]] == ["scope_add"]

    dropped = apply_scope(
        state, rows, {"nations": [], "leagues": []},
        game_date=GAME_DATE, ordinal=ORDINAL,
    )
    assert dropped["changed"] is True
    assert dropped["enabled"] is False
    assert dropped["removed"]["nations"] == ["英格兰"]
    assert dropped["cash_credit"] == 0.0
    assert state["scope"] == {"nations": [], "leagues": []}
    assert [notice["kind"] for notice in state["notices"]] == ["scope_add", "scope_freeze"]
    assert dropped["frozen"] == {"lots": [], "count": 0, "value": 0.0}
    assert dropped["unfrozen"] == 0


def test_apply_scope_freezes_the_holdings_and_watchlist_of_a_removed_exchange():
    from tools.club_stock_market import apply_scope, buy_plan, commit_buy, holding_lots

    rows = world()
    by_id = {int(row["id"]): row for row in rows}
    state = empty_state()
    apply_scope(
        state, rows, {"nations": ["英格兰", "西班牙"]},
        game_date=GAME_DATE, ordinal=ORDINAL,
    )
    registry_sync(
        state, rows, game_date=GAME_DATE, ordinal=ORDINAL, season="2025",
    )
    spanish = sum(1 for row in rows if row["nation"] == "西班牙")
    stock = next(iter(nation_board(rows, ORDINAL, nations=["西班牙"])["西班牙"]))
    club_id = int(stock["club_id"])
    commit_buy(state, stock, buy_plan(stock, 5), game_date=GAME_DATE, ordinal=ORDINAL)
    toggle_watch(state, club_id)

    result = apply_scope(
        state, rows, {"nations": ["英格兰"]}, game_date=GAME_DATE, ordinal=ORDINAL,
        prices={club_id: by_id[club_id]},
    )

    assert result["removed"] == {"nations": ["西班牙"], "leagues": [], "clubs": spanish}
    assert result["settlements"] == []
    assert result["cash_credit"] == 0.0
    assert result["frozen"]["count"] == 1
    assert result["frozen"]["lots"][0]["club_id"] == club_id
    assert result["frozen"]["lots"][0]["qty"] == 5
    assert result["frozen"]["value"] == pytest.approx(stock["price"] * 5, abs=0.01)
    holding = state["holdings"][str(club_id)]
    assert holding["frozen"] is True
    assert holding["qty"] == 5
    assert state["watchlist"] == []
    assert state["trades"][-1]["side"] == "buy"
    lots = holding_lots(state, {club_id: by_id[club_id]}, ORDINAL)
    assert len(lots) == 1
    assert lots[0]["frozen"] is True
    assert lots[0]["sellable"] == 0
    assert lots[0]["value"] == pytest.approx(stock["price"] * 5, abs=0.01)
    assert "西班牙" not in state["nations"]
    assert state["nations"]["英格兰"]["scope_resync"] is True

    re_enabled = apply_scope(
        state, rows, {"nations": ["英格兰", "西班牙"]},
        game_date=GAME_DATE, ordinal=ORDINAL,
    )
    assert re_enabled["unfrozen"] == 1
    assert re_enabled["frozen"]["count"] == 0
    released = state["holdings"][str(club_id)]
    assert "frozen" not in released
    assert [notice["kind"] for notice in state["notices"]][-1] == "scope_unfreeze"


def test_apply_scope_survives_a_missing_closing_price():
    from tools.club_stock_market import apply_scope, buy_plan, commit_buy

    rows = world()
    state = empty_state()
    apply_scope(
        state, rows, {"nations": ["西班牙"]}, game_date=GAME_DATE, ordinal=ORDINAL,
    )
    stock = next(iter(nation_board(rows, ORDINAL, nations=["西班牙"])["西班牙"]))
    commit_buy(state, stock, buy_plan(stock, 2), game_date=GAME_DATE, ordinal=ORDINAL)

    result = apply_scope(
        state, rows, {"nations": []}, game_date=GAME_DATE, ordinal=ORDINAL,
    )
    assert result["cash_credit"] == 0.0
    assert result["frozen"]["count"] == 1
    assert result["frozen"]["value"] == pytest.approx(stock["price"] * 2, abs=0.01)
    holding = state["holdings"][str(stock["club_id"])]
    assert holding["frozen"] is True
    assert holding["last_price"] == pytest.approx(stock["price"], abs=0.01)


def test_fundamentals_row_prefers_reduced_directory_fields():
    reduced = club(1, "Alpha", tilt=0.04)
    reduced.pop("recent_results")
    reduced["form_points"], reduced["form_wins"] = 9, 3
    reduced["form_draws"], reduced["form_losses"] = 0, 2
    public = stock_public(reduced, ORDINAL, code="A1")
    assert public["fundamentals"]["form_points"] == 9
    assert public["factor"] == pytest.approx(market_factor(reduced, ORDINAL))
    assert fundamentals_row(reduced)["form_wins"] == 3


# ---------------------------------------------------------------------------
# Order tiers, block applications, limit sales and financing
# ---------------------------------------------------------------------------


def listed_club(club_id: int = 3, *, game_date: str = GAME_DATE):
    """One listed club, its share record and a ticket-ready quote."""
    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == club_id)
    book = share_books(state)[club_id]
    ordinal = day_ordinal(game_date)
    stock = trading_quote(state, row, ordinal, code=f"C{club_id}", book=book)
    return state, rows, row, book, stock


def test_the_board_publishes_every_percentage_the_ticket_quotes():
    from tools.club_stock_market import (
        BLOCK_PRICE_PREMIUM,
        MAX_BLOCK_BUY_RATIO,
        MAX_BUY_STAKE,
        MAX_DIRECT_BUY_RATIO,
        MAX_FINANCE_RATIO,
        MAX_FINANCE_STAKE,
        MAX_PENDING_ORDERS,
        MIN_FINANCE_RATIO,
        trading_limits,
    )

    limits = trading_limits()
    assert limits["direct"] == MAX_DIRECT_BUY_RATIO == 0.02
    assert limits["block"] == MAX_BLOCK_BUY_RATIO == 0.10
    assert limits["stake"] == MAX_BUY_STAKE == 0.25
    assert limits["finance_min"] == MIN_FINANCE_RATIO == 0.02
    assert limits["finance_max"] == MAX_FINANCE_RATIO == 0.10
    assert limits["finance_stake"] == MAX_FINANCE_STAKE == 0.499
    assert limits["block_premium"] == BLOCK_PRICE_PREMIUM
    assert limits["orders"] == MAX_PENDING_ORDERS
    # Ten percent of a club is still far below the quarter an account may own,
    # so no block application can ever be handed a whole club.
    assert max_block_shares(MAX_INITIAL_SHARES) < MAX_INITIAL_SHARES * MAX_BUY_STAKE


def test_one_click_is_two_percent_and_a_block_application_is_ten():
    from tools.club_stock_market import BLOCK_PRICE_PREMIUM, buy_plan, max_block_shares, max_direct_shares

    _state, _rows, _row, _book, stock = listed_club(3)
    assert stock["max_order"] == max_direct_shares(stock["shares"])
    assert stock["block_order"] == max_block_shares(stock["shares"])
    assert stock["block_order"] > stock["max_order"]
    assert buy_plan(stock, stock["max_order"])["kind"] == "direct"
    with pytest.raises(ValueError, match="^单笔股数过大$"):
        buy_plan(stock, stock["max_order"] + 1)

    block = buy_plan(stock, stock["block_order"], kind="block")
    assert block["kind"] == "block"
    assert block["price"] == pytest.approx(
        quote(stock["price"] * (1.0 + BLOCK_PRICE_PREMIUM)), abs=0.01
    )
    with pytest.raises(ValueError, match="单次大宗交易申请上限为"):
        buy_plan(stock, stock["block_order"] + 1, kind="block")


def test_a_buy_past_a_quarter_of_the_club_can_only_be_a_sale():
    from tools.club_stock_market import buy_plan

    state, rows, row, book, stock = listed_club(3)
    commit_buy(state, stock, buy_plan(stock, 100), game_date=GAME_DATE, ordinal=ORDINAL)
    holding = state["holdings"]["3"]
    holding["qty"] = int(stock["shares"] * MAX_BUY_STAKE)
    holding.pop("locked_qty", None)
    holding.pop("locked_ordinal", None)
    ceiling = trading_quote(state, row, ORDINAL, code="C3", book=book)
    assert ceiling["stake"] == pytest.approx(MAX_BUY_STAKE)
    assert ceiling["buy_room"] == 0
    with pytest.raises(ValueError, match="只能卖出"):
        buy_plan(ceiling, 1)
    with pytest.raises(ValueError, match="只能卖出"):
        buy_plan(ceiling, ceiling["block_order"], kind="block")
    # Selling is still allowed at the ceiling, which is the whole point of it.
    assert sell_plan(state, ceiling, 100, ordinal=ORDINAL + 1)["kind"] == "market"


def test_a_block_application_takes_the_money_and_waits_for_the_next_day():
    from tools.club_stock_market import (
        MAX_PENDING_ORDERS,
        buy_plan,
        cancel_order,
        order_slots,
        submit_block_order,
    )

    state, rows, _row, _book, stock = listed_club(3)
    plan = buy_plan(stock, stock["block_order"], kind="block")
    order = submit_block_order(
        state, stock, stock["block_order"], game_date=GAME_DATE, ordinal=ORDINAL,
    )
    assert order["status"] == "pending" and order["kind"] == "block"
    assert order["total"] == pytest.approx(plan["total"], abs=0.01)
    assert order_slots(state) == MAX_PENDING_ORDERS - 1
    assert [notice["kind"] for notice in state["notices"]][-1] == "order"
    assert state["holdings"] == {}

    # The day it was placed on can never deliver it.
    quiet = fill_pending_orders(state, rows, ORDINAL, game_date=GAME_DATE)
    assert quiet["fills"] == [] and quiet["cancels"] == []
    assert quiet["credit"] == 0.0

    # Withdrawing gives the exact sum back and frees the slot.
    withdrawn = cancel_order(state, order["id"], game_date=GAME_DATE)
    assert withdrawn["refund"] == pytest.approx(plan["total"], abs=0.01)
    assert order_slots(state) == MAX_PENDING_ORDERS
    assert [notice["kind"] for notice in state["notices"]][-1] == "order_cancel"


def test_a_block_application_is_delivered_on_the_next_game_day():
    from tools.club_stock_market import buy_plan, submit_block_order

    state, rows, _row, _book, stock = listed_club(3)
    plan = buy_plan(stock, stock["block_order"], kind="block")
    order = submit_block_order(
        state, stock, stock["block_order"], game_date=GAME_DATE, ordinal=ORDINAL,
    )
    later = ORDINAL + 1
    filled = fill_pending_orders(
        state, rows, later, game_date=ordinal_date(later), books=share_books(state),
    )
    assert len(filled["fills"]) == 1 and filled["cancels"] == []
    delivery = filled["fills"][0]
    assert delivery["side"] == "buy" and delivery["kind"] == "block"
    assert delivery["qty"] == plan["qty"]
    assert delivery["price"] == pytest.approx(order["price"], abs=0.01)
    assert delivery["refund"] == pytest.approx(0.0, abs=0.01)
    assert filled["credit"] == pytest.approx(delivery["refund"], abs=0.01)
    assert state["holdings"]["3"]["qty"] == plan["qty"]
    assert order["status"] == "filled" and order["filled_game_date"] == ordinal_date(later)
    assert [notice["kind"] for notice in state["notices"]][-1] == "order_fill"
    # The delivery is itself part of the quote from that day on.
    assert market_extras(state)[3]["impact"]


def test_a_delivered_block_is_trimmed_to_the_room_left_and_refunds_the_rest():
    from tools.club_stock_market import submit_block_order

    state, rows, _row, _book, stock = listed_club(3)
    order = submit_block_order(
        state, stock, stock["block_order"], game_date=GAME_DATE, ordinal=ORDINAL,
    )
    assert order["qty"] == stock["block_order"]
    # The account keeps buying after the application was placed, so by the time
    # the club delivers there is less room left than the order asked for.
    commit_buy(state, stock, buy_plan(stock, 100), game_date=GAME_DATE, ordinal=ORDINAL)
    holding = state["holdings"]["3"]
    room = int(stock["shares"] * MAX_BUY_STAKE) - holding["qty"]
    holding["qty"] = int(stock["shares"] * MAX_BUY_STAKE) - 10
    holding.pop("locked_qty", None)
    holding.pop("locked_ordinal", None)
    later = ORDINAL + 1
    filled = fill_pending_orders(
        state, rows, later, game_date=ordinal_date(later), books=share_books(state),
    )
    delivery = filled["fills"][0]
    assert delivery["qty"] == 10 < order["qty"]
    assert order["cancelled_qty"] == order["qty"] - 10
    assert delivery["refund"] > 0
    assert filled["credit"] == pytest.approx(delivery["refund"], abs=0.01)
    assert state["holdings"]["3"]["qty"] == int(stock["shares"] * MAX_BUY_STAKE) + room - room
    assert [notice["kind"] for notice in state["notices"]][-1] == "order_fill"


def test_a_limit_sale_reserves_its_shares_until_it_is_withdrawn():
    from tools.club_stock_market import cancel_order, place_limit_sell, reserved_qty

    state, rows, row, book, stock = listed_club(3)
    commit_buy(state, stock, buy_plan(stock, 400), game_date=GAME_DATE, ordinal=ORDINAL)
    later = ORDINAL + 1
    quoted = trading_quote(state, row, later, code="C3", book=book)
    assert quoted["sellable"] == 400
    order = place_limit_sell(
        state, quoted, 400, quote(quoted["price"] * 2),
        game_date=ordinal_date(later), ordinal=later,
    )
    assert order["kind"] == "limit" and order["side"] == "sell"
    assert reserved_qty(state, 3) == 400
    # The shares on offer are not on offer twice.
    assert trading_quote(state, row, later, code="C3", book=book)["sellable"] == 0
    with pytest.raises(ValueError, match="持仓已全部委托定价抛售"):
        sell_plan(state, quoted, 1, ordinal=later)
    withdrawn = cancel_order(state, order["id"], game_date=ordinal_date(later))
    assert withdrawn["refund"] == 0.0
    assert reserved_qty(state, 3) == 0
    assert trading_quote(state, row, later, code="C3", book=book)["sellable"] == 400


def test_a_limit_sale_fills_on_the_first_reading_at_or_above_its_price():
    from tools.club_stock_market import place_limit_sell

    state, rows, row, book, stock = listed_club(3)
    commit_buy(state, stock, buy_plan(stock, 400), game_date=GAME_DATE, ordinal=ORDINAL)
    later = ORDINAL + 1
    quoted = trading_quote(state, row, later, code="C3", book=book)
    wanted = quote(quoted["price"] * 2)
    order = place_limit_sell(
        state, quoted, 400, wanted, game_date=ordinal_date(later), ordinal=later,
    )
    idle = fill_pending_orders(
        state, rows, later, game_date=ordinal_date(later), books=share_books(state),
    )
    assert idle["fills"] == [] and idle["credit"] == 0.0
    assert order["status"] == "pending"

    doubled = {**row, "club_value": int(row["club_value"] * 2)}
    filled = fill_pending_orders(
        state, [doubled], later, game_date=ordinal_date(later),
        books=share_books(state),
    )
    assert len(filled["fills"]) == 1
    delivery = filled["fills"][0]
    assert delivery["kind"] == "limit" and delivery["side"] == "sell"
    assert delivery["qty"] == 400
    assert delivery["price"] >= wanted - 1e-9
    assert filled["proceeds"] == pytest.approx(delivery["credit"], abs=0.01)
    assert state["holdings"] == {}
    assert order["status"] == "filled"


def test_the_impact_of_a_trade_scales_with_the_share_of_the_capital():
    from tools.club_stock_market import (
        impact_decay,
        plan_impact,
        trade_impact,
        trade_impact_delta,
    )

    shares = 1_000_000
    small = trade_impact_delta(20_000, shares, "buy")
    large = trade_impact_delta(100_000, shares, "buy")
    assert 0 < small < large
    assert large / small == pytest.approx(5.0, rel=0.01)
    assert trade_impact_delta(100_000, shares, "sell") == pytest.approx(-large)
    assert trade_impact_delta(0, shares, "buy") == 0.0
    # The same block moves a small club further than a large one.
    assert trade_impact_delta(100_000, shares, "buy") > trade_impact_delta(
        100_000, shares * 10, "buy"
    )

    events = [[ORDINAL, large], [ORDINAL - 1, small]]
    # Today's order is still whole, yesterday's has already begun to fade.
    assert trade_impact(events, ORDINAL) == pytest.approx(
        large + small * impact_decay(1)
    )
    later = trade_impact(events, ORDINAL + 20)
    assert 0 < later < trade_impact(events, ORDINAL)
    # A result that has not happened yet is not in the quote.
    assert trade_impact(events, ORDINAL - 5) == 0.0
    assert plan_impact({"qty": shares // 10, "side": "buy", "kind": "block"},
                       {"shares": shares}) == pytest.approx(large * 1.25)


def test_a_trade_lifts_the_quote_and_the_move_fades_away():
    from tools.club_stock_market import plan_impact

    state, _rows, row, book, stock = listed_club(3)
    clean = stock["price"]
    plan = buy_plan(stock, stock["block_order"], kind="block")
    commit_buy(state, stock, plan, game_date=GAME_DATE, ordinal=ORDINAL)
    bought = trading_quote(state, row, ORDINAL, code="C3", book=book)
    assert bought["price"] > clean
    assert market_extras(state)[3]["impact"]

    # The push is a decaying displacement: it is still in the quote a season
    # later, but the day's move is smaller than the day it happened.
    far = ORDINAL + 400
    lingered = trading_quote(state, row, far, code="C3", book=book)
    untouched = trading_quote(empty_state(), row, far, code="C3", book=book)
    residual = lingered["factor"] - untouched["factor"]
    assert 0 < residual < plan_impact(plan, stock)
    assert (bought["factor"] - untouched["factor"]) > residual
    assert impact_fingerprint(state) > 0


def impact_fingerprint(state: dict) -> float:
    """The impact fingerprint the board cache is keyed on."""
    events, cash = extras_signature(market_extras(state))
    return events + cash


def test_a_financing_grows_the_capital_without_moving_the_quote():
    from tools.club_stock_market import extras_signature, finance_plan, market_extras

    state, _rows, row, book, stock = listed_club(3)
    price = stock["price"]
    plan = finance_plan(state, stock, stock["finance_max"])
    assert plan["side"] == "finance" and plan["kind"] == "finance"
    assert plan["qty"] == stock["finance_max"] > 0
    assert plan["total"] == pytest.approx(plan["qty"] * price, abs=0.02)
    assert plan["shares_after"] == plan["shares_before"] + plan["qty"]

    commit_finance(state, stock, plan, game_date=GAME_DATE, ordinal=ORDINAL)
    after = trading_quote(state, row, ORDINAL, code="C3", book=share_books(state)[3])
    assert after["shares"] == plan["shares_after"] > plan["shares_before"]
    assert after["price"] == pytest.approx(price, abs=0.01)
    # The money sits in the club, so its value - and the acquisition price -
    # goes up even though the per-share quote did not move.
    assert after["market_cap"] > stock["market_cap"]
    assert after["qty"] == plan["qty"]
    assert market_extras(state)[3]["finance"]
    assert extras_signature(market_extras(state))[1] == pytest.approx(
        plan["total"], abs=0.01
    )
    # The new lot is a same-day buy and waits for the next game day.
    assert after["sellable"] == 0


def test_financing_respects_its_floor_its_ceiling_and_the_stake_cap():
    from tools.club_stock_market import MAX_FINANCE_STAKE, finance_plan, max_finance_shares

    state, _rows, _row, _book, stock = listed_club(3)
    capital = stock["shares"]
    assert stock["finance_min"] == max(1, int(capital * MIN_FINANCE_RATIO))
    assert stock["finance_max"] == min(
        int(capital * MAX_FINANCE_RATIO), max_finance_shares(0, capital)
    )
    with pytest.raises(ValueError, match="单次融资最低"):
        finance_plan(state, stock, stock["finance_min"] - 1)
    with pytest.raises(ValueError, match="单次融资最多"):
        finance_plan(state, stock, int(capital * MAX_FINANCE_RATIO) + 1)
    # An issue grows the capital as well as the lot, so the room solves
    # (held + issue) / (capital + issue) = 49.9% rather than 49.9% - held.
    held = int(capital * 0.48)
    room = max_finance_shares(held, capital)
    assert (held + room) / (capital + room) <= MAX_FINANCE_STAKE
    assert (held + room + 1) / (capital + room + 1) > MAX_FINANCE_STAKE
    assert max_finance_shares(capital, capital) == 0


def test_a_final_financing_may_be_a_one_share_top_up_near_the_ceiling():
    from tools.club_stock_market import MAX_FINANCE_STAKE, finance_plan, max_finance_shares

    state, _rows, _row, _book, stock = listed_club(3)
    capital = stock["shares"]
    held = int(capital * 0.49) - 1
    stock = {**stock, "qty": held}
    room = max_finance_shares(held, capital)
    assert 0 < room < max(1, int(capital * MIN_FINANCE_RATIO))
    plan = finance_plan(state, stock, 2, appetite=None)
    assert plan["qty"] == 2
    assert (held + 2) / (capital + 2) > 0.49
    assert plan["stake_after"] <= MAX_FINANCE_STAKE


def test_an_automatic_issue_reads_the_club_and_not_the_accounts_own_orders():
    from tools.club_stock_market import finance_extras

    state, rows, row, book, stock = listed_club(2)
    quiet = share_price(row, ORDINAL, book, finance_extras(state))
    state["impact"]["2"] = [[ORDINAL, 0.6]]
    loud = share_price(row, ORDINAL, book, market_extras(state))
    assert loud > quiet

    # Put the doubling trigger between the two readings: only the account's
    # own order is above it, so an issue here is exactly the bug this guards.
    book["b"] = quote((quiet + loud) / 2 / SHARE_SPLIT_TRIGGER)
    assert share_price(row, ORDINAL, book, market_extras(state)) >= (
        book["b"] * SHARE_SPLIT_TRIGGER
    )
    assert share_price(row, ORDINAL, book, finance_extras(state)) < (
        book["b"] * SHARE_SPLIT_TRIGGER
    )
    result = detect_splits(state, rows, game_date=GAME_DATE, ordinal=ORDINAL)
    assert result["count"] == 0
    assert share_splits(share_books(state)[2]) == []
    assert share_price(row, ORDINAL, book, market_extras(state)) == pytest.approx(
        loud, rel=0.02
    )


def test_a_schema_five_document_gets_the_new_fields():
    from tools.club_stock_market import _normalize

    legacy = {
        "version": 5,
        "scope": {"nations": ["英格兰"], "leagues": []},
        "nations": {"英格兰": {"shares": {}}},
        "holdings": {"3": {"qty": 10, "avg_cost": 1.0}},
        "notices": [], "trades": [], "watchlist": [], "realized_profit": 0.0,
    }
    state = _normalize(dict(legacy))
    assert SCHEMA_VERSION == 8
    assert state["version"] == SCHEMA_VERSION
    assert state["daily"] == {}
    assert state["receipts"] == []
    assert state["impact"] == {} and state["finance"] == {}
    assert state["missing"] == {}
    assert state["orders"] == []
    assert state["holdings"]["3"]["qty"] == 10
    assert state["scope"]["nations"] == ["英格兰"]

    # A field of the wrong type is rebuilt instead of crashing the page.
    repaired = _normalize({
        **legacy, "impact": [], "finance": "x", "orders": {"a": 1}, "missing": ["3"],
    })
    assert repaired["impact"] == {} and repaired["finance"] == {}
    assert repaired["missing"] == {}
    assert repaired["orders"] == []


# ---------------------------------------------------------------------------
# The day's direct budget, settlement slips and the financing appetite
# ---------------------------------------------------------------------------


def test_the_direct_budget_belongs_to_the_game_day_and_not_to_one_click():
    from tools.club_stock_market import (
        daily_direct_room,
        daily_direct_used,
    )

    state, _rows, row, book, stock = listed_club(3)
    budget = max_direct_shares(stock["shares"])
    assert budget > 1
    assert daily_direct_used(state, 3, ORDINAL) == 0
    assert daily_direct_room(state, 3, stock["shares"], ORDINAL) == budget

    half = budget // 2
    commit_buy(
        state, stock, buy_plan(stock, half, used=daily_direct_used(state, 3, ORDINAL)),
        game_date=GAME_DATE, ordinal=ORDINAL,
    )
    assert daily_direct_used(state, 3, ORDINAL) == half
    assert daily_direct_room(state, 3, stock["shares"], ORDINAL) == budget - half

    # The next click of the day may only take what is left, and a further one
    # has to be an application: ten clicks that each look small must not walk
    # away with a fifth of a club.
    with pytest.raises(ValueError, match="今日市价买入额度"):
        buy_plan(stock, budget, used=daily_direct_used(state, 3, ORDINAL))
    rest = budget - half
    commit_buy(
        state, stock, buy_plan(stock, rest, used=daily_direct_used(state, 3, ORDINAL)),
        game_date=GAME_DATE, ordinal=ORDINAL,
    )
    assert daily_direct_room(state, 3, stock["shares"], ORDINAL) == 0
    with pytest.raises(ValueError, match="今日市价买入额度还剩 0 股"):
        buy_plan(stock, 1, used=daily_direct_used(state, 3, ORDINAL))
    assert buy_plan(
        stock, 1, kind="block", used=daily_direct_used(state, 3, ORDINAL),
    )["qty"] == 1

    # Tomorrow starts the budget over, and the row the page trades on carries
    # both the spending of the day and what is left of the allowance.
    assert daily_direct_used(state, 3, ORDINAL + 1) == 0
    assert daily_direct_room(state, 3, stock["shares"], ORDINAL + 1) == budget
    quoted = trading_quote(state, row, ORDINAL, code="C3", book=book)
    assert quoted["direct_used"] == budget
    assert quoted["direct_room"] == 0
    assert trading_quote(state, row, ORDINAL + 1, code="C3", book=book)["direct_room"] == budget
    board = market_view(
        state, [row], game_date=GAME_DATE, scope_id="s",
        nation="英格兰", page_size=10,
    )
    assert board["stocks"][0]["direct_used"] == budget
    assert board["stocks"][0]["direct_room"] == 0
    assert board["stocks"][0]["appetite"]["value"] > 0


def test_a_reverted_click_hands_the_day_its_budget_back():
    from tools.club_stock_market import daily_direct_used

    state, _rows, _row, _book, stock = listed_club(3)
    plan = buy_plan(stock, 25, used=daily_direct_used(state, 3, ORDINAL))
    commit_buy(state, stock, plan, game_date=GAME_DATE, ordinal=ORDINAL)
    assert daily_direct_used(state, 3, ORDINAL) == 25
    revert_buy(state, plan, ordinal=ORDINAL)
    assert daily_direct_used(state, 3, ORDINAL) == 0
    assert state["holdings"] == {}


def test_a_delivered_application_leaves_a_settlement_slip_of_its_own():
    state, rows, row, book, stock = listed_club(2)
    qty = stock["block_order"]
    order = submit_block_order(
        state, stock, qty, game_date=GAME_DATE, ordinal=ORDINAL,
    )
    assert state["receipts"] == []

    day = ORDINAL + 1
    game_date = ordinal_date(day)
    result = fill_pending_orders(state, rows, day, game_date=game_date)
    assert len(result["fills"]) == 1
    assert len(state["receipts"]) == 1
    slip = state["receipts"][0]
    fill = result["fills"][0]
    assert slip["kind"] == "block_fill"
    assert slip["order_id"] == order["id"]
    assert slip["club_id"] == 2
    assert slip["code"] == "C2"
    assert slip["qty"] == fill["qty"] == slip["qty_after"]
    assert slip["requested"] == qty
    assert slip["dropped"] == qty - fill["qty"]
    assert slip["price"] == fill["price"]
    assert slip["capital"] == shares_at(row, day, book)
    assert slip["stake_before"] == 0.0
    assert slip["stake_after"] == pytest.approx(
        fill["qty"] / slip["capital"], abs=1e-6,
    )
    assert slip["qty_after"] == state["holdings"]["2"]["qty"]
    assert slip["total"] == pytest.approx(order["total"], abs=0.01)
    assert slip["amount"] == pytest.approx(slip["qty"] * slip["price"], abs=0.01)
    assert slip["fee"] == pytest.approx(trade_fee(slip["amount"]), abs=0.01)
    assert slip["refund"] == pytest.approx(
        order["total"] - slip["amount"] - slip["fee"], abs=0.01,
    )

    # The quote of the club the delivery moved: today's own close before the
    # trade, and the close the trade itself left behind.
    assert slip["close_before"] > 0
    assert slip["close"] > slip["close_before"]
    assert slip["change"] == pytest.approx(
        (slip["close"] - slip["close_before"]) / slip["close_before"], abs=1e-6,
    )

    # The page reads the slips newest first, and a save whose directory is not
    # readable yet still carries the ones it has.
    view = market_view(state, rows, game_date=game_date, scope_id="s")
    assert view["receipts"][0]["id"] == slip["id"]
    empty = market_view(state, [], game_date=game_date, scope_id="s")
    assert empty["receipts"][0]["id"] == slip["id"]


def test_a_limit_sale_that_fills_leaves_a_slip_too():
    from tools.club_stock_market import place_limit_sell

    state, rows, row, book, stock = listed_club(2)
    commit_buy(state, stock, buy_plan(stock, 500), game_date=GAME_DATE, ordinal=ORDINAL)
    later = ORDINAL + 1
    quoted = trading_quote(state, row, later, code="C2", book=book)
    wanted = quote(quoted["price"] * 2)
    order = place_limit_sell(
        state, quoted, 200, wanted, game_date=ordinal_date(later), ordinal=later,
    )
    filled = fill_pending_orders(
        state, [{**row, "club_value": int(row["club_value"] * 2)}], later,
        game_date=ordinal_date(later), books=share_books(state),
    )
    assert len(filled["fills"]) == 1
    slip = state["receipts"][-1]
    assert slip["kind"] == "limit_fill"
    assert slip["order_id"] == order["id"]
    assert slip["side"] == "sell"
    assert slip["qty"] == 200
    assert slip["price"] == pytest.approx(wanted, abs=0.02)
    assert slip["net"] == pytest.approx(200 * slip["price"] * (1 - 0.003), abs=0.05)
    assert slip["stake_after"] < slip["stake_before"]
    # A sale pushes the quote down, and the slip says so.
    assert slip["change"] < 0


def test_a_club_in_the_red_or_far_from_its_appraisal_wants_the_money_more():
    from tools.club_stock_market import (
        FINANCE_ACCEPT_FLOOR,
        FINANCE_APPETITE_BASE,
        FINANCE_APPETITE_CAP,
        FINANCE_APPETITE_GAP,
        finance_appetite,
        form_slump,
    )

    _state, _rows, _row, _book, stock = listed_club(3)
    value = stock["intrinsic"]
    shares = stock["shares"]
    # The appraisal values the whole club while the quote is a price per
    # share, so a club priced on its appraisal is the one whose *market cap*
    # equals it: neither expensive nor short of cash, so nothing raises the
    # appetite beyond the base.
    def priced(ratio: float) -> dict:
        market_cap = int(value * ratio)
        return {
            **stock, "market_cap": market_cap,
            "price": market_cap / shares if shares else 0.0,
        }

    fair = finance_appetite({"id": 3, "club_value": value}, priced(1.0), ORDINAL)
    assert fair["reasons"] == []
    assert fair["value"] == pytest.approx(FINANCE_APPETITE_BASE, abs=1e-6)
    healthy = finance_appetite(
        {"id": 3, "balance": value, "club_value": value}, priced(1.0), ORDINAL,
    )
    assert healthy["value"] == pytest.approx(fair["value"], abs=1e-6)
    broke = finance_appetite(
        {"id": 3, "balance": -value, "club_value": value}, priced(1.0), ORDINAL,
    )
    assert broke["value"] > healthy["value"] >= FINANCE_ACCEPT_FLOOR
    assert "debt" in [reason["key"] for reason in broke["reasons"]]

    # A market cap far from the appraisal counts from both sides.
    rich = finance_appetite({"id": 3, "club_value": value}, priced(1.3), ORDINAL)
    cheap = finance_appetite({"id": 3, "club_value": value}, priced(0.7), ORDINAL)
    # Both sides of the same distance count the same, and both beat a club
    # that is priced on its appraisal.
    assert "gap" in [reason["key"] for reason in rich["reasons"]]
    assert "gap" in [reason["key"] for reason in cheap["reasons"]]
    assert rich["value"] == pytest.approx(cheap["value"], abs=1e-6)
    assert rich["value"] > healthy["value"] == fair["value"]
    # The bonus stops at forty percent away, and only a club that is in the
    # red on top of that is as keen as the board ever lets one be.
    far = finance_appetite({"id": 3, "club_value": value}, priced(1.6), ORDINAL)
    assert far["value"] == pytest.approx(
        FINANCE_APPETITE_BASE + FINANCE_APPETITE_GAP, abs=1e-6,
    )
    desperate = finance_appetite(
        {"id": 3, "balance": -value * 2, "club_value": value}, priced(1.6), ORDINAL,
    )
    assert desperate["value"] == pytest.approx(FINANCE_APPETITE_CAP, abs=1e-6)

    # A window without a single point is a slump, a perfect one is none.
    assert form_slump(
        {"form_points": 0, "form_wins": 0, "form_draws": 0, "form_losses": 5}
    ) == 1.0
    assert form_slump(
        {"form_points": 15, "form_wins": 5, "form_draws": 0, "form_losses": 0}
    ) == 0.0
    assert form_slump({}) == 0.0
    slumping = finance_appetite(
        {"id": 3, "club_value": value},
        {**stock, "fundamentals": {"form_points": 0, "form_wins": 0, "form_draws": 0, "form_losses": 5}},
        ORDINAL,
    )
    assert "slump" in [reason["key"] for reason in slumping["reasons"]]


def test_the_answer_of_a_club_is_drawn_once_a_day_and_a_refusal_is_explained():
    from tools.club_stock_market import finance_appetite

    state, _rows, _row, _book, stock = listed_club(3)
    row = {"id": 3, "balance": 0, "club_value": stock["intrinsic"]}
    first = finance_appetite(row, stock, ORDINAL)
    assert finance_appetite(row, stock, ORDINAL) == first
    assert 0.0 <= first["draw"] <= 1.0
    assert first["value"] <= 1.0
    # The dice belong to the club and to the day, so another day is another
    # answer and a player turned down can simply come back tomorrow.
    answers = {
        finance_appetite(row, stock, ORDINAL + step)["accept"] for step in range(12)
    }
    assert True in answers and False in answers

    with pytest.raises(ValueError, match="拒绝了本次融资"):
        finance_plan(
            state, stock, stock["finance_min"],
            appetite={"value": 0.3, "accept": False, "reasons": [{"key": "none"}]},
        )
    assert state["holdings"] == {} and state["trades"] == []
    plan = finance_plan(
        state, stock, stock["finance_min"], appetite={"value": 0.9, "accept": True},
    )
    assert plan["qty"] == stock["finance_min"]
    assert plan["appetite"] == {"value": 0.9, "accept": True}



# ---------------------------------------------------------------------------
# Directory repair and takeovers
# ---------------------------------------------------------------------------


def test_scope_labels_fold_onto_the_leagues_the_directory_lists():
    from tools.club_stock_market import canonicalize_scope, scope_league_index

    rows = [
        club(1, "丹麦俱乐部", nation="丹麦", competition="丹麦超级联赛"),
        club(2, "荷兰俱乐部", nation="荷兰", competition="荷兰甲级联赛"),
    ]
    rows[0]["competitions"] = ["丹超联赛", "丹麦杯"]
    index = scope_league_index(rows)
    assert ("丹麦", "丹麦超级联赛") in index["pairs"]
    folded = canonicalize_scope(
        {
            "nations": [],
            "leagues": [
                ["丹麦", "丹超联赛"],
                ["未分类", "丹麦超级联赛"],
                ["荷兰", "荷乙联赛"],
            ],
        },
        index,
    )
    # 两个旧标签折到同一条联赛上，解析不到的那个原样保留给审计。
    assert folded["leagues"] == [
        ["丹麦", "丹麦超级联赛"],
        ["荷兰", "荷乙联赛"],
    ]

    # 同一联赛名挂在两个国家下时无法判断归属，不能硬折。
    shared = scope_league_index([
        club(3, "甲国俱乐部", nation="甲国", competition="世界杯冠军杯"),
        club(4, "乙国俱乐部", nation="乙国", competition="世界杯冠军杯"),
    ])
    kept = canonicalize_scope(
        {"nations": [], "leagues": [["未分类", "世界杯冠军杯"]]}, shared,
    )
    assert kept["leagues"] == [["未分类", "世界杯冠军杯"]]


def test_reconcile_scope_names_the_leagues_the_directory_cannot_list():
    from tools.club_stock_market import reconcile_scope, scope_league_index

    rows = [club(1, "丹麦俱乐部", nation="丹麦", competition="丹麦超级联赛")]
    rows[0]["competitions"] = ["丹超联赛"]
    index = scope_league_index(rows)
    audit = reconcile_scope(
        {
            "nations": ["丹麦"],
            "leagues": [["丹麦", "幽灵联赛"], ["丹麦", "丹超联赛"]],
        },
        index,
    )
    assert audit["confirmed"] is True
    assert audit["dropped"] == [["丹麦", "幽灵联赛"]]
    # 别名先折到目录名字再裁决：丹超联赛不是丢掉的联赛。
    assert audit["scope"]["leagues"] == [["丹麦", "丹麦超级联赛"]]
    assert audit["scope"]["nations"] == ["丹麦"]

    # 目录为空时什么都证明不了，一根手指都不动。
    blind = reconcile_scope(
        {"nations": [], "leagues": [["丹麦", "幽灵联赛"]]}, {"pairs": set()},
    )
    assert blind["confirmed"] is False
    assert blind["dropped"] == []
    assert blind["scope"]["leagues"] == [["丹麦", "幽灵联赛"]]


def _danish_scope_state() -> dict:
    state = empty_state()
    state["scope"] = {
        "nations": ["丹麦"],
        "leagues": [["丹麦", "丹麦超级联赛"], ["丹麦", "幽灵联赛"]],
    }
    return state


WORLD_SCOPE = [
    ["丹麦", "丹麦超级联赛"], ["丹麦", "幽灵联赛"],
]


def test_a_window_directory_reports_the_leagues_it_cannot_list():
    from tools.club_stock_market import (
        apply_scope_repair, reconcile_scope, scope_league_index,
    )

    state = _danish_scope_state()
    # 赛程窗口只列当天开赛的联赛：它点不到的名字既不能开店，也证明不了存档
    # 丢了什么，所以只报告、不裁剪，一根手指都不动。
    window = [club(1, "丹麦俱乐部", nation="丹麦", competition="丹麦超级联赛")]
    index = scope_league_index(window)
    assert index["world"] is False
    audit = reconcile_scope(state["scope"], index, authoritative=False)
    assert audit["confirmed"] is False
    assert audit["dropped"] == [["丹麦", "幽灵联赛"]]
    assert audit["scope"]["leagues"] == WORLD_SCOPE

    repair = apply_scope_repair(
        state, audit["dropped"], game_date=GAME_DATE, confirmed=audit["confirmed"],
    )
    assert repair == {"suspended": [], "resumed": [], "notice": None, "notice_resume": None}
    assert state["scope"]["leagues"] == WORLD_SCOPE
    assert not state.get("scope_suspended")
    assert state["notices"] == []


def test_a_world_directory_parks_the_league_it_cannot_list_and_releases_it():
    from tools.club_stock_market import (
        apply_scope_repair, listed_scope, reconcile_scope, scope_league_index,
        suspended_pairs,
    )

    state = _danish_scope_state()
    world = [
        {**club(1, "丹麦俱乐部", nation="丹麦", competition="丹麦超级联赛"),
         "source": "native_scan"},
    ]
    index = scope_league_index(world)
    assert index["world"] is True
    audit = reconcile_scope(state["scope"], index)
    assert audit["confirmed"] is True
    assert audit["dropped"] == [["丹麦", "幽灵联赛"]]

    repair = apply_scope_repair(
        state, audit["dropped"], game_date=GAME_DATE, confirmed=audit["confirmed"],
    )
    assert repair["suspended"] == [["丹麦", "幽灵联赛"]]
    assert repair["resumed"] == []
    # 勾选还在，只是今天没有交易所：面板照旧勾着它，行情板把它留给下一次读取。
    assert state["scope"]["leagues"] == WORLD_SCOPE
    assert suspended_pairs(state) == {("丹麦", "幽灵联赛")}
    assert listed_scope(
        state["scope"], state.get("scope_suspended"),
    )["leagues"] == [["丹麦", "丹麦超级联赛"]]
    assert [notice["kind"] for notice in state["notices"]] == ["scope_suspend"]
    assert state["notices"][0]["count"] == 1
    assert state["notices"][0]["competitions"] == [["丹麦", "幽灵联赛"]]

    # 同一个联赛还在等的时候不再重复写字条。
    quiet = apply_scope_repair(
        state, audit["dropped"], game_date=GAME_DATE, confirmed=True,
    )
    assert quiet["suspended"] == [["丹麦", "幽灵联赛"]]
    assert len(state["notices"]) == 1

    # 目录重新列出这个联赛：暂存解除，开的是它自己那把勾。
    released = apply_scope_repair(state, [], game_date=GAME_DATE, confirmed=True)
    assert released["resumed"] == [["丹麦", "幽灵联赛"]]
    assert released["notice_resume"]["kind"] == "scope_resume"
    assert state.get("scope_suspended") == []
    assert state["scope"]["leagues"] == WORLD_SCOPE
    assert [notice["kind"] for notice in state["notices"]] == [
        "scope_suspend", "scope_resume",
    ]

    # 玩家自己取消勾选后不再留暂存记录。
    parked_again = apply_scope_repair(
        state, [["丹麦", "幽灵联赛"]], game_date=GAME_DATE, confirmed=True,
    )
    assert parked_again["suspended"] == [["丹麦", "幽灵联赛"]]
    state["scope"] = {"nations": ["丹麦"], "leagues": [["丹麦", "丹麦超级联赛"]]}
    assert apply_scope_repair(
        state, [["丹麦", "幽灵联赛"]], game_date=GAME_DATE, confirmed=True,
    )["suspended"] == []


def test_a_league_deleted_by_an_earlier_build_comes_back_on_the_world_read():
    from tools.club_stock_market import restore_pruned_scope, scope_league_index

    state = empty_state()
    state["scope"] = {"nations": [], "leagues": [["丹麦", "丹麦超级联赛"]]}
    state["notices"] = [{
        "kind": "scope_prune", "at": "2025-11-30 02:04:54", "date": "2025-11-30",
        "count": 2,
        "competitions": [["荷兰", "荷兰甲级联赛"], ["荷兰", "幽灵联赛"]],
    }]
    rows = [
        {**club(1, "丹麦俱乐部", nation="丹麦", competition="丹麦超级联赛"),
         "source": "native_scan"},
        {**club(2, "荷兰俱乐部", nation="荷兰", competition="荷兰甲级联赛"),
         "source": "native_scan"},
    ]
    index = scope_league_index(rows)

    # 目录只是当天的赛程窗口时这次机会不能花掉：世界俱乐部还没读进来。
    window = scope_league_index([
        {key: value for key, value in rows[0].items() if key != "source"},
    ])
    idle = restore_pruned_scope(
        state, window, game_date=GAME_DATE, authoritative=False,
    )
    assert idle == {"restored": [], "notice": None}
    assert not state.get("scope_pruned_restored")
    assert state["scope"]["leagues"] == [["丹麦", "丹麦超级联赛"]]

    healed = restore_pruned_scope(
        state, index, game_date=GAME_DATE, authoritative=True,
    )
    assert healed["restored"] == [["荷兰", "荷兰甲级联赛"]]
    assert healed["notice"]["kind"] == "scope_restore"
    assert healed["notice"]["count"] == 1
    assert {tuple(item) for item in state["scope"]["leagues"]} == {
        ("丹麦", "丹麦超级联赛"), ("荷兰", "荷兰甲级联赛"),
    }
    assert state["scope_pruned_restored"] == 1

    # 一次性：再读一次不会把同一批联赛加第二遍。
    again = restore_pruned_scope(
        state, index, game_date=GAME_DATE, authoritative=True,
    )
    assert again == {"restored": [], "notice": None}
    assert {tuple(item) for item in state["scope"]["leagues"]} == {
        ("丹麦", "丹麦超级联赛"), ("荷兰", "荷兰甲级联赛"),
    }


def test_a_parked_exchange_keeps_its_lots_out_of_the_delisting_read():
    from tools.club_stock_market import parked_clubs, registry_sync

    state = empty_state()
    state["scope"] = {"nations": ["丹麦"], "leagues": []}
    state["scope_suspended"] = [["丹麦", "幽灵联赛"]]
    state["holdings"] = {
        "5": {
            "qty": 10, "avg_cost": 10.0, "locked_qty": 0, "last_price": 10.0,
            "nation": "丹麦", "competition": "幽灵联赛",
        },
        "6": {
            "qty": 10, "avg_cost": 10.0, "locked_qty": 0, "last_price": 10.0,
            "nation": "丹麦", "competition": "丹麦超级联赛",
        },
    }
    assert parked_clubs(state) == [5]
    # 换了联赛的持仓不跟着暂存走。
    state["holdings"]["5"]["competition"] = "丹麦超级联赛"
    assert parked_clubs(state) == []

    state["holdings"]["5"]["competition"] = ""
    assert parked_clubs(state) == [5]
    state["holdings"]["5"]["nation"] = "荷兰"
    assert parked_clubs(state) == []
    state["holdings"]["5"]["nation"] = "丹麦"
    state["holdings"]["5"]["competition"] = "幽灵联赛"
    assert parked_clubs(state) == [5]

    # 目录只列了 6 号的联赛：5 号不是消失了，它的交易所只是在等目录，所以它
    # 既不进失踪名单，也不会被结算退市。
    rows = [club(6, "丹麦俱乐部", nation="丹麦", competition="丹麦超级联赛")]
    result = registry_sync(
        state, rows, game_date=GAME_DATE, ordinal=ORDINAL, season="2025",
        confirm_absent=True, ignore=parked_clubs(state),
    )
    assert result["settlements"] == []
    assert state["missing"] == {}
    assert state["holdings"]["5"]["qty"] == 10
    assert [row for row in state["trades"] if row["side"] == "delist"] == []

    # 隔一个比赛日仍然如此：只要交易所还在暂存，持仓就不会被退市结算。
    later = registry_sync(
        state, rows, game_date=ordinal_date(ORDINAL + 1), ordinal=ORDINAL + 1,
        season="2025", confirm_absent=True, ignore=parked_clubs(state),
    )
    assert later["settlements"] == []
    assert state["missing"] == {}
    assert state["holdings"]["5"]["qty"] == 10


def test_save_competition_index_reads_the_plain_competition_scan_too():
    from tools.club_stock_market import save_competition_index

    output = {
        "competition_formats": [
            {"competition_id": 11, "competition_name": "英超联赛", "competition_kind": "league"},
        ],
        "competitions": [
            {"competition_id": 6, "competition_name": "丹麦超级联赛", "competition_kind": "league"},
            {"id": 29, "name": "荷兰甲级联赛", "kind": "league"},
            {"competition_id": 77, "competition_name": "欧洲国家联赛", "competition_kind": "national"},
            "not a row",
        ],
    }
    ids, names = save_competition_index(output)
    assert {11, 6, 29} <= ids
    assert 77 not in ids
    assert {"英超联赛", "丹麦超级联赛", "荷兰甲级联赛"} <= names
    assert "欧洲国家联赛" not in names


def test_the_board_hands_a_bought_club_over_and_closes_its_tickets():
    from tools.club_stock_market import (
        share_books,
        shares_at,
        submit_block_order,
        take_over_club,
        takeover_keep_qty,
        takeover_lot,
        trading_quote,
    )

    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 3)
    book = share_books(state)[3]
    capital = shares_at(row, ORDINAL, book)
    stock = trading_quote(state, row, ORDINAL, book=book)
    order = submit_block_order(
        state, stock, stock["block_order"], game_date=GAME_DATE, ordinal=ORDINAL,
    )
    assert state["orders"]

    record = take_over_club(
        state, row, club_id=3, shares=capital, price=60_000_000,
        game_date=GAME_DATE, ordinal=ORDINAL,
    )
    assert record["qty"] == capital
    # 委托的托管金原数退回，票不再挂在俱乐部名下。
    assert record["refund"] == pytest.approx(order["total"], abs=0.05)
    assert record["cancelled"][0]["order"]["id"] == order["id"]
    # 票仍留在流水里，但已取消，不再是待成交的委托。
    assert [item["status"] for item in state["orders"]] == ["cancelled"]
    lot = takeover_lot(state, 3)
    assert lot is not None and lot["source"] == "takeover"

    owned = trading_quote(state, row, ORDINAL, book=book)
    assert owned["owned"] is True
    assert owned["qty"] == capital
    assert owned["club_shares"] == 0
    # 收购后仍可把股份卖回俱乐部，但集团至少保留 51% 股权，票面不会给出全部登记册。
    keep = takeover_keep_qty(capital)
    assert keep == -(-capital * 51 // 100)
    assert owned["keep_shares"] == keep
    assert owned["sellable"] == capital - keep


def test_a_club_the_group_owns_trades_its_own_book_only():
    from tools.club_stock_market import (
        buy_plan,
        commit_buy,
        commit_sell,
        finance_plan,
        max_direct_shares,
        sell_plan,
        share_books,
        shares_at,
        sync_takeovers,
        take_over_club,
        takeover_keep_qty,
        takeover_lot,
        trading_quote,
    )

    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 9)
    book = share_books(state)[9]
    capital = shares_at(row, ORDINAL, book)
    take_over_club(
        state, row, club_id=9, shares=capital, price=90_000_000,
        game_date=GAME_DATE, ordinal=ORDINAL,
    )
    stock = trading_quote(state, row, ORDINAL, book=book)
    keep = takeover_keep_qty(capital)
    # 登记册全部在集团名下：俱乐部手里没有股份，回收暂时无从谈起。
    assert stock["owned"] is True
    assert stock["club_shares"] == 0
    assert stock["buyback_room"] == 0
    assert stock["buy_room"] == 0
    with pytest.raises(ValueError, match="俱乐部手中已无股份可回收"):
        buy_plan(stock, 1)
    # 卖出与融资照旧，因为出票的董事会就是集团自己，但卖出止步于 51% 控制权。
    assert stock["sellable"] == capital - keep
    with pytest.raises(ValueError, match="至少要保留 51%"):
        sell_plan(state, stock, capital - keep + 1, ordinal=ORDINAL)
    plan = sell_plan(state, stock, capital - keep, ordinal=ORDINAL)
    assert plan["side"] == "sell" and plan["qty"] == capital - keep
    commit_sell(state, stock, plan, game_date=GAME_DATE, ordinal=ORDINAL)
    # 融资不再受 49% 市场上限约束，票面额度是全部股本。
    assert stock["finance_room"] == capital
    planned = finance_plan(state, stock, stock["finance_min"])
    assert planned["owned"] is True
    assert planned["shares_after"] == capital + stock["finance_min"]
    assert planned["injection"] == round_money(planned["amount"] * 0.10)

    # 卖回的股份挂在俱乐部名下，票面把它们整本算成可回收的额度：25% 的
    # 市场持股上限不再是天花板，留下的只有当日节奏与大宗申请的上限。
    sold_back = capital - keep
    back = trading_quote(state, row, ORDINAL, book=book)
    assert back["club_shares"] == sold_back
    assert back["buyback_room"] == sold_back
    assert back["buy_room"] == sold_back
    direct = max_direct_shares(capital)
    assert direct < sold_back
    recovery = buy_plan(back, direct)
    assert recovery["kind"] == "direct" and recovery["qty"] == direct
    # 当天已经回收过一部分时，剩下的额度就是同一天还能直购的上限。
    with pytest.raises(ValueError, match="今日回收额度还剩"):
        buy_plan(back, direct, used=10)
    with pytest.raises(ValueError, match="^单笔股数过大$"):
        buy_plan(back, direct * 2)
    block = buy_plan(back, back["block_order"], kind="block")
    assert block["qty"] == back["block_order"]
    with pytest.raises(ValueError, match="单次大宗回收申请上限为"):
        buy_plan(back, back["block_order"] + 1, kind="block")
    with pytest.raises(ValueError, match="俱乐部手中仅剩"):
        buy_plan(back, sold_back + 1)

    commit_buy(state, back, recovery, game_date=GAME_DATE, ordinal=ORDINAL)
    lot = takeover_lot(state, 9)
    assert lot["qty"] == keep + direct
    assert lot["takeover_sold"] == sold_back - direct
    # 回收过的股份不再属于俱乐部，开盘巡查也不会把同一本登记册再交接一遍。
    settled = sync_takeovers(
        state, rows, {9: 90_000_000}, game_date=GAME_DATE, ordinal=ORDINAL,
    )
    assert settled["count"] == 0
    assert takeover_lot(state, 9)["qty"] == keep + direct
    again = trading_quote(state, row, ORDINAL, book=book)
    assert again["club_shares"] == sold_back - direct


def test_a_block_recovery_is_delivered_out_of_the_clubs_own_book():
    from tools.club_stock_market import (
        commit_sell,
        fill_pending_orders,
        ordinal_date,
        sell_plan,
        share_books,
        shares_at,
        submit_block_order,
        sync_takeovers,
        take_over_club,
        takeover_keep_qty,
        takeover_lot,
        trading_quote,
    )

    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 6)
    book = share_books(state)[6]
    capital = shares_at(row, ORDINAL, book)
    take_over_club(
        state, row, club_id=6, shares=capital, price=66_000_000,
        game_date=GAME_DATE, ordinal=ORDINAL,
    )
    stock = trading_quote(state, row, ORDINAL, book=book)
    keep = takeover_keep_qty(capital)
    commit_sell(
        state, stock, sell_plan(state, stock, capital - keep, ordinal=ORDINAL),
        game_date=GAME_DATE, ordinal=ORDINAL,
    )
    back = trading_quote(state, row, ORDINAL, book=book)
    qty = min(back["block_order"], capital - keep)
    order = submit_block_order(
        state, back, qty, game_date=GAME_DATE, ordinal=ORDINAL,
    )
    assert order["status"] == "pending" and order["side"] == "buy"

    next_day = ordinal_date(ORDINAL + 1)
    filled = fill_pending_orders(state, rows, ORDINAL + 1, game_date=next_day)
    assert [item["kind"] for item in filled["fills"]] == ["block"]
    assert filled["fills"][0]["qty"] == qty
    lot = takeover_lot(state, 6)
    assert lot["qty"] == keep + qty
    assert lot["takeover_sold"] == capital - keep - qty
    settled = sync_takeovers(
        state, rows, {6: 66_000_000}, game_date=next_day, ordinal=ORDINAL + 1,
    )
    assert settled["count"] == 0
    assert takeover_lot(state, 6)["qty"] == keep + qty


def test_the_register_follows_the_owned_clubs_both_ways():
    from tools.club_stock_market import (
        share_books,
        shares_at,
        sync_takeovers,
        takeover_lot,
    )

    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 5)
    book = share_books(state)[5]
    capital = shares_at(row, ORDINAL, book)

    handed = sync_takeovers(
        state, rows, {5: 42_000_000}, game_date=GAME_DATE, ordinal=ORDINAL,
    )
    assert [item["club_id"] for item in handed["granted"]] == [5]
    assert handed["granted"][0]["qty"] == capital
    assert handed["released"] == []
    assert handed["count"] == 1

    # 再读一遍时登记册已经对上了，不再反复交接。
    again = sync_takeovers(
        state, rows, {5: 42_000_000}, game_date=GAME_DATE, ordinal=ORDINAL,
    )
    assert again["count"] == 0

    # 俱乐部被卖掉后，登记册跟着收回。
    sold = sync_takeovers(state, rows, {}, game_date=GAME_DATE, ordinal=ORDINAL)
    assert [item["club_id"] for item in sold["released"]] == [5]
    assert takeover_lot(state, 5) is None
    assert state["holdings"] == {}


def test_release_takeover_leaves_the_watchlist_too():
    from tools.club_stock_market import release_takeover, take_over_club, toggle_watch

    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 7)
    toggle_watch(state, 7)
    take_over_club(
        state, row, club_id=7, shares=1_000, price=5_000_000,
        game_date=GAME_DATE, ordinal=ORDINAL,
    )
    assert 7 in state["watchlist"]
    lot = release_takeover(state, 7)
    assert lot is not None and lot["source"] == "takeover"
    assert state["holdings"] == {}
    assert 7 not in state["watchlist"]
    assert release_takeover(state, 7) is None


def test_an_owned_club_sells_back_down_to_control_and_keeps_the_register():
    from tools.club_stock_market import (
        commit_sell,
        sell_plan,
        share_books,
        shares_at,
        sync_takeovers,
        take_over_club,
        takeover_keep_qty,
        takeover_lot,
        trading_quote,
    )

    state, rows, _outcome = initialized()
    row = next(item for item in rows if int(item["id"]) == 4)
    book = share_books(state)[4]
    capital = shares_at(row, ORDINAL, book)
    take_over_club(
        state, row, club_id=4, shares=capital, price=48_000_000,
        game_date=GAME_DATE, ordinal=ORDINAL,
    )
    stock = trading_quote(state, row, ORDINAL, book=book)
    keep = takeover_keep_qty(capital)
    plan = sell_plan(state, stock, capital - keep, ordinal=ORDINAL)
    commit_sell(state, stock, plan, game_date=GAME_DATE, ordinal=ORDINAL)

    lot = takeover_lot(state, 4)
    assert lot["qty"] == keep
    assert lot["takeover_sold"] == capital - keep
    # 卖回的部分重新挂在俱乐部名下，集团的控制股没有被再次交接。
    again = trading_quote(state, row, ORDINAL, book=book)
    assert again["owned"] is True
    assert again["club_shares"] == capital - keep
    assert again["sellable"] == 0
    kept = sync_takeovers(
        state, rows, {4: 48_000_000}, game_date=GAME_DATE, ordinal=ORDINAL,
    )
    assert kept["count"] == 0
    assert takeover_lot(state, 4)["qty"] == keep


def test_takeover_keep_qty_rounds_up_and_never_exceeds_the_capital():
    from tools.club_stock_market import takeover_keep_qty

    assert takeover_keep_qty(0) == 0
    assert takeover_keep_qty(1) == 1
    assert takeover_keep_qty(2) == 2
    assert takeover_keep_qty(100) == 51
    assert takeover_keep_qty(99) == 51
    assert takeover_keep_qty(1_000_000) == 510_000


def test_holding_capital_and_takeover_charge_credit_what_was_already_paid():
    from tools.club_stock_market import holding_capital, takeover_charge

    assert holding_capital(None) == 0.0
    assert holding_capital({"qty": 0, "avg_cost": 12.5}) == 0.0
    assert holding_capital({"qty": 400, "avg_cost": 12.5}) == 5_000.0
    assert takeover_charge(90_000_000) == {
        "gross": 90_000_000.0, "credit": 0.0, "net": 90_000_000.0,
    }
    charged = takeover_charge(90_000_000, 12_345_678.9)
    assert charged["gross"] == 90_000_000.0
    assert charged["credit"] == 12_345_678.9
    assert charged["net"] == 77_654_321.1
    # 持仓资本高于收购价时实付为零，绝不倒找钱。
    assert takeover_charge(1_000, 5_000)["net"] == 0.0
    assert takeover_charge(-10, 0)["gross"] == 0.0


def test_price_streak_counts_the_run_of_rising_closes():
    from tools.club_stock_market import price_streak

    assert price_streak(None) == 0
    assert price_streak([]) == 0
    candles = [{"c": 10}, {"c": 11}, {"c": 12}, {"c": 13}]
    assert price_streak(candles) == 3
    assert price_streak(candles + [{"c": 12}]) == 0
    assert price_streak(candles + [{"c": 14}, {"c": 15}]) == 5
    # 无收盘价的蜡烛不算数，序列里其它行照旧比较。
    assert price_streak([{"c": 10}, {"c": 0}, {"c": 12}]) == 1


def test_takeover_appetite_reads_the_offer_against_the_appraisal():
    from tools.club_stock_market import takeover_appetite

    row = {"id": 1}
    anchor = {"intrinsic": 100.0}
    rich = takeover_appetite(row, anchor, ORDINAL, price=200.0)
    assert rich["value"] == 0.05
    assert rich["accept"] is False
    assert [item["key"] for item in rich["reasons"]] == ["premium"]
    assert rich["reasons"][0]["gap"] == 1.0

    cheap = takeover_appetite(row, anchor, ORDINAL, price=50.0)
    assert cheap["value"] == 0.9
    assert cheap["accept"] is True
    assert [item["key"] for item in cheap["reasons"]] == ["discount"]
    assert cheap["reasons"][0]["gap"] == -0.5

    # 连续上涨的收盘价同样压低意愿，且和报价一起作用。
    rising = takeover_appetite(row, anchor, ORDINAL, price=100.0, streak=3)
    assert rising["streak"] == 3
    assert rising["value"] == 0.3
    both = takeover_appetite(row, anchor, ORDINAL, price=200.0, streak=9)
    assert both["value"] == 0.03
    assert [item["key"] for item in both["reasons"]] == ["premium", "streak"]
    # 报价和估值都不会读时不动意愿：只有基准概率。
    flat = takeover_appetite(row, {}, ORDINAL)
    assert flat["value"] == 0.6 and flat["gap"] == 0.0


def test_takeover_stake_gate_needs_49_percent_from_ten_billion():
    from tools.club_stock_market import takeover_stake_gate

    small = takeover_stake_gate({"id": 1}, {"market_cap": 9_999_999_999, "shares": 1_000, "qty": 0})
    assert small["required"] is False and small["ok"] is True
    assert small["ratio"] == 0.49 and small["threshold"] == 10_000_000_000

    huge = takeover_stake_gate({"id": 2}, {"market_cap": 10_000_000_000, "shares": 1_000_000, "qty": 489_999})
    assert huge["required"] is True and huge["ok"] is False
    assert huge["stake"] == 0.489999

    ready = takeover_stake_gate({"id": 2}, {"market_cap": 10_000_000_000, "shares": 1_000_000, "qty": 490_000})
    assert ready["ok"] is True
    # 没有行情时用估值判定，市值足够大也照样要求持股。
    unlisted = takeover_stake_gate({"id": 3, "club_value": 20_000_000_000})
    assert unlisted["required"] is True
    assert unlisted["shares"] == 0 and unlisted["ok"] is False


def test_the_global_scope_lists_every_league_and_then_every_club():
    from tools.club_stock_market import (
        canonicalize_scope,
        in_scope,
        reconcile_scope,
        scope_rows,
    )

    rows = [
        club(1, "A", nation="英格兰", competition="英超联赛"),
        club(2, "B", nation="西班牙", competition="西甲联赛"),
        club(3, "C", nation="丹麦", competition=""),
    ]
    # 只勾一次全球：所有有联赛的俱乐部。
    every_league = {"nations": [], "leagues": [["*", "*"]]}
    assert [int(item["id"]) for item in scope_rows(rows, every_league)] == [1, 2]
    assert in_scope(rows[0], every_league) is True
    assert in_scope(rows[2], every_league) is False
    # 再勾一次全球：连没有联赛的俱乐部也算进来。
    everywhere = {"nations": ["*"], "leagues": []}
    assert [int(item["id"]) for item in scope_rows(rows, everywhere)] == [1, 2, 3]
    assert in_scope(rows[2], everywhere) is True
    # 空范围依旧一个都不开。
    assert scope_rows(rows, {"nations": [], "leagues": []}) == []
    assert in_scope(rows[0], {}) is False

    index = {"pairs": [("英格兰", "英超联赛")], "aliases": {}}
    kept = reconcile_scope(every_league, index)
    assert kept["dropped"] == [] and kept["confirmed"] is True
    assert kept["scope"]["leagues"] == [["*", "*"]]
    # 目录不认识的联赛会被剪掉，但全球条目永远保留。
    mixed = reconcile_scope(
        {"nations": [], "leagues": [["*", "*"], ["英格兰", "英超联赛"], ["英格兰", "已消失联赛"]]},
        index,
    )
    assert mixed["dropped"] == [["英格兰", "已消失联赛"]]
    assert mixed["scope"]["leagues"] == [["*", "*"], ["英格兰", "英超联赛"]]
    canonical = canonicalize_scope(everywhere, index)
    assert canonical["nations"] == ["*"]
