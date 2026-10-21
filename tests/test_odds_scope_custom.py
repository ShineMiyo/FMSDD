from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from tools import app_settings
from tools.preview_cup_odds import (
    fixture_in_custom_scope,
    filter_fixture_rows_for_odds,
    odds_scope_signature,
)
from fm_odds_web import MODEL_VERSION, expected_odds_scope_signature, startup_cache_validation


ROOT = (Path(__file__).resolve().parents[1] / "src")


def _scope(nations, leagues, *, directory=True):
    payload = {"nations": nations, "leagues": leagues}
    if directory:
        payload["competition_nation"] = {"英超": "英格兰", "足总杯": "英格兰"}
        payload["competition_id_nation"] = {100: "英格兰", 200: "西班牙"}
        payload["club_nation"] = {1: "英格兰", 2: "西班牙"}
        payload["club_league"] = {1: ["英格兰", "英超"], 2: ["西班牙", "西甲"]}
    return payload


def _row(day, competition_id, competition, home_id, away_id):
    return (
        type("Fixture", (), {"match_date": day})(),
        {"id": competition_id, "name": competition},
        {"id": home_id},
        {"id": away_id},
    )


class OddsScopeSelectionTests(unittest.TestCase):
    def test_selection_is_sorted_deduplicated_and_blank_safe(self):
        nations, leagues = app_settings.normalize_odds_scope_selection(
            ["西班牙", " 英格兰 ", "英格兰", "", None],
            [
                ["西班牙", "西甲"],
                ["英格兰", "英超"],
                {"nation": "英格兰", "competition": "英超"},
                ["英格兰", ""],
                ["", "意甲"],
                "nonsense",
                ["英格兰", "英冠"],
            ],
        )

        self.assertEqual(nations, ["英格兰", "西班牙"])
        self.assertEqual(
            leagues, [["英格兰", "英冠"], ["英格兰", "英超"], ["西班牙", "西甲"]],
        )

    def test_scope_limits_drop_excess_entries_instead_of_failing(self):
        nations, leagues = app_settings.normalize_odds_scope_selection(
            [f"国家{index}" for index in range(app_settings.MAX_ODDS_SCOPE_NATIONS + 25)],
            [
                ["国家", f"联赛{index}"]
                for index in range(app_settings.MAX_ODDS_SCOPE_LEAGUES + 25)
            ],
        )

        self.assertEqual(len(nations), app_settings.MAX_ODDS_SCOPE_NATIONS)
        self.assertEqual(len(leagues), app_settings.MAX_ODDS_SCOPE_LEAGUES)

    def test_settings_default_to_the_whole_window_and_no_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            with patch.object(app_settings, "SETTINGS_PATH", path):
                settings = app_settings.load_settings()

        self.assertEqual(settings["odds_scope"], "all")
        self.assertEqual(settings["odds_nations"], [])
        self.assertEqual(settings["odds_leagues"], [])

    def test_custom_scope_and_selection_round_trip_through_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            with patch.object(app_settings, "SETTINGS_PATH", path):
                saved = app_settings.set_odds_reading(
                    "custom", 14, 8,
                    nations=["英格兰", "西班牙"],
                    leagues=[["英格兰", "英超"], ["西班牙", "西甲"]],
                )
                reloaded = app_settings.load_settings()

        self.assertEqual(saved["odds_scope"], "custom")
        self.assertEqual(reloaded["odds_scope"], "custom")
        self.assertEqual(reloaded["odds_nations"], ["英格兰", "西班牙"])
        self.assertEqual(reloaded["odds_leagues"], [["英格兰", "英超"], ["西班牙", "西甲"]])

    def test_preset_switch_keeps_the_saved_selection_for_later(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            with patch.object(app_settings, "SETTINGS_PATH", path):
                app_settings.set_odds_reading(
                    "custom", 7, 8, nations=["英格兰"], leagues=[["英格兰", "英超"]],
                )
                preset = app_settings.set_odds_reading("famous", 7, 8)
                reloaded = app_settings.load_settings()

        self.assertEqual(preset["odds_scope"], "famous")
        self.assertEqual(reloaded["odds_nations"], ["英格兰"])
        self.assertEqual(reloaded["odds_leagues"], [["英格兰", "英超"]])

    def test_unknown_scope_is_rejected_and_unknown_stored_scope_falls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            with patch.object(app_settings, "SETTINGS_PATH", path):
                with self.assertRaisesRegex(ValueError, "盘口读取范围无效"):
                    app_settings.set_odds_reading("nonsense", 7, 8)
                path.write_text('{"odds_scope":"nonsense"}', encoding="utf-8")
                self.assertEqual(app_settings.load_settings()["odds_scope"], "all")


class OddsScopeSignatureTests(unittest.TestCase):
    def test_presets_return_an_empty_signature(self):
        self.assertEqual(odds_scope_signature([], []), "")
        self.assertEqual(odds_scope_signature(None, None), "")

    def test_signature_ignores_tick_order_but_tracks_membership(self):
        first = odds_scope_signature(
            ["英格兰", "西班牙"], [["西班牙", "西甲"], ["英格兰", "英超"]],
        )
        second = odds_scope_signature(
            ["西班牙", "英格兰"], [{"nation": "英格兰", "competition": "英超"},
                                    ["西班牙", "西甲"]],
        )

        self.assertEqual(first, second)
        self.assertNotEqual(first, odds_scope_signature(["英格兰"], [["英格兰", "英超"]]))

    def test_expected_signature_is_empty_for_presets(self):
        self.assertEqual(
            expected_odds_scope_signature({"odds_scope": "famous"}), "",
        )
        self.assertEqual(
            expected_odds_scope_signature(
                {"odds_scope": "custom", "odds_nations": ["英格兰"], "odds_leagues": []},
            ),
            odds_scope_signature(["英格兰"], []),
        )


class FixtureInCustomScopeTests(unittest.TestCase):
    def test_unticked_scope_keeps_the_whole_window(self):
        scope = _scope([], [])

        self.assertTrue(fixture_in_custom_scope({"name": "英超", "id": 100}, 1, 2, scope))
        self.assertTrue(fixture_in_custom_scope({"name": "海外", "id": 999}, 7, 8, scope))

    def test_missing_directory_keeps_the_whole_window(self):
        scope = _scope(["英格兰"], [], directory=False)

        self.assertTrue(fixture_in_custom_scope({"name": "英超", "id": 100}, 1, 2, scope))

    def test_competition_nation_matches_a_ticked_nation(self):
        scope = _scope(["英格兰"], [])

        self.assertTrue(fixture_in_custom_scope({"name": "英超", "id": 100}, 1, 2, scope))
        self.assertFalse(fixture_in_custom_scope({"name": "荷甲", "id": 300}, 5, 6, scope))

    def test_competition_id_lookup_works_when_the_name_is_not_indexed(self):
        scope = _scope([], [["西班牙", "西甲"]], directory=False)
        scope["competition_id_nation"] = {200: "西班牙"}

        self.assertTrue(fixture_in_custom_scope({"name": "西甲", "id": 200}, 3, 4, scope))
        self.assertFalse(fixture_in_custom_scope({"name": "英超", "id": 100}, 3, 4, scope))

    def test_club_league_keeps_domestic_cups_and_continental_ties(self):
        scope = _scope([], [["英格兰", "英超"]])

        self.assertTrue(fixture_in_custom_scope({"name": "足总杯", "id": 500}, 1, 3, scope))
        self.assertFalse(fixture_in_custom_scope({"name": "国王杯", "id": 600}, 3, 4, scope))

    def test_ticked_nation_keeps_clubs_from_other_competitions_of_that_nation(self):
        scope = _scope(["英格兰"], [])
        scope["club_nation"][9] = "英格兰"
        scope["club_league"][9] = ["英格兰", "英冠"]

        self.assertTrue(fixture_in_custom_scope({"name": "联赛杯", "id": 700}, 9, 2, scope))


class FilterFixtureRowsForOddsTests(unittest.TestCase):
    def test_custom_scope_drops_unticked_competitions_and_keeps_managed_club(self):
        rows = [
            _row(date(2026, 10, 20), 100, "英超", 1, 2),
            _row(date(2026, 10, 20), 600, "国王杯", 3, 4),
            _row(date(2026, 10, 21), 600, "国王杯", 3, 42),
            _row(date(2026, 11, 30), 100, "英超", 1, 2),
        ]

        kept = filter_fixture_rows_for_odds(
            rows, "custom", date(2026, 10, 31),
            managed_team_ids={42}, custom_scope=_scope(["英格兰"], []),
        )

        self.assertEqual(
            [(row[1]["name"], row[2]["id"]) for row in kept],
            [("英超", 1), ("国王杯", 3)],
        )

    def test_missing_custom_scope_keeps_the_window_and_still_applies_the_window(self):
        rows = [
            _row(date(2026, 10, 20), 600, "国王杯", 3, 4),
            _row(date(2026, 11, 30), 600, "国王杯", 3, 4),
        ]

        kept = filter_fixture_rows_for_odds(rows, "custom", date(2026, 10, 31))

        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0][1]["name"], "国王杯")


