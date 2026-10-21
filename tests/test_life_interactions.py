from __future__ import annotations

import unittest
from copy import deepcopy
from datetime import date
from unittest.mock import patch

from tools import life_interactions as interactions


MONDAY = date(2026, 1, 5)
DAY = MONDAY.toordinal()
WEEK_LATER = date(2026, 1, 12).toordinal()
TWO_WEEKS_LATER = date(2026, 1, 19).toordinal()


def player_row(player_id: int = 1001, *, age: int = 24, name: str = "测试球员") -> dict:
    return {
        "id": player_id,
        "name": name,
        "age": age,
        "female": True,
        "nationality_id": 200,
        "nationality": "英格兰",
        "team_id": 10,
        "team_name": "测试俱乐部",
        "positions": ["ST"],
        "ca": 140,
        "pa": 160,
        "world_reputation": 4000,
        "object_type": "player",
        "date_of_birth": "2002-03-04",
    }


def state_with_people(*rows: dict) -> dict:
    state = interactions.normalize_state({}, DAY)
    interactions.save_profile(state, {"name": "玩家", "age": 30}, DAY)
    for row in rows or (player_row(),):
        interactions.cache_search_row(state, row, DAY)
    return state


def set_relationship(state: dict, player_id: int, **values) -> dict:
    relationship = state["relationships"][str(player_id)]
    relationship.update(values)
    relationship["social_stage"] = interactions.social_stage_for(relationship)
    return relationship


class PersonCacheTests(unittest.TestCase):
    def test_minor_is_rejected_from_interaction_cache(self) -> None:
        state = interactions.normalize_state({}, DAY)
        with self.assertRaisesRegex(ValueError, "18"):
            interactions.cache_search_row(state, player_row(age=17), DAY)

    def test_preferences_are_stable_for_a_player_uid(self) -> None:
        first = interactions.preference_for(1001)
        second = interactions.preference_for(1001)
        other = interactions.preference_for(1002)
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertIn(first["gift"], interactions.GIFT_CATEGORIES)
        self.assertIn(first["activity"], interactions.DATE_ACTIVITIES)

    def test_incremental_refresh_keeps_history_and_updates_snapshot(self) -> None:
        state = state_with_people()
        relationship = state["relationships"]["1001"]
        relationship["affection"] = 42.0
        refreshed = player_row(name="新名称")
        refreshed["team_name"] = "新俱乐部"
        person, changed = interactions.refresh_person_row(state, refreshed, DAY + 1)
        self.assertTrue(changed)
        self.assertEqual(person["name"], "新名称")
        self.assertEqual(state["relationships"]["1001"]["affection"], 42.0)
        self.assertEqual(state["relationships"]["1001"]["person_name"], "新名称")


class ActionPointTests(unittest.TestCase):
    def test_weekly_recovery_is_six_and_caps_at_twelve(self) -> None:
        state = interactions.normalize_state({}, DAY)
        state["action_points"]["current"] = 5
        self.assertTrue(interactions.refresh_action_points(state, WEEK_LATER))
        self.assertEqual(state["action_points"]["current"], 11)
        self.assertTrue(interactions.refresh_action_points(state, TWO_WEEKS_LATER))
        self.assertEqual(state["action_points"]["current"], 12)

    def test_chat_costs_one_action_point_and_keeps_the_player_message(self) -> None:
        state = state_with_people()
        message = "  我很喜欢你的比赛视野  " + "x" * interactions.MAX_CHAT_MESSAGE_CHARS
        result = interactions.chat_plan(state, 1001, DAY, "football", message)
        self.assertEqual(state["action_points"]["current"], 11)
        self.assertGreater(result["deltas"]["familiarity"], 0)
        self.assertEqual(len(result["message"]), interactions.MAX_CHAT_MESSAGE_CHARS)
        self.assertTrue(result["message"].startswith("我很喜欢你的比赛视野"))
        self.assertEqual(result["reply_mode"], "template")
        self.assertEqual(result["dialogue"]["kind"], "chat")
        self.assertEqual(result["timeline"]["result"]["message"], result["message"])
        self.assertEqual(state["timeline"][-1]["result"]["dialogue"], result["dialogue"])

    def test_actions_reject_insufficient_action_points(self) -> None:
        state = state_with_people()
        state["action_points"]["current"] = 0
        with self.assertRaisesRegex(ValueError, "行动力不足"):
            interactions.chat_plan(state, 1001, DAY, "football")

    def test_action_points_report_recovery_forecast_and_cost_breakdown(self) -> None:
        state = interactions.normalize_state({}, DAY)
        state["action_points"]["current"] = 5
        forecast = interactions.action_points(state, DAY)
        self.assertEqual(forecast["next_recovery_gain"], 6)
        self.assertEqual(forecast["days_until_full"], 14)
        self.assertFalse(forecast["is_full"])
        self.assertEqual(forecast["costs"]["asset_gift"], 1)
        self.assertEqual(forecast["costs"]["date_min"], 2)
        self.assertEqual(forecast["costs"]["date_max"], 4)

        state["action_points"]["current"] = 11
        forecast = interactions.action_points(state, DAY)
        self.assertEqual(forecast["next_recovery_gain"], 1)
        self.assertEqual(forecast["days_until_full"], 7)


