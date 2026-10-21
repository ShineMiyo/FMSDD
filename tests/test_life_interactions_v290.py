from __future__ import annotations

import unittest
from copy import deepcopy
from datetime import date
from unittest.mock import patch

from tools import life_interactions as interactions
from tools import life_system


DAY = date(2026, 1, 5).toordinal()


def player_row(player_id: int = 1001, *, name: str = "Test Player") -> dict:
    return {
        "id": player_id,
        "name": name,
        "age": 24,
        "female": True,
        "nationality_id": 200,
        "nationality": "England",
        "team_id": 10,
        "team_name": "Test Club",
        "positions": ["ST"],
        "ca": 140,
        "pa": 160,
        "world_reputation": 4000,
        "object_type": "player",
        "date_of_birth": "2002-03-04",
    }


def state_with_people(*rows: dict) -> dict:
    state = interactions.normalize_state({}, DAY)
    interactions.save_profile(state, {"name": "Player", "age": 30}, DAY)
    for row in rows or (player_row(),):
        interactions.cache_search_row(state, row, DAY)
    return state


def set_relationship(state: dict, player_id: int, **values) -> dict:
    relationship = state["relationships"][str(player_id)]
    relationship.update(values)
    relationship["social_stage"] = interactions.social_stage_for(relationship)
    return relationship


class SignedIntimacyTests(unittest.TestCase):
    def test_negative_intimacy_uses_distinct_bands_and_is_persisted(self) -> None:
        self.assertEqual(interactions.intimacy_band(-100), "fractured")
        self.assertEqual(interactions.intimacy_band(-70), "hostile")
        self.assertEqual(interactions.intimacy_band(-30), "strained")
        self.assertEqual(interactions.intimacy_band(-5), "cold")
        self.assertEqual(interactions.intimacy_band(0), "new")

        state = state_with_people()
        relationship = set_relationship(
            state, 1001, romance_stage="partner", intimacy=-30,
        )
        interactions.settle_periodic_events(state, DAY)
        normalized = interactions.normalize_state(state, DAY)["relationships"]["1001"]
        self.assertEqual(normalized["intimacy"], -30.0)
        self.assertEqual(normalized["intimacy_negative_since"], DAY)
        self.assertEqual(relationship["intimacy_negative_since"], DAY)

    def test_severe_negative_intimacy_queues_a_crisis_event(self) -> None:
        state = state_with_people()
        set_relationship(
            state, 1001, romance_stage="partner", intimacy=-75,
        )
        self.assertTrue(interactions.settle_periodic_events(state, DAY))
        event = state["events"][-1]
        self.assertEqual(event["kind"], "relationship_crisis")
        self.assertEqual(event["options"], ["repair", "accept_separation"])

        result = interactions.event_plan(
            state, event["id"], "accept_separation", DAY,
        )
        self.assertTrue(result["success"])
        self.assertEqual(
            state["relationships"]["1001"]["romance_stage"], "none",
        )

    def test_failed_crisis_repair_reports_failure_and_ends_romance(self) -> None:
        state = state_with_people()
        relationship = set_relationship(
            state, 1001, romance_stage="partner", intimacy=-75,
        )
        event = interactions._queue_event(
            state, kind="relationship_crisis",
            person=state["people"]["1001"], day=DAY, available_day=DAY,
            data={"intimacy": -75}, options=["repair", "accept_separation"],
        )
        with patch("tools.life_interactions._stable_unit", return_value=1.0):
            result = interactions.event_plan(
                state, event["id"], "repair", DAY,
            )
        self.assertFalse(result["success"])
        self.assertEqual(result["event"]["resolution"]["success"], False)
        self.assertEqual(relationship["romance_stage"], "none")
        self.assertEqual(
            result["detail"]["ended_stage"], "partner",
        )


