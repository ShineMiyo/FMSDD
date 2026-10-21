"""Application wiring for the per-nation club stock market."""

from __future__ import annotations

import json
import threading

import pytest

import fm_odds_web
from fm_odds_web import LocalOddsState
from tools import club_stock_market as stock_market

GAME_DATE = "2026-08-12"
NATIONS = ("英格兰", "西班牙", "意大利")
PER_NATION = 25


def club_rows(per_nation: int = PER_NATION) -> list[dict]:
    """Three nations; 英格兰 is the richest exchange of the save."""
    rows: list[dict] = []
    club_id = 0
    for rank, nation in enumerate(NATIONS):
        for index in range(1, per_nation + 1):
            club_id += 1
            rows.append({
                "id": club_id,
                "name": f"{nation}俱乐部{index}",
                "short_name": "",
                "nation": nation,
                "competition": f"{nation}超级联赛",
                "reputation": 9_000 - rank * 1_500 - index * 20,
                "balance": 5_000_000 * (per_nation - index + 1),
                "recent_results": [{"result": "胜"}] * (index % 5) + [{"result": "平"}],
                "league_position": index,
                "league_team_count": per_nation,
                # The world club database, which is what the market may read a
                # league as missing from; the day's fixture window is built
                # without this mark.
                "source": "native_scan",
            })
    return rows


def open_session(store: dict, calls: dict, rows: list | None = None, **output) -> LocalOddsState:
    """A LocalOddsState wired for the market without touching a live save."""
    instance = LocalOddsState.__new__(LocalOddsState)
    instance.lock = threading.RLock()
    instance.cache_verified = True
    instance.data_version = 7
    instance.stock_market_caches = None
    instance.output = {
        "save_instance_id": "save-1",
        "game_date": GAME_DATE,
        "manual_account_scope_id": "scope-1",
        "season_start": "2026",
        **output,
    }
    world = club_rows() if rows is None else list(rows)
    instance._world_club_native_cache = lambda save_id: None
    instance._world_club_directory = lambda output, save_id, native: {"clubs": list(world)}
    instance.stock_store = store
    instance.stock_calls = calls
    return instance


def reopen(state: LocalOddsState, **output) -> LocalOddsState:
    """Simulate the next launch of ODD on the same save."""
    session = open_session(state.stock_store, state.stock_calls, **output)
    session.output = {**state.output, **session.output, **output}
    return session


@pytest.fixture
def state(monkeypatch):
    store: dict[str, dict] = {}
    calls: dict[str, list] = {"charge": [], "credit": [], "refund": []}
    monkeypatch.setattr(
        stock_market, "load_state",
        lambda scope_id=None: json.loads(json.dumps(store["state"])),
    )
    monkeypatch.setattr(
        stock_market, "save_state",
        lambda payload, scope_id=None: store.__setitem__(
            "state", json.loads(json.dumps(payload)),
        ),
    )
    monkeypatch.setattr(
        fm_odds_web, "charge_combined_funds",
        lambda amount, kind, **details: (
            calls["charge"].append((amount, kind, details))
            or {"bank": amount, "wallet": 0.0, "total": amount, "transaction_id": "tx"}
        ),
    )
    monkeypatch.setattr(
        fm_odds_web, "adjust_bank_balance",
        lambda delta, kind, **details: (
            calls["credit"].append((delta, kind, details)) or {"bank_balance": delta}
        ),
    )
    monkeypatch.setattr(
        fm_odds_web, "refund_combined_funds",
        lambda payment, kind, **details: (
            calls["refund"].append((payment, kind, details))
            or {"total": payment["total"]}
        ),
    )
    store["state"] = stock_market.empty_state()
    return open_session(store, calls)


def credits(state: LocalOddsState, kind: str) -> list:
    return [row for row in state.stock_calls["credit"] if row[1] == kind]


def enable(state: LocalOddsState, nations=None, leagues=None, **extra) -> dict:
    """Open exchanges the way the stock-market filter does."""
    return state.apply_stock_market_scope({
        "nations": list(NATIONS) if nations is None else list(nations),
        "leagues": list(leagues or []),
        **extra,
    })


def open_market(state: LocalOddsState, **extra) -> LocalOddsState:
    """Fixture state with every nation enabled and its boards ready."""
    enable(state, **extra)
    return state


# ---------------------------------------------------------------------------
# Opening the exchange
# ---------------------------------------------------------------------------


def test_public_market_requires_a_bound_save():
    instance = LocalOddsState.__new__(LocalOddsState)
    instance.lock = threading.RLock()
    instance.cache_verified = False
    instance.output = {}
    assert instance.public_stock_market()["ready"] is False


def test_market_stays_closed_until_an_exchange_is_enabled(state):
    view = state.public_stock_market()
    assert view["ready"] is True
    assert view["scope_id"] == "scope-1"
    assert view["enabled"] is False
    assert view["scope"] == {"nations": [], "leagues": []}
    assert view["nations"] == []
    assert view["stocks"] == []
    assert view["tick"]["skipped"] == "disabled"
    assert view["tick"]["enabled"] is False
    assert view["tick"]["initialized"] is False
    assert state.stock_store["state"]["initialized"] is False
    assert state.stock_store["state"]["nations"] == {}
    assert view["notices"] == []


def test_the_scope_route_lists_every_nation_before_anything_is_enabled(state):
    payload = state.stock_market_scope()
    assert payload["ready"] is True
    assert payload["enabled"] is False
    assert payload["stats"]["clubs"] == 0
    assert payload["stats"]["total_clubs"] == PER_NATION * len(NATIONS)
    assert payload["stats"]["total_nations"] == len(NATIONS)
    by_name = {row["name"]: row for row in payload["nations"]}
    assert sorted(by_name) == sorted(NATIONS)
    assert by_name["英格兰"]["clubs"] == PER_NATION
    assert by_name["英格兰"]["leagues"] == 1
    assert by_name["英格兰"]["selected"] is False
    assert by_name["英格兰"]["partial"] is False
    assert payload["scope_leagues"] == []
    assert payload["suggestions"]
    assert all(item["clubs"] >= 8 for item in payload["suggestions"])


def test_stock_market_directory_excludes_womens_clubs(state):
    rows = club_rows()
    rows.append({
        "id": 999_999,
        "name": "Women's Test Club",
        "gender": "women",
        "nation": "英格兰",
        "competition": "英格兰女子超级联赛",
        "reputation": 1_000,
    })
    state._world_club_directory = lambda output, save_id, native: {"clubs": rows}
    visible, _key = state._stock_market_raw_directory(state.output, "save-1")
    self_ids = {int(row.get("id") or 0) for row in visible}
    assert 999_999 not in self_ids
    assert len(visible) == PER_NATION * len(NATIONS)


def test_the_save_competitions_lead_the_filter_and_the_rest_follow(state):
    """The dialog lists the leagues this save runs, then everything else."""
    output = {
        "competition_formats": [
            {"competition_id": 1301, "competition_name": "西班牙超级联赛", "competition_kind": "league"},
            {"competition_id": 1302, "competition_name": "西班牙国王杯", "competition_kind": "cup"},
        ],
    }
    session = reopen(state, **output)
    world = club_rows()
    for row in world:
        row["competition_id"] = (
            1301 if row["competition"] == "西班牙超级联赛" else 9000 + int(row["id"]) % 7
        )
    session._world_club_directory = lambda payload, save_id, native: {"clubs": list(world)}

    payload = session.stock_market_scope()
    assert payload["save_ready"] is True
    assert payload["stats"]["save_ready"] is True
    assert payload["stats"]["save_nations"] == 1
    assert payload["stats"]["save_leagues"] == 1
    assert payload["stats"]["save_clubs"] == PER_NATION
    by_name = {row["name"]: row for row in payload["nations"]}
    assert by_name["西班牙"]["save_clubs"] == PER_NATION
    assert by_name["西班牙"]["in_save"] is True
    assert by_name["英格兰"]["save_clubs"] == 0
    assert by_name["英格兰"]["in_save"] is False
    # 西班牙 is the save's own exchange, so it leads despite being smaller.
    assert payload["nations"][0]["name"] == "西班牙"
    assert [item["nation"] for item in payload["suggestions"]] == ["西班牙"]
    assert payload["scan"]["scanning"] is False

    leagues = session.stock_market_scope_leagues({"nation": "西班牙"})
    assert leagues["save_ready"] is True
    assert [row["name"] for row in leagues["leagues"]] == ["西班牙超级联赛"]
    assert leagues["leagues"][0]["in_save"] is True
    assert leagues["leagues"][0]["save_clubs"] == PER_NATION

    english = session.stock_market_scope_leagues({"nation": "英格兰"})
    assert [row["name"] for row in english["leagues"]] == ["英格兰超级联赛"]
    assert english["leagues"][0]["in_save"] is False
    assert english["leagues"][0]["save_clubs"] == 0