class CdkPerkTests(unittest.TestCase):
    def test_action_point_perk_raises_cap_and_weekly_recovery_once(self) -> None:
        state = interactions.normalize_state({}, DAY)
        self.assertEqual(state["action_points"]["current"], 12)

        record = interactions.activate_cdk_perk(
            state, "action_points", code="日理万机", day=DAY,
        )

        self.assertEqual(record["maximum_bonus"], 12)
        self.assertEqual(state["action_points"]["current"], 24)
        self.assertEqual(state["action_points"]["maximum"], 24)
        self.assertEqual(state["action_points"]["weekly_recovery"], 30)
        state["action_points"]["current"] = 5
        interactions.activate_cdk_perk(
            state, "action_points", code="日理万机", day=DAY,
        )
        self.assertEqual(state["action_points"]["current"], 5)
        self.assertTrue(interactions.refresh_action_points(state, WEEK_LATER))
        self.assertEqual(state["action_points"]["current"], 24)

    def test_relationship_perk_multiplies_positive_gain_but_not_penalties(self) -> None:
        relationship = {
            "familiarity": 0, "affection": 50, "trust": 0,
            "attraction": 0, "respect": 0,
        }
        interactions._apply_deltas(
            relationship, {"familiarity": 2.0, "affection": -3.0},
            gain_multiplier=interactions.RELATIONSHIP_GAIN_PERK_MULTIPLIER,
        )
        self.assertEqual(relationship["familiarity"], 20)
        self.assertEqual(relationship["affection"], 47)

    def test_chat_uses_the_relationship_perk_after_activation(self) -> None:
        plain = state_with_people()
        boosted = deepcopy(plain)
        interactions.activate_cdk_perk(
            boosted, "relationship_gain", code="魅力四射", day=DAY,
        )

        baseline = interactions.chat_plan(plain, 1001, DAY, "football")
        result = interactions.chat_plan(boosted, 1001, DAY, "football")

        for key, value in baseline["deltas"].items():
            expected = round(value * 10, 2) if value > 0 else value
            self.assertEqual(result["deltas"][key], expected)


