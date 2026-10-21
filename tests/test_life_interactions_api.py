from __future__ import annotations

import threading
import unittest
from copy import deepcopy
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import fm_odds_web as web
from tools import life_interactions as interactions
from tools import life_system
from tools import preview_cup_odds as odds


DAY = date(2026, 1, 5).toordinal()
GAME_DATE = "2026-01-05"
SCOPE_ID = "interaction-api-test-save"


def player_row() -> dict:
    return {
        "id": 91001, "name": "Test Winger", "age": 24, "female": True,
        "nationality_id": 200, "nationality": "England",
        "team_id": 10, "team_name": "Test Club", "positions": ["AML"],
        "ca": 145, "pa": 165, "world_reputation": 4200,
        "object_type": "player", "date_of_birth": "2002-03-04",
    }


class InteractionApiHarness(web.LocalOddsState):
    def __init__(self, state: dict, life: dict) -> None:
        self.lock = threading.RLock()
        self.interaction_state = state
        self.life_state = life
        self.live_row = player_row()

    def _life_context(self) -> tuple[str, str, int, int]:
        return SCOPE_ID, GAME_DATE, DAY, 1

    def _life_interaction_state(self, scope_id: str, ordinal: int) -> dict:
        self.assert_scope(scope_id, ordinal)
        return self.interaction_state

    def _life_state(self, scope_id: str, ordinal: int) -> dict:
        self.assert_scope(scope_id, ordinal)
        return self.life_state

    def _life_interaction_live_rows(self, player_ids) -> list[dict]:
        requested = {int(value) for value in player_ids}
        return [deepcopy(self.live_row)] if int(self.live_row["id"]) in requested else []

    @staticmethod
    def _life_interaction_items() -> list[dict]:
        return [{
            "id": "item-1", "sku": "book_1", "name": "Test book",
            "category": "book", "value": 5000, "tier": "common", "description": "",
        }]

    @staticmethod
    def assert_scope(scope_id: str, ordinal: int) -> None:
        if scope_id != SCOPE_ID or int(ordinal) != DAY:
            raise AssertionError((scope_id, ordinal))


class ManagerReputationReadTests(unittest.TestCase):
    def test_manager_reputation_reads_verified_layout_offsets(self) -> None:
        layout = SimpleNamespace(
            staff_complete_object_offset=0x100,
            staff_domestic_reputation_offset=0x10,
            staff_current_reputation_offset=0x20,
            staff_world_reputation_offset=0x30,
        )
        values = {0x1F10: 6800, 0x1F20: 7200, 0x1F30: 5400}
        reader = SimpleNamespace(
            layout=layout,
            u16=lambda address: values.get(address, 0),
        )
        result = odds._manager_reputation(reader, 0x2000)
        self.assertTrue(result["available"])
        self.assertEqual(result["current"], 7200)
        self.assertEqual(result["domestic"], 6800)
        self.assertEqual(result["world"], 5400)
        self.assertEqual(result["source"], "fm_manager")

    def test_manager_reputation_stays_unavailable_without_offsets(self) -> None:
        layout = SimpleNamespace(
            staff_complete_object_offset=0x100,
            staff_domestic_reputation_offset=None,
            staff_current_reputation_offset=None,
            staff_world_reputation_offset=None,
        )
        reader = SimpleNamespace(layout=layout, u16=lambda _address: 0)
        result = odds._manager_reputation(reader, 0x2000)
        self.assertFalse(result["available"])
        self.assertIsNone(result["current"])
        self.assertEqual(result["source"], "unavailable")