def test_the_whole_directory_answers_in_one_read_for_the_worldwide_row(state):
    """The worldwide row covers every country without one read per country."""
    payload = state.stock_market_scope_leagues({"nation": "*"})
    assert payload["bulk"] is True
    assert set(payload["tables"]) == set(NATIONS)
    english = state.stock_market_scope_leagues({"nation": "英格兰"})
    # The bulk rows are exactly the rows a single nation lists.
    assert payload["tables"]["英格兰"] == english["leagues"]


def test_a_nation_without_a_league_answers_with_an_empty_list(state):
    """A worldwide tick still addresses countries the directory lists alone."""
    world = club_rows() + [{
        "id": 99999, "name": "无联赛俱乐部", "short_name": "", "nation": "丹麦",
        "competition": "", "reputation": 1000, "balance": 1000,
    }]
    session = open_session(state.stock_store, state.stock_calls, rows=world)
    payload = session.stock_market_scope_leagues({"nation": "*"})
    assert payload["tables"]["丹麦"] == []
    assert payload["tables"]["英格兰"][0]["name"] == "英格兰超级联赛"


def test_a_save_that_was_not_read_yet_keeps_every_nation_available(state):
    """Without competition formats the filter falls back to the whole directory."""
    payload = state.stock_market_scope()
    assert payload["save_ready"] is False
    assert payload["stats"]["save_ready"] is False
    assert payload["stats"]["save_clubs"] == 0
    assert all(row["in_save"] is False for row in payload["nations"])
    assert {row["name"] for row in payload["nations"]} == set(NATIONS)
    assert state.stock_market_scope_leagues({"nation": "英格兰"})["save_ready"] is False


def test_scope_stats_follow_the_saved_scope(state):
    enable(
        state, nations=["英格兰"],
        leagues=[["西班牙", "西班牙超级联赛"]],
    )
    payload = state.stock_market_scope()
    assert payload["enabled"] is True
    # A league-only selection still counts the country it belongs to.
    assert payload["stats"]["nations"] == 2
    assert payload["stats"]["leagues"] == 1
    assert payload["stats"]["clubs"] == PER_NATION * 2
    by_name = {row["name"]: row for row in payload["nations"]}
    assert by_name["英格兰"]["selected"] is True
    assert by_name["西班牙"]["selected"] is False
    assert by_name["西班牙"]["partial"] is True
    assert by_name["西班牙"]["selected_leagues"] == 1
    assert [item["nation"] for item in payload["scope_leagues"]] == ["西班牙"]


def test_scope_leagues_route_lists_one_nation(state):
    enable(state, nations=["英格兰"])
    handler = type("Handler", (), {"state": state})()
    payload = fm_odds_web._get_stock_scope_leagues_route(
        handler, {}, {"nation": ["英格兰"]},
    )
    assert payload["ready"] is True
    assert payload["nation"] == "英格兰"
    assert [row["name"] for row in payload["leagues"]] == ["英格兰超级联赛"]
    league = payload["leagues"][0]
    assert league["clubs"] == PER_NATION
    assert league["nation_selected"] is True
    assert league["selected"] is False


def test_the_exchange_filter_routes_are_registered():
    routes = {
        path: name for _method, path, name in fm_odds_web.API_ROUTES.describe()
    }
    assert "/api/stock/scope" in routes
    assert "/api/stock/scope/leagues" in routes
    assert routes["/api/stock/scope/save"] == "apply_stock_market_scope"


def test_enabling_every_nation_opens_them_once(state):
    result = enable(state)
    assert result["ok"] is True
    assert result["changed"] is True
    assert result["enabled"] is True
    assert sorted(result["scope"]["nations"]) == sorted(NATIONS)
    assert sorted(result["added"]["nations"]) == sorted(NATIONS)
    assert result["added"]["clubs"] == PER_NATION * len(NATIONS)
    assert result["listed"] == PER_NATION * len(NATIONS)
    assert result["market"]["enabled"] is True

    view = state.public_stock_market()
    assert view["ready"] is True
    assert view["enabled"] is True
    assert view["initialized"] is True
    assert view["initialized_game_date"] == GAME_DATE
    assert [row["name"] for row in view["nations"]] == list(NATIONS)
    assert view["nation"] == "英格兰"
    assert view["summary"]["clubs"] == PER_NATION
    assert [notice["kind"] for notice in view["notices"]] == ["init", "scope_add"]
    assert state.stock_store["state"]["initialized"] is True


def test_a_newly_enabled_nation_lists_from_scratch(state):
    open_market(state, nations=["英格兰"])
    english = state.stock_store["state"]["nations"]["英格兰"]["listed_ordinal"]

    moved = reopen(state, game_date="2026-08-20")
    enable(moved, nations=["英格兰", "西班牙"])
    nations = moved.stock_store["state"]["nations"]
    assert nations["英格兰"]["listed_ordinal"] == english
    assert nations["西班牙"]["listed_ordinal"] > english
    assert nations["西班牙"]["listed_game_date"] == "2026-08-20"

    view = moved.public_stock_market(nation="西班牙")
    assert view["ready"] is True
    assert view["enabled"] is True
    assert view["summary"]["listed_game_date"] == "2026-08-20"
    assert [row["change"] for row in view["stocks"]] == [0.0] * PER_NATION
    assert {row["name"] for row in view["nations"]} == {"英格兰", "西班牙"}
    assert moved.stock_store["state"]["scope"]["nations"] == ["英格兰", "西班牙"]


def test_removing_a_nation_freezes_the_holdings_and_drops_the_data(state):
    open_market(state, nations=["英格兰", "西班牙"])
    state.buy_stock({"club_id": 27, "qty": 10})

    moved = reopen(state, game_date="2026-08-13")
    result = moved.apply_stock_market_scope({"nations": ["英格兰"]})

    assert result["changed"] is True
    assert result["enabled"] is True
    assert result["removed"]["nations"] == ["西班牙"]
    assert result["removed"]["clubs"] == PER_NATION
    assert result["scope"]["nations"] == ["英格兰"]
    assert result["settlements"] == []
    assert result["credit"] == 0.0
    frozen = result["frozen"]
    assert frozen["count"] == 1
    assert frozen["lots"][0]["club_id"] == 27
    assert frozen["lots"][0]["qty"] == 10
    assert frozen["value"] == pytest.approx(frozen["lots"][0]["price"] * 10, abs=0.01)
    assert "西班牙" not in moved.stock_store["state"]["nations"]
    holding = moved.stock_store["state"]["holdings"]["27"]
    assert holding["frozen"] is True
    assert holding["qty"] == 10
    assert not credits(moved, "stock_delist_settlement")
    view = result["market"]
    assert [row["name"] for row in view["nations"]] == ["英格兰"]
    assert "scope_freeze" in [notice["kind"] for notice in view["notices"]]
    lots = {row["club_id"]: row for row in view["holdings"]}
    assert lots[27]["frozen"] is True
    assert lots[27]["qty"] == 10
    assert lots[27]["sellable"] == 0
    assert lots[27]["value"] == pytest.approx(frozen["value"], abs=0.01)
    assert view["totals"]["frozen_value"] == pytest.approx(frozen["value"], abs=0.01)
    assert view["totals"]["frozen_count"] == 1

    re_enabled = moved.apply_stock_market_scope({
        "nations": ["英格兰", "西班牙"],
    })
    assert re_enabled["added"]["nations"] == ["西班牙"]
    assert re_enabled["unfrozen"] == 1
    assert re_enabled["scope"]["nations"] == ["英格兰", "西班牙"]
    assert "frozen" not in moved.stock_store["state"]["holdings"]["27"]
    assert (
        moved.stock_store["state"]["nations"]["西班牙"]["listed_game_date"]
        == "2026-08-13"
    )