class RelationshipRuleTests(unittest.TestCase):
    def test_options_match_backend_relationship_thresholds(self) -> None:
        state = state_with_people(player_row(1001), player_row(1002))
        set_relationship(
            state, 1001, familiarity=60, affection=75, trust=70, attraction=70,
            social_stage="close_friend", romance_stage="partner",
        )
        second = set_relationship(
            state, 1002, familiarity=40, affection=40, trust=35, attraction=50,
            social_stage="friend", romance_stage="ambiguous",
        )
        options = {
            row["target"]: row["available"]
            for row in interactions.relationship_options(state, second)
        }
        self.assertFalse(options["partner"])
        self.assertFalse(options["secret_lover"])
        second.update({"affection": 50, "trust": 45, "attraction": 60})
        options = {
            row["target"]: row["available"]
            for row in interactions.relationship_options(state, second)
        }
        self.assertFalse(options["partner"])
        self.assertTrue(options["secret_lover"])

    def test_social_stage_thresholds(self) -> None:
        relationship = {"familiarity": 25, "affection": 30, "trust": 20, "respect": 0}
        self.assertEqual(interactions.social_stage_for(relationship), "friend")
        relationship.update({"familiarity": 50, "affection": 55, "trust": 45, "respect": 35})
        self.assertEqual(interactions.social_stage_for(relationship), "close_friend")
        relationship.update({"familiarity": 75, "affection": 75, "trust": 70, "respect": 60})
        self.assertEqual(interactions.social_stage_for(relationship), "confidant")

    def test_secret_lover_requires_an_existing_partner(self) -> None:
        state = state_with_people(player_row(1001), player_row(1002))
        second = set_relationship(
            state, 1002, familiarity=60, affection=80, trust=80, attraction=80,
            social_stage="close_friend", romance_stage="ambiguous",
        )
        with self.assertRaisesRegex(ValueError, "没有其他情侣或配偶"):
            interactions.relationship_plan(state, 1002, DAY, "secret_lover")
        self.assertEqual(second["romance_stage"], "ambiguous")

    def test_secret_lovers_are_parallel_and_partner_is_exclusive(self) -> None:
        state = state_with_people(
            player_row(1001), player_row(1002), player_row(1003),
        )
        set_relationship(
            state, 1001, familiarity=80, affection=90, trust=85, attraction=90,
            social_stage="confidant", romance_stage="partner",
        )
        set_relationship(
            state, 1002, familiarity=60, affection=75, trust=75, attraction=80,
            social_stage="close_friend", romance_stage="ambiguous",
        )
        set_relationship(
            state, 1003, familiarity=60, affection=70, trust=70, attraction=75,
            social_stage="close_friend", romance_stage="ambiguous",
        )
        with self.assertRaisesRegex(ValueError, "只能发展为情人"):
            interactions.relationship_plan(state, 1002, DAY, "partner")
        with patch("tools.life_interactions._stable_unit", return_value=0.1):
            first = interactions.relationship_plan(state, 1002, DAY, "secret_lover")
            second = interactions.relationship_plan(state, 1003, DAY, "secret_lover")
        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        self.assertTrue(state["relationships"]["1002"]["secret_lover"])
        self.assertTrue(state["relationships"]["1003"]["secret_lover"])
        self.assertEqual(state["relationships"]["1001"]["romance_stage"], "partner")

    def test_breakup_unlocks_a_public_partner(self) -> None:
        state = state_with_people(player_row(1001), player_row(1002))
        first = set_relationship(
            state, 1001, familiarity=70, affection=85, trust=80, attraction=80,
            social_stage="close_friend", romance_stage="partner",
        )
        set_relationship(
            state, 1002, familiarity=60, affection=70, trust=70, attraction=75,
            social_stage="close_friend", romance_stage="ambiguous",
        )
        with patch("tools.life_interactions._stable_unit", return_value=0.1):
            interactions.relationship_plan(state, 1001, DAY, "breakup")
            result = interactions.relationship_plan(state, 1002, DAY, "partner")
        self.assertTrue(result["success"])
        self.assertEqual(first["romance_stage"], "none")
        self.assertEqual(state["relationships"]["1002"]["romance_stage"], "partner")


class ResidenceTests(unittest.TestCase):
    def test_capacity_depends_primarily_on_area(self) -> None:
        small_high_level = interactions.residence_capacity({"area_sqm": 70, "level": 5})
        large_low_level = interactions.residence_capacity({"area_sqm": 190, "level": 1})
        self.assertEqual(small_high_level, 3)
        self.assertEqual(large_low_level, 4)
        self.assertGreater(large_low_level, small_high_level)

    def test_friend_can_move_into_a_self_use_residence(self) -> None:
        state = state_with_people()
        set_relationship(
            state, 1001, familiarity=40, affection=45, trust=35,
            social_stage="friend",
        )
        life = {
            "properties": {
                "property-1": {
                    "id": "property-1", "kind": "residential", "tenure": "owned",
                    "mode": "self", "area_sqm": 95, "level": 2,
                    "name_zh": "测试住宅", "name_en": "Test Home",
                    "city_name_zh": "深圳", "city_name_en": "Shenzhen",
                    "city_id": "shenzhen", "base_price": 1_000_000,
                    "district_name_zh": "南山", "district_name_en": "Nanshan",
                },
            },
            "vehicles": {}, "garages": {},
        }
        result = interactions.assign_residence_plan(
            state, life, person_id=1001, asset_id="property-1", day=DAY,
        )
        self.assertFalse(result["unchanged"])
        self.assertEqual(state["residences"]["1001"], "property-1")


