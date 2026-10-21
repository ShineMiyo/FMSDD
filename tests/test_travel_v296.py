from __future__ import annotations

from datetime import date
from unittest.mock import patch

from tools import life_interactions as interactions
from tools import life_travel


DAY = date(2026, 1, 5).toordinal()


def _state_with_person() -> tuple[dict, dict]:
    state = interactions.normalize_state({}, DAY)
    state["people"]["1"] = {
        "id": 1, "name": "Test", "age": 30, "female": True,
        "traits": {}, "team_id": 0, "team_name": "",
        "positions": [], "source": "encounter", "npc": True,
    }
    state["relationships"]["1"] = interactions._normalize_relationship(
        {"person_name": "Test", "romance_stage": "partner", "intimacy": 60},
        1,
    )
    state["action_points"]["current"] = 12
    return state, state["relationships"]["1"]


def test_catalog_reuses_nine_countries_and_sixty_eight_cities() -> None:
    payload = life_travel.public_catalog()
    assert len(payload["countries"]) == 9
    assert payload["city_count"] == 68
    assert payload["place_count"] >= payload["city_count"] * 5
    assert [row["code"] for row in payload["countries"]] == [
        "CN", "GB", "FR", "DE", "ES", "BE", "NL", "JP", "KR",
    ]
    assert life_travel.resolve_destination("CN", "shanghai") is not None
    assert life_travel.resolve_destination("CN", "not-a-city") is None


def test_asset_level_is_the_only_encounter_bonus() -> None:
    assert life_travel.encounter_chance(1) == 0.45
    assert life_travel.encounter_chance(7) == 0.57
    assert life_travel.encounter_chance(12) == 0.67
    assert life_travel.encounter_chance(99) == 0.69
    assert life_travel.asset_bonus(12) == 0.22


def test_fictional_person_is_marked_and_hidden_until_contact() -> None:
    state = interactions.normalize_state({}, DAY)
    person, relation = interactions.create_encounter_person(
        state, country="JP", city="kyoto", city_name_zh="京都",
        city_name_en="Kyoto", place="鸭川", day=DAY,
    )
    assert person["source"] == "encounter"
    assert person["npc"] is True
    assert person["met_city"] == "kyoto"
    assert relation["contact_known"] is False
    assert interactions.public_view(
        state, game_date="2026-01-05", day=DAY,
    )["relationships"] == []
    with patch("tools.life_interactions.random.random", return_value=0.0):
        result = interactions.travel_ask_contact(state, person["id"], DAY)
    assert result["success"] is True
    assert state["relationships"][str(person["id"])]["contact_known"] is True
    assert len(interactions.public_view(
        state, game_date="2026-01-05", day=DAY,
    )["relationships"]) == 1


def test_intimacy_items_and_protection_are_applied() -> None:
    state, relationship = _state_with_person()
    result = interactions.intimacy_plan(
        state, 1, DAY, "playful_night", item_sku="intimate_toy",
    )
    assert result["item_sku"] == "intimate_toy"
    assert result["item_bonus"]
    assert result["protection"] == ""

    state, relationship = _state_with_person()
    result = interactions.intimacy_plan(
        state, 1, DAY, "stay_close", protection="condom",
    )
    assert result["protection"] == "condom"
    assert relationship["contraception"]["sku"] == "intimate_condoms"

    try:
        interactions.intimacy_plan(state, 1, DAY, "playful_night")
    except ValueError as error:
        assert "道具" in str(error)
    else:
        raise AssertionError("item action accepted without an item")


def test_travel_routes_and_tab_are_wired() -> None:
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    api = (root / "src" / "fm_odds_web.py").read_text(encoding="utf-8")
    page = (root / "src" / "web" / "interactions_page.js").read_text(encoding="utf-8")
    styles = (root / "src" / "web" / "interactions.css").read_text(encoding="utf-8")
    html = (root / "src" / "web" / "index.html").read_text(encoding="utf-8")
    assert "def public_life_travel" in api
    assert "def travel_life_go_out" in api
    assert "def travel_life_encounter" in api
    assert '"/api/life/interactions/travel": lambda' in api
    assert '"/api/life/interactions/travel/go-out": "travel_life_go_out"' in api
    assert '"/api/life/interactions/travel/encounter": "travel_life_encounter"' in api
    assert '["travel", "life.interactions.tabs.travel", "plane"]' in page
    assert "function renderTravel" in page
    assert "data-travel-encounter" in page
    assert "interaction-travel-hero" in styles
    assert "/i18n.travel.v296.js" in html


def test_fictional_share_is_deliberate_not_only_a_fallback() -> None:
    with patch("tools.life_travel.random.random", return_value=0.0):
        assert life_travel.prefer_fictional_encounter() is True
    with patch("tools.life_travel.random.random", return_value=0.99):
        assert life_travel.prefer_fictional_encounter() is False


def test_travel_view_reads_current_asset_level() -> None:
    state = interactions.normalize_state({}, DAY)
    view = interactions.travel_public_view(state, {"current_level": 7}, DAY)
    assert view["asset_bonus"] == 0.12
    assert view["encounter_chance"] == 0.57


def test_obedience_and_pregnancy_flags_apply_to_new_actions() -> None:
    state, relationship = _state_with_person()
    result = interactions.intimacy_plan(
        state, 1, DAY, "blindfold_night", item_sku="intimate_blindfold",
    )
    assert result["obedience_gain"] == 8.0
    assert result["obedience_after"] == 8.0
    assert result["pregnancy_chance"] >= 0
    assert relationship["obedience"] == 8.0
    assert "future_plan" not in interactions.INTIMATE_ACTIONS


def test_person_affiliation_call_sites_are_not_malformed() -> None:
    from pathlib import Path as _Path
    root = _Path(__file__).resolve().parents[1]
    page = (root / "src" / "web" / "interactions_page.js").read_text(encoding="utf-8")
    assert "selected.personAffiliation" not in page
    helper = page.split("function personAffiliation(person) {", 1)[1].split(
        "function personNationality(person)", 1,
    )[0]
    assert "return String(person.team_name" in helper
    assert "return String(personAffiliation" not in helper