class PregnancyAndExposureTests(unittest.TestCase):
    def test_due_pregnancy_can_be_kept_and_creates_a_child(self) -> None:
        state = state_with_people()
        relationship = set_relationship(
            state, 1001, romance_stage="partner", intimacy=55,
        )
        relationship["pregnancy"] = {
            "status": "expecting", "conceived_day": DAY - 280,
            "due_day": DAY, "due_early": DAY - 28, "due_late": DAY + 21,
            "decision": "kept", "kept": True, "event_id": "",
        }
        self.assertTrue(interactions.settle_periodic_events(state, DAY))
        self.assertEqual(relationship["pregnancy"]["status"], "born")
        self.assertEqual(len(relationship["children"]), 1)
        self.assertGreater(relationship["intimacy"], 55)
        self.assertTrue(relationship["children"][0]["id"].startswith("child-"))

    def test_ending_a_pregnancy_sharply_reduces_intimacy(self) -> None:
        state = state_with_people()
        relationship = set_relationship(
            state, 1001, romance_stage="partner", intimacy=55,
        )
        relationship["pregnancy"] = {
            "status": "expecting", "conceived_day": DAY,
            "due_day": DAY + 280, "due_early": DAY + 252, "due_late": DAY + 301,
            "decision": "pending", "kept": False, "event_id": "",
        }
        later = DAY + interactions.PREGNANCY_DISCOVERY_DAYS
        interactions.settle_periodic_events(state, later)
        event = state["events"][-1]
        interactions.event_plan(state, event["id"], "end_pregnancy", later)
        self.assertEqual(relationship["pregnancy"]["status"], "ended")
        self.assertEqual(relationship["intimacy"], 0.0)
        self.assertLess(relationship["affection"], 55)

    def _exposed_state(self) -> tuple[dict, dict, dict]:
        state = state_with_people(player_row(1001), player_row(1002))
        public = set_relationship(
            state, 1001, romance_stage="partner", intimacy=48,
            affection=70, trust=75, attraction=70, respect=65,
        )
        secret = set_relationship(
            state, 1002, romance_stage="none", secret_lover=True,
            intimacy=35, affection=60, trust=55, attraction=70, respect=50,
        )
        with patch("tools.life_interactions._stable_unit", return_value=0.0):
            event = interactions._register_secret_meeting(
                state, secret, DAY, 50.0, source="test",
            )
        self.assertIsNotNone(event)
        self.assertEqual(event["kind"], "secret_exposure")
        return state, public, secret

    def test_secret_exposure_penalises_the_public_partner(self) -> None:
        state, public, _secret = self._exposed_state()
        self.assertLess(public["trust"], 75)
        self.assertLess(public["intimacy"], 48)
        self.assertEqual(
            state["events"][-1]["options"],
            ["end_secret", "end_public_relationship"],
        )

    def test_exposure_can_end_the_secret_or_public_relationship(self) -> None:
        state, _public, secret = self._exposed_state()
        event_id = state["events"][-1]["id"]
        interactions.event_plan(state, event_id, "end_secret", DAY)
        self.assertFalse(secret["secret_lover"])
        self.assertEqual(secret["romance_stage"], "none")
        self.assertEqual(secret["last_exposure_resolution"], "ended_secret")

        state, public, secret = self._exposed_state()
        event_id = state["events"][-1]["id"]
        interactions.event_plan(
            state, event_id, "end_public_relationship", DAY,
        )
        self.assertEqual(public["romance_stage"], "none")
        self.assertTrue(secret["secret_lover"])
        self.assertEqual(secret["last_exposure_resolution"], "ended_public")


class EmotionalIntelligenceTests(unittest.TestCase):
    def _results(self, eq: int) -> tuple[dict, dict]:
        state = state_with_people()
        interactions.save_profile(state, {"name": "Player", "eq": eq}, DAY)
        set_relationship(
            state, 1001, familiarity=20, affection=20, trust=20,
            attraction=20, respect=20, social_stage="friend",
        )
        chat = interactions.chat_plan(state, 1001, DAY, "football", "Hello")
        gift = interactions.gift_plan(
            state, 1001, DAY, item_id="item-1", sku="book_1",
            item_name="Book", item_value=50_000, category="book",
        )
        return chat, gift

    def test_higher_eq_improves_action_and_gift_results(self) -> None:
        low_chat, low_gift = self._results(1)
        high_chat, high_gift = self._results(100)
        self.assertGreater(high_chat["eq_factor"], low_chat["eq_factor"])
        self.assertGreater(
            high_chat["deltas"]["familiarity"],
            low_chat["deltas"]["familiarity"],
        )
        self.assertGreater(
            high_gift["deltas"]["affection"],
            low_gift["deltas"]["affection"],
        )