class AssetGiftTests(unittest.TestCase):
    def _state_and_life(self) -> tuple[dict, dict]:
        state = state_with_people()
        set_relationship(
            state, 1001, familiarity=40, affection=45, trust=35,
            social_stage="friend",
        )
        life = {
            "properties": {
                "property-1": {
                    "id": "property-1", "kind": "commercial", "tenure": "owned",
                    "mode": "rent", "area_sqm": 220, "level": 2,
                    "city_name_zh": "深圳", "city_name_en": "Shenzhen",
                    "city_id": "shenzhen", "base_price": 5_000_000,
                    "name_zh": "测试商铺", "name_en": "Test Shop",
                    "garage_id": "garage-1",
                },
            },
            "vehicles": {
                "vehicle-1": {
                    "id": "vehicle-1", "name": "Test Car", "manufacturer": "Test",
                    "class": "A", "rarity": "Rare", "base_price": 500_000,
                    "condition": 1.0, "purchase_day": DAY, "garage_id": "garage-1",
                },
            },
            "garages": {"garage-1": {"id": "garage-1", "capacity": 2}},
        }
        return state, life

    def test_property_with_vehicle_is_blocked(self) -> None:
        state, life = self._state_and_life()
        with self.assertRaisesRegex(ValueError, "车辆"):
            interactions.asset_gift_plan(
                state, life, person_id=1001, asset_type="property",
                asset_id="property-1", day=DAY,
            )

    def test_vehicle_gift_is_recorded_as_permanent(self) -> None:
        state, life = self._state_and_life()
        plan = interactions.asset_gift_plan(
            state, life, person_id=1001, asset_type="vehicle",
            asset_id="vehicle-1", day=DAY,
        )
        self.assertEqual(plan["action_cost"], 1)
        self.assertEqual(state["action_points"]["current"], 11)
        self.assertEqual(plan["social_stage_before"], "friend")
        self.assertIn("affection_gain", plan)
        result = interactions.commit_asset_gift(state, life, plan, DAY)
        self.assertNotIn("vehicle-1", life["vehicles"])
        self.assertEqual(result["kind"], "asset_gift")
        self.assertTrue(result["permanent"])
        self.assertFalse(result["recoverable"])
        self.assertEqual(state["gifted_assets"][-1]["person_id"], 1001)

    def test_public_preview_exposes_per_person_affection_and_stage_outcome(self) -> None:
        state, life = self._state_and_life()
        view = interactions.public_view(state, life_state=life, day=DAY)
        relationship = view["relationships"][0]["relationship"]
        preview = relationship["asset_gift_previews"]["vehicle:vehicle-1"]
        self.assertGreater(preview["affection_gain"], 0)
        self.assertEqual(preview["social_stage_before"], "friend")
        self.assertIn("social_stage_after", preview)
        self.assertIn("may_upgrade", preview)
        self.assertEqual(view["assets"]["vehicles"][0]["action_cost"], 1)

    def test_property_gift_removes_its_garage(self) -> None:
        state, life = self._state_and_life()
        life["vehicles"].clear()
        plan = interactions.asset_gift_plan(
            state, life, person_id=1001, asset_type="property",
            asset_id="property-1", day=DAY,
        )
        interactions.commit_asset_gift(state, life, plan, DAY)
        self.assertNotIn("property-1", life["properties"])
        self.assertNotIn("garage-1", life["garages"])

    def test_property_gift_keeps_bilingual_asset_names_in_history(self) -> None:
        state, life = self._state_and_life()
        life["vehicles"].clear()
        plan = interactions.asset_gift_plan(
            state, life, person_id=1001, asset_type="property",
            asset_id="property-1", day=DAY,
        )
        self.assertEqual(plan["asset_name_zh"], "测试商铺")
        self.assertEqual(plan["asset_name_en"], "Test Shop")
        result = interactions.commit_asset_gift(state, life, plan, DAY)
        self.assertEqual(result["asset_name_zh"], "测试商铺")
        self.assertEqual(result["asset_name_en"], "Test Shop")
        ledger = state["gifted_assets"][-1]
        self.assertEqual(ledger["asset_name_zh"], "测试商铺")
        self.assertEqual(ledger["asset_name_en"], "Test Shop")
        timeline = result["timeline"]["result"]
        self.assertEqual(timeline["asset_name_zh"], "测试商铺")
        self.assertEqual(timeline["asset_name_en"], "Test Shop")