class StartupCacheSignatureTests(unittest.TestCase):
    def _snapshot(self, settings, signature=None):
        snapshot = {
            "matches": [{"fixture_date": "2028-06-06"}],
            "save_instance_id": "save-123",
            "game_date": "2028-06-06",
            "fixture_scan_mode": "heap",
            "model_version": MODEL_VERSION,
            "odds_days": 7,
            "odds_scope": settings["odds_scope"],
        }
        if signature is not None:
            snapshot["odds_scope_signature"] = signature
        return snapshot

    def test_preset_snapshot_without_a_signature_still_validates(self):
        settings = {"odds_scope": "famous", "odds_days": 7}

        valid, reason = startup_cache_validation(
            self._snapshot(settings), "save-123", {"date": "2028-06-06"}, settings,
        )

        self.assertTrue(valid)
        self.assertEqual(reason, "valid")

    def test_custom_snapshot_validates_only_with_the_matching_signature(self):
        settings = {
            "odds_scope": "custom", "odds_days": 7,
            "odds_nations": ["英格兰"], "odds_leagues": [["英格兰", "英超"]],
        }
        matching = odds_scope_signature(["英格兰"], [["英格兰", "英超"]])

        valid, reason = startup_cache_validation(
            self._snapshot(settings, matching), "save-123", {"date": "2028-06-06"}, settings,
        )
        self.assertTrue(valid)

        stale, stale_reason = startup_cache_validation(
            self._snapshot(settings, odds_scope_signature(["西班牙"], [])),
            "save-123", {"date": "2028-06-06"}, settings,
        )
        self.assertFalse(stale)
        self.assertEqual(stale_reason, "settings_changed")

        missing, missing_reason = startup_cache_validation(
            self._snapshot(settings), "save-123", {"date": "2028-06-06"}, settings,
        )
        self.assertFalse(missing)
        self.assertEqual(missing_reason, "settings_changed")