class LifeInteractionApiTests(unittest.TestCase):
    def setUp(self) -> None:
        state = interactions.normalize_state({}, DAY)
        life = life_system.normalize_state({})
        life["properties"] = {
            "home-1": {
                "id": "home-1", "kind": "residential", "tenure": "owned",
                "mode": "self", "area_sqm": 96, "level": 2,
                "name_zh": "测试住宅", "name_en": "Test Home",
                "city_name_zh": "深圳", "city_name_en": "Shenzhen",
                "city_id": "shenzhen", "district_name_zh": "南山",
                "district_name_en": "Nanshan", "base_price": 2_000_000,
            },
        }
        life["vehicles"] = {
            "vehicle-1": {
                "id": "vehicle-1", "name": "Test Car", "manufacturer": "Test",
                "class": "A", "rarity": "Rare", "base_price": 500_000,
                "condition": 1.0, "purchase_day": DAY, "garage_id": "",
            },
        }
        self.api = InteractionApiHarness(state, life)
        self.save_patch = patch("tools.life_interactions.save_state")
        self.save_patch.start()
        self.addCleanup(self.save_patch.stop)

    def test_profile_player_chat_and_residence_flow(self) -> None:
        self.api.output = {
            "manager": {
                "id": 1, "name": "Manager", "team_name": "Test Club",
                "reputation": {
                    "current": 7200, "domestic": 6800, "world": 5400,
                    "available": True, "source": "fm_manager",
                },
            },
            "club": {"id": 42, "team_id": 42, "name": "Test Club"},
        }
        response = self.api.update_life_interaction_profile({
            "name": "Manager", "gender": "male", "age": 33,
            "appearance": 72, "charisma": 80,
        })
        self.assertTrue(response["profile"]["completed"])

        response = self.api.cache_life_interaction_player({"player_id": 91001})
        self.assertEqual(response["summary"]["people"], 1)
        self.assertEqual(response["summary"]["relationships"], 1)

        relationship = self.api.interaction_state["relationships"]["91001"]
        relationship.update({
            "familiarity": 50, "affection": 60, "trust": 55,
            "attraction": 50, "respect": 40, "social_stage": "friend",
        })
        chat = self.api.chat_life_interaction({
            "person_id": 91001, "topic": "life", "message": "今天过得怎么样？",
        })
        self.assertTrue(chat["ok"])
        self.assertIn("dialogue", chat["result"])
        self.assertEqual(chat["result"]["dialogue"]["kind"], "chat")
        self.assertEqual(chat["result"]["message"], "今天过得怎么样？")
        self.assertEqual(chat["result"]["timeline"]["result"]["message"], "今天过得怎么样？")
        self.assertEqual(chat["manager_reputation"]["current"], 7200)
        self.assertTrue(chat["manager_reputation"]["available"])
        self.assertEqual(chat["manager_identity"]["team_name"], "Test Club")
        self.assertEqual(chat["manager_identity"]["team_id"], 42)
        self.assertEqual(chat["action_points"]["current"], 11)

        residence = self.api.residence_life_interaction({
            "person_id": 91001, "asset_id": "home-1",
        })
        self.assertEqual(residence["result"]["asset_id"], "home-1")
        self.assertEqual(residence["summary"]["residents"], 1)

    def test_item_gift_and_permanent_asset_gift_flow(self) -> None:
        self.api.interaction_state["profile"] = {
            **interactions._empty_profile(), "name": "Manager", "completed": True,
        }
        self.api.interaction_state["people"] = {
            "91001": {
                "id": 91001, "name": "Test Winger", "age": 24, "female": True,
                "team_name": "Test Club", "positions": ["AML"],
            },
        }
        self.api.interaction_state["relationships"] = {
            "91001": interactions._normalize_relationship({
                "person_name": "Test Winger", "familiarity": 40,
                "affection": 45, "trust": 35, "attraction": 30,
                "respect": 30, "social_stage": "friend",
            }, 91001),
        }
        product = {"name": "Test book", "price": 5000, "category": "book"}
        economy = {"inventory": [{
            "id": "item-1", "sku": "book_1", "status": "available", "name": "Test book",
        }]}
        with patch.object(web, "load_economy", return_value=economy), \
             patch.dict(web.PRODUCTS, {"book_1": product}, clear=False), \
             patch.object(web, "consume_instant_item") as consume:
            gift = self.api.gift_life_interaction({
                "person_id": 91001, "item_id": "item-1",
            })
        self.assertEqual(gift["result"]["dialogue"]["kind"], "gift")
        consume.assert_called_once()

        preview = self.api.gift_asset_life_interaction({
            "person_id": 91001, "asset_type": "vehicle",
            "asset_id": "vehicle-1", "confirm": False,
        })
        self.assertTrue(preview["preview"])
        self.assertTrue(preview["plan"]["permanent"])

        def update_documents(_defaults, mutate, _scope_id):
            documents = {
                life_system.DOCUMENT: deepcopy(self.api.life_state),
                interactions.DOCUMENT: deepcopy(self.api.interaction_state),
            }
            mutate(documents)
            self.api.life_state = documents[life_system.DOCUMENT]
            self.api.interaction_state = documents[interactions.DOCUMENT]

        with patch.object(web, "update_documents", side_effect=update_documents):
            committed = self.api.gift_asset_life_interaction({
                "person_id": 91001, "asset_type": "vehicle",
                "asset_id": "vehicle-1", "confirm": True,
            })
        self.assertTrue(committed["result"]["permanent"])
        self.assertFalse(committed["result"]["recoverable"])
        self.assertNotIn("vehicle-1", self.api.life_state["vehicles"])
        self.assertEqual(committed["summary"]["gifted_assets"], 1)

    def test_intimacy_endpoint_requires_commitment_and_spends_both_resources(self) -> None:
        settings_patch = patch(
            "fm_odds_web.load_settings", return_value={"adult_content_enabled": True},
        )
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        self.api.cache_life_interaction_player({"player_id": 91001})
        relationship = self.api.interaction_state["relationships"]["91001"]
        relationship.update({
            "familiarity": 90, "affection": 90, "trust": 90,
            "attraction": 80, "respect": 90, "social_stage": "close_friend",
            "romance_stage": "ambiguous", "intimacy": 0,
        })
        with self.assertRaisesRegex(ValueError, "情侣、情人或夫妻"):
            self.api.intimacy_life_interaction({
                "person_id": 91001, "action": "embrace",
            })

        relationship.update({
            "romance_stage": "partner", "secret_lover": False, "intimacy": 20,
        })
        response = self.api.intimacy_life_interaction({
            "person_id": 91001, "action": "embrace",
        })
        result = response["result"]
        self.assertEqual(result["kind"], "intimacy")
        self.assertEqual(result["action"], "embrace")
        self.assertEqual(result["action_cost"], 1)
        self.assertEqual(result["intimacy_cost"], 3.0)
        self.assertEqual(result["intimacy_after"], 17.0)
        self.assertEqual(response["action_points"]["current"], 11)
        selected = next(
            row for row in response["relationships"]
            if row["person"]["id"] == 91001
        )
        self.assertTrue(selected["relationship"]["is_intimate"])
        self.assertEqual(selected["relationship"]["intimacy"], 17.0)

    def test_intimacy_endpoint_is_closed_when_adult_content_is_disabled(self) -> None:
        self.api.cache_life_interaction_player({"player_id": 91001})
        with patch("fm_odds_web.load_settings", return_value={}):
            with self.assertRaisesRegex(ValueError, "成人项目已关闭"):
                self.api.intimacy_life_interaction({
                    "person_id": 91001, "action": "embrace",
                })

    def test_adult_shop_purchases_are_rejected_server_side_when_disabled(self) -> None:
        with (
            patch("fm_odds_web.load_settings", return_value={}),
            patch.object(self.api, "_account_application") as account_application,
        ):
            with self.assertRaisesRegex(ValueError, "成人项目已关闭"):
                self.api.shop_purchase({"sku": "intimate_toy"})
            with self.assertRaisesRegex(ValueError, "成人项目已关闭"):
                self.api.shop_batch_purchase({
                    "items": [{"sku": "intimate_lube", "quantity": 1}],
                })
        account_application.assert_not_called()

    def test_adult_gifts_are_rejected_server_side_when_disabled(self) -> None:
        inventory = {
            "inventory": [{
                "id": "adult-item-1", "sku": "intimate_toy",
                "status": "available",
            }],
        }
        with (
            patch("fm_odds_web.load_settings", return_value={}),
            patch("fm_odds_web.load_economy", return_value=inventory),
        ):
            with self.assertRaisesRegex(ValueError, "成人项目已关闭"):
                self.api.gift_life_interaction({
                    "person_id": 91001, "item_id": "adult-item-1",
                })

    def test_event_endpoint_derives_person_from_the_event(self) -> None:
        self.api.cache_life_interaction_player({"player_id": 91001})
        person = self.api.interaction_state["people"]["91001"]
        event = interactions._queue_event(
            self.api.interaction_state,
            kind="relationship_crisis", person=person,
            day=DAY, available_day=DAY,
            data={"intimacy": -75},
            options=["repair", "accept_separation"],
        )
        response = self.api.event_life_interaction({
            "event_id": event["id"], "option": "accept_separation",
        })
        self.assertEqual(response["selected_person_id"], 91001)
        self.assertEqual(response["result"]["kind"], "event")
        self.assertTrue(response["result"]["success"])
        self.assertEqual(
            response["result"]["event"]["status"], "resolved",
        )
        self.assertEqual(
            response["result"]["event"]["selected_option"],
            "accept_separation",
        )

    def test_remove_contact_endpoint_clears_person_and_keeps_gift_record(self) -> None:
        self.api.cache_life_interaction_player({"player_id": 91001})
        person_id = "91001"
        self.api.interaction_state["residences"] = {person_id: "home-1"}
        self.api.interaction_state["gifted_assets"] = [{
            "person_id": 91001, "asset_type": "property",
            "asset_id": "home-1", "asset_name": "Test Home",
            "value": 2_000_000, "day": DAY,
        }]

        response = self.api.remove_life_interaction({"person_id": 91001})

        self.assertTrue(response["result"]["removed"])
        self.assertEqual(response["result"]["preserved_permanent_gifts"], 1)
        self.assertEqual(response["summary"]["people"], 0)
        self.assertEqual(response["relationships"], [])
        self.assertNotIn(person_id, self.api.interaction_state["people"])
        self.assertNotIn(person_id, self.api.interaction_state["relationships"])
        self.assertNotIn(person_id, self.api.interaction_state["residences"])
        self.assertEqual(
            self.api.interaction_state["gifted_assets"][0]["asset_id"], "home-1",
        )

    def test_player_search_combines_club_nationality_gender_and_age_filters(self) -> None:
        result = {
            "players": [player_row()],
            "pagination": {"page": 1, "page_size": 24, "total": 1},
            "filter_options": {"nationalities": [{"id": 200, "name": "England"}]},
        }
        with patch.object(
            self.api,
            "_life_interaction_club_player_ids",
            return_value=((91001, 91002), "Test Club"),
        ), patch.object(
            self.api, "public_world_players", return_value=result,
        ) as search:
            response = self.api.search_life_interaction_players(
                query="Wing", page=2, page_size=24, gender="women",
                nationality_id=200, min_age=22, max_age=30, club_id=10,
            )

        search.assert_called_once()
        kwargs = search.call_args.kwargs
        self.assertEqual(kwargs["search"], "Wing")
        self.assertEqual(kwargs["page"], 2)
        self.assertEqual(kwargs["page_size"], 24)
        self.assertEqual(kwargs["gender"], "women")
        self.assertEqual(kwargs["nationality_id"], 200)
        self.assertEqual(kwargs["min_age"], 22)
        self.assertEqual(kwargs["max_age"], 30)
        self.assertEqual(kwargs["candidate_uids"], (91001, 91002))
        self.assertEqual(response["interaction_filter"]["min_age"], 22)
        self.assertEqual(response["interaction_filter"]["club_name"], "Test Club")

    def test_player_search_never_allows_a_filter_below_adult_age(self) -> None:
        with patch.object(
            self.api,
            "_life_interaction_club_player_ids",
            return_value=((), "Empty Club"),
        ):
            response = self.api.search_life_interaction_players(min_age=12, club_id=99)
        self.assertEqual(response["interaction_filter"]["min_age"], interactions.MIN_ADULT_AGE)
        self.assertEqual(response["filters"]["min_age"], interactions.MIN_ADULT_AGE)


if __name__ == "__main__":
    unittest.main()