class ProfileAllocationTests(unittest.TestCase):
    def test_new_profile_starts_at_one_point_per_attribute(self) -> None:
        state = interactions.normalize_state({}, DAY)
        profile = state["profile"]
        self.assertEqual(
            [profile[key] for key in interactions.PROFILE_ATTRIBUTE_KEYS],
            [1, 1, 1, 1],
        )
        self.assertEqual(profile["points_available"], 191)
        saved = interactions.save_profile(
            state, {"name": "玩家", "age": 30}, DAY,
        )
        self.assertEqual(saved["points_spent"], 9)
        self.assertEqual(saved["points_available"], 191)

    def test_completed_legacy_profile_keeps_explicit_allocations(self) -> None:
        state = interactions.normalize_state({
            "profile": {
                "name": "旧档案", "completed": True,
                "appearance": 50, "ability": 50,
                "charisma": 50, "reputation": 50,
            },
        }, DAY)
        profile = state["profile"]
        self.assertEqual(profile["points_spent"], 401)
        self.assertEqual(profile["points_available"], 50)
        self.assertEqual(
            [profile[key] for key in interactions.PROFILE_ATTRIBUTE_KEYS],
            [50, 50, 50, 1],
        )
        self.assertEqual(profile["reputation"], 50)

    def test_fm_height_and_weight_flow_into_cached_person_traits(self) -> None:
        state = state_with_people()
        row = player_row(1002, name="高个球员")
        row.update({"height_cm": 191, "weight_kg": 84})
        person, _relationship, _changed = interactions.cache_search_row(state, row, DAY)
        self.assertEqual(person["height_cm"], 191)
        self.assertEqual(person["weight_kg"], 84)
        self.assertEqual(person["traits"]["height_cm"], 191)
        self.assertEqual(person["traits"]["weight_kg"], 84)
        self.assertTrue(person["traits"]["measurements"])

        male = player_row(1003, name="男足球员")
        male["female"] = False
        male_person, _relationship, _changed = interactions.cache_search_row(state, male, DAY)
        self.assertEqual(male_person["traits"]["measurements"], {})

    def test_normalize_state_preserves_top_level_fm_measurements(self) -> None:
        raw = {
            "people": {
                "1001": {
                    "id": 1001,
                    "name": "测试球员",
                    "age": 24,
                    "female": False,
                    "height_cm": 191,
                    "weight_kg": 84,
                    "object_type": "player",
                },
            },
            "relationships": {
                "1001": {"person_name": "测试球员"},
            },
        }
        person = interactions.normalize_state(raw, DAY)["people"]["1001"]
        self.assertEqual(person["height_cm"], 191)
        self.assertEqual(person["weight_kg"], 84)
        self.assertEqual(person["traits"]["height_cm"], 191)
        self.assertEqual(person["traits"]["weight_kg"], 84)

    def test_profile_names_split_for_chinese_and_western_names(self) -> None:
        self.assertEqual(
            interactions._split_profile_name("欧阳娜娜"),
            ("欧阳", "娜娜"),
        )
        self.assertEqual(
            interactions._split_profile_name("Alex Morgan"),
            ("Morgan", "Alex"),
        )
        state = interactions.normalize_state({
            "profile": {"name": "Alex Morgan", "completed": True},
        }, DAY)
        profile = state["profile"]
        self.assertEqual(profile["surname"], "Morgan")
        self.assertEqual(profile["given_name"], "Alex")
        self.assertEqual(profile["name"], "Alex Morgan")
        saved = interactions.save_profile(
            state, {"surname": "李", "given_name": "明", "age": 30}, DAY,
        )
        self.assertEqual(saved["name"], "李明")

    def test_identity_cost_uses_younger_taller_and_lighter_weights(self) -> None:
        self.assertEqual(
            interactions.profile_identity_cost(30, 180, 75)["total"],
            0,
        )
        younger = interactions.profile_identity_cost(18, 180, 75)
        older = interactions.profile_identity_cost(25, 180, 75)
        self.assertGreater(younger["age"], older["age"])
        self.assertGreater(
            interactions.profile_identity_cost(30, 200, 75)["height"],
            interactions.profile_identity_cost(30, 190, 75)["height"],
        )
        self.assertGreater(
            interactions.profile_identity_cost(30, 180, 60)["weight"],
            interactions.profile_identity_cost(30, 180, 70)["weight"],
        )

    def test_completed_profile_attributes_have_no_cap_and_reputation_is_costed(self) -> None:
        state = interactions.normalize_state({}, DAY)
        saved = interactions.save_profile(state, {
            "surname": "测试", "given_name": "经理",
            "appearance": 25, "ability": 25,
            "charisma": 25, "reputation": 5,
        }, DAY)
        self.assertEqual(saved["appearance"], 25)
        self.assertEqual(saved["ability"], 25)
        self.assertEqual(saved["charisma"], 25)
        self.assertEqual(saved["reputation"], 5)
        self.assertEqual(
            saved["points_spent"],
            25 + 25 + 25 + 1 + 5 * interactions.PROFILE_REPUTATION_COST,
        )
        with self.assertRaisesRegex(ValueError, "只能增加"):
            interactions.save_profile(state, {
                "surname": "测试", "given_name": "经理", "reputation": 4,
            }, DAY)
        raised = interactions.save_profile(state, {
            "surname": "测试", "given_name": "经理", "reputation": 6,
        }, DAY)
        self.assertEqual(raised["reputation"], 6)

    def test_adjusting_identity_back_to_baseline_releases_points(self) -> None:
        state = interactions.normalize_state({}, DAY)
        young = interactions.save_profile(state, {
            "surname": "测试", "given_name": "经理",
            "age": 18, "height_cm": 200, "weight_kg": 60,
        }, DAY)
        self.assertGreater(young["identity_cost"]["total"], 0)
        self.assertLess(young["points_available"], 191)
        baseline = interactions.save_profile(state, {
            "surname": "测试", "given_name": "经理",
            "age": 30, "height_cm": 180, "weight_kg": 75,
        }, DAY)
        self.assertEqual(baseline["identity_cost"]["total"], 0)
        self.assertEqual(baseline["points_available"], 191)

    def test_legacy_identity_profile_migration_keeps_a_valid_budget(self) -> None:
        state = interactions.normalize_state({
            "schema_version": 2,
            "profile": {
                "name": "旧档案", "completed": True,
                "age": 18, "height_cm": 200, "weight_kg": 60,
                "appearance": 50, "ability": 50,
                "charisma": 50, "reputation": 50,
            },
        }, DAY)
        profile = state["profile"]
        identity_cost = interactions.profile_identity_cost(18, 200, 60)
        self.assertEqual(profile["identity_cost"], identity_cost)
        self.assertGreater(identity_cost["total"], 0)
        self.assertEqual(
            profile["points_spent"],
            401 + identity_cost["total"],
        )
        self.assertGreaterEqual(profile["points_earned"], identity_cost["total"])
        self.assertGreaterEqual(profile["points_available"], 0)

    def test_relationship_depth_controls_npc_trait_disclosure(self) -> None:
        state = state_with_people()
        relationship = state["relationships"]["1001"]
        relationship.update({
            "familiarity": 0, "affection": 0, "trust": 0,
            "attraction": 0, "respect": 0,
            "social_stage": "acquaintance", "romance_stage": "none",
        })
        shallow = interactions.public_view(state, day=DAY)["relationships"][0]["person"]["traits"]
        self.assertEqual(shallow["disclosure"]["level"], 0)
        self.assertEqual(len(shallow["personality"]), 1)
        self.assertEqual(shallow["values"], [])
        self.assertEqual(shallow["measurements"], {})
        self.assertTrue(shallow["measurement_ranges"])
        self.assertTrue(all(len(values) == 1 for values in shallow["likes"].values()))
        self.assertEqual(shallow["dislikes"], {})

        relationship.update({
            "familiarity": 90, "affection": 90, "trust": 90,
            "attraction": 80, "respect": 90,
            "social_stage": "confidant", "romance_stage": "none",
        })
        deep = interactions.public_view(state, day=DAY)["relationships"][0]["person"]["traits"]
        self.assertEqual(deep["disclosure"]["level"], 3)
        self.assertEqual(len(deep["personality"]), 2)
        self.assertEqual(len(deep["values"]), 2)
        self.assertEqual(deep["measurement_ranges"], {})
        self.assertTrue(deep["measurements"])
        self.assertTrue(all(len(values) == 3 for values in deep["likes"].values()))
        self.assertTrue(deep["dislikes"]["gifts"])
        self.assertTrue(deep["dislikes"]["activities"])