def test_closing_every_exchange_leaves_the_market_disabled(state):
    open_market(state)
    result = state.apply_stock_market_scope({"nations": []})
    assert result["changed"] is True
    assert result["enabled"] is False
    assert result["scope"] == {"nations": [], "leagues": []}
    assert state.stock_store["state"]["nations"] == {}
    view = state.public_stock_market()
    assert view["enabled"] is False
    assert view["tick"]["skipped"] == "disabled"
    assert view["nations"] == []


def test_saving_the_same_scope_again_changes_nothing(state):
    open_market(state)
    result = state.apply_stock_market_scope({"nations": list(NATIONS)})
    assert result["changed"] is False
    assert result["added"]["nations"] == []
    assert result["removed"]["nations"] == []


def test_the_saved_market_is_reused_instead_of_being_initialized_again(state):
    enable(state)
    first = state.public_stock_market()
    state.buy_stock({"club_id": 1, "qty": 100})

    again = reopen(state)
    second = again.public_stock_market()
    assert second["tick"]["initialized"] is False
    assert second["tick"]["skipped"] != "directory"
    assert second["initialized"] is True
    assert second["initialized_game_date"] == GAME_DATE
    assert [notice["kind"] for notice in second["notices"]].count("init") == 1
    assert len(second["notices"]) == len(first["notices"])
    assert [row["club_id"] for row in second["holdings"]] == [1]
    assert len(second["trades"]) == 1


def test_repeated_reads_in_one_session_skip_the_tick(state):
    open_market(state)
    second = state.public_stock_market()
    assert second["tick"]["skipped"] == "unchanged"
    assert [notice["kind"] for notice in second["notices"]] == ["init", "scope_add"]


def test_market_route_reports_the_board_for_a_query(state):
    open_market(state)
    handler = type("Handler", (), {"state": state})()
    view = fm_odds_web._get_stock_market_route(
        handler, {}, {"nation": ["西班牙"], "page_size": ["10"], "watch": ["1"]},
    )
    assert view["ready"] is True
    assert view["nation"] == "西班牙"
    assert view["pagination"]["page_size"] == 10


def test_the_board_pages_searches_and_sorts_one_nation(state):
    open_market(state)
    page_one = state.public_stock_market(nation="西班牙", page_size=10, sort="price")
    assert page_one["nation"] == "西班牙"
    assert page_one["pagination"]["total"] == PER_NATION
    assert page_one["pagination"]["page_count"] == 3
    assert len(page_one["stocks"]) == 10
    assert all(row["nation"] == "西班牙" for row in page_one["stocks"])
    prices = [row["price"] for row in page_one["stocks"]]
    assert prices == sorted(prices, reverse=True)
    assert page_one["stocks"][0]["market_cap"] > 0
    assert page_one["stocks"][0]["history"]

    page_two = state.public_stock_market(nation="西班牙", page_size=10, sort="price", page=2)
    assert page_two["pagination"]["page"] == 2
    assert {row["club_id"] for row in page_two["stocks"]}.isdisjoint(
        {row["club_id"] for row in page_one["stocks"]},
    )

    found = state.public_stock_market(nation="西班牙", search="西班牙俱乐部7")
    assert [row["club_id"] for row in found["stocks"]] != []
    assert all("7" in row["name"] for row in found["stocks"])


def test_a_save_without_a_readable_directory_still_answers(state):
    state._world_club_directory = lambda output, save_id, native: {"clubs": []}
    open_market(state)
    view = state.public_stock_market()
    assert view["ready"] is True
    assert view["stocks"] == []
    assert view["nations"] == []
    assert view["tick"]["skipped"] == "directory"


# ---------------------------------------------------------------------------
# Trading
# ---------------------------------------------------------------------------


def test_buy_stock_charges_the_combined_funds_and_records_the_holding(state):
    open_market(state)
    result = state.buy_stock({"club_id": 1, "qty": 100})
    amount, kind, details = state.stock_calls["charge"][-1]
    trade = result["trade"]
    assert kind == "stock_buy"
    assert details["club_id"] == 1 and details["qty"] == 100
    assert amount == pytest.approx(trade["amount"] + trade["fee"])
    holding = state.stock_store["state"]["holdings"]["1"]
    assert holding["qty"] == 100
    stock = next(item for item in result["market"]["stocks"] if item["club_id"] == 1)
    assert stock["qty"] == 100
    assert stock["sellable"] == 0
    assert stock["holding_value"] == pytest.approx(100 * stock["price"], abs=0.01)
    assert result["market"]["totals"]["market_value"] > 0
    assert result["market"]["totals"]["cost"] == pytest.approx(amount, abs=0.5)
    assert not state.stock_calls["refund"]


def test_a_click_past_a_million_shares_is_still_a_plain_buy(state):
    open_market(state)
    stock = max(state.public_stock_market()["stocks"], key=lambda row: row["shares"])
    # Two percent of the capital is the whole ceiling of a click: the round lot
    # of a million shares may never push a smaller order into a block trade.
    assert stock["max_order"] == int(stock["shares"] * 0.02)
    assert stock["max_order"] > 1_000_000
    qty = 1_000_000 + 1
    result = state.buy_stock({"club_id": stock["club_id"], "qty": qty})
    assert result["trade"]["side"] == "buy"
    assert result["trade"]["qty"] == qty
    assert state.stock_calls["charge"][-1][1] == "stock_buy"
    holding = state.stock_store["state"]["holdings"][str(stock["club_id"])]
    assert holding["qty"] == qty
    assert state.stock_store["state"]["orders"] == []


def test_buy_stock_refunds_and_reverts_when_the_market_cannot_be_saved(state, monkeypatch):
    open_market(state)
    monkeypatch.setattr(
        stock_market, "save_state",
        lambda payload, scope_id=None: (_ for _ in ()).throw(RuntimeError("磁盘写入失败")),
    )
    with pytest.raises(RuntimeError):
        state.buy_stock({"club_id": 1, "qty": 50})
    assert state.stock_calls["refund"][-1][1] == "stock_buy_rollback"
    assert "1" not in state.stock_store["state"]["holdings"]
    assert all(row.get("side") != "buy" for row in state.stock_store["state"]["trades"])


def test_sell_stock_waits_for_the_next_game_day_and_credits_the_bank(state):
    open_market(state)
    state.buy_stock({"club_id": 2, "qty": 100})
    with pytest.raises(ValueError, match="下一个比赛日"):
        state.sell_stock({"club_id": 2, "qty": 100})

    moved = reopen(state, game_date="2026-08-13")
    result = moved.sell_stock({"club_id": 2, "qty": 100})
    net, kind, details = credits(moved, "stock_sell")[-1]
    assert kind == "stock_sell"
    assert details["club_id"] == 2
    assert net == pytest.approx(result["trade"]["amount"] - result["trade"]["fee"])
    assert "2" not in moved.stock_store["state"]["holdings"]
    assert result["market"]["totals"]["realized_profit"] == pytest.approx(
        result["trade"]["realized"],
    )
    assert moved.stock_store["state"]["realized_profit"] == pytest.approx(
        result["trade"]["realized"],
    )


def test_trades_are_rejected_for_clubs_outside_the_directory(state):
    open_market(state)
    with pytest.raises(ValueError, match="股票不存在"):
        state.buy_stock({"club_id": 9_999, "qty": 10})
    with pytest.raises(ValueError, match="未在股市上市"):
        state.toggle_stock_watch({"club_id": 9_999})


def test_trades_are_rejected_outside_the_enabled_scope(state):
    open_market(state, nations=["英格兰"])
    with pytest.raises(ValueError, match="股票不存在"):
        state.buy_stock({"club_id": 26, "qty": 10})
    with pytest.raises(ValueError, match="未在股市上市"):
        state.toggle_stock_watch({"club_id": 26})
    assert state.buy_stock({"club_id": 1, "qty": 10})["trade"]["qty"] == 10


def test_a_closed_market_refuses_to_trade(state):
    with pytest.raises(ValueError, match="股市尚未开启"):
        state.buy_stock({"club_id": 1, "qty": 10})
    with pytest.raises(ValueError, match="股市尚未开启"):
        state.sell_stock({"club_id": 1, "qty": 10})
    with pytest.raises(ValueError, match="股市尚未开启"):
        state.toggle_stock_watch({"club_id": 1})