class OddsScopeFrontendTests(unittest.TestCase):
    def setUp(self):
        self.html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        self.source = (ROOT.parent / "src" / "fm_odds_web.py").read_text(encoding="utf-8")

    def test_scope_picker_offers_a_custom_option_and_a_tick_list(self):
        scope = self.html.split('id="odds-scope"', 1)[1].split("</select>", 1)[0]

        self.assertIn('<option value="custom"', scope)
        self.assertIn('id="odds-scope-custom"', self.html)
        self.assertIn('id="odds-scope-picker"', self.html)
        self.assertIn('id="odds-scope-count"', self.html)

    def test_frontend_posts_the_selection_and_reuses_the_exchange_picker(self):
        for needle in (
            "oddsScopeCycleNation", "/api/settings/odds-scope",
            '"odds-scope-dialog"', "odds_nations", "odds_leagues",
        ):
            self.assertIn(needle, self.app, f"app.js is missing {needle}")

    def test_the_worldwide_row_reuses_the_exchange_picker_machinery(self):
        for needle in (
            "async function oddsScopeEnsureTables()",
            "function oddsScopeWorldApply(mode)",
            "async function oddsScopeCycleWorld()",
            "async function oddsScopeAdoptWorld()",
            "stockScopeWorldNext(oddsScopeWorldState())",
            "await oddsScopeAdoptWorld();",
            "/api/stock/scope/leagues?nation=*",
        ):
            self.assertIn(needle, self.app, f"app.js is missing {needle}")

    def test_settings_route_is_registered(self):
        for needle in ('"/api/settings/odds-scope"', 'payload.get("nations")',
                       'payload.get("leagues")'):
            self.assertIn(needle, self.source, f"fm_odds_web.py is missing {needle}")


if __name__ == "__main__":
    unittest.main()