class SocialAttributeTests(unittest.TestCase):
    ATTRIBUTES = ("appearance", "ability", "charisma", "eq")

    def _state_with_attributes(self, value: int) -> dict:
        state = state_with_people()
        state["profile"].update({key: value for key in self.ATTRIBUTES})
        set_relationship(
            state, 1001, familiarity=20, affection=20, trust=20,
            attraction=20, respect=20, social_stage="friend",
        )
        return state

    def test_appearance_ability_charisma_and_eq_drive_different_dimensions(self) -> None:
        low = self._state_with_attributes(1)
        high = self._state_with_attributes(100)
        low_chat = interactions.chat_plan(low, 1001, DAY, "football")
        high_chat = interactions.chat_plan(high, 1001, DAY, "football")

        self.assertGreater(
            high_chat["deltas"]["attraction"], low_chat["deltas"]["attraction"],
        )
        self.assertGreater(
            high_chat["deltas"]["respect"], low_chat["deltas"]["respect"],
        )
        self.assertGreater(
            high_chat["deltas"]["affection"], low_chat["deltas"]["affection"],
        )
        self.assertGreater(
            high_chat["deltas"]["trust"], low_chat["deltas"]["trust"],
        )
        factors = high_chat["attribute_factors"]
        self.assertGreater(factors["attraction"], factors["respect"])
        self.assertEqual(factors["familiarity"], 1.0)

    def test_social_effects_are_bounded_above_attribute_100(self) -> None:
        capped = self._state_with_attributes(100)
        unbounded = self._state_with_attributes(1_000_000_000)
        capped_chat = interactions.chat_plan(capped, 1001, DAY, "football")
        unbounded_chat = interactions.chat_plan(
            unbounded, 1001, DAY, "football",
        )
        self.assertEqual(unbounded_chat["deltas"], capped_chat["deltas"])
        self.assertEqual(
            unbounded_chat["attribute_factors"],
            capped_chat["attribute_factors"],
        )

    def test_relationship_chance_uses_all_four_profile_attributes(self) -> None:
        low = self._state_with_attributes(1)
        high = self._state_with_attributes(100)
        low_relationship = low["relationships"]["1001"]
        high_relationship = high["relationships"]["1001"]
        low_chance = interactions.relationship_chance(
            low, low_relationship, "partner", secret=False,
        )
        high_chance = interactions.relationship_chance(
            high, high_relationship, "partner", secret=False,
        )
        self.assertGreater(high_chance, low_chance)

    def test_intimacy_preview_uses_the_same_attribute_scaling_as_settlement(self) -> None:
        state = self._state_with_attributes(100)
        relationship = set_relationship(
            state, 1001, romance_stage="partner", intimacy=20,
        )
        preview = next(
            row for row in interactions.intimacy_options(
                state, relationship, DAY,
            ) if row["id"] == "embrace"
        )["delta_preview"]
        result = interactions.intimacy_plan(state, 1001, DAY, "embrace")
        self.assertEqual(result["deltas"]["attraction"], preview["attraction"])
        self.assertEqual(result["deltas"]["respect"], preview["respect"])