def test_watchlist_persists_and_filters_the_board(state):
    open_market(state)
    assert state.toggle_stock_watch({"club_id": 3})["watched"] is True
    assert state.toggle_stock_watch({"club_id": 4})["watched"] is True

    again = reopen(state)
    view = again.public_stock_market(nation="英格兰", watch_only=True)
    assert [row["club_id"] for row in view["stocks"]] == [3, 4]
    assert view["watchlist"] == [3, 4]

    assert again.toggle_stock_watch({"club_id": 3})["watched"] is False
    assert reopen(again).public_stock_market()["watchlist"] == [4]


def test_delisting_settles_the_holding_into_the_bank(state):
    open_market(state)
    state.buy_stock({"club_id": 5, "qty": 10})
    price = float(state.stock_store["state"]["holdings"]["5"]["last_price"])

    reduced = [row for row in club_rows() if int(row["id"]) != 5]
    # The world directory is read in over minutes, so a club missing from one
    # reading is a sighting: the lot stays, the day is remembered and nothing
    # reaches the bank yet.
    sighting = reopen(state, rows=reduced)
    sighting.advance_stock_market()
    assert not credits(sighting, "stock_delist_settlement")
    assert "5" in sighting.stock_store["state"]["holdings"]
    assert int(sighting.stock_store["state"]["missing"]["5"]) > 0

    # Still gone on a later game day is a club the save lost: the lot is bought
    # out at its last known quote and the proceeds reach the bank.
    moved = reopen(sighting, rows=reduced, game_date="2026-08-13")
    moved.advance_stock_market()

    settled = credits(moved, "stock_delist_settlement")
    assert settled, "delisting proceeds must reach the bank"
    assert settled[-1][0] == pytest.approx(10 * price, abs=0.01)
    assert "5" not in moved.stock_store["state"]["holdings"]
    assert moved.stock_store["state"]["trades"][-1]["side"] == "delist"
    assert moved.stock_store["state"]["notices"][-1]["kind"] == "delisting"
    # The sighting is dropped once nothing waits on the club any more.
    later = reopen(moved, rows=reduced, game_date="2026-08-14")
    later.advance_stock_market()
    assert later.stock_store["state"]["missing"] == {}


def test_a_financed_lot_survives_a_reading_that_has_not_reached_the_club(state):
    open_market(state)
    stock = next(
        row for row in state.public_stock_market()["stocks"] if row["club_id"] == 1
    )
    qty = max(1, int(stock["shares"] * 0.02))
    state.finance_stock({"club_id": 1, "qty": qty})
    assert state.stock_store["state"]["holdings"]["1"]["qty"] == qty

    # The next launch reads a directory that has not reached the club yet: the
    # capital the account just paid for may not be settled away as a delisting.
    reduced = [row for row in club_rows() if int(row["id"]) != 1]
    moved = reopen(state, rows=reduced, game_date="2026-08-13")
    moved.advance_stock_market()

    assert not credits(moved, "stock_delist_settlement")
    assert moved.stock_store["state"]["holdings"]["1"]["qty"] == qty
    assert [
        row for row in moved.stock_store["state"]["trades"] if row["side"] == "delist"
    ] == []
    assert int(moved.stock_store["state"]["missing"]["1"]) > 0


def test_an_exchange_listed_in_the_future_trades_again_the_next_game_day(state):
    open_market(state)
    # Closing an exchange and opening it again after the game clock went
    # backwards used to stamp the nation with a listing day the save no longer
    # reaches: its quotes, candles and index then stood still for ever.
    state.stock_store["state"]["nations"]["英格兰"]["listed_ordinal"] = (
        stock_market.day_ordinal("2026-08-20")
    )

    first = reopen(state, game_date="2026-08-13")
    first.advance_stock_market()
    entry = first.stock_store["state"]["nations"]["英格兰"]
    assert entry["listed_ordinal"] == stock_market.day_ordinal("2026-08-13")

    before = {
        row["club_id"]: row["price"]
        for row in first.public_stock_market(nation="英格兰")["stocks"]
    }
    second = reopen(first, game_date="2026-08-14")
    view = second.public_stock_market(nation="英格兰")
    after = {row["club_id"]: row["price"] for row in view["stocks"]}
    assert len(after) == PER_NATION
    assert len([key for key in after if after[key] != before[key]]) == PER_NATION
    assert view["index"]["change"] != 0.0
    assert len(view["index"]["history"]) > 1
    assert len(view["stocks"][0]["history"]) > 1


def test_refresh_hook_skips_saves_without_an_account_scope():
    instance = LocalOddsState.__new__(LocalOddsState)
    instance.lock = threading.RLock()
    result = instance.advance_stock_market({"game_date": GAME_DATE})
    assert result["skipped"] == "scope"


# ---------------------------------------------------------------------------
# The exchange follows the game clock, not the last odds refresh
# ---------------------------------------------------------------------------


def test_the_market_trades_on_the_live_game_clock(state):
    """A running session must not stay frozen on the last refreshed date."""
    open_market(state)
    assert state.public_stock_market()["game_date"] == GAME_DATE

    # The odds snapshot still stands on GAME_DATE while the clock moved on.
    state.last_connection_clock = {"date": "2026-08-15", "minutes": 600}
    view = state.public_stock_market()
    assert view["game_date"] == "2026-08-15"
    assert view["ordinal"] == stock_market.day_ordinal("2026-08-15")
    assert view["game_date"] > view["initialized_game_date"]
    ordinals = {row["club_id"]: stock_market.day_ordinal("2026-08-15") for row in view["stocks"]}
    assert ordinals
    # Every quote is the one the day's own model produces, so a chart that
    # reaches the new day is not merely relabelled.
    assert next(row for row in view["stocks"] if row["club_id"] == 1)["price"] == pytest.approx(
        stock_market.share_price(
            state._stock_market_directory(state.output, "save-1")[1],
            stock_market.day_ordinal("2026-08-15"),
        ),
    )


def test_the_daily_tick_reopens_the_market_every_game_day(state):
    open_market(state)
    first = state.public_stock_market()
    assert first["tick"]["skipped"] == "unchanged"

    state.last_connection_clock = {"date": "2026-08-13"}
    second = state.public_stock_market()
    assert second["game_date"] == "2026-08-13"
    assert second["tick"]["skipped"] != "unchanged"
    assert second["ordinal"] == stock_market.day_ordinal("2026-08-13")
    # The same day still answers from the cache instead of re-syncing.
    assert state.public_stock_market()["tick"]["skipped"] == "unchanged"


def test_a_result_that_lands_mid_day_reopens_the_session(state):
    """An evening kick-off re-syncs the same day, not only the next one."""
    open_market(state)
    assert state.public_stock_market()["tick"]["skipped"] == "unchanged"

    # Same game day and the same directory object: only the odds snapshot
    # gained a result, which is what bumps the data version.
    with state.lock:
        state.data_version += 1
    assert state.public_stock_market()["tick"]["skipped"] != "unchanged"


def test_a_same_day_win_moves_the_quote_while_the_day_is_running(state):
    """The news of a 20:00 kick-off is paid on that day's close."""
    ordinal = stock_market.day_ordinal(GAME_DATE)
    rows = club_rows()
    rows[0]["recent_results"] = [
        {"result": "胜", "date": GAME_DATE},
        {"result": "负", "date": stock_market.ordinal_date(ordinal - 6)},
    ]
    played = reopen(state, rows=rows)
    open_market(played)
    quoted = next(
        item for item in played.public_stock_market()["stocks"] if item["club_id"] == 1
    )

    rest = [{**rows[0], "recent_results": rows[0]["recent_results"][1:]}] + rows[1:]
    idle = reopen(state, rows=rest)
    open_market(idle)
    pending = next(
        item for item in idle.public_stock_market()["stocks"] if item["club_id"] == 1
    )
    assert quoted["factor"] > pending["factor"]
    assert quoted["price"] > pending["price"]
    assert quoted["fundamentals"]["form_wins"] == 1


def test_a_clock_behind_the_snapshot_never_rewinds_the_market(state):
    open_market(state)
    state.last_connection_clock = {"date": "2026-01-02"}
    view = state.public_stock_market()
    assert view["game_date"] == GAME_DATE


def test_a_pending_save_change_keeps_the_snapshot_date(state):
    open_market(state)
    state.save_change_pending = True
    state.last_connection_clock = {"date": "2026-08-15"}
    assert state.public_stock_market()["game_date"] == GAME_DATE