class IntimacyTests(unittest.TestCase):
    def test_migration_initialises_intimacy_and_preserves_future_family_state(self) -> None:
        state = state_with_people()
        relationship = state["relationships"]["1001"]
        relationship.update({
            "social_stage": "close_friend", "romance_stage": "partner",
            "family_plan_discussed": True, "last_intimacy_day": DAY - 2,
        })
        relationship.pop("intimacy", None)

        migrated = interactions.normalize_state(state, DAY)
        value = migrated["relationships"]["1001"]
        self.assertEqual(value["intimacy"], 18.0)
        self.assertTrue(value["family_plan_discussed"])
        self.assertEqual(value["last_intimacy_day"], DAY - 2)

        state["relationships"]["1001"]["intimacy"] = 0
        preserved = interactions.normalize_state(state, DAY)
        self.assertEqual(preserved["relationships"]["1001"]["intimacy"], 0)

    def test_intimacy_is_blocked_before_a_committed_relationship(self) -> None:
        state = state_with_people()
        relationship = state["relationships"]["1001"]
        relationship.update({
            "social_stage": "friend", "romance_stage": "ambiguous",
            "intimacy": 0,
        })

        options = interactions.intimacy_options(state, relationship, DAY)
        self.assertTrue(options)
        self.assertTrue(all(not row["available"] for row in options))
        self.assertTrue(all(
            row["blocked_reason"] == "commitment_required" for row in options
        ))
        with self.assertRaisesRegex(ValueError, "情侣、情人或夫妻"):
            interactions.intimacy_plan(state, 1001, DAY, "embrace")

    def test_committed_stages_expose_intimacy_actions_and_public_view(self) -> None:
        state = state_with_people()
        relationship = set_relationship(
            state, 1001, familiarity=90, affection=90, trust=90,
            attraction=80, respect=90, romance_stage="partner", intimacy=40,
        )
        partner_options = interactions.intimacy_options(state, relationship, DAY)
        for row in partner_options:
            if "partner" in row["stages"]:
                self.assertTrue(row["available"], row["id"])
        getaway = next(row for row in partner_options if row["id"] == "getaway")
        command = next(row for row in partner_options if row["id"] == "command_night")
        self.assertTrue(getaway["available"])
        self.assertTrue(command["available"])

        view = interactions.public_view(state, day=DAY)["relationships"][0]["relationship"]
        self.assertTrue(view["is_intimate"])
        self.assertEqual(view["effective_romance_stage"], "partner")
        self.assertEqual(view["intimacy_band"], "close")
        self.assertEqual(len(view["intimacy_options"]), len(interactions.INTIMATE_ACTIONS))

        relationship.update({
            "romance_stage": "ambiguous", "secret_lover": True,
        })
        secret_view = interactions.public_view(state, day=DAY)["relationships"][0]["relationship"]
        self.assertTrue(secret_view["is_intimate"])
        self.assertEqual(secret_view["effective_romance_stage"], "secret_lover")

        relationship.update({"romance_stage": "spouse", "secret_lover": False})
        spouse_view = interactions.public_view(state, day=DAY)["relationships"][0]["relationship"]
        spouse_options = {row["id"]: row for row in spouse_view["intimacy_options"]}
        self.assertTrue(spouse_options["command_night"]["available"])

    def test_intimate_action_spends_action_points_and_intimacy(self) -> None:
        state = state_with_people()
        relationship = set_relationship(
            state, 1001, familiarity=90, affection=90, trust=90,
            attraction=80, respect=90, romance_stage="partner", intimacy=20,
        )

        result = interactions.intimacy_plan(state, 1001, DAY, "embrace")
        self.assertEqual(result["kind"], "intimacy")
        self.assertEqual(result["action_cost"], 1)
        self.assertEqual(result["intimacy_cost"], 3.0)
        self.assertEqual(result["intimacy_after"], 17.0)
        self.assertEqual(state["action_points"]["current"], 11)
        self.assertEqual(relationship["last_intimacy_day"], DAY)
        self.assertEqual(result["dialogue"]["kind"], "intimacy")

        state["action_points"]["current"] = 12
        relationship.update({
            "romance_stage": "spouse", "secret_lover": False,
            "intimacy": 50,
        })
        command = interactions.intimacy_plan(state, 1001, DAY, "command_night")
        self.assertFalse(command["family_planning"])
        self.assertGreater(command["obedience_gain"], 0)
        self.assertGreater(relationship["obedience"], 0)
        self.assertEqual(command["intimacy_after"], 36.0)
        self.assertEqual(state["action_points"]["current"], 9)
        persisted = interactions.normalize_state(state, DAY)["relationships"]["1001"]
        self.assertGreater(persisted["obedience"], 0)

    def test_intimate_action_rejects_stage_intimacy_and_action_point_gates(self) -> None:
        state = state_with_people()
        relationship = set_relationship(
            state, 1001, familiarity=90, affection=90, trust=90,
            attraction=80, respect=90, romance_stage="partner", intimacy=20,
        )
        with self.assertRaisesRegex(ValueError, "亲密行为无效"):
            interactions.intimacy_plan(state, 1001, DAY, "future_plan")

        relationship["intimacy"] = 0
        with self.assertRaisesRegex(ValueError, "亲密度不足"):
            interactions.intimacy_plan(state, 1001, DAY, "embrace")

        relationship["intimacy"] = 20
        state["action_points"]["current"] = 0
        with self.assertRaisesRegex(ValueError, "行动力不足"):
            interactions.intimacy_plan(state, 1001, DAY, "embrace")

    def test_shared_time_builds_intimacy_only_after_commitment(self) -> None:
        state = state_with_people()
        relationship = set_relationship(
            state, 1001, familiarity=90, affection=90, trust=90,
            attraction=80, respect=90, romance_stage="none", intimacy=0,
        )
        chat = interactions.chat_plan(state, 1001, DAY, "life", "今天怎么样？")
        self.assertEqual(chat["intimacy_gain"], 0)
        self.assertEqual(relationship["intimacy"], 0)

        relationship.update({"romance_stage": "partner", "intimacy": 10})
        state["action_points"]["current"] = 12
        chat = interactions.chat_plan(state, 1001, DAY, "life", "再聊一会儿")
        self.assertEqual(chat["action_cost"], 1)
        self.assertGreater(chat["intimacy_gain"], 0)

        preference = interactions.preference_for(1001)
        gift = interactions.gift_plan(
            state, 1001, DAY, item_id="item-1", sku="book_1",
            item_name="测试礼物", item_value=50_000,
            category=str(preference["gift"]),
        )
        self.assertEqual(gift["action_cost"], 1)
        self.assertGreater(gift["intimacy_gain"], 0)

        relationship["social_stage"] = "close_friend"
        date = interactions.date_plan(state, 1001, DAY, "cafe")
        self.assertEqual(date["action_cost"], 2)
        self.assertGreater(date["intimacy_gain"], 0)
        self.assertGreater(relationship["intimacy"], 10)


if __name__ == "__main__":
    unittest.main()