class AssetLevelRewardTests(unittest.TestCase):
    def _state_and_life(self) -> tuple[dict, dict]:
        state = interactions.normalize_state({}, DAY)
        life = life_system._empty_state()
        life["properties"] = {
            "property-rich": {
                "id": "property-rich", "kind": "commercial",
                "tenure": "owned", "market_value": 900_000_000,
            },
        }
        return state, life

    def test_asset_level_rewards_are_claimable_and_idempotent(self) -> None:
        state, life = self._state_and_life()
        self.assertTrue(interactions.sync_asset_level_rewards(state, life, DAY))
        self.assertEqual(
            [row for row in life["vehicles"].values() if row.get("catalog_id") == "car-71"],
            [],
        )
        references = [
            row["reference"] for row in state["profile"]["point_ledger"]
            if row.get("source") == "asset_level"
        ]
        self.assertEqual(references.count("asset-level:7"), 1)
        claimed = interactions.claim_asset_level_vehicle(state, life, 7, DAY)
        self.assertEqual(claimed["vehicle"]["catalog_id"], "car-71")
        self.assertEqual(claimed["vehicle"]["garage_id"], "storage")
        record = state["asset_level_rewards"]["7"]
        self.assertTrue(record["vehicle_claimed"])
        self.assertFalse(interactions.sync_asset_level_rewards(state, life, DAY))
        self.assertEqual(
            len([
                row for row in life["vehicles"].values()
                if row.get("catalog_id") == "car-71"
            ]),
            1,
        )
        with self.assertRaisesRegex(ValueError, "已经领取"):
            interactions.claim_asset_level_vehicle(state, life, 7, DAY)

    def test_new_lower_level_rewards_are_stored_in_storage_first(self) -> None:
        state, life = self._state_and_life()
        interactions.sync_asset_level_rewards(state, life, DAY)
        expected = {
            2: "car-462", 3: "car-339", 4: "car-120",
            5: "car-383", 6: "car-124",
        }
        for level, car_id in expected.items():
            claimed = interactions.claim_asset_level_vehicle(state, life, level, DAY)
            self.assertEqual(claimed["vehicle"]["catalog_id"], car_id)
            self.assertEqual(claimed["vehicle"]["garage_id"], "storage")
        self.assertEqual(len(life["vehicles"]), 5)

    def test_full_garage_keeps_the_car_pending_and_retries_later(self) -> None:
        state, life = self._state_and_life()
        interactions.sync_asset_level_rewards(state, life, DAY)
        record = state["asset_level_rewards"]["7"]
        self.assertTrue(record["points_awarded"])
        self.assertFalse(record["vehicle_claimed"])
        with patch(
            "tools.life_system.grant_vehicle_award",
            side_effect=ValueError("所有车库都没有空位"),
        ):
            with self.assertRaisesRegex(ValueError, "空位"):
                interactions.claim_asset_level_vehicle(state, life, 7, DAY)
        snapshot = interactions._asset_level_snapshot(state, life, DAY)
        level_seven = next(
            row for row in snapshot["levels"] if row["level"] == 7
        )
        self.assertTrue(level_seven["vehicle_pending"])

        claimed = interactions.claim_asset_level_vehicle(state, life, 7, DAY)
        self.assertEqual(claimed["vehicle"]["catalog_id"], "car-71")
        self.assertTrue(record["vehicle_claimed"])
        self.assertEqual(
            len([
                row for row in life["vehicles"].values()
                if row.get("catalog_id") == "car-71"
            ]),
            1,
        )


class V290FrontendContractTests(unittest.TestCase):
    def test_event_copy_footer_and_api_contract_are_present(self) -> None:
        root = __import__("pathlib").Path(__file__).resolve().parents[1]
        page = (root / "src" / "web" / "interactions_page.js").read_text(encoding="utf-8")
        styles = (root / "src" / "web" / "interactions.css").read_text(encoding="utf-8")
        api = (root / "src" / "fm_odds_web.py").read_text(encoding="utf-8")
        self.assertIn("result_fail", page)
        self.assertIn(
            ".interaction-intimacy-meter-foot { display: grid; "
            "grid-template-columns: minmax(0, 1fr)",
            styles,
        )
        self.assertIn('"/api/life/interactions/event"', api)
        self.assertIn("def event_life_interaction", api)
        self.assertIn("settle_periodic_events", api)
        self.assertIn("sync_asset_level_rewards", api)
        self.assertIn(".interaction-ap-ledger-dialog,\n.interaction-event-dialog {", styles)
        self.assertIn(
            ':root[data-theme="dark"] .interaction-ap-ledger-dialog,\n'
            ':root[data-theme="dark"] .interaction-event-dialog {',
            styles,
        )


if __name__ == "__main__":
    unittest.main()