def test_an_unreadable_or_missing_clock_keeps_the_snapshot_date(state):
    open_market(state)
    for clock in (
        None, {}, {"date": ""}, {"date": "not-a-date"}, {"date": "12/08/2026"},
        {"date": GAME_DATE}, {"date": 20260101},
    ):
        state.last_connection_clock = clock
        assert state.public_stock_market()["game_date"] == GAME_DATE
    del state.last_connection_clock
    assert state.public_stock_market()["game_date"] == GAME_DATE


def test_the_acquisition_and_the_sale_quote_the_live_game_day(state):
    """A takeover must settle at the price the board is quoting today."""
    open_market(state)
    rows = state._stock_market_directory(state.output, "save-1")
    club_id = next(iter(rows))
    frozen = state._stock_market_factors(state.output, "save-1", [club_id])[club_id]
    assert frozen == pytest.approx(
        stock_market.club_factor(rows, club_id, stock_market.day_ordinal(GAME_DATE)),
    )

    state.last_connection_clock = {"date": "2026-08-15"}
    live = stock_market.day_ordinal("2026-08-15")
    assert state._stock_market_factors(state.output, "save-1", [club_id])[club_id] == pytest.approx(
        stock_market.club_factor(rows, club_id, live),
    )
    assert state._stock_market_factors(state.output, "save-1", [club_id])[club_id] != pytest.approx(
        frozen,
    )

    # A save that has not been re-bound yet keeps the snapshot price.
    state.save_change_pending = True
    assert state._stock_market_factors(state.output, "save-1", [club_id])[club_id] == pytest.approx(
        frozen,
    )


def test_a_compact_clock_date_is_canonicalised_before_it_reaches_the_board(state):
    open_market(state)
    state.last_connection_clock = {"date": "20260815"}
    view = state.public_stock_market()
    assert view["game_date"] == "2026-08-15"
    assert view["ordinal"] == stock_market.day_ordinal("2026-08-15")


def test_the_market_carries_a_daily_random_swing_on_top_of_the_results(state):
    open_market(state)
    rows = state._stock_market_directory(state.output, "save-1")
    club_id = next(iter(rows))
    day = stock_market.day_ordinal(GAME_DATE)
    factor = stock_market.market_factor(rows[club_id], day, club_id)
    without_swing = (
        1.0 + stock_market.performance_tilt(rows[club_id])
        + stock_market.market_noise(club_id, day)
    )
    assert factor == pytest.approx(
        max(stock_market.FACTOR_FLOOR, min(
            stock_market.FACTOR_CAP, without_swing + stock_market.daily_swing(club_id, day),
        )),
        abs=1e-6,
    )


# ---------------------------------------------------------------------------
# Match prestige weights the results a club carries
# ---------------------------------------------------------------------------


def test_match_reputation_is_read_from_the_live_match_window(state):
    output = {
        "matches": [
            {"competition_name": "英格兰超级联赛", "competition_reputation_native": 180},
            {"competition_name": "英格兰超级联赛", "competition_reputation_native": 165},
            {"competition_name": "英格兰足总杯", "competition_reputation": 90},
            {"competition_name": "", "competition_reputation_native": 200},
            {"competition_name": "无声望杯", "competition_reputation_native": 0},
            {"competition_name": "文本声望杯", "competition_reputation_native": "not-a-number"},
            {"competition_name": "字符串声望杯", "competition_reputation_native": "120"},
        ],
    }
    reputations = state._stock_market_match_reputation(output)
    assert reputations["英格兰超级联赛"] == 180
    assert reputations["英格兰足总杯"] == 90
    assert reputations["字符串声望杯"] == 120
    assert "无声望杯" not in reputations
    assert "文本声望杯" not in reputations
    assert "" not in reputations
    assert state._stock_market_match_reputation({}) == {}
    assert state._stock_market_match_reputation({"matches": None}) == {}


def test_a_prestigious_result_moves_the_price_further(state):
    reputation = state._stock_market_match_reputation({
        "matches": [{
            "competition_name": "英格兰超级联赛",
            "competition_reputation_native": 190,
        }],
    })
    outcomes = [{"result": "胜", "competition": "英格兰超级联赛"}] + [
        {"result": "负", "competition": "英格兰超级联赛"},
    ] * 4
    weighted = state._stock_market_weighted_results(outcomes, reputation)
    assert all(row["reputation"] == 190 for row in weighted)
    # A competition outside the window keeps the neutral weight.
    plain = state._stock_market_weighted_results(
        [{"result": "胜", "competition": "不存在的联赛"}], reputation,
    )
    assert "reputation" not in plain[0]
    # The copy carries the game day of each result as an ordinal; the source
    # rows (here undated) keep their shape and gain a null day.
    for table in ({}, None):
        copied = state._stock_market_weighted_results(outcomes, table)
        assert copied == [{**dict(row), "day": None} for row in outcomes]
    dated = state._stock_market_weighted_results(
        [{"result": "胜", "date": "2025-10-24"}], {},
    )
    assert dated[0]["day"] == stock_market.day_ordinal("2025-10-24")
    assert stock_market.news_tilt(dated, stock_market.day_ordinal("2025-10-24")) > 0

    appraised = state._stock_market_appraise([
        {
            "id": 1, "name": "Alpha", "nation": "英格兰",
            "competition": "英格兰超级联赛", "balance": 500_000_000,
            "reputation": 7_000, "recent_results": outcomes,
            "league_position": 5, "league_team_count": 20,
        },
        {
            "id": 2, "name": "Beta", "nation": "英格兰",
            "competition": "英格兰超级联赛", "balance": 500_000_000,
            "reputation": 7_000,
            "recent_results": [{"result": "胜"}] + [dict(row) for row in outcomes[1:]],
            "league_position": 5, "league_team_count": 20,
        },
    ], reputation)
    assert appraised[1]["recent_results"][0]["reputation"] == 190
    assert "reputation" not in appraised[2]["recent_results"][0]
    assert appraised[1]["tilt"] > appraised[2]["tilt"]
    assert appraised[1]["tilt"] == pytest.approx(
        stock_market.weighted_tilt(appraised[1]["recent_results"], 5, 20), abs=1e-6,
    )


def test_the_appraisal_keeps_its_plain_price_without_match_prestige(state):
    row = {
        "id": 3, "name": "Gamma", "nation": "英格兰",
        "competition": "英格兰超级联赛", "balance": 500_000_000,
        "reputation": 7_000,
        "recent_results": [
            {"result": "胜", "competition": "英格兰超级联赛"},
            {"result": "平", "competition": "英格兰超级联赛"},
        ],
        "league_position": 3, "league_team_count": 20,
    }
    plain = state._stock_market_appraise([row])
    weighted = state._stock_market_appraise([row], {"英格兰超级联赛": 0})
    assert plain[3]["club_value"] == weighted[3]["club_value"]
    assert plain[3]["tilt"] == pytest.approx(
        stock_market.weighted_tilt(plain[3]["recent_results"], 3, 20), abs=1e-6,
    )
    assert plain[3]["tilt"] == pytest.approx(
        stock_market.tilt_from(plain[3]["form_points"], 3, 20), abs=1e-6,
    )


# ---------------------------------------------------------------------------
# Coupling with the club acquisition and sale price
# ---------------------------------------------------------------------------


def test_market_factor_drives_the_acquisition_and_the_sale_price(state):
    open_market(state)
    view = state.public_stock_market()
    club_id = view["stocks"][0]["club_id"]
    rows = state._stock_market_directory(state.output, "save-1")
    ordinal = state._stock_market_ordinal(state.output)

    factors = state._stock_market_factors(state.output, "save-1", [club_id, 999_999])
    assert factors[club_id] == pytest.approx(
        stock_market.club_factor(rows, club_id, ordinal),
    )
    assert factors[999_999] == 1.0

    appraisal = rows[club_id]["club_value"]
    assert stock_market.apply_factor(appraisal, factors[club_id]) == pytest.approx(
        round(appraisal * factors[club_id]), abs=0.5,
    )
    quote = next(row for row in view["stocks"] if row["club_id"] == club_id)
    # The quote is a rounded per-share price, so the capital times the price
    # reproduces the market cap to the tick and not to the last unit.
    assert quote["market_cap"] == pytest.approx(
        quote["shares"] * quote["price"], rel=1e-3,
    )
    assert quote["factor"] == pytest.approx(factors[club_id], rel=1e-6)

    metrics = state._apply_stock_market_factor(
        {"current_valuation": 1_000_000}, {club_id: 1.5}, club_id,
    )
    assert metrics["market_factor"] == pytest.approx(1.5)
    assert metrics["market_cap"] == 1_500_000


