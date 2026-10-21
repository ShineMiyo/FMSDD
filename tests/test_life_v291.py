from __future__ import annotations

import unittest
from copy import deepcopy
from datetime import date
from pathlib import Path
from unittest.mock import patch

from tools import life_interactions as interactions
from tools import life_system

ROOT = Path(__file__).resolve().parents[1]
DAY = date(2026, 1, 5).toordinal()


def make_state(gender: str, female: bool = True) -> tuple[dict, dict]:
    state = interactions.normalize_state({}, DAY)
    interactions.save_profile(state, {"name": "Player", "age": 30, "gender": gender}, DAY)
    interactions.cache_search_row(
        state,
        {
            "id": 1001,
            "name": "NPC",
            "age": 25,
            "female": female,
            "nationality": "England",
            "team_id": 10,
            "team_name": "Test Club",
            "positions": ["ST"],
            "ca": 140,
            "pa": 160,
            "world_reputation": 4000,
            "object_type": "player",
        },
        DAY,
    )
    relationship = state["relationships"]["1001"]
    relationship.update({
        "social_stage": "close_friend",
        "familiarity": 90,
        "affection": 90,
        "trust": 90,
        "respect": 90,
        "attraction": 90,
    })
    state["action_points"]["current"] = 12
    return state, relationship


class RelationshipLineTests(unittest.TestCase):
    def test_gender_matrix_matches_the_requested_lines(self) -> None:
        cases = [
            ("male", True, {
                "romance": True, "sisterhood": True, "brotherhood": False,
                "brotherhood_direct": False, "brotherhood_kindred": False,
            }),
            ("male", False, {
                "romance": False, "sisterhood": False, "brotherhood": True,
                "brotherhood_direct": True, "brotherhood_kindred": False,
            }),
            ("female", True, {
                "romance": False, "sisterhood": True, "brotherhood": False,
                "brotherhood_direct": False, "brotherhood_kindred": False,
            }),
            ("female", False, {
                "romance": True, "sisterhood": False, "brotherhood": True,
                "brotherhood_direct": False, "brotherhood_kindred": True,
            }),
            ("nonbinary", True, {
                "romance": True, "sisterhood": True, "brotherhood": True,
                "brotherhood_direct": True, "brotherhood_kindred": False,
            }),
            ("nonbinary", False, {
                "romance": True, "sisterhood": True, "brotherhood": True,
                "brotherhood_direct": True, "brotherhood_kindred": False,
            }),
        ]
        for gender, female, expected in cases:
            state, relationship = make_state(gender, female)
            self.assertEqual(
                interactions.relationship_branch_capabilities(state, relationship),
                expected,
            )

    def test_branch_options_are_gendered(self) -> None:
        state, relationship = make_state("male", True)
        options = interactions.relationship_progress(state, relationship)["branch"]["options"]
        self.assertEqual(
            [row["target"] for row in options],
            ["ambiguous", "bond_partner_sisterhood"],
        )
        state, relationship = make_state("male", False)
        options = interactions.relationship_progress(state, relationship)["branch"]["options"]
        self.assertEqual([row["target"] for row in options], ["bond_partner_brotherhood"])
        state, relationship = make_state("nonbinary", True)
        options = interactions.relationship_progress(state, relationship)["branch"]["options"]
        self.assertEqual(
            [row["target"] for row in options],
            ["ambiguous", "bond_partner_sisterhood", "bond_partner_brotherhood"],
        )

    def test_level_and_tone_are_separate(self) -> None:
        state, relationship = make_state("male", True)
        self.assertEqual(interactions.relationship_level(relationship), "close_friend")
        self.assertEqual(interactions.relationship_tone(relationship)["key"], "trusted")
        relationship.update({"bond_stage": "best_friend", "bond_path": "bond"})
        self.assertEqual(interactions.relationship_level(relationship), "best_friend")
        relationship.update({"romance_stage": "partner", "bond_stage": "none"})
        self.assertEqual(interactions.relationship_level(relationship), "couple")

    def test_sisterhood_chain_reaches_best_friend(self) -> None:
        state, relationship = make_state("male", True)
        for target, expected in (
            ("bond_partner_sisterhood", "partner"),
            ("bond_kindred", "kindred"),
            ("bond_best_friend", "best_friend"),
        ):
            state["action_points"]["current"] = 12
            with patch.object(interactions, "_stable_unit", return_value=0.0):
                result = interactions.relationship_plan(state, 1001, DAY, target)
            self.assertTrue(result["success"])
            self.assertEqual(result["bond_stage"], expected)
            self.assertEqual(relationship["bond_line"], "sisterhood")

    def test_brotherhood_chain_reaches_sworn_brother(self) -> None:
        state, relationship = make_state("male", False)
        for target, expected in (
            ("bond_partner_brotherhood", "partner"),
            ("bond_brother", "brother"),
            ("bond_sworn_brother", "sworn_brother"),
        ):
            state["action_points"]["current"] = 12
            with patch.object(interactions, "_stable_unit", return_value=0.0):
                result = interactions.relationship_plan(state, 1001, DAY, target)
            self.assertTrue(result["success"])
            self.assertEqual(result["bond_stage"], expected)
            self.assertEqual(relationship["bond_line"], "brotherhood")

    def test_female_male_brotherhood_uses_kindred_and_ends_at_brother(self) -> None:
        state, relationship = make_state("female", False)
        for target, expected in (
            ("bond_partner_brotherhood", "partner"),
            ("bond_kindred", "kindred"),
            ("bond_brother", "brother"),
        ):
            state["action_points"]["current"] = 12
            with patch.object(interactions, "_stable_unit", return_value=0.0):
                result = interactions.relationship_plan(state, 1001, DAY, target)
            self.assertTrue(result["success"])
            self.assertEqual(result["bond_stage"], expected)
        self.assertEqual(relationship["bond_variant"], "brotherhood_kindred")
        with self.assertRaisesRegex(ValueError, "兄弟线"):
            interactions.relationship_plan(state, 1001, DAY, "bond_sworn_brother")

    def test_romance_cannot_start_from_a_bond_line(self) -> None:
        state, _relationship = make_state("male", True)
        state["action_points"]["current"] = 12
        with patch.object(interactions, "_stable_unit", return_value=0.0):
            interactions.relationship_plan(state, 1001, DAY, "bond_partner_sisterhood")
        with self.assertRaisesRegex(ValueError, "朋友线"):
            interactions.relationship_plan(state, 1001, DAY, "ambiguous")


class BulkLifePlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = life_system.normalize_state({})
        self.state.setdefault("garages", {})["lot"] = {
            "id": "lot", "kind": "standalone", "category": "standalone",
            "capacity": 300, "name_zh": "Test garage", "name_en": "Test garage",
        }

    def test_batch_dealer_purchase_allocates_distinct_slots(self) -> None:
        cars = life_system.car_catalog()["cars"][:3]
        plan = life_system.buy_vehicle_batch_plan(self.state, cars, "lot", DAY)
        self.assertEqual(plan["count"], 3)
        self.assertEqual(len({row["record"]["id"] for row in plan["plans"]}), 3)
        self.assertTrue(all(row["record"]["garage_id"] == "lot" for row in plan["plans"]))
        for row in plan["plans"]:
            life_system.commit_buy_vehicle(self.state, row, DAY)
        self.assertEqual(len(self.state["vehicles"]), 3)

    def test_gacha_multiplier_uses_ten_pack_pricing(self) -> None:
        tier = life_system.gacha_tiers()[0]
        plan = life_system.gacha_plan(self.state, tier["id"], 100, "lot", DAY, "seed")
        self.assertEqual(plan["draws"], 100)
        self.assertEqual(plan["cost"], int(tier["ten_ticket_price"]) * 10)
        self.assertEqual(len(plan["records"]), 100)

    def test_high_capacity_garages_can_be_generated(self) -> None:
        city = {
            "id": "v291-test-city", "name_zh": "Test", "name_en": "Test",
            "lat": 51.5, "lng": -0.1,
            "districts": [
                {
                    "id": f"d{index}", "name_zh": f"D{index}", "name_en": f"D{index}",
                    "lat": 51.5 + index * 0.01, "lng": -0.1 + index * 0.01,
                    "residential": 1000, "commercial": 1000, "industrial": 1000,
                }
                for index in range(8)
            ],
        }
        pack = life_system.generate_city_pack(city)
        capacities = [
            int(parcel.get("parking_spaces") or 0)
            for parcel in pack["parcels"] if parcel.get("kind") == "garage"
        ]
        self.assertTrue(capacities)
        self.assertGreaterEqual(max(capacities), 64)


class V291StaticTests(unittest.TestCase):
    def test_version_metadata_matches_v291(self) -> None:
        api = (ROOT / "src/fm_odds_web.py").read_text(encoding="utf-8")
        host = (ROOT / "src/desktop/WebViewHost.csproj").read_text(encoding="utf-8")
        title = (ROOT / "src/desktop/WebViewHost.cs").read_text(encoding="utf-8")
        self.assertIn('PRODUCT_VERSION = "V', api)
        self.assertIn("APP_VERSION = PRODUCT_VERSION if FROZEN", api)
        self.assertIn("<Version>", host)
        self.assertIn("FMSDD V", title)

    def test_frontend_exposes_the_new_controls(self) -> None:
        life = (ROOT / "src/web/life_page.js").read_text(encoding="utf-8")
        page = (ROOT / "src/web/interactions_page.js").read_text(encoding="utf-8")
        html = (ROOT / "src/web/index.html").read_text(encoding="utf-8")
        self.assertIn('data-life-action="open-map-bulk"', life)
        self.assertIn('data-life-action="open-garage-bulk"', life)
        self.assertIn('data-life-action="buy-filtered-cars"', life)
        self.assertIn('data-life-action="gacha-multiplier"', life)
        self.assertIn('["standalone", "standalone"], ["property", "property"]', life)
        self.assertIn('data-interaction-action="open-asset-level"', page)
        self.assertIn("function renderBranchPanel", page)
        self.assertIn('id="life-map-bulk-dialog"', html)
        self.assertIn('id="life-garage-bulk-dialog"', html)
        self.assertIn('id="life-interactions-asset-level-dialog"', html)


if __name__ == "__main__":
    unittest.main()