# ---------------------------------------------------------------------------
# Share capital: one book per club, automatic issues, the club as the seller
# ---------------------------------------------------------------------------


def test_the_board_quotes_the_capital_of_every_listed_club(state):
    open_market(state, nations=["英格兰"])
    view = state.public_stock_market(nation="英格兰", page_size=50)
    assert view["share_trigger"] == stock_market.SHARE_SPLIT_TRIGGER
    assert view["max_order_ratio"] == stock_market.MAX_ORDER_SHARE_RATIO
    books = state.stock_store["state"]["nations"]["英格兰"]["shares"]
    assert len(books) == view["summary"]["clubs"] == len(view["stocks"])
    rows = state._stock_market_directory(state.output, "save-1")
    for stock in view["stocks"]:
        source = rows[stock["club_id"]]
        assert stock["shares"] == stock_market.initial_shares(source)
        assert stock["initial_shares"] == stock["shares"]
        assert stock["club_shares"] == stock["shares"]
        assert stock["max_order"] == stock_market.max_shares_per_order(stock["shares"])
        assert stock["split_count"] == 0
        assert stock["share_base"] > 0
        assert stock["split_price"] == pytest.approx(
            stock_market.quote(stock["share_base"] * stock_market.SHARE_SPLIT_TRIGGER),
        )


def test_an_issue_reaches_the_tape_the_board_and_the_next_order(state):
    open_market(state, nations=["英格兰"])
    rows = state._stock_market_directory(state.output, "save-1")
    ordinal = stock_market.day_ordinal(GAME_DATE)
    book = state.stock_store["state"]["nations"]["英格兰"]["shares"]["1"]
    # An issue base the quote has long passed: the next tick must issue.
    book["b"] = round(stock_market.share_price(rows[1], ordinal) / 4, 2)
    with state.lock:
        state.data_version += 1

    view = state.public_stock_market(nation="英格兰", page_size=50)
    assert view["tick"]["split_count"] == 1
    event = view["tick"]["splits"][0]
    assert event["club_id"] == 1 and event["issue"] == 1
    assert event["shares_after"] > event["shares_before"]
    assert state.stock_store["state"]["nations"]["英格兰"]["shares"]["1"]["s"] == [ordinal]
    stock = next(item for item in view["stocks"] if item["club_id"] == 1)
    assert stock["split_count"] == 1
    assert stock["shares"] == event["shares_after"]
    assert stock["share_base"] == pytest.approx(event["base"])
    assert stock["split_price"] == pytest.approx(
        stock_market.quote(event["base"] * stock_market.SHARE_SPLIT_TRIGGER),
    )
    notice = view["notices"][0]
    assert notice["kind"] == "split" and notice["club_id"] == 1
    assert notice["issue"] == 1
    assert notice["before"] == event["shares_before"]
    assert notice["after"] == event["shares_after"]

    # The order that follows trades the issued capital at the issued price,
    # not the capital the cached board was built on.
    bought = state.buy_stock({"club_id": 1, "qty": 100})
    traded = next(item for item in bought["market"]["stocks"] if item["club_id"] == 1)
    assert traded["shares"] == event["shares_after"]
    assert traded["club_shares"] == event["shares_after"] - 100
    assert traded["price"] == pytest.approx(stock["price"], rel=1e-6)
    assert bought["trade"]["price"] == pytest.approx(stock["price"], rel=1e-6)


def test_an_order_cannot_pass_the_club_book_or_the_order_cap(state):
    open_market(state, nations=["英格兰"])
    view = state.public_stock_market(nation="英格兰", page_size=50)
    stock = next(item for item in view["stocks"] if item["club_id"] == 1)
    holding = state.stock_store["state"]["holdings"]["1"] = {
        "qty": int(stock["shares"]) - 50, "avg_cost": float(stock["price"]),
        "code": stock["code"], "name": stock["name"], "nation": "英格兰",
        "competition": stock["competition"], "last_price": float(stock["price"]),
    }
    # The account already owns all but fifty shares, so the club has nothing
    # left to sell even though the order is inside the per-order cap.
    with pytest.raises(ValueError, match="俱乐部可售股份不足"):
        state.buy_stock({"club_id": 1, "qty": 100})
    holding["qty"] = int(stock["shares"])
    with pytest.raises(ValueError, match="俱乐部已无可售股份"):
        state.buy_stock({"club_id": 1, "qty": 10})
    holding["qty"] = 10
    with pytest.raises(ValueError, match="单笔股数过大"):
        state.buy_stock({"club_id": 1, "qty": int(stock["max_order"]) + 1})
    assert state.sell_stock({"club_id": 1, "qty": 10})["trade"]["qty"] == 10


def test_a_holding_scales_with_the_issue_and_still_trades(state):
    open_market(state, nations=["英格兰"])
    state.buy_stock({"club_id": 2, "qty": 500})
    bought = state.stock_store["state"]["holdings"]["2"]
    cost = round(bought["qty"] * bought["avg_cost"], 2)
    rows = state._stock_market_directory(state.output, "save-1")
    ordinal = stock_market.day_ordinal(GAME_DATE)
    book = state.stock_store["state"]["nations"]["英格兰"]["shares"]["2"]
    book["b"] = round(stock_market.share_price(rows[2], ordinal) / 4, 2)
    with state.lock:
        state.data_version += 1

    view = state.public_stock_market(nation="英格兰", page_size=50)
    event = view["tick"]["splits"][0]
    scale = event["shares_after"] / event["shares_before"]
    assert event["club_id"] == 2
    held = state.stock_store["state"]["holdings"]["2"]
    assert held["qty"] == round(500 * scale)
    assert held["avg_cost"] == pytest.approx(cost / held["qty"], abs=0.01)
    stock = next(item for item in view["stocks"] if item["club_id"] == 2)
    assert stock["qty"] == held["qty"]
    assert stock["club_shares"] == stock["shares"] - held["qty"]
    # The lot is worth the value it had at the quote that forced the issue.
    assert stock["holding_value"] == pytest.approx(500 * event["price"], rel=0.02)
    assert view["holdings"][0]["shares"] == event["shares_after"]
    assert view["holdings"][0]["split_count"] == 1


def test_a_legacy_lot_is_repaired_once_and_the_tick_says_so(state):
    open_market(state, nations=["英格兰"])
    view = state.public_stock_market(nation="英格兰", page_size=50)
    stock = next(item for item in view["stocks"] if item["club_id"] == 6)
    price = float(stock["price"])
    capital = int(stock["shares"])
    assert capital != stock_market.LEGACY_SHARES_OUTSTANDING
    state.buy_stock({"club_id": 6, "qty": 400})
    # Rewrite the lot the way a pre-2.7.5beta save held it: every club was
    # priced against one global share count, so the printed rate is today's
    # rate scaled by the club's capital over that legacy count.
    legacy_price = stock_market.quote(
        price * capital / stock_market.LEGACY_SHARES_OUTSTANDING,
    )
    holding = state.stock_store["state"]["holdings"]["6"]
    holding["avg_cost"] = legacy_price
    holding["last_price"] = legacy_price
    for trade in state.stock_store["state"]["trades"]:
        if trade["club_id"] == 6:
            trade["price"] = legacy_price
            trade["amount"] = stock_market.quote(400 * legacy_price)
    # A save written before the capital model changed carries no repair mark,
    # so the next tick has to read the lot again.
    state.stock_store["state"].pop("capital_repair", None)
    with state.lock:
        state.data_version += 1

    view = state.public_stock_market(nation="英格兰", page_size=50)
    assert view["tick"]["capital_repairs"] == 1
    repaired = state.stock_store["state"]["holdings"]["6"]
    assert repaired["qty"] == round(400 * capital / stock_market.LEGACY_SHARES_OUTSTANDING)
    # The money stays in the lot: the shares it now holds are worth what the
    # legacy lot was worth at the legacy price.
    assert repaired["qty"] * float(stock["price"]) == pytest.approx(
        400 * legacy_price, rel=0.02,
    )
    notice = view["notices"][0]
    assert notice["kind"] == "capital" and notice["club_id"] == 6
    assert notice["before"] == 400
    assert notice["after"] == repaired["qty"]

    # The repair is a one-off; a second launch leaves the lot as it stands.
    with state.lock:
        state.data_version += 1
    again = state.public_stock_market(nation="英格兰", page_size=50)
    assert again["tick"]["capital_repairs"] == 0
    assert state.stock_store["state"]["holdings"]["6"]["qty"] == repaired["qty"]


def test_a_lot_on_another_exchange_still_carries_its_board(state):
    open_market(state)
    state.buy_stock({"club_id": 30, "qty": 200})
    view = state.public_stock_market(nation="英格兰", page_size=50)
    assert all(item["club_id"] != 30 for item in view["stocks"])
    lot = next(item for item in view["holdings"] if item["club_id"] == 30)
    # The ticket draws the candles and the facts of this lot alone, so a
    # holding of another exchange must arrive with its whole board.
    assert lot["qty"] == 200
    assert lot["intrinsic"] > 0
    assert lot["market_cap"] > 0
    assert lot["factor"] > 0
    assert lot["price"] > 0
    assert lot["shares"] > 0
    assert lot["initial_shares"] == lot["shares"]
    assert lot["club_shares"] == lot["shares"] - 200
    assert lot["split_price"] > 0
    assert len(lot["history"]) >= 2
    candle = lot["history"][-1]
    assert candle["c"] > 0 and candle["o"] > 0
    assert candle["l"] <= candle["c"] <= candle["h"]


def test_market_factors_stay_neutral_when_the_market_is_unknown(state):
    state._world_club_directory = lambda output, save_id, native: (_ for _ in ()).throw(
        RuntimeError("目录不可用"),
    )
    assert state._stock_market_factors(state.output, "save-1", [7]) == {7: 1.0}
    assert state._apply_stock_market_factor(
        {"current_valuation": 12}, {7: 1.0}, 7,
    )["market_cap"] == 12


# ---------------------------------------------------------------------------
# The day's direct budget, the settlement slips and the financing appetite
# ---------------------------------------------------------------------------


def test_a_click_spends_the_day_and_the_next_one_buys_a_budget_not_a_lot(state):
    open_market(state)
    board = state.public_stock_market()
    stock = board["stocks"][0]
    club_id = int(stock["club_id"])
    budget = int(stock["max_order"])
    assert budget > 1
    assert stock["direct_used"] == 0
    assert stock["direct_room"] == budget
    assert stock["appetite"]["value"] > 0

    half = budget // 2
    state.buy_stock({"club_id": club_id, "qty": half})
    daily = state.stock_store["state"]["daily"][str(club_id)]
    assert daily["qty"] == half

    # The rest of the allowance still goes through as a click, and the one
    # after that is refused: what is left of a day is a budget, not a lot.
    state.buy_stock({"club_id": club_id, "qty": budget - half})
    assert state.stock_store["state"]["daily"][str(club_id)]["qty"] == budget
    with pytest.raises(ValueError, match="今日市价买入额度"):
        state.buy_stock({"club_id": club_id, "qty": 1})
    order = state.submit_stock_order({"club_id": club_id, "qty": 1, "kind": "block"})
    assert order["order"]["status"] == "pending"

    row = next(
        item for item in state.public_stock_market()["stocks"]
        if int(item["club_id"]) == club_id
    )
    assert row["direct_used"] == budget
    assert row["direct_room"] == 0


def test_a_delivered_application_reaches_the_page_as_a_settlement_slip(state):
    open_market(state)
    stock = state.public_stock_market()["stocks"][0]
    club_id = int(stock["club_id"])
    qty = int(stock["block_order"])
    state.submit_stock_order({"club_id": club_id, "qty": qty, "kind": "block"})
    assert state.public_stock_market()["receipts"] == []

    later = reopen(state, game_date="2026-08-14")
    view = later.public_stock_market()
    assert view["receipts"]
    slip = view["receipts"][0]
    assert slip["kind"] == "block_fill"
    assert slip["club_id"] == club_id
    assert slip["code"] and slip["name"]
    assert 0 < slip["qty"] <= qty
    assert slip["dropped"] == qty - slip["qty"]
    assert slip["stake_before"] == 0.0
    assert slip["stake_after"] > slip["stake_before"]
    assert slip["qty_after"] == slip["qty"]
    assert slip["close_before"] > 0 and slip["close"] > slip["close_before"]
    assert slip["change"] == pytest.approx(
        (slip["close"] - slip["close_before"]) / slip["close_before"], abs=1e-6,
    )
    assert later.stock_store["state"]["receipts"][0]["id"] == slip["id"]


def test_a_refused_financing_is_reported_and_issues_nothing(state):
    open_market(state)
    stock = state.public_stock_market()["stocks"][0]
    club_id = int(stock["club_id"])
    ordinal = int(state._stock_market_ordinal(state.output))
    refusal = {"value": 0.3, "accept": False, "reasons": [{"key": "none"}]}
    original = stock_market.finance_appetite
    try:
        stock_market.finance_appetite = lambda row, listed, day: dict(refusal)
        with pytest.raises(ValueError, match="拒绝了本次融资"):
            state.finance_stock({"club_id": club_id, "qty": int(stock["finance_min"])})
    finally:
        stock_market.finance_appetite = original
    assert state.stock_store["state"]["holdings"] == {}
    assert state.stock_store["state"]["finance"] == {}
    assert ordinal > 0

    # The same offer on a day the club says yes issues the shares and books
    # the money, so the gate is the only difference between the two runs.
    accepted = {"value": 0.9, "accept": True}
    try:
        stock_market.finance_appetite = lambda row, listed, day: dict(accepted)
        result = state.finance_stock({
            "club_id": club_id, "qty": int(stock["finance_min"]),
        })
    finally:
        stock_market.finance_appetite = original
    assert result["trade"]["side"] == "finance"
    assert state.stock_store["state"]["holdings"][str(club_id)]["qty"] == int(
        stock["finance_min"]
    )
    assert state.stock_calls["charge"][-1][1] == "stock_finance"



# ---------------------------------------------------------------------------
# Scope repair and takeovers
# ---------------------------------------------------------------------------


def test_a_league_that_never_listed_is_parked_and_reported(state):
    enable(
        state, nations=[],
        leagues=[["英格兰", "幽灵联赛"], ["英格兰", "英格兰超级联赛"]],
    )
    stored = state.stock_store["state"]
    # 勾选还在：幽灵联赛只是今天开不了盘，等世界目录读进来再自己放行。
    assert {tuple(item) for item in stored["scope"]["leagues"]} == {
        ("英格兰", "幽灵联赛"), ("英格兰", "英格兰超级联赛"),
    }
    assert [list(item) for item in stored["scope_suspended"]] == [["英格兰", "幽灵联赛"]]
    suspend = [row for row in stored["notices"] if row["kind"] == "scope_suspend"]
    assert len(suspend) == 1
    assert suspend[0]["count"] == 1
    assert suspend[0]["competitions"] == [["英格兰", "幽灵联赛"]]
    assert not [row for row in stored["notices"] if row["kind"] == "scope_prune"]

    # 行情板与面板接下来只算挂着的那个交易所：开不了盘的联赛不冒充已开盘。
    board = state.public_stock_market()
    assert board["scope_suspended"] == [["英格兰", "幽灵联赛"]]
    assert [list(item) for item in board["scope"]["leagues"]] == [
        ["英格兰", "英格兰超级联赛"],
    ]
    assert board["enabled"] is True


def test_a_league_the_world_directory_lists_again_resumes(state):
    enable(
        state, nations=[],
        leagues=[["英格兰", "幽灵联赛"], ["英格兰", "英格兰超级联赛"]],
    )
    assert state.stock_store["state"]["scope_suspended"] == [["英格兰", "幽灵联赛"]]

    # 世界目录下一版把幽灵联赛也列进来了：暂存解除，它的俱乐部重新上市。
    listed = [
        {**row, "competition": "幽灵联赛"} for row in club_rows(per_nation=3)
    ]
    session = reopen(state, rows=club_rows() + listed, game_date="2026-08-13")
    session.advance_stock_market()
    stored = session.stock_store["state"]
    assert stored["scope_suspended"] == []
    assert [row for row in stored["notices"] if row["kind"] == "scope_resume"]
    board = session.public_stock_market()
    assert board["scope_suspended"] == []
    assert {tuple(item) for item in board["scope"]["leagues"]} == {
        ("英格兰", "幽灵联赛"), ("英格兰", "英格兰超级联赛"),
    }


def test_a_scan_still_running_never_parks_the_scope(state):
    state.world_club_scanning = True
    enable(
        state, nations=[],
        leagues=[["英格兰", "幽灵联赛"], ["英格兰", "英格兰超级联赛"]],
    )
    stored = state.stock_store["state"]
    leagues = {tuple(item) for item in stored["scope"]["leagues"]}
    assert leagues == {("英格兰", "幽灵联赛"), ("英格兰", "英格兰超级联赛")}
    # 半读进来的目录不是结论：不暂存、不裁剪、连字条都不写。
    assert not stored.get("scope_suspended")
    assert not [
        row for row in stored["notices"]
        if row["kind"] in {"scope_prune", "scope_suspend"}
    ]


def test_a_fixture_window_never_narrows_a_wide_scope(state):
    """当天的赛程窗口只列今天开赛的联赛，它证明不了存档丢了什么。"""
    enable(
        state, nations=[],
        leagues=[
            ["英格兰", "英格兰超级联赛"],
            ["西班牙", "西班牙超级联赛"],
            ["意大利", "意大利超级联赛"],
        ],
    )
    window = [
        {key: value for key, value in row.items() if key != "source"}
        for row in club_rows() if row["nation"] == "英格兰"
    ]
    session = reopen(state, rows=window, game_date="2026-08-16")
    session.advance_stock_market()
    stored = session.stock_store["state"]
    assert {tuple(item) for item in stored["scope"]["leagues"]} == {
        ("英格兰", "英格兰超级联赛"),
        ("西班牙", "西班牙超级联赛"),
        ("意大利", "意大利超级联赛"),
    }
    assert not stored.get("scope_suspended")
    assert not [
        row for row in stored["notices"]
        if row["kind"] in {"scope_prune", "scope_suspend"}
    ]
    # 窗口外的俱乐部没有被当成退市买断：它们只是今天没被读到。
    assert [row for row in stored["trades"] if row["side"] == "delist"] == []
    assert stored["missing"] == {}
    assert not credits(session, "stock_delist_settlement")


def test_a_scope_pruned_by_a_window_comes_back_on_the_world_read(state):
    """旧版把赛程窗口当目录，删掉的联赛在世界俱乐部读进来时回来。"""
    enable(
        state, nations=[],
        leagues=[
            ["英格兰", "英格兰超级联赛"],
            ["西班牙", "西班牙超级联赛"],
            ["意大利", "意大利超级联赛"],
        ],
    )
    stored = state.stock_store["state"]
    stored["scope"] = {"nations": [], "leagues": [["英格兰", "英格兰超级联赛"]]}
    stored["notices"] = [{
        "kind": "scope_prune", "at": "2025-11-30 02:04:54", "date": "2025-11-30",
        "count": 2,
        "competitions": [
            ["西班牙", "西班牙超级联赛"], ["意大利", "意大利超级联赛"],
        ],
    }]

    session = reopen(state, game_date="2026-08-16")
    tick = session.advance_stock_market(session.output)
    session.advance_stock_market()
    restored = session.stock_store["state"]
    assert {tuple(item) for item in restored["scope"]["leagues"]} == {
        ("英格兰", "英格兰超级联赛"),
        ("西班牙", "西班牙超级联赛"),
        ("意大利", "意大利超级联赛"),
    }
    assert restored["scope_pruned_restored"] == 1
    restore = [row for row in restored["notices"] if row["kind"] == "scope_restore"]
    assert len(restore) == 1 and restore[0]["count"] == 2

    # 恢复的交易所当场上线：三个国家的行情板都开得出来。
    board = session.public_stock_market()
    assert {tuple(item) for item in board["scope"]["leagues"]} == {
        ("英格兰", "英格兰超级联赛"),
        ("西班牙", "西班牙超级联赛"),
        ("意大利", "意大利超级联赛"),
    }
    west = session.public_stock_market(nation="西班牙")
    assert len(west["stocks"]) == PER_NATION
    assert {row["nation"] for row in west["stocks"]} == {"西班牙"}


def test_a_stored_scope_folds_onto_the_listed_league_label(state):
    rows = club_rows()
    for row in rows:
        if row["nation"] == "英格兰":
            row["competitions"] = ["英超联赛"]
    state._world_club_directory = lambda output, save_id, native: {"clubs": list(rows)}
    result = state.apply_stock_market_scope({
        "nations": [], "leagues": [["英格兰", "英超联赛"]],
    })
    stored = state.stock_store["state"]
    assert [list(item) for item in stored["scope"]["leagues"]] == [
        ["英格兰", "英格兰超级联赛"],
    ]
    assert result["enabled"] is True
    assert result["listed"] == PER_NATION


def test_the_filter_reports_the_leagues_it_cannot_list(state):
    state.stock_store["state"]["scope"] = {
        "nations": [],
        "leagues": [["英格兰", "幽灵联赛"], ["英格兰", "英格兰超级联赛"]],
    }
    payload = state.stock_market_scope()
    assert payload["unresolved"] == [["英格兰", "幽灵联赛"]]
    # 面板把这根勾当成"在等俱乐部数据"继续勾着，行情板把它留给下一次读取。
    assert payload["suspended"] == [["英格兰", "幽灵联赛"]]
    assert [list(item) for item in payload["scope"]["leagues"]] == [
        ["英格兰", "英格兰超级联赛"],
    ]
    by_name = {row["name"]: row for row in payload["nations"]}
    assert by_name["英格兰"]["selected_leagues"] == 1
    assert by_name["英格兰"]["selected"] is False
    assert by_name["英格兰"]["partial"] is True


def test_an_acquired_club_hands_its_register_to_the_group(state, monkeypatch):
    open_market(state)
    monkeypatch.setattr(
        fm_odds_web, "account_acquired_clubs",
        lambda scope_id, output, include_suspended=False: [
            {"id": 4, "acquisition_price": 123_456_789, "ownership_active": True},
        ],
    )
    handover = state._stock_market_sync_club_ownership("scope-1", state.output, team_id=4)
    assert handover["listed"] is True
    assert handover["granted"] == 1
    assert handover["handover"]["club_id"] == 4

    stored = state.stock_store["state"]
    lot = stored["holdings"]["4"]
    assert lot["source"] == "takeover"
    assert lot["takeover_price"] == 123_456_789

    market = state.public_stock_market(nation="英格兰")
    row = next(item for item in market["stocks"] if item["club_id"] == 4)
    assert row["owned"] is True
    assert row["qty"] == row["shares"]
    assert row["club_shares"] == 0
    # 收购后集团仍可卖回给俱乐部，但 51% 的控制股始终保留。
    keep = stock_market.takeover_keep_qty(row["shares"])
    assert row["keep_shares"] == keep
    assert row["sellable"] == row["shares"] - keep

    # 登记册全部在集团名下，俱乐部手里没有股份，回收无从谈起。
    with pytest.raises(ValueError, match="俱乐部手中已无股份可回收"):
        state.buy_stock({"club_id": 4, "qty": 1})

    # 卖回一部分后，同一个交易界面就能把股份回收回集团名下。
    state.sell_stock({"club_id": 4, "qty": keep // 2})
    market = state.public_stock_market(nation="英格兰")
    row = next(item for item in market["stocks"] if item["club_id"] == 4)
    capital = row["shares"]
    assert row["club_shares"] == keep // 2
    assert row["buyback_room"] == keep // 2
    assert row["buy_room"] == keep // 2

    recovered = state.buy_stock({"club_id": 4, "qty": 10})
    assert recovered["trade"]["side"] == "buy"
    assert recovered["trade"]["qty"] == 10
    lot = state.stock_store["state"]["holdings"]["4"]
    assert lot["qty"] == capital - keep // 2 + 10
    assert lot["takeover_sold"] == keep // 2 - 10


def test_selling_a_club_takes_its_register_back_from_the_group(state, monkeypatch):
    open_market(state)
    owned = [{"id": 4, "acquisition_price": 7_000_000, "ownership_active": True}]
    monkeypatch.setattr(
        fm_odds_web, "account_acquired_clubs",
        lambda scope_id, output, include_suspended=False: list(owned),
    )
    state._stock_market_sync_club_ownership("scope-1", state.output, team_id=4)
    assert "4" in state.stock_store["state"]["holdings"]

    owned.clear()
    released = state._stock_market_release_club("scope-1", 4)
    assert released["released"] is True
    assert "4" not in state.stock_store["state"]["holdings"]
    market = state.public_stock_market(nation="英格兰")
    row = next(item for item in market["stocks"] if item["club_id"] == 4)
    assert row["owned"] is False
