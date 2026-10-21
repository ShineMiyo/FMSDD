"""Save-scoped player interactions for FMSDD.

The module owns the interaction document: the save-scoped player profile,
cached adult players, five-dimensional relationships, weekly action points,
residences, permanent gift records and the relationship timeline. It never
moves wallet money or owns FM native data. The HTTP facade resolves live player
snapshots and coordinates the existing life, inventory and wallet documents.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import threading
from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

from tools import life_system
from tools import life_travel
from tools.account_store import load_document, save_document
from tools.money import round_money
from tools import life_children


DOCUMENT = "life_interactions"
SCHEMA_VERSION = 8
MAX_ACTION_POINTS = 12
WEEKLY_ACTION_RECOVERY = 6
ACTION_POINT_PERK_MAXIMUM_BONUS = 12
ACTION_POINT_PERK_RECOVERY_BONUS = 24
RELATIONSHIP_GAIN_PERK_MULTIPLIER = 10.0
CDK_PERK_EFFECTS = ("action_points", "relationship_gain")
MIN_ADULT_AGE = 18
MAX_TIMELINE_ROWS = 800
MAX_GIFT_LEDGER_ROWS = 500
MAX_ACTION_POINT_LEDGER_ROWS = 300
PROFILE_ATTRIBUTE_KEYS = ("appearance", "ability", "charisma", "eq")
PROFILE_REPUTATION_KEY = "reputation"
PROFILE_ALLOCATABLE_KEYS = (*PROFILE_ATTRIBUTE_KEYS, PROFILE_REPUTATION_KEY)
PROFILE_REPUTATION_COST = 5
PROFILE_LEGACY_REPUTATION_KEY = PROFILE_REPUTATION_KEY
MAX_CHAT_MESSAGE_CHARS = 500
PROFILE_BASE_POINTS = 200
PROFILE_ATTRIBUTE_MIN = 1
PROFILE_ATTRIBUTE_SAFE_MAX = 1_000_000_000
PROFILE_IDENTITY_MODEL_VERSION = 3
PROFILE_IDENTITY_ANCHOR_AGE = 30
PROFILE_IDENTITY_ANCHOR_HEIGHT_CM = 180
PROFILE_IDENTITY_ANCHOR_WEIGHT_KG = 75
PROFILE_AGE_COST_RATE = 2.2
PROFILE_AGE_COST_EXPONENT = 1.4
PROFILE_HEIGHT_COST_RATE = 1.15
PROFILE_WEIGHT_COST_RATE = 0.9
MAX_PROFILE_POINT_LEDGER_ROWS = 240
ACTION_POINT_PURCHASE_PRICE = 50_000_000
MONEY_GIFT_MIN = 100_000
MONEY_GIFT_MAX = 1_000_000_000
ENCOUNTER_ID_BASE = 1_800_000_000
ENCOUNTER_ID_LIMIT = 1_899_999_999
TRAVEL_PLACE_MAX = 80
TRAVEL_PENDING_MAX_AGE_DAYS = 30

COMPOUND_SURNAMES = (
    "欧阳", "上官", "司马", "诸葛", "东方", "皇甫", "尉迟", "公孙",
    "慕容", "长孙", "宇文", "司徒", "夏侯", "令狐", "钟离", "轩辕",
    "端木", "独孤", "南宫", "西门", "百里", "呼延", "东郭", "北冥",
    "名取", "安倍", "佐藤", "铃木", "高桥", "田中", "渡边", "伊藤",
)

DIMENSIONS = ("familiarity", "affection", "trust", "attraction", "respect")
SOCIAL_STAGES = ("acquaintance", "friend", "close_friend", "confidant")
SOCIAL_STAGE_RANK = {stage: rank for rank, stage in enumerate(SOCIAL_STAGES)}
ROMANCE_STAGES = ("none", "ambiguous", "partner", "spouse")
ROMANCE_STAGE_RANK = {stage: rank for rank, stage in enumerate(ROMANCE_STAGES)}

SOCIAL_STAGE_REQUIREMENTS = {
    "friend": {"familiarity": 25.0, "affection": 30.0, "trust": 20.0},
    "close_friend": {
        "familiarity": 50.0, "affection": 55.0,
        "trust": 45.0, "respect": 35.0,
    },
    "confidant": {
        "familiarity": 75.0, "affection": 75.0,
        "trust": 70.0, "respect": 60.0,
    },
}
ROMANCE_STAGE_REQUIREMENTS = {
    "ambiguous": {"social_stage": "close_friend", "attraction": 35.0, "affection": 30.0},
    "partner": {"attraction": 50.0, "affection": 45.0},
    "secret_lover": {"attraction": 55.0, "trust": 40.0},
    "spouse": {"affection": 70.0, "trust": 65.0},
}
BOND_STAGES = ("none", "partner", "kindred", "best_friend", "brother", "sworn_brother")
BOND_STAGE_RANK = {stage: rank for rank, stage in enumerate(BOND_STAGES)}
BOND_STAGE_REQUIREMENTS = {
    "partner": {
        "social_stage": "close_friend", "familiarity": 55.0,
        "trust": 45.0, "respect": 35.0,
    },
    "kindred": {
        "bond_stage": "partner", "familiarity": 65.0,
        "affection": 60.0, "respect": 45.0,
    },
    "best_friend": {
        "bond_stage": "kindred", "affection": 75.0,
        "trust": 65.0, "respect": 55.0,
    },
    "brother": {
        "trust": 70.0, "respect": 60.0, "affection": 55.0,
    },
    "sworn_brother": {
        "bond_stage": "brother", "trust": 85.0,
        "respect": 75.0, "affection": 70.0,
    },
}
RELATIONSHIP_TONES = ("stranger", "distant", "polite", "familiar", "close", "trusted", "bonded")
RELATIONSHIP_TONE_BANDS = (
    (0.0, "stranger"), (20.0, "distant"), (35.0, "polite"),
    (50.0, "familiar"), (65.0, "close"), (80.0, "trusted"),
    (92.0, "bonded"),
)

GIFT_CATEGORIES = (
    "book", "fashion", "technology", "food", "sport", "music", "art", "luxury",
    "romance", "intimate",
)
CONVERSATION_TOPICS = (
    "football", "life", "ambition", "culture", "humour", "family",
)
DATE_ACTIVITIES = {
    "cafe": {"ap": 2, "label": "咖啡馆"},
    "walk": {"ap": 2, "label": "城市散步"},
    "cinema": {"ap": 2, "label": "看电影"},
    "museum": {"ap": 2, "label": "看展"},
    "dinner": {"ap": 3, "label": "共进晚餐"},
    "sports": {"ap": 3, "label": "现场观赛"},
    "concert": {"ap": 3, "label": "音乐会"},
    "trip": {"ap": 4, "label": "短途旅行"},
}
ACTION_COSTS = {"chat": 1, "gift": 1, "asset_gift": 1, "money_gift": 1, "date": 2, "relationship": 3}
INTIMACY_MIN = -100.0
INTIMACY_MAX = 100.0
INTIMACY_DEFAULTS = {"partner": 18.0, "secret_lover": 15.0, "spouse": 28.0}
INTIMACY_BANDS = (
    (-100.0, "fractured"), (-70.0, "hostile"), (-40.0, "strained"),
    (-15.0, "cold"), (0.0, "new"), (20.0, "warm"), (40.0, "close"),
    (60.0, "devoted"), (80.0, "bonded"),
)
INTIMATE_ACTIONS = {
    "embrace": {
        "ap": 1, "intimacy": 3.0, "icon": "heart-handshake",
        "stages": ("partner", "secret_lover", "spouse"),
        "obedience_gain": 0.5,
        "deltas": {"affection": 1.2, "trust": 0.4, "attraction": 1.6, "respect": 0.2},
    },
    "kiss": {
        "ap": 2, "intimacy": 7.0, "icon": "heart",
        "stages": ("partner", "secret_lover", "spouse"),
        "obedience_gain": 1.0,
        "deltas": {"affection": 2.2, "trust": 0.8, "attraction": 2.8, "respect": 0.2},
    },
    "cuddle": {
        "ap": 2, "intimacy": 9.0, "icon": "sofa",
        "stages": ("partner", "secret_lover", "spouse"),
        "obedience_gain": 1.5,
        "deltas": {"familiarity": 0.8, "affection": 2.0, "trust": 2.2, "attraction": 1.8},
    },
    "stay_close": {
        "ap": 3, "intimacy": 13.0, "icon": "moon-star",
        "stages": ("partner", "secret_lover", "spouse"),
        "pregnancy": True, "obedience_gain": 3.0,
        "deltas": {"affection": 2.8, "trust": 3.0, "attraction": 2.0, "respect": 0.6},
    },
    "playful_night": {
        "ap": 3, "intimacy": 12.0, "icon": "sparkles",
        "stages": ("partner", "secret_lover", "spouse"),
        "requires_item": "intimate_toy",
        "pregnancy": True, "obedience_gain": 6.0,
        "deltas": {"affection": 3.2, "trust": 1.4, "attraction": 3.4, "respect": 0.4},
    },
    "blindfold_night": {
        "ap": 3, "intimacy": 10.0, "icon": "eye-off",
        "stages": ("partner", "secret_lover", "spouse"),
        "requires_item": "intimate_blindfold",
        "pregnancy": True, "obedience_gain": 8.0,
        "deltas": {"affection": 2.0, "trust": 4.0, "attraction": 2.2, "respect": 0.6},
    },
    "dice_night": {
        "ap": 2, "intimacy": 8.0, "icon": "dices",
        "stages": ("partner", "secret_lover", "spouse"),
        "requires_item": "intimate_dice",
        "pregnancy": True, "obedience_gain": 4.0,
        "deltas": {"affection": 2.2, "trust": 1.8, "attraction": 2.6, "respect": 0.2},
    },
    "command_night": {
        "ap": 3, "intimacy": 14.0, "icon": "crown",
        "stages": ("partner", "secret_lover", "spouse"),
        "pregnancy": True, "obedience_gain": 10.0,
        "deltas": {"affection": 2.4, "trust": 2.0, "attraction": 4.0, "respect": 2.8},
    },
    "claim_night": {
        "ap": 4, "intimacy": 16.0, "icon": "flame",
        "stages": ("partner", "secret_lover", "spouse"),
        "pregnancy": True, "obedience_gain": 12.0,
        "deltas": {"affection": 3.0, "trust": 2.4, "attraction": 4.6, "respect": 2.2},
    },
    "getaway": {
        "ap": 4, "intimacy": 18.0, "icon": "plane",
        "stages": ("partner", "secret_lover", "spouse"),
        "obedience_gain": 2.0,
        "deltas": {"familiarity": 1.8, "affection": 3.8, "trust": 3.2, "attraction": 3.0, "respect": 0.8},
    },
}

PREGNANCY_GESTATION_DAYS = 280
PREGNANCY_EARLY_DAYS = 252
PREGNANCY_LATE_DAYS = 301
PREGNANCY_DISCOVERY_DAYS = 30
PREGNANCY_MIN_CHANCE = 0.035
PREGNANCY_MAX_CHANCE = 0.38
SECRET_EXPOSURE_THRESHOLD = 45.0
RELATIONSHIP_CRISIS_THRESHOLD = -40.0
RELATIONSHIP_CRISIS_SEVERE_THRESHOLD = -70.0
RELATIONSHIP_CRISIS_GRACE_DAYS = 7
MAX_EVENT_ROWS = 120

ASSET_LEVELS = (
    {"level": 1, "threshold": 0, "points": 0, "vehicle": ""},
    {"level": 2, "threshold": 2_000_000, "points": 2, "vehicle": "car-462"},
    {"level": 3, "threshold": 8_000_000, "points": 3, "vehicle": "car-339"},
    {"level": 4, "threshold": 30_000_000, "points": 4, "vehicle": "car-120"},
    {"level": 5, "threshold": 100_000_000, "points": 5, "vehicle": "car-383"},
    {"level": 6, "threshold": 300_000_000, "points": 7, "vehicle": "car-124"},
    {"level": 7, "threshold": 900_000_000, "points": 9, "vehicle": "car-71"},
    {"level": 8, "threshold": 2_700_000_000, "points": 11, "vehicle": ""},
    {"level": 9, "threshold": 8_000_000_000, "points": 14, "vehicle": ""},
    {"level": 10, "threshold": 24_000_000_000, "points": 18, "vehicle": ""},
    {"level": 11, "threshold": 72_000_000_000, "points": 23, "vehicle": "car-816"},
    {"level": 12, "threshold": 216_000_000_000, "points": 30, "vehicle": ""},
)

PERSONALITY_TRAITS = (
    "warm", "outgoing", "reserved", "driven", "playful", "grounded",
)
CORE_VALUES = (
    "family", "career", "honesty", "freedom", "stability", "loyalty",
)

_LOCK = threading.RLock()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clamp(value: Any, minimum: float = 0.0, maximum: float = 100.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(maximum, parsed))


def _clamp_intimacy(value: Any) -> float:
    return _clamp(value, INTIMACY_MIN, INTIMACY_MAX)


def _eq_factor(state: dict[str, Any]) -> float:
    """Return a bounded social-calibration multiplier for emotional intelligence."""
    profile = state.get("profile") if isinstance(state.get("profile"), dict) else {}
    try:
        eq = max(PROFILE_ATTRIBUTE_MIN, int(profile.get("eq") or PROFILE_ATTRIBUTE_MIN))
    except (TypeError, ValueError):
        eq = PROFILE_ATTRIBUTE_MIN
    return round(0.80 + min(1.0, eq / 100.0) * 0.40, 4)


def _pregnancy_chance(
    state: dict[str, Any], relationship: dict[str, Any],
) -> float:
    """Return a bounded conception chance for the eligible couple.

    The interaction model only needs a plausible, deterministic roll.  It is
    intentionally restricted to a male player and an adult female NPC, and an
    already expectant relationship cannot roll a second pregnancy.
    """
    profile = state.get("profile") if isinstance(state.get("profile"), dict) else {}
    if str(profile.get("gender") or "") != "male":
        return 0.0
    person = (state.get("people") or {}).get(str(int(relationship.get("person_id") or 0)))
    if not isinstance(person, dict) or person.get("female") is not True:
        return 0.0
    age = _integer(person.get("age"), MIN_ADULT_AGE, 99, MIN_ADULT_AGE)
    if age > 45:
        return 0.0
    pregnancy = relationship.get("pregnancy") if isinstance(relationship.get("pregnancy"), dict) else {}
    if str(pregnancy.get("status") or "") == "expecting":
        return 0.0
    contraception = relationship.get("contraception") if isinstance(relationship.get("contraception"), dict) else {}
    contraception_until = int(contraception.get("until_day") or 0)
    chance_factor = 0.05 if (
        contraception_until > 0
        and contraception_until >= int(relationship.get("last_action_day") or 0)
    ) else 1.0
    stage = effective_romance_stage(relationship)
    if stage not in {"partner", "secret_lover", "spouse"}:
        return 0.0
    intimacy = max(0.0, _clamp_intimacy(relationship.get("intimacy")))
    ratio = max(0.0, min(1.0, intimacy / INTIMACY_MAX))
    # Higher intimacy always means a higher chance; the curve is intentionally
    # flat at the low end so early intimacy does not feel deterministic.
    chance = (
        0.04
        + (ratio ** 1.2) * 0.30
        + (0.055 if stage == "spouse" else 0.015)
    )
    age_factor = max(0.35, 1.0 - max(0, age - 28) * 0.025)
    return round(max(
        PREGNANCY_MIN_CHANCE,
        min(PREGNANCY_MAX_CHANCE, chance * age_factor * chance_factor),
    ), 4)


def _integer(value: Any, minimum: int, maximum: int, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def effective_romance_stage(relationship: Any) -> str:
    """Resolve the user-facing bond, including a committed secret lover."""
    source = relationship if isinstance(relationship, dict) else {}
    romance = str(source.get("romance_stage") or "none")
    if romance == "ambiguous" and bool(source.get("secret_lover")):
        return "secret_lover"
    return romance if romance in ROMANCE_STAGES else "none"


def _profile_gender(state: dict[str, Any]) -> str:
    profile = state.get("profile") if isinstance(state.get("profile"), dict) else {}
    gender = str(profile.get("gender") or "male").strip().lower()
    return gender if gender in {"male", "female", "nonbinary"} else "male"


def _person_female(state: dict[str, Any], relationship: dict[str, Any]) -> bool | None:
    person = (state.get("people") or {}).get(str(int(relationship.get("person_id") or 0)))
    if not isinstance(person, dict):
        return None
    value = person.get("female")
    return value if isinstance(value, bool) else None


def relationship_branch_capabilities(
    state: dict[str, Any], relationship: dict[str, Any],
) -> dict[str, bool]:
    """Return the relationship lines available for this player/NPC pair.

    The game only exposes a binary NPC flag today. Unknown NPC gender is treated
    as permissive so an old or partially refreshed snapshot never locks the
    player out of the only line they could advance.
    """
    gender = _profile_gender(state)
    female = _person_female(state, relationship)
    if gender == "nonbinary" or female is None:
        return {
            "romance": True, "sisterhood": True,
            "brotherhood": True, "brotherhood_direct": True,
            "brotherhood_kindred": False,
        }
    if gender == "female":
        return {
            "romance": female is False,
            "sisterhood": female is True,
            "brotherhood": female is False,
            "brotherhood_direct": False,
            "brotherhood_kindred": female is False,
        }
    return {
        "romance": female is True,
        "sisterhood": female is True,
        "brotherhood": female is False,
        "brotherhood_direct": female is False,
        "brotherhood_kindred": False,
    }


def bond_variant_for(state: dict[str, Any], relationship: dict[str, Any]) -> str:
    """Return which friendship line a bond belongs to.

    Female player + male NPC uses partner → kindred → brother; male + male and
    non-binary brotherhood use partner → brother → sworn brother; sisterhood
    uses partner → kindred → best friend. Legacy rows without a variant are
    inferred from the current gender pair.
    """
    explicit = str(relationship.get("bond_variant") or "")
    if explicit in {"sisterhood", "brotherhood_direct", "brotherhood_kindred"}:
        return explicit
    if str(relationship.get("bond_line") or "") == "sisterhood":
        return "sisterhood"
    caps = relationship_branch_capabilities(state, relationship)
    return "brotherhood_kindred" if caps["brotherhood_kindred"] else "brotherhood_direct"


def relationship_level(relationship: Any) -> str:
    """Resolve one user-facing level across the social, romance and bond lines."""
    source = relationship if isinstance(relationship, dict) else {}
    romance = effective_romance_stage(source)
    if romance == "ambiguous":
        return "ambiguous"
    if romance == "partner":
        return "couple"
    if romance == "spouse":
        return "spouse"
    bond = str(source.get("bond_stage") or "none")
    if bond in BOND_STAGES and bond != "none":
        return bond
    social = str(source.get("social_stage") or "acquaintance")
    if social == "confidant":
        return "best_friend"
    return social if social in {"acquaintance", "friend", "close_friend"} else "acquaintance"


def relationship_tone(relationship: Any) -> dict[str, Any]:
    """Describe how the two people currently relate, separately from the level."""
    source = relationship if isinstance(relationship, dict) else {}
    score = (
        float(source.get("familiarity") or 0) * 0.30
        + float(source.get("affection") or 0) * 0.30
        + float(source.get("trust") or 0) * 0.25
        + float(source.get("respect") or 0) * 0.15
    )
    key = RELATIONSHIP_TONES[0]
    for threshold, candidate in RELATIONSHIP_TONE_BANDS:
        if score >= threshold:
            key = candidate
    return {"key": key, "score": round(score, 1)}


def relationship_allows_intimacy(relationship: Any) -> bool:
    return effective_romance_stage(relationship) in {"partner", "secret_lover", "spouse"}


def intimacy_band(value: Any) -> str:
    score = _clamp_intimacy(value)
    band = "fractured"
    for threshold, key in INTIMACY_BANDS:
        if score >= threshold:
            band = key
    return band


def _initial_intimacy_for_stage(stage: str) -> float:
    return float(INTIMACY_DEFAULTS.get(str(stage or ""), 0.0))


def _add_intimacy(
    relationship: dict[str, Any], amount: float, *, gain_multiplier: float = 1.0,
) -> float:
    """Adjust signed intimacy for a committed relationship and return the change."""
    if not relationship_allows_intimacy(relationship):
        return 0.0
    before = _clamp_intimacy(relationship.get("intimacy"))
    gain = float(amount or 0.0)
    if gain > 0:
        gain *= max(1.0, float(gain_multiplier or 1.0))
    after = _clamp_intimacy(before + gain)
    relationship["intimacy"] = round(after, 2)
    relationship["updated_at"] = _now()
    return round(after - before, 2)


def _normalize_action_point_ledger(raw: Any) -> list[dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    for row in raw if isinstance(raw, list) else []:
        if not isinstance(row, dict):
            continue
        amount = _integer(row.get("amount"), -999, 999, 0)
        if not amount:
            continue
        ledger.append({
            "id": str(row.get("id") or "")[:80],
            "day": _integer(row.get("day"), 0, 10_000_000, 0),
            "at": str(row.get("at") or _now()),
            "amount": amount,
            "balance_after": _integer(row.get("balance_after"), 0, 999, 0),
            "reason": str(row.get("reason") or "other")[:80],
            "person_id": _integer(row.get("person_id"), 0, 2_147_483_647, 0),
            "person_name": str(row.get("person_name") or "")[:160],
            "detail": str(row.get("detail") or "")[:160],
        })
    return ledger[-MAX_ACTION_POINT_LEDGER_ROWS:]


def _record_action_point_change(
    state: dict[str, Any], day: int, amount: int, reason: str, *,
    person_id: int = 0, person_name: str = "", detail: str = "",
) -> dict[str, Any] | None:
    delta = _integer(amount, -999, 999, 0)
    if not delta:
        return None
    points = state.get("action_points") if isinstance(state.get("action_points"), dict) else {}
    row = {
        "id": _next_id(state, "action-point"),
        "day": int(day or 0),
        "at": _now(),
        "amount": delta,
        "balance_after": int(points.get("current") or 0),
        "reason": str(reason or "other")[:80],
        "person_id": int(person_id or 0),
        "person_name": str(person_name or "")[:160],
        "detail": str(detail or "")[:160],
    }
    ledger = _normalize_action_point_ledger(state.get("action_point_ledger"))
    ledger.append(row)
    state["action_point_ledger"] = ledger[-MAX_ACTION_POINT_LEDGER_ROWS:]
    return row


def _normalize_entitlements(raw: Any) -> dict[str, dict[str, Any]]:
    """Normalize permanent CDK benefits stored with the interaction save."""
    source = raw if isinstance(raw, dict) else {}
    entitlements: dict[str, dict[str, Any]] = {}
    for effect in CDK_PERK_EFFECTS:
        record = source.get(effect)
        if not isinstance(record, dict) or not str(record.get("code") or "").strip():
            continue
        normalized = {
            "code": str(record.get("code") or "").strip()[:80],
            "effect": effect,
            "activated_at": str(record.get("activated_at") or record.get("at") or _now()),
            "day": _integer(record.get("day"), 0, 10_000_000, 0),
        }
        if effect == "action_points":
            normalized.update({
                "maximum_bonus": ACTION_POINT_PERK_MAXIMUM_BONUS,
                "weekly_recovery_bonus": ACTION_POINT_PERK_RECOVERY_BONUS,
            })
        else:
            normalized["multiplier"] = RELATIONSHIP_GAIN_PERK_MULTIPLIER
        entitlements[effect] = normalized
    return entitlements


def _action_point_limits(state: dict[str, Any]) -> tuple[int, int]:
    entitlements = state.get("entitlements") if isinstance(state.get("entitlements"), dict) else {}
    bonus = ACTION_POINT_PERK_MAXIMUM_BONUS if "action_points" in entitlements else 0
    recovery = ACTION_POINT_PERK_RECOVERY_BONUS if "action_points" in entitlements else 0
    return MAX_ACTION_POINTS + bonus, WEEKLY_ACTION_RECOVERY + recovery


def _relationship_gain_multiplier(state: dict[str, Any]) -> float:
    entitlements = state.get("entitlements") if isinstance(state.get("entitlements"), dict) else {}
    return RELATIONSHIP_GAIN_PERK_MULTIPLIER if "relationship_gain" in entitlements else 1.0


def _scale_positive_deltas(
    deltas: dict[str, float], multiplier: float = 1.0,
) -> dict[str, float]:
    scale = max(1.0, float(multiplier or 1.0))
    return {
        key: round(float(value) * scale if float(value) > 0 else float(value), 2)
        for key, value in deltas.items()
    }


def _stable_unit(*parts: Any) -> float:
    raw = "|".join(str(part) for part in parts).encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    return int.from_bytes(digest[:8], "little") / float(1 << 64)


def _date_monday_ordinal(day: int) -> int:
    current = date.fromordinal(int(day))
    return (current - timedelta(days=current.weekday())).toordinal()


def _week_key(day: int) -> str:
    iso = date.fromordinal(int(day)).isocalendar()
    return f"{int(iso.year)}-W{int(iso.week):02d}"


def _empty_profile() -> dict[str, Any]:
    return {
        "name": "", "surname": "", "given_name": "", "gender": "male",
        "age": 30, "height_cm": 180,
        "weight_kg": 75, "appearance": 1, "ability": 1, "charisma": 1, "eq": 1,
        "reputation": 1, "bio": "", "completed": False, "updated_at": "",
        "points_base": PROFILE_BASE_POINTS, "points_earned": 0,
        "points_spent": len(PROFILE_ATTRIBUTE_KEYS) + PROFILE_REPUTATION_COST,
        "points_available": PROFILE_BASE_POINTS - len(PROFILE_ATTRIBUTE_KEYS) - PROFILE_REPUTATION_COST,
        "point_ledger": [], "profile_model": PROFILE_IDENTITY_MODEL_VERSION,
        "identity_cost": {"total": 0, "age": 0, "height": 0, "weight": 0},
    }


def _has_cjk_name(value: str) -> bool:
    return any(
        "\u3400" <= character <= "\u9fff"
        or "\uf900" <= character <= "\ufaff"
        for character in value
    )


def _split_profile_name(raw_name: Any) -> tuple[str, str]:
    """Split a legacy display name while keeping the original display text."""
    text = str(raw_name or "").strip()
    if not text:
        return "", ""
    if _has_cjk_name(text):
        for surname in sorted(COMPOUND_SURNAMES, key=len, reverse=True):
            if text.startswith(surname) and len(text) > len(surname):
                return surname, text[len(surname):]
        if len(text) > 1:
            return text[0], text[1:]
        return "", text
    parts = text.rsplit(None, 1)
    if len(parts) == 2:
        return parts[1], parts[0]
    return "", text


def _compose_profile_name(surname: Any, given_name: Any) -> str:
    family = str(surname or "").strip()
    given = str(given_name or "").strip()
    if not family:
        return given
    if not given:
        return family
    if _has_cjk_name(family + given):
        return f"{family}{given}"
    return f"{given} {family}"


def profile_identity_cost(age: Any, height_cm: Any, weight_kg: Any) -> dict[str, int]:
    """Return the point cost of the current age, height and weight settings.

    Cost is measured against a neutral 30-year-old, 180 cm, 75 kg anchor.
    Being younger, taller or lighter consumes points; moving toward the anchor
    releases them again. The calculation is target-based, not cumulative.
    """
    resolved_age = _integer(age, MIN_ADULT_AGE, 99, PROFILE_IDENTITY_ANCHOR_AGE)
    resolved_height = _integer(height_cm, 120, 230, PROFILE_IDENTITY_ANCHOR_HEIGHT_CM)
    resolved_weight = _integer(weight_kg, 35, 200, PROFILE_IDENTITY_ANCHOR_WEIGHT_KG)
    age_gap = max(0, PROFILE_IDENTITY_ANCHOR_AGE - resolved_age)
    age_cost = int(round((age_gap ** PROFILE_AGE_COST_EXPONENT) * PROFILE_AGE_COST_RATE))
    height_cost = int(round(max(0, resolved_height - PROFILE_IDENTITY_ANCHOR_HEIGHT_CM) * PROFILE_HEIGHT_COST_RATE))
    weight_cost = int(round(max(0, PROFILE_IDENTITY_ANCHOR_WEIGHT_KG - resolved_weight) * PROFILE_WEIGHT_COST_RATE))
    return {
        "total": age_cost + height_cost + weight_cost,
        "age": age_cost,
        "height": height_cost,
        "weight": weight_cost,
    }


def _normalize_profile_point_ledger(raw: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        points = _integer(item.get("points"), 1, PROFILE_ATTRIBUTE_SAFE_MAX, 0)
        if not points:
            continue
        rows.append({
            "id": str(item.get("id") or "")[:80],
            "source": str(item.get("source") or "manual")[:80],
            "reference": str(item.get("reference") or "")[:160],
            "points": points,
            "at": str(item.get("at") or _now()),
            "day": _integer(item.get("day"), 0, 10_000_000, 0),
        })
    return rows[-MAX_PROFILE_POINT_LEDGER_ROWS:]


def _normalize_profile(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    profile = _empty_profile()
    completed = bool(source.get("completed"))
    profile_model = _integer(source.get("profile_model"), 0, 999, 0)
    # Profiles created before the allocation system stored 50 in every
    # attribute. Preserve explicit values, and use 50 only for a genuinely
    # missing attribute on an already-completed legacy profile.
    attribute_fallback = 50 if completed else PROFILE_ATTRIBUTE_MIN
    raw_name = str(source.get("name") or "")[:80]
    surname = str(source.get("surname") or "").strip()[:40]
    given_name = str(source.get("given_name") or "").strip()[:40]
    if not surname and not given_name and raw_name:
        surname, given_name = _split_profile_name(raw_name)
    display_name = _compose_profile_name(surname, given_name) or raw_name
    eq_missing = source.get("eq") in (None, "")
    profile.update({
        "name": display_name[:80],
        "surname": surname,
        "given_name": given_name,
        "gender": str(source.get("gender") or "male")[:20],
        "age": _integer(source.get("age"), 18, 99, 30),
        "height_cm": _integer(source.get("height_cm"), 120, 230, 180),
        "weight_kg": _integer(source.get("weight_kg"), 35, 200, 75),
        "appearance": _integer(source.get("appearance"), PROFILE_ATTRIBUTE_MIN, PROFILE_ATTRIBUTE_SAFE_MAX, attribute_fallback),
        "ability": _integer(source.get("ability"), PROFILE_ATTRIBUTE_MIN, PROFILE_ATTRIBUTE_SAFE_MAX, attribute_fallback),
        "charisma": _integer(source.get("charisma"), PROFILE_ATTRIBUTE_MIN, PROFILE_ATTRIBUTE_SAFE_MAX, attribute_fallback),
        "eq": _integer(source.get("eq"), PROFILE_ATTRIBUTE_MIN, PROFILE_ATTRIBUTE_SAFE_MAX, PROFILE_ATTRIBUTE_MIN),
        "reputation": _integer(source.get("reputation"), PROFILE_ATTRIBUTE_MIN, PROFILE_ATTRIBUTE_SAFE_MAX, attribute_fallback),
        "bio": str(source.get("bio") or "")[:500],
        "completed": completed,
        "updated_at": str(source.get("updated_at") or ""),
        "profile_model": PROFILE_IDENTITY_MODEL_VERSION,
    })
    identity_cost = profile_identity_cost(
        profile["age"], profile["height_cm"], profile["weight_kg"],
    )
    profile["identity_cost"] = identity_cost
    ledger = _normalize_profile_point_ledger(source.get("point_ledger"))
    # Older saves predate the ledger. Reconstruct a permanent legacy balance so
    # a later asset reward cannot erase points that made an existing profile
    # valid. A completed legacy profile may also have allocated more than the
    # base 200 points before the allocation system was introduced.
    explicit_earned = _integer(
        source.get("points_earned"), 0, 99 * MAX_PROFILE_POINT_LEDGER_ROWS, 0,
    )
    ledger_points = sum(int(row["points"]) for row in ledger)
    core_attribute_spent = sum(int(profile[key]) for key in PROFILE_ATTRIBUTE_KEYS)
    attribute_spent = core_attribute_spent + int(profile[PROFILE_REPUTATION_KEY]) * PROFILE_REPUTATION_COST
    legacy_points = max(0, explicit_earned - ledger_points)
    if profile["completed"]:
        legacy_points = max(
            legacy_points,
            core_attribute_spent - PROFILE_BASE_POINTS - explicit_earned,
        )
    if legacy_points > 0:
        ledger.append({
            "id": "legacy-profile-points",
            "source": "legacy",
            "reference": "pre-ledger",
            "points": min(99 * MAX_PROFILE_POINT_LEDGER_ROWS, legacy_points),
            "at": str(source.get("updated_at") or _now()),
            "day": 0,
        })
        ledger_points += int(ledger[-1]["points"])
    if (
        profile["completed"]
        and profile_model < PROFILE_IDENTITY_MODEL_VERSION
        and identity_cost["total"] > 0
    ):
        ledger.append({
            "id": "identity-profile-points",
            "source": "identity_migration",
            "reference": "pre-identity-cost-model",
            "points": identity_cost["total"],
            "at": str(source.get("updated_at") or _now()),
            "day": 0,
        })
        ledger_points += identity_cost["total"]
    if (
        profile["completed"]
        and profile_model < PROFILE_IDENTITY_MODEL_VERSION
        and not any(row.get("source") == "reputation_migration" for row in ledger)
    ):
        reputation_points = int(profile[PROFILE_REPUTATION_KEY]) * PROFILE_REPUTATION_COST
        if reputation_points > 0:
            ledger.append({
                "id": "reputation-profile-points",
                "source": "reputation_migration",
                "reference": "pre-reputation-cost-model",
                "points": reputation_points,
                "at": str(source.get("updated_at") or _now()),
                "day": 0,
            })
            ledger_points += reputation_points
    if profile["completed"] and eq_missing and not any(
        row.get("source") == "eq_migration" for row in ledger
    ):
        ledger.append({
            "id": "eq-profile-points",
            "source": "eq_migration",
            "reference": "pre-equilibrium-model",
            "points": 1,
            "at": str(source.get("updated_at") or _now()),
            "day": 0,
        })
        ledger_points += 1
    earned = max(explicit_earned, ledger_points)
    total = PROFILE_BASE_POINTS + earned
    spent = attribute_spent + identity_cost["total"]
    profile.update({
        "points_base": PROFILE_BASE_POINTS,
        "points_earned": earned,
        "points_spent": spent,
        "points_available": max(0, total - spent),
        "point_ledger": ledger,
    })
    return profile


def _stable_key_order(items: tuple[str, ...], *parts: Any) -> list[str]:
    return sorted(items, key=lambda item: _stable_unit(*parts, item))


def _normalize_person_traits(
    raw: Any, person_id: int, *, female: bool | None, age: int,
) -> dict[str, Any]:
    """Return stable, game-appropriate traits for one adult player.

    FM height and weight are kept when a live snapshot supplies plausible
    values.  Personality, values, preferences and the optional adult-female
    measurements are deterministic per UID, so refreshes never reroll a person.
    """

    source = raw if isinstance(raw, dict) else {}
    seed = hashlib.sha256(f"life-person-traits:{int(person_id)}:v2".encode("utf-8")).digest()
    female_value = bool(female) if isinstance(female, bool) else False

    fallback_height = (
        158 + seed[0] % 29 if female_value else 170 + seed[0] % 31
    )
    height = _integer(source.get("height_cm"), 140, 220, fallback_height)
    bmi_target = 20.2 + (seed[1] % 46) / 10.0
    fallback_weight = int(round(bmi_target * (height / 100.0) ** 2))
    weight = _integer(source.get("weight_kg"), 42, 150, fallback_weight)

    personality_order = _stable_key_order(PERSONALITY_TRAITS, "personality", person_id)
    values_order = _stable_key_order(CORE_VALUES, "values", person_id)
    personality = [
        value for value in (source.get("personality") or [])
        if str(value) in PERSONALITY_TRAITS
    ][:2]
    for value in personality_order:
        if len(personality) >= 2:
            break
        if value not in personality:
            personality.append(value)
    core_values = [
        value for value in (source.get("values") or [])
        if str(value) in CORE_VALUES
    ][:2]
    for value in values_order:
        if len(core_values) >= 2:
            break
        if value not in core_values:
            core_values.append(value)

    preferences = preference_for(int(person_id))
    topic_order = _stable_key_order(CONVERSATION_TOPICS, "liked-topics", person_id)
    activity_order = _stable_key_order(tuple(DATE_ACTIVITIES), "liked-activities", person_id)
    gift_order = _stable_key_order(GIFT_CATEGORIES, "liked-gifts", person_id)
    likes_source = source.get("likes") if isinstance(source.get("likes"), dict) else {}
    likes = {
        "topics": [
            value for value in (likes_source.get("topics") or [])
            if str(value) in CONVERSATION_TOPICS
        ][:3],
        "activities": [
            value for value in (likes_source.get("activities") or [])
            if str(value) in DATE_ACTIVITIES
        ][:3],
        "gifts": [
            value for value in (likes_source.get("gifts") or [])
            if str(value) in GIFT_CATEGORIES
        ][:3],
    }
    for collection, primary, ordered in (
        (likes["topics"], preferences["topic"], topic_order),
        (likes["activities"], preferences["activity"], activity_order),
        (likes["gifts"], preferences["gift"], gift_order),
    ):
        for value in (primary, *ordered):
            if len(collection) >= 3:
                break
            if value not in collection:
                collection.append(value)

    measurements: dict[str, int] = {}
    raw_measurements = source.get("measurements") if isinstance(source.get("measurements"), dict) else {}
    if female_value and int(age) >= MIN_ADULT_AGE:
        measurements = {
            "bust_cm": _integer(
                raw_measurements.get("bust_cm"), 74, 118,
                int(round(height * 0.53 + (seed[2] % 9) - 4)),
            ),
            "waist_cm": _integer(
                raw_measurements.get("waist_cm"), 52, 100,
                int(round(height * 0.39 + (seed[3] % 9) - 4)),
            ),
            "hips_cm": _integer(
                raw_measurements.get("hips_cm"), 76, 126,
                int(round(height * 0.55 + (seed[4] % 11) - 5)),
            ),
        }

    return {
        "height_cm": height,
        "weight_kg": weight,
        "personality": personality,
        "values": core_values,
        "likes": likes,
        "dislikes": {
            "gifts": [preferences["disliked_gift"]],
            "activities": [preferences["disliked_activity"]],
        },
        "measurements": measurements,
    }


def _person_traits_source(row: dict[str, Any]) -> dict[str, Any]:
    """Merge FM's top-level height and weight into cached trait data."""
    raw = row.get("traits")
    source = deepcopy(raw) if isinstance(raw, dict) else {}
    for key in ("height_cm", "weight_kg"):
        value = row.get(key)
        if value not in (None, ""):
            source[key] = value
    return source


def _empty_action_points(
    day: int | None = None, *, maximum: int = MAX_ACTION_POINTS,
    weekly_recovery: int = WEEKLY_ACTION_RECOVERY,
) -> dict[str, Any]:
    return {
        "current": maximum,
        "maximum": maximum,
        "weekly_recovery": weekly_recovery,
        "week_ordinal": _date_monday_ordinal(day) if day else 0,
        "week_key": _week_key(day) if day else "",
        "updated_at": _now(),
    }


def _normalize_event(raw: Any) -> dict[str, Any] | None:
    source = raw if isinstance(raw, dict) else None
    if not source:
        return None
    kind = str(source.get("kind") or "").strip().lower()
    if kind not in {"pregnancy", "secret_exposure", "relationship_crisis", "child_football"}:
        return None
    status = str(source.get("status") or "pending").strip().lower()
    if status not in {"pending", "resolved", "expired"}:
        status = "pending"
    event_id = str(source.get("id") or "").strip()[:80]
    if not event_id:
        return None
    options = [
        str(value).strip().lower()[:80]
        for value in (source.get("options") or [])
        if str(value).strip()
    ]
    return {
        "id": event_id,
        "kind": kind,
        "person_id": _integer(source.get("person_id"), 0, 2_147_483_647, 0),
        "person_name": str(source.get("person_name") or "")[:160],
        "created_day": _integer(source.get("created_day"), 0, 10_000_000, 0),
        "available_day": _integer(source.get("available_day"), 0, 10_000_000, 0),
        "status": status,
        "options": options,
        "data": deepcopy(source.get("data")) if isinstance(source.get("data"), dict) else {},
        "selected_option": str(source.get("selected_option") or "")[:80],
        "resolution": deepcopy(source.get("resolution")) if isinstance(source.get("resolution"), dict) else {},
        "resolved_day": _integer(source.get("resolved_day"), 0, 10_000_000, 0),
        "created_at": str(source.get("created_at") or _now()),
        "resolved_at": str(source.get("resolved_at") or ""),
    }


def _normalize_asset_level_rewards(raw: Any) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    maximum_level = len(ASSET_LEVELS)
    source = raw if isinstance(raw, dict) else {}
    for raw_level, row in source.items():
        level = _integer(raw_level, 1, maximum_level, 0)
        if not level or not isinstance(row, dict):
            continue
        rows[str(level)] = {
            "level": level,
            "points_awarded": bool(row.get("points_awarded")),
            "vehicle_catalog_id": str(row.get("vehicle_catalog_id") or "")[:80],
            "vehicle_claimed": bool(row.get("vehicle_claimed")),
            "vehicle_id": str(row.get("vehicle_id") or "")[:80],
            "claimed_at": str(row.get("claimed_at") or ""),
            "awarded_day": _integer(row.get("awarded_day"), 0, 10_000_000, 0),
            "last_error": str(row.get("last_error") or "")[:160],
        }
    return rows


TRAVEL_NAME_POOLS = {
    "CN": (
        ("李", "王", "张", "陈", "林", "沈", "顾", "许", "宋", "周"),
        ("知夏", "思远", "雨桐", "嘉宁", "清越", "予安", "若曦", "沐辰"),
    ),
    "JP": (
        ("佐藤", "铃木", "高桥", "田中", "伊藤", "渡边", "山本", "中村"),
        ("结衣", "绫", "遥", "美咲", "葵", "凛", "悠真", "拓海"),
    ),
    "KR": (
        ("朴", "金", "李", "崔", "郑", "姜", "赵", "尹"),
        ("智恩", "서연", "하늘", "민지", "지우", "예린", "도윤", "시우"),
    ),
    "LATIN": (
        ("Emma", "Olivia", "Sophie", "Clara", "Léa", "Mia", "Anna", "Elena", "Nora", "Isabel"),
        ("Martin", "Lucas", "Hugo", "Noah", "Louis", "Adam", "Leo", "Daniel", "Oliver", "Elias"),
    ),
}
TRAVEL_PERSONA_KEYS = (
    "designer", "photographer", "curator", "teacher", "musician",
    "athlete", "chef", "student", "writer", "architect",
)
TRAVEL_PERSONALITY_KEYS = ("warm", "outgoing", "reserved", "driven", "playful", "grounded")


def _empty_travel() -> dict[str, Any]:
    return {
        "current_country": "", "current_city": "", "current_place": "",
        "pending": None, "last_day": 0, "visits": [],
    }


def _normalize_travel(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    pending_raw = source.get("pending") if isinstance(source.get("pending"), dict) else {}
    pending = None
    person_id = _integer(pending_raw.get("person_id"), 1, 2_147_483_647, 0)
    if person_id:
        pending = {
            "person_id": person_id,
            "country": str(pending_raw.get("country") or "").strip().upper()[:8],
            "city": str(pending_raw.get("city") or "").strip()[:80],
            "city_name_zh": str(pending_raw.get("city_name_zh") or "").strip()[:80],
            "city_name_en": str(pending_raw.get("city_name_en") or "").strip()[:80],
            "place": str(pending_raw.get("place") or "").strip()[:80],
            "source": str(pending_raw.get("source") or "fm").strip()[:24],
            "known": bool(pending_raw.get("known")),
            "day": _integer(pending_raw.get("day"), 0, 10_000_000, 0),
        }
    visits = []
    for row in source.get("visits") or []:
        if not isinstance(row, dict):
            continue
        visits.append({
            "country": str(row.get("country") or "").strip().upper()[:8],
            "city": str(row.get("city") or "").strip()[:80],
            "place": str(row.get("place") or "").strip()[:80],
            "day": _integer(row.get("day"), 0, 10_000_000, 0),
        })
    return {
        "current_country": str(source.get("current_country") or "").strip().upper()[:8],
        "current_city": str(source.get("current_city") or "").strip()[:80],
        "current_place": str(source.get("current_place") or "").strip()[:80],
        "pending": pending,
        "last_day": _integer(source.get("last_day"), 0, 10_000_000, 0),
        "visits": visits[-TRAVEL_PLACE_MAX:],
    }


def _empty_state(day: int | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(), "updated_at": _now(), "seq": 0,
        "profile": _empty_profile(), "people": {}, "relationships": {},
        "residences": {}, "gifted_assets": [],
        "entitlements": {},
        "action_points": _empty_action_points(day),
        "action_point_ledger": [], "timeline": [], "events": [],
        "asset_level_rewards": {},
        "travel": _empty_travel(),
    }


def activate_cdk_perk(
    state: dict[str, Any], effect: str, *, code: str, day: int = 0,
) -> dict[str, Any]:
    """Activate one permanent interaction benefit exactly once."""
    resolved_effect = str(effect or "").strip()
    if resolved_effect not in CDK_PERK_EFFECTS:
        raise ValueError("CDK 权益类型无效")
    entitlements = state.setdefault("entitlements", _normalize_entitlements({}))
    existing = entitlements.get(resolved_effect)
    if isinstance(existing, dict):
        return deepcopy(existing)
    record = {
        "code": str(code or "").strip()[:80],
        "effect": resolved_effect,
        "activated_at": _now(),
        "day": int(day or 0),
    }
    if resolved_effect == "action_points":
        record.update({
            "maximum_bonus": ACTION_POINT_PERK_MAXIMUM_BONUS,
            "weekly_recovery_bonus": ACTION_POINT_PERK_RECOVERY_BONUS,
        })
        entitlements[resolved_effect] = record
        maximum, weekly_recovery = _action_point_limits(state)
        points = state.setdefault("action_points", _empty_action_points(
            day, maximum=maximum, weekly_recovery=weekly_recovery,
        ))
        before = int(points.get("current") or 0)
        points["current"] = min(
            maximum,
            before + ACTION_POINT_PERK_MAXIMUM_BONUS,
        )
        points["maximum"] = maximum
        points["weekly_recovery"] = weekly_recovery
        points["updated_at"] = _now()
        _record_action_point_change(
            state, day, int(points["current"]) - before,
            "cdk_action_points", detail=record["code"],
        )
    else:
        record["multiplier"] = RELATIONSHIP_GAIN_PERK_MULTIPLIER
        entitlements[resolved_effect] = record
    state["updated_at"] = _now()
    return deepcopy(record)


def refill_action_points(
    state: dict[str, Any], *, code: str = "10086", day: int = 0,
) -> dict[str, Any]:
    """Fill current action points to the current maximum, without limit.

    Unlike ``activate_cdk_perk`` this grants no permanent maximum/recovery
    bonus and writes no entitlement, so repeated use is safe.
    """
    maximum, weekly_recovery = _action_point_limits(state)
    points = state.setdefault("action_points", _empty_action_points(
        day, maximum=maximum, weekly_recovery=weekly_recovery,
    ))
    before = int(points.get("current") or 0)
    points["maximum"] = maximum
    points["weekly_recovery"] = weekly_recovery
    points["current"] = maximum
    points["updated_at"] = _now()
    if maximum != before:
        _record_action_point_change(
            state, day, maximum - before, "cdk_refill_action_points",
            detail=str(code or "10086"),
        )
    state["updated_at"] = _now()
    return {
        "code": str(code or "10086"),
        "effect": "refill_action_points",
        "before": before,
        "current": maximum,
        "maximum": maximum,
        "amount": 0,
        "at": _now(),
    }


def _normalize_relationship(raw: Any, person_id: int) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    social = str(source.get("social_stage") or "acquaintance")
    romance = str(source.get("romance_stage") or "none")
    bond_path = str(source.get("bond_path") or "none")
    bond_stage = str(source.get("bond_stage") or "none")
    bond_line = str(source.get("bond_line") or "")
    bond_variant = str(source.get("bond_variant") or "")
    if social not in SOCIAL_STAGES:
        social = "acquaintance"
    if romance not in ROMANCE_STAGES:
        romance = "none"
    if bond_path not in {"none", "romance", "bond"}:
        bond_path = "none"
    if bond_stage not in BOND_STAGES:
        bond_stage = "none"
    if bond_line not in {"", "sisterhood", "brotherhood"}:
        bond_line = ""
    if bond_variant not in {"", "sisterhood", "brotherhood_direct", "brotherhood_kindred"}:
        bond_variant = ""
    if bond_line == "sisterhood":
        bond_variant = "sisterhood"
    if romance != "none":
        bond_path = "romance"
        bond_stage = "none"
        bond_line = ""
        bond_variant = ""
    elif bond_stage != "none":
        bond_path = "bond"
    elif bond_path == "bond":
        bond_path = "none"
    resolved_stage = effective_romance_stage({
        "romance_stage": romance, "secret_lover": bool(source.get("secret_lover")),
    })
    raw_intimacy = source.get("intimacy")
    intimacy = (
        _clamp_intimacy(raw_intimacy)
        if raw_intimacy is not None
        else _initial_intimacy_for_stage(resolved_stage)
    )
    pregnancy = deepcopy(source.get("pregnancy")) if isinstance(source.get("pregnancy"), dict) else {}
    if pregnancy:
        conceived = _integer(pregnancy.get("conceived_day"), 0, 10_000_000, 0)
        due = _integer(pregnancy.get("due_day"), 0, 10_000_000, 0)
        due_early = _integer(pregnancy.get("due_early"), 0, 10_000_000, 0)
        due_late = _integer(pregnancy.get("due_late"), 0, 10_000_000, 0)
        if conceived and (not due or due - conceived < PREGNANCY_EARLY_DAYS):
            # Older 30-day pregnancies are migrated to the ten-month model.
            due = conceived + PREGNANCY_GESTATION_DAYS
        if conceived and not due_early:
            due_early = conceived + PREGNANCY_EARLY_DAYS
        if conceived and not due_late:
            due_late = conceived + PREGNANCY_LATE_DAYS
        if due and due_early and due_late:
            due = max(due_early, min(due_late, due))
        decision = str(pregnancy.get("decision") or "").strip().lower()
        if decision not in {"pending", "kept", "ended"}:
            decision = "kept" if str(pregnancy.get("status") or "") == "expecting" else ""
        pregnancy = {
            "status": str(pregnancy.get("status") or "expecting")[:40],
            "conceived_day": conceived,
            "due_day": due,
            "due_early": due_early,
            "due_late": due_late,
            "decision": decision,
            "kept": bool(pregnancy.get("kept")) or decision == "kept" or (
                not decision and str(pregnancy.get("status") or "") == "expecting"
            ),
            "born_day": _integer(pregnancy.get("born_day"), 0, 10_000_000, 0),
            "event_id": str(pregnancy.get("event_id") or "")[:80],
        }
    children = [
        life_children.normalize_child(row, date.today().toordinal())
        for row in (source.get("children") or [])
        if isinstance(row, dict)
    ][-20:]
    return {
        "person_id": int(person_id),
        "person_name": str(source.get("person_name") or ""),
        "contact_known": bool(source.get("contact_known", True)),
        "contact_source": str(source.get("contact_source") or "fm")[:24],
        "met_country": str(source.get("met_country") or "")[:8].upper(),
        "met_city": str(source.get("met_city") or "")[:80],
        "met_place": str(source.get("met_place") or "")[:80],
        "familiarity": round(_clamp(source.get("familiarity")), 2),
        "affection": round(_clamp(source.get("affection")), 2),
        "trust": round(_clamp(source.get("trust")), 2),
        "attraction": round(_clamp(source.get("attraction")), 2),
        "respect": round(_clamp(source.get("respect")), 2),
        "obedience": round(max(0.0, min(100.0, float(source.get("obedience") or 0.0))), 2),
        "social_stage": social, "romance_stage": romance,
        "bond_path": bond_path, "bond_stage": bond_stage,
        "bond_line": bond_line, "bond_variant": bond_variant,
        "secret_lover": bool(source.get("secret_lover")),
        "intimacy": round(intimacy, 2),
        "intimacy_negative_since": source.get("intimacy_negative_since"),
        "secret_risk": round(max(0.0, float(source.get("secret_risk") or 0.0)), 2),
        "last_secret_meeting_day": source.get("last_secret_meeting_day"),
        "pregnancy": pregnancy,
        "children": children,
        "last_crisis_day": source.get("last_crisis_day"),
        "family_plan_discussed": bool(source.get("family_plan_discussed")),
        "last_intimacy_day": source.get("last_intimacy_day"),
        "preference": deepcopy(source.get("preference")) if isinstance(source.get("preference"), dict) else {},
        "daily": deepcopy(source.get("daily")) if isinstance(source.get("daily"), dict) else {},
        "counters": deepcopy(source.get("counters")) if isinstance(source.get("counters"), dict) else {},
        "last_action_day": source.get("last_action_day"),
        "last_relationship_day": source.get("last_relationship_day"),
        "residence_asset_id": str(source.get("residence_asset_id") or ""),
        "gifted_value_total": round_money(float(source.get("gifted_value_total") or 0)),
        "created_at": str(source.get("created_at") or _now()),
        "updated_at": str(source.get("updated_at") or _now()),
    }


def normalize_state(raw: Any, day: int | None = None) -> dict[str, Any]:
    state = _empty_state(day)
    source = raw if isinstance(raw, dict) else {}
    state["created_at"] = str(source.get("created_at") or state["created_at"])
    state["updated_at"] = str(source.get("updated_at") or state["updated_at"])
    state["seq"] = max(0, _integer(source.get("seq"), 0, 10_000_000, 0))
    state["profile"] = _normalize_profile(source.get("profile"))
    people: dict[str, dict[str, Any]] = {}
    for raw_id, row in (source.get("people") or {}).items():
        if not isinstance(row, dict):
            continue
        person_id = _integer(raw_id, 1, 2_147_483_647, 0)
        if not person_id:
            continue
        age = _integer(row.get("age"), 0, 99, 18)
        female = row.get("female") if isinstance(row.get("female"), bool) else None
        traits = _normalize_person_traits(
            _person_traits_source(row), person_id, female=female, age=age,
        )
        people[str(person_id)] = {
            "id": person_id, "name": str(row.get("name") or person_id)[:160],
            "age": age, "height_cm": traits["height_cm"],
            "weight_kg": traits["weight_kg"], "traits": traits,
            "date_of_birth": str(row.get("date_of_birth") or ""),
            "female": female,
            "nationality_id": row.get("nationality_id"),
            "nationality": str(row.get("nationality") or ""),
            "team_id": row.get("team_id"), "team_name": str(row.get("team_name") or ""),
            "positions": list(row.get("positions") or [])[:16],
            "ca": row.get("ca"), "pa": row.get("pa"),
            "world_reputation": row.get("world_reputation"),
            "object_type": str(row.get("object_type") or ""),
            "source": str(row.get("source") or "fm")[:24],
            "npc": bool(row.get("npc")),
            "nationality_code": str(row.get("nationality_code") or "")[:8].upper(),
            "met_country": str(row.get("met_country") or "")[:8].upper(),
            "met_city": str(row.get("met_city") or "")[:80],
            "met_place": str(row.get("met_place") or "")[:80],
            "persona_key": str(row.get("persona_key") or "")[:40],
            "occupation_key": str(row.get("occupation_key") or "")[:40],
            "personality_key": str(row.get("personality_key") or "")[:40],
            "refreshed_day": row.get("refreshed_day"),
            "refreshed_at": str(row.get("refreshed_at") or ""),
            "snapshot_hash": str(row.get("snapshot_hash") or ""),
        }
    state["people"] = people
    relationships: dict[str, dict[str, Any]] = {}
    for raw_id, row in (source.get("relationships") or {}).items():
        person_id = _integer(raw_id, 1, 2_147_483_647, 0)
        if (
            person_id and str(person_id) in people
            and int(people[str(person_id)].get("age") or 0) >= MIN_ADULT_AGE
        ):
            relationships[str(person_id)] = _normalize_relationship(row, person_id)
    state["relationships"] = relationships
    residences: dict[str, str] = {}
    for raw_id, asset_id in (source.get("residences") or {}).items():
        person_id = _integer(raw_id, 1, 2_147_483_647, 0)
        if person_id:
            residences[str(person_id)] = str(asset_id or "")
    state["residences"] = residences
    state["gifted_assets"] = [
        deepcopy(row) for row in (source.get("gifted_assets") or []) if isinstance(row, dict)
    ][-MAX_GIFT_LEDGER_ROWS:]
    state["timeline"] = [
        deepcopy(row) for row in (source.get("timeline") or []) if isinstance(row, dict)
    ][-MAX_TIMELINE_ROWS:]
    state["events"] = [
        event for event in (
            _normalize_event(row) for row in (source.get("events") or [])
        ) if event is not None
    ][-MAX_EVENT_ROWS:]
    state["asset_level_rewards"] = _normalize_asset_level_rewards(
        source.get("asset_level_rewards"),
    )
    state["travel"] = _normalize_travel(source.get("travel"))
    state["entitlements"] = _normalize_entitlements(source.get("entitlements"))
    points_raw = source.get("action_points") if isinstance(source.get("action_points"), dict) else {}
    maximum, weekly_recovery = _action_point_limits(state)
    points = _empty_action_points(
        day, maximum=maximum, weekly_recovery=weekly_recovery,
    )
    points.update({
        "current": _integer(points_raw.get("current"), 0, maximum, maximum),
        "maximum": maximum, "weekly_recovery": weekly_recovery,
        "week_ordinal": _integer(points_raw.get("week_ordinal"), 0, 10_000_000, points["week_ordinal"]),
        "week_key": str(points_raw.get("week_key") or points["week_key"]),
        "updated_at": str(points_raw.get("updated_at") or _now()),
    })
    state["action_points"] = points
    state["action_point_ledger"] = _normalize_action_point_ledger(
        source.get("action_point_ledger"),
    )
    return state


def load_state(scope_id: str, day: int | None = None) -> dict[str, Any]:
    with _LOCK:
        payload = load_document(DOCUMENT, None, scope_id)
    return normalize_state(payload, day)


def save_state(state: dict[str, Any], scope_id: str, day: int | None = None) -> None:
    state = normalize_state(state, day)
    state["updated_at"] = _now()
    with _LOCK:
        save_document(DOCUMENT, state, scope_id)


def interactions_lock() -> threading.RLock:
    return _LOCK


def refresh_action_points(state: dict[str, Any], day: int) -> bool:
    maximum, weekly_recovery = _action_point_limits(state)
    points = state.setdefault("action_points", _empty_action_points(day))
    current_week = _date_monday_ordinal(day)
    previous_week = int(points.get("week_ordinal") or 0)
    if not previous_week:
        points.update({
            "current": maximum, "maximum": maximum,
            "weekly_recovery": weekly_recovery,
            "week_ordinal": current_week, "week_key": _week_key(day),
            "updated_at": _now(),
        })
        return True
    if current_week <= previous_week:
        if points.get("week_key") != _week_key(day) and current_week == previous_week:
            points["week_key"] = _week_key(day)
            return True
        return False
    weeks = max(1, (current_week - previous_week) // 7)
    before = int(points.get("current") or 0)
    current = min(maximum, before + weeks * weekly_recovery)
    points.update({
        "current": current, "maximum": maximum,
        "weekly_recovery": weekly_recovery,
        "week_ordinal": current_week, "week_key": _week_key(day),
        "updated_at": _now(),
    })
    _record_action_point_change(
        state, day, current - before, "weekly_recovery",
        detail=f"weeks:{weeks}",
    )
    return True


def ensure_state(scope_id: str, day: int) -> tuple[dict[str, Any], bool]:
    raw = load_document(DOCUMENT, None, scope_id)
    state = normalize_state(raw, day)
    changed = (
        not isinstance(raw, dict)
        or raw.get("schema_version") != SCHEMA_VERSION
        or not isinstance(raw.get("people"), dict)
        or not isinstance(raw.get("relationships"), dict)
    )
    changed = refresh_action_points(state, day) or changed
    return state, changed


def days_until_monday(current: date) -> int:
    return (7 - current.weekday()) % 7 or 7


def action_points(state: dict[str, Any], day: int) -> dict[str, Any]:
    refresh_action_points(state, day)
    points = state["action_points"]
    maximum, weekly_recovery = _action_point_limits(state)
    current = int(points.get("current") or 0)
    remaining = max(0, maximum - current)
    days_until_recovery = days_until_monday(date.fromordinal(day))
    recovery_cycles = math.ceil(remaining / weekly_recovery) if remaining else 0
    return {
        "current": current,
        "maximum": maximum,
        "weekly_recovery": weekly_recovery,
        "week_key": str(points.get("week_key") or ""),
        "days_until_recovery": days_until_recovery,
        "next_recovery_gain": min(remaining, weekly_recovery),
        "days_until_full": (
            days_until_recovery + (recovery_cycles - 1) * 7
            if recovery_cycles else 0
        ),
        "is_full": remaining == 0,
        "purchase_price": int(ACTION_POINT_PURCHASE_PRICE),
        "purchase_available": int(remaining),
        "ledger": list(reversed(
            _normalize_action_point_ledger(state.get("action_point_ledger"))
        ))[:100],
        "ledger_total": len(_normalize_action_point_ledger(
            state.get("action_point_ledger")
        )),
        "costs": {
            "chat": ACTION_COSTS["chat"],
            "gift": ACTION_COSTS["gift"],
            "asset_gift": ACTION_COSTS["asset_gift"],
            "money_gift": ACTION_COSTS["money_gift"],
            "date_min": min(int(value["ap"]) for value in DATE_ACTIVITIES.values()),
            "date_max": max(int(value["ap"]) for value in DATE_ACTIVITIES.values()),
            "relationship": ACTION_COSTS["relationship"],
            "intimacy_min": min(int(value["ap"]) for value in INTIMATE_ACTIONS.values()),
            "intimacy_max": max(int(value["ap"]) for value in INTIMATE_ACTIONS.values()),
        },
    }


def purchase_action_points(
    state: dict[str, Any], day: int, points: int,
    unit_price: int = ACTION_POINT_PURCHASE_PRICE,
) -> dict[str, Any]:
    """Refill action points with money; the endpoint debits the bank."""
    refresh_action_points(state, int(day))
    maximum, _weekly = _action_point_limits(state)
    record = state.setdefault("action_points", _empty_action_points(int(day)))
    current = int(record.get("current") or 0)
    missing = max(0, maximum - current)
    requested = _integer(points, 1, maximum, 0)
    if missing <= 0:
        raise ValueError("行动力已经满了")
    if not requested:
        raise ValueError("补充数量无效")
    quantity = min(requested, missing)
    cost = int(quantity) * int(unit_price)
    record["current"] = current + quantity
    record["updated_at"] = _now()
    _record_action_point_change(
        state, int(day), quantity, "purchase",
        detail=f"cost:{cost}",
    )
    return {
        "kind": "action_points",
        "points": quantity, "cost": cost,
        "current": int(record["current"]), "maximum": maximum,
    }


def _consume_action_points(
    state: dict[str, Any], day: int, amount: int, *, reason: str,
    person_id: int = 0, detail: str = "",
) -> None:
    refresh_action_points(state, day)
    points = state["action_points"]
    cost = max(0, int(amount))
    if int(points.get("current") or 0) < cost:
        raise ValueError("行动力不足，请等待每周恢复")
    points["current"] = int(points.get("current") or 0) - cost
    points["updated_at"] = _now()
    person = (state.get("people") or {}).get(str(int(person_id or 0))) or {}
    _record_action_point_change(
        state, day, -cost, reason, person_id=person_id,
        person_name=str(person.get("name") or ""), detail=detail,
    )


def _next_id(state: dict[str, Any], prefix: str) -> str:
    state["seq"] = int(state.get("seq") or 0) + 1
    return f"{prefix}-{state['seq']:06d}"


def _add_timeline(
    state: dict[str, Any], *, day: int, person: dict[str, Any],
    kind: str, action: str, result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "id": _next_id(state, "timeline"), "day": int(day), "at": _now(),
        "person_id": int(person["id"]),
        "person_name": str(person.get("name") or ""),
        "kind": str(kind), "action": str(action),
        "result": deepcopy(result or {}),
    }
    state.setdefault("timeline", []).append(row)
    state["timeline"] = state["timeline"][-MAX_TIMELINE_ROWS:]
    return row


def _has_pending_event(
    state: dict[str, Any], kind: str, person_id: int,
) -> bool:
    return any(
        isinstance(row, dict)
        and str(row.get("kind") or "") == kind
        and int(row.get("person_id") or 0) == int(person_id or 0)
        and str(row.get("status") or "") == "pending"
        for row in state.get("events") or []
    )


def _queue_event(
    state: dict[str, Any], *, kind: str, person: dict[str, Any], day: int,
    available_day: int, data: dict[str, Any], options: list[str],
) -> dict[str, Any]:
    event = {
        "id": _next_id(state, "event"),
        "kind": kind,
        "person_id": int(person["id"]),
        "person_name": str(person.get("name") or ""),
        "created_day": int(day),
        "available_day": int(available_day),
        "status": "pending",
        "options": list(options),
        "data": deepcopy(data),
        "selected_option": "",
        "resolution": {},
        "resolved_day": 0,
        "created_at": _now(),
        "resolved_at": "",
    }
    state.setdefault("events", []).append(event)
    state["events"] = state["events"][-MAX_EVENT_ROWS:]
    _add_timeline(
        state, day=day, person=person, kind="event", action=kind,
        result={"event_id": event["id"], "available_day": int(available_day)},
    )
    return event


def _track_negative_intimacy(relationship: dict[str, Any], day: int) -> bool:
    before = relationship.get("intimacy_negative_since")
    value = float(relationship.get("intimacy") or 0.0)
    if value < 0:
        if before in (None, ""):
            relationship["intimacy_negative_since"] = int(day)
            return True
    elif before not in (None, ""):
        relationship["intimacy_negative_since"] = None
        return True
    return False


def _deliver_child_now(
    state: dict[str, Any], relationship: dict[str, Any],
    pregnancy: dict[str, Any], day: int,
) -> dict[str, Any]:
    due_day = int(day)
    child_id = _next_id(state, "child")
    child = life_children.normalize_child(
        {"id": child_id, "name": "", "born_day": due_day}, due_day,
    )
    child = life_children.seed_child_football(child, state, relationship)
    relationship.setdefault("children", []).append(child)
    relationship["children"] = relationship["children"][-20:]
    pregnancy.update({
        "status": "born", "born_day": due_day,
        "decision": "kept",
        "due_day": due_day,
        "event_id": str(pregnancy.get("event_id") or ""),
    })
    relationship["pregnancy"] = pregnancy
    relationship["last_action_day"] = due_day
    _apply_deltas(
        relationship,
        {"affection": 10.0, "trust": 12.0, "respect": 6.0},
        gain_multiplier=_relationship_gain_multiplier(state),
    )
    _add_intimacy(
        relationship, 22.0,
        gain_multiplier=_relationship_gain_multiplier(state),
    )
    return child


def use_birth_pill(
    state: dict[str, Any], person_id: int, day: int,
) -> dict[str, Any]:
    """Force an expecting NPC to give birth immediately."""
    relationship = _relationship(state, person_id)
    pregnancy = relationship.get("pregnancy") if isinstance(
        relationship.get("pregnancy"), dict,
    ) else {}
    if str(pregnancy.get("status") or "") != "expecting":
        raise ValueError("该人物当前没有怀孕，不能使用快速分娩丹")
    for event in state.get("events") or []:
        if not isinstance(event, dict):
            continue
        if str(event.get("kind") or "") != "pregnancy":
            continue
        if int(event.get("person_id") or 0) != int(person_id):
            continue
        if str(event.get("status") or "") == "pending":
            event["status"] = "resolved"
            event["resolution"] = "keep_child"
            event["resolved_day"] = int(day)
    pregnancy["decision"] = "kept"
    child = _deliver_child_now(state, relationship, pregnancy, int(day))
    return {
        "person_id": int(person_id),
        "child": deepcopy(child),
        "pregnancy": deepcopy(pregnancy),
    }


def settle_periodic_events(state: dict[str, Any], day: int) -> bool:
    """Materialise pregnancy, exposure and separation events that are due."""
    changed = False
    for person_id, relationship in (state.get("relationships") or {}).items():
        if not isinstance(relationship, dict):
            continue
        changed = _track_negative_intimacy(relationship, int(day)) or changed
        person = (state.get("people") or {}).get(str(person_id))
        if not isinstance(person, dict):
            continue
        pregnancy = relationship.get("pregnancy") if isinstance(relationship.get("pregnancy"), dict) else {}
        pregnancy_status = str(pregnancy.get("status") or "")
        decision = str(pregnancy.get("decision") or "")
        if pregnancy_status == "expecting":
            if decision == "pending":
                if not _has_pending_event(state, "pregnancy", int(person_id)):
                    event = _queue_event(
                        state, kind="pregnancy", person=person,
                        day=int(pregnancy.get("conceived_day") or day),
                        available_day=int(pregnancy.get("conceived_day") or day) + PREGNANCY_DISCOVERY_DAYS,
                        data={
                            "conceived_day": int(pregnancy.get("conceived_day") or 0),
                            "due_day": int(pregnancy.get("due_day") or day),
                            "due_early": int(pregnancy.get("due_early") or 0),
                            "due_late": int(pregnancy.get("due_late") or 0),
                            "relationship_stage": effective_romance_stage(relationship),
                        },
                        options=["keep_child", "end_pregnancy"],
                    )
                    pregnancy["event_id"] = event["id"]
                    relationship["pregnancy"] = pregnancy
                    changed = True
            elif decision == "kept" and int(pregnancy.get("due_day") or 0) <= int(day):
                # The decision event already happened; birth is automatic at
                # the randomised delivery date, and only now does the child
                # enter the family list.
                _deliver_child_now(state, relationship, pregnancy, int(day))
                changed = True
        for child in (relationship.get("children") or []):
            if not isinstance(child, dict):
                continue
            age = life_children.child_age(child, int(day))
            if age >= life_children.CHILD_ADULT_AGE:
                continue
            # Growth events are age-bound. If elixirs aged the child past a
            # pending event, it becomes a missed result and cannot be rerolled.
            for pending in state.get("events") or []:
                if not isinstance(pending, dict):
                    continue
                if str(pending.get("kind") or "") != "child_football":
                    continue
                if str(pending.get("status") or "") != "pending":
                    continue
                pending_data = pending.get("data") or {}
                if str(pending_data.get("child_id") or "") != str(child.get("id") or ""):
                    continue
                pending_age = int(pending_data.get("milestone") or pending_data.get("age") or 0)
                if pending_age < age:
                    pending["status"] = "expired"
                    pending["resolved_day"] = int(day)
                    pending["selected_option"] = "missed"
                    pending["resolution"] = {"missed": True, "age_passed": True}
                    changed = True
            due_milestone = life_children.training_due(child, int(day))
            if due_milestone and not any(
                isinstance(event, dict)
                and str(event.get("kind") or "") == "child_football"
                and str((event.get("data") or {}).get("child_id") or "") == str(child.get("id") or "")
                and str(event.get("status") or "") == "pending"
                for event in state.get("events") or []
            ):
                options = life_children.training_options(child, age)
                event = _queue_event(
                    state, kind="child_football", person=person, day=int(day),
                    available_day=int(day),
                    data={
                        "child_id": str(child.get("id") or ""),
                        "child_name": str(child.get("name") or ""),
                        "age": int(age), "milestone": int(due_milestone),
                        "options": options,
                        "ca": int(child.get("ca") or 0),
                        "pa": int(child.get("pa") or 0),
                    },
                    options=[str(row["id"]) for row in options],
                )
                child["last_training_event_id"] = event["id"]
                relationship["children"] = relationship.get("children") or []
                changed = True
            # A milestone missed by more than a year permanently lowers CA/PA.
            for milestone in life_children.CHILD_TRAINING_AGES:
                if age <= milestone + 1:
                    continue
                if milestone in {int(value) for value in (child.get("training_milestones") or [])}:
                    continue
                if milestone in {int(value) for value in (child.get("neglected_milestones") or [])}:
                    continue
                if any(
                    isinstance(event, dict)
                    and str(event.get("kind") or "") == "child_football"
                    and str((event.get("data") or {}).get("child_id") or "") == str(child.get("id") or "")
                    and str(event.get("status") or "") == "pending"
                    for event in state.get("events") or []
                ):
                    continue
                if life_children.apply_neglect_penalty(child, milestone, int(day)):
                    changed = True
        intimacy = float(relationship.get("intimacy") or 0.0)
        negative_since = relationship.get("intimacy_negative_since")
        severe = intimacy <= RELATIONSHIP_CRISIS_SEVERE_THRESHOLD
        sustained = (
            intimacy <= RELATIONSHIP_CRISIS_THRESHOLD
            and negative_since not in (None, "")
            and int(day) - int(negative_since) >= RELATIONSHIP_CRISIS_GRACE_DAYS
        )
        last_crisis = int(relationship.get("last_crisis_day") or 0)
        if (
            (severe or sustained)
            and not _has_pending_event(state, "relationship_crisis", int(person_id))
            and (not last_crisis or int(day) - last_crisis >= 30)
        ):
            _queue_event(
                state, kind="relationship_crisis", person=person, day=int(day),
                available_day=int(day),
                data={
                    "intimacy": round(intimacy, 2),
                    "negative_since": negative_since,
                    "severe": severe,
                    "stage": effective_romance_stage(relationship),
                },
                options=["repair", "accept_separation"],
            )
            relationship["last_crisis_day"] = int(day)
            changed = True
    return changed


def _register_secret_meeting(
    state: dict[str, Any], relationship: dict[str, Any], day: int,
    risk: float, *, source: str,
) -> dict[str, Any] | None:
    if not bool(relationship.get("secret_lover")):
        return None
    person_id = int(relationship["person_id"])
    before = float(relationship.get("secret_risk") or 0.0)
    updated = round(max(0.0, before + max(0.0, float(risk))), 2)
    relationship["secret_risk"] = updated
    relationship["last_secret_meeting_day"] = int(day)
    if updated < SECRET_EXPOSURE_THRESHOLD or _has_pending_event(
        state, "secret_exposure", person_id,
    ):
        return None
    exposure_chance = max(0.18, min(0.86, 0.18 + (updated - SECRET_EXPOSURE_THRESHOLD) / 90.0))
    roll = _stable_unit("secret-exposure", person_id, int(day), source, state.get("seq", 0))
    if roll > exposure_chance:
        return None
    public = _exclusive_relationship(state, excluding_person_id=person_id)
    penalty: dict[str, float] = {}
    if public is not None:
        penalty = _apply_deltas(
            public,
            {"affection": -32.0, "trust": -42.0, "attraction": -18.0, "respect": -24.0},
        )
        public["intimacy"] = round(_clamp_intimacy(
            float(public.get("intimacy") or 0.0) - 35.0
        ), 2)
        public["last_relationship_day"] = int(day)
        _track_negative_intimacy(public, int(day))
    secret_person = (state.get("people") or {}).get(str(person_id)) or {
        "id": person_id, "name": str(relationship.get("person_name") or ""),
    }
    event = _queue_event(
        state, kind="secret_exposure", person=secret_person, day=int(day),
        available_day=int(day),
        data={
            "risk": updated,
            "chance": round(exposure_chance, 4),
            "source": str(source),
            "public_person_id": int(public["person_id"]) if public else 0,
            "public_person_name": str(public.get("person_name") or "") if public else "",
            "public_stage": effective_romance_stage(public) if public else "",
            "public_penalty": penalty,
        },
        options=["end_secret", "end_public_relationship"] if public else ["end_secret"],
    )
    relationship["secret_risk"] = 12.0
    relationship["last_exposure_day"] = int(day)
    relationship["last_exposure_event_id"] = event["id"]
    return event


def _maybe_conceive(
    state: dict[str, Any], relationship: dict[str, Any], day: int,
) -> tuple[float, bool]:
    """Roll conception once per stay-close action without revealing it early."""
    chance = _pregnancy_chance(state, relationship)
    if chance <= 0:
        return chance, False
    person_id = int(relationship.get("person_id") or 0)
    counters = relationship.setdefault("counters", {})
    rolls = _integer(counters.get("pregnancy_rolls"), 0, 1_000_000, 0)
    counters["pregnancy_rolls"] = rolls + 1
    roll = _stable_unit(
        "pregnancy", person_id, int(day), rolls, state.get("seq", 0), chance,
    )
    if roll > chance:
        return chance, False
    due_early = int(day) + PREGNANCY_EARLY_DAYS
    due_late = int(day) + PREGNANCY_LATE_DAYS
    spread = max(0, due_late - due_early)
    due_day = due_early + int(round(_stable_unit(
        "pregnancy_due", person_id, int(day), state.get("seq", 0), spread,
    ) * spread))
    relationship["pregnancy"] = {
        "status": "expecting",
        "conceived_day": int(day),
        "due_day": due_day,
        "due_early": due_early,
        "due_late": due_late,
        "decision": "pending",
        "kept": False,
        "born_day": 0,
        "event_id": "",
    }
    return chance, True


def _end_romance(
    relationship: dict[str, Any], day: int, reason: str,
) -> str:
    previous = effective_romance_stage(relationship)
    relationship["romance_stage"] = "none"
    relationship["secret_lover"] = False
    relationship["intimacy"] = 0.0
    relationship["intimacy_negative_since"] = None
    relationship["secret_risk"] = 0.0
    relationship["family_plan_discussed"] = False
    relationship["last_relationship_day"] = int(day)
    relationship["breakup_reason"] = str(reason or "event")[:80]
    relationship["breakup_day"] = int(day)
    return previous


def event_plan(
    state: dict[str, Any], event_id: str, option: str, day: int,
) -> dict[str, Any]:
    """Resolve one due, pending relationship event exactly once."""
    resolved_id = str(event_id or "").strip()
    selected = str(option or "").strip().lower()
    event = next((
        row for row in state.get("events") or []
        if isinstance(row, dict) and str(row.get("id") or "") == resolved_id
    ), None)
    if not isinstance(event, dict):
        raise ValueError("事件不存在")
    if str(event.get("status") or "") != "pending":
        raise ValueError("该事件已经处理")
    if int(event.get("available_day") or 0) > int(day):
        raise ValueError("该事件尚未到发生时间")
    if selected not in (event.get("options") or []):
        raise ValueError("事件选项无效")
    person_id = int(event.get("person_id") or 0)
    relationship = (state.get("relationships") or {}).get(str(person_id))
    if not isinstance(relationship, dict):
        raise ValueError("该人物关系已不存在")
    person = (state.get("people") or {}).get(str(person_id)) or {
        "id": person_id, "name": str(event.get("person_name") or ""),
    }
    kind = str(event.get("kind") or "")
    event_data = event.get("data") if isinstance(event.get("data"), dict) else {}
    applied: dict[str, float] = {}
    success = True
    effect = selected
    detail: dict[str, Any] = {}
    if kind == "pregnancy":
        pregnancy = relationship.get("pregnancy") if isinstance(relationship.get("pregnancy"), dict) else {}
        if selected == "keep_child":
            pregnancy.update({
                "status": "expecting", "decision": "kept", "kept": True,
                "event_id": str(event["id"]),
            })
            applied = _apply_deltas(
                relationship, {"affection": 6.0, "trust": 7.0, "respect": 4.0},
                gain_multiplier=_relationship_gain_multiplier(state),
            )
            intimacy_change = _add_intimacy(
                relationship, 8.0,
                gain_multiplier=_relationship_gain_multiplier(state),
            )
            detail = {"pregnancy": "kept", "intimacy_change": intimacy_change}
        else:
            pregnancy.update({
                "status": "ended", "decision": "ended", "kept": False,
                "ended_day": int(day), "event_id": str(event["id"]),
            })
            intimacy_change = _add_intimacy(relationship, -55.0)
            applied = _apply_deltas(
                relationship,
                {"affection": -18.0, "trust": -22.0, "respect": -10.0, "attraction": -8.0},
            )
            _track_negative_intimacy(relationship, int(day))
            detail = {"intimacy_change": intimacy_change}
        relationship["pregnancy"] = pregnancy
        relationship["last_action_day"] = int(day)
    elif kind == "child_football":
        child_id = str(event_data.get("child_id") or "")
        found = life_children.find_child(state, child_id)
        if found is None:
            raise ValueError("子女记录已不存在")
        _parent, child = found
        milestone = int(event_data.get("milestone") or 0)
        applied_training = life_children.apply_training(
            child, selected, int(day), milestone=milestone,
        )
        applied = _apply_deltas(
            relationship, {"affection": 1.5, "trust": 1.5},
            gain_multiplier=_relationship_gain_multiplier(state),
        )
        detail = {"child": deepcopy(child), "training": applied_training}
    elif kind == "secret_exposure":
        public_person_id = int(event_data.get("public_person_id") or 0)
        public = (state.get("relationships") or {}).get(str(public_person_id))
        if selected == "end_secret":
            previous = _end_romance(relationship, int(day), "secret_exposure")
            relationship["last_exposure_resolution"] = "ended_secret"
            if isinstance(public, dict):
                applied = _apply_deltas(
                    public,
                    {"trust": 6.0, "affection": 3.0},
                    gain_multiplier=_relationship_gain_multiplier(state),
                )
                _add_intimacy(
                    public, 6.0,
                    gain_multiplier=_relationship_gain_multiplier(state),
                )
            detail = {
                "ended_stage": previous,
                "public_person_id": public_person_id,
            }
        else:
            public_stage = _end_romance(public, int(day), "public_choice_after_exposure") if isinstance(public, dict) else ""
            relationship["secret_lover"] = True
            relationship["secret_risk"] = 10.0
            relationship["last_exposure_resolution"] = "ended_public"
            detail = {"ended_public_stage": public_stage, "public_person_id": public_person_id}
    elif kind == "relationship_crisis":
        if selected == "accept_separation":
            previous = _end_romance(relationship, int(day), "crisis_separation")
            detail = {"ended_stage": previous}
        else:
            profile = state.get("profile") if isinstance(state.get("profile"), dict) else {}
            eq = min(100.0, max(1.0, float(profile.get("eq") or 1.0)))
            trust = max(0.0, float(relationship.get("trust") or 0.0))
            intimacy = max(0.0, _clamp_intimacy(relationship.get("intimacy")))
            chance = min(0.92, 0.28 + eq / 100.0 * 0.42 + trust / 100.0 * 0.14 + intimacy / 100.0 * 0.08)
            roll = _stable_unit(
                "crisis-repair", person_id, int(day), state.get("seq", 0), event["id"],
            )
            success = roll <= chance
            detail = {"chance": round(chance, 4), "roll": round(roll, 4)}
            if success:
                applied = _apply_deltas(
                    relationship,
                    {"affection": 8.0, "trust": 6.0, "respect": 4.0},
                    gain_multiplier=_relationship_gain_multiplier(state),
                )
                detail["intimacy_change"] = _add_intimacy(
                    relationship, 20.0,
                    gain_multiplier=_relationship_gain_multiplier(state),
                )
            else:
                detail["ended_stage"] = _end_romance(
                    relationship, int(day), "crisis_repair_failed",
                )
    else:
        raise ValueError("未知事件类型")
    event.update({
        "status": "resolved",
        "selected_option": selected,
        "resolution": {
            "kind": kind, "option": selected, "success": success,
            "deltas": applied, "detail": detail,
        },
        "resolved_day": int(day),
        "resolved_at": _now(),
    })
    _add_timeline(
        state, day=int(day), person=person, kind="event", action=kind,
        result={
            "event_id": event["id"], "option": selected,
            "success": success, "deltas": applied, "detail": detail,
        },
    )
    state["updated_at"] = _now()
    return {
        "kind": "event", "event": deepcopy(event), "success": success,
        "option": selected, "deltas": applied, "detail": detail,
        "person_id": person_id, "person_name": str(person.get("name") or ""),
        "relationship": deepcopy(relationship),
    }


def _snapshot_hash(snapshot: dict[str, Any]) -> str:
    body = {
        key: snapshot.get(key)
        for key in (
            "id", "name", "age", "height_cm", "weight_kg", "female", "nationality_id", "team_id",
            "team_name", "positions", "ca", "pa", "world_reputation",
        )
    }
    encoded = json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _snapshot_from_row(row: dict[str, Any], day: int) -> dict[str, Any]:
    try:
        person_id = int(row.get("id") or 0)
    except (TypeError, ValueError) as error:
        raise ValueError("球员 ID 无效") from error
    if person_id <= 0:
        raise ValueError("球员 ID 无效")
    object_type = str(row.get("object_type") or "").strip().lower()
    if object_type and (
        "staff" in object_type or "non_player" in object_type
        or "player" not in object_type
    ):
        raise ValueError("互动系统首版仅支持球员，不支持职员")
    try:
        age = int(row.get("age"))
    except (TypeError, ValueError) as error:
        raise ValueError("无法确认该球员年龄，暂不能加入互动") from error
    if age < MIN_ADULT_AGE:
        raise ValueError("仅可添加年满 18 岁的成年球员")
    female = row.get("female") if isinstance(row.get("female"), bool) else None
    traits = _normalize_person_traits(
        _person_traits_source(row), person_id, female=female, age=age,
    )
    snapshot = {
        "id": person_id, "name": str(row.get("name") or person_id)[:160],
        "age": age, "height_cm": traits["height_cm"],
        "weight_kg": traits["weight_kg"], "traits": traits,
        "date_of_birth": str(row.get("date_of_birth") or ""),
        "female": female,
        "nationality_id": row.get("nationality_id"),
        "nationality": str(row.get("nationality") or ""),
        "team_id": row.get("team_id"), "team_name": str(row.get("team_name") or ""),
        "positions": list(row.get("positions") or [])[:16],
        "ca": row.get("ca"), "pa": row.get("pa"),
        "world_reputation": row.get("world_reputation"),
        "object_type": object_type,
        "refreshed_day": int(day), "refreshed_at": _now(),
    }
    snapshot["snapshot_hash"] = _snapshot_hash(snapshot)
    return snapshot


def preference_for(person_id: int) -> dict[str, Any]:
    seed = hashlib.sha256(f"life-interactions:{int(person_id)}:v1".encode("utf-8")).digest()
    gift = GIFT_CATEGORIES[seed[0] % len(GIFT_CATEGORIES)]
    disliked_gift = GIFT_CATEGORIES[(seed[0] + 3 + seed[1] % 4) % len(GIFT_CATEGORIES)]
    if disliked_gift == gift:
        disliked_gift = GIFT_CATEGORIES[(GIFT_CATEGORIES.index(gift) + 1) % len(GIFT_CATEGORIES)]
    activities = tuple(DATE_ACTIVITIES)
    activity = activities[seed[2] % len(activities)]
    disliked_activity = activities[(seed[2] + 3 + seed[3] % 4) % len(activities)]
    if disliked_activity == activity:
        disliked_activity = activities[(activities.index(activity) + 1) % len(activities)]
    return {
        "gift": gift, "disliked_gift": disliked_gift,
        "activity": activity, "disliked_activity": disliked_activity,
        "topic": CONVERSATION_TOPICS[seed[4] % len(CONVERSATION_TOPICS)],
    }


def is_interaction_player_row(row: dict[str, Any]) -> bool:
    """Return whether a native search row is an adult-capable player entry.

    FM distinguishes players from staff through the shared Person object type.
    The interaction feature intentionally excludes staff in its first release.
    """
    object_type = str((row or {}).get("object_type") or "").strip().lower()
    return object_type in {"player", "actual_player"}


def cache_person(
    state: dict[str, Any], snapshot: dict[str, Any], day: int,
) -> tuple[dict[str, Any], bool]:
    person = deepcopy(snapshot)
    person_id = int(person["id"])
    if int(person.get("age") or 0) < MIN_ADULT_AGE:
        raise ValueError("仅可添加年满 18 岁的成年球员")
    existing = state.setdefault("people", {}).get(str(person_id))
    changed = not isinstance(existing, dict) or existing.get("snapshot_hash") != person.get("snapshot_hash")
    state["people"][str(person_id)] = person
    relationship = state.setdefault("relationships", {}).get(str(person_id))
    if not isinstance(relationship, dict):
        relationship = _normalize_relationship({
            "person_name": person["name"],
            "preference": preference_for(person_id),
            "created_at": _now(),
        }, person_id)
        state["relationships"][str(person_id)] = relationship
        changed = True
    else:
        relationship = _normalize_relationship(relationship, person_id)
        relationship["person_name"] = person["name"]
        state["relationships"][str(person_id)] = relationship
    return relationship, changed


def cache_search_row(
    state: dict[str, Any], row: dict[str, Any], day: int,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    snapshot = _snapshot_from_row(row, day)
    relationship, changed = cache_person(state, snapshot, day)
    return state["people"][str(snapshot["id"])], relationship, changed


def refresh_person_row(
    state: dict[str, Any], row: dict[str, Any], day: int,
) -> tuple[dict[str, Any] | None, bool]:
    try:
        snapshot = _snapshot_from_row(row, day)
    except ValueError:
        return None, False
    person_id = str(snapshot["id"])
    if person_id not in state.get("people", {}):
        return None, False
    existing = state["people"][person_id]
    refreshed = dict(existing)
    refreshed.update({
        "name": snapshot["name"], "age": snapshot["age"],
        "height_cm": snapshot.get("height_cm"),
        "weight_kg": snapshot.get("weight_kg"),
        "traits": deepcopy(snapshot.get("traits") or {}),
        "date_of_birth": snapshot.get("date_of_birth") or refreshed.get("date_of_birth") or "",
        "female": snapshot.get("female") if snapshot.get("female") is not None else refreshed.get("female"),
        "nationality_id": snapshot.get("nationality_id"),
        "nationality": snapshot.get("nationality") or refreshed.get("nationality") or "",
        "team_id": snapshot.get("team_id"), "team_name": snapshot.get("team_name") or "",
        "positions": snapshot.get("positions") or refreshed.get("positions") or [],
        "ca": snapshot.get("ca"), "pa": snapshot.get("pa"),
        "world_reputation": snapshot.get("world_reputation"),
        "object_type": snapshot.get("object_type") or refreshed.get("object_type") or "",
        "refreshed_day": int(day), "refreshed_at": _now(),
    })
    refreshed["snapshot_hash"] = _snapshot_hash(refreshed)
    changed = refreshed.get("snapshot_hash") != existing.get("snapshot_hash")
    state["people"][person_id] = refreshed
    relationship = state.setdefault("relationships", {}).get(person_id)
    if relationship:
        relationship["person_name"] = refreshed["name"]
    return refreshed, changed


def _relationship(state: dict[str, Any], person_id: int) -> dict[str, Any]:
    person_key = str(int(person_id))
    person = state.get("people", {}).get(person_key)
    relationship = state.get("relationships", {}).get(person_key)
    if not isinstance(person, dict) or not isinstance(relationship, dict):
        raise ValueError("请先将该球员加入互动列表")
    if int(person.get("age") or 0) < MIN_ADULT_AGE:
        raise ValueError("仅可添加年满 18 岁的成年球员")
    return relationship


def _stage_rank(relationship: dict[str, Any]) -> int:
    stage = str(relationship.get("social_stage") or "acquaintance")
    return SOCIAL_STAGE_RANK.get(stage, 0)


def social_stage_for(relationship: dict[str, Any]) -> str:
    familiarity = float(relationship.get("familiarity") or 0)
    affection = float(relationship.get("affection") or 0)
    trust = float(relationship.get("trust") or 0)
    respect = float(relationship.get("respect") or 0)
    if familiarity >= 75 and affection >= 75 and trust >= 70 and respect >= 60:
        return "confidant"
    if familiarity >= 50 and affection >= 55 and trust >= 45 and respect >= 35:
        return "close_friend"
    if familiarity >= 25 and affection >= 30 and trust >= 20:
        return "friend"
    return "acquaintance"


def _upgrade_social_stage(relationship: dict[str, Any]) -> str | None:
    current = str(relationship.get("social_stage") or "acquaintance")
    target = social_stage_for(relationship)
    # V2.9.1 moves the fourth common step to an explicit branch choice. New
    # relationships stop at close friend (好友); confidant is kept only as a
    # legacy save value and is not produced again.
    if target == "confidant" and current != "confidant":
        target = "close_friend"
    if SOCIAL_STAGE_RANK[target] > SOCIAL_STAGE_RANK[current]:
        relationship["social_stage"] = target
        return target
    return None


def _relationship_requirements(
    relationship: dict[str, Any], requirements: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, required in requirements.items():
        if key == "social_stage":
            current = str(relationship.get("social_stage") or "acquaintance")
            met = _stage_rank(relationship) >= SOCIAL_STAGE_RANK.get(str(required), 0)
            rows.append({
                "key": key, "current": current, "required": str(required),
                "met": met,
            })
            continue
        if key == "romance_stage":
            current = str(relationship.get("romance_stage") or "none")
            met = ROMANCE_STAGE_RANK.get(current, 0) >= ROMANCE_STAGE_RANK.get(str(required), 0)
            rows.append({
                "key": key, "current": current, "required": str(required),
                "met": met,
            })
            continue
        if key == "bond_stage":
            current = str(relationship.get("bond_stage") or "none")
            met = BOND_STAGE_RANK.get(current, 0) >= BOND_STAGE_RANK.get(str(required), 0)
            rows.append({
                "key": key, "current": current, "required": str(required),
                "met": met,
            })
            continue
        current_value = round(float(relationship.get(key) or 0), 2)
        required_value = round(float(required or 0), 2)
        rows.append({
            "key": str(key), "current": current_value,
            "required": required_value, "met": current_value >= required_value,
        })
    return rows


def relationship_progress(
    state: dict[str, Any], relationship: dict[str, Any],
) -> dict[str, Any]:
    """Expose the next common, romantic or bond gate to the web client.

    The common ladder ends at close friend (好友). From there the player picks
    either the romance line (暧昧 → 情侣 → 夫妻) or one of the friendship lines
    (搭档 → 同好 → 闺蜜/兄弟 → 生死兄弟). The qualitative relationship tone is
    reported separately so the UI never confuses it with the level.
    """
    current_social = str(relationship.get("social_stage") or "acquaintance")
    social_rank = SOCIAL_STAGE_RANK.get(current_social, 0)
    next_social = (
        SOCIAL_STAGES[social_rank + 1]
        if social_rank < SOCIAL_STAGE_RANK["close_friend"] else ""
    )
    social_requirements = _relationship_requirements(
        relationship, SOCIAL_STAGE_REQUIREMENTS.get(next_social, {}),
    ) if next_social else []

    caps = relationship_branch_capabilities(state, relationship)
    raw_romance = str(relationship.get("romance_stage") or "none")
    current_romance = (
        "secret_lover" if bool(relationship.get("secret_lover"))
        else raw_romance
    )
    exclusive = _exclusive_relationship(
        state, excluding_person_id=int(relationship["person_id"]),
    )
    bond_path = str(relationship.get("bond_path") or "none")
    current_bond = str(relationship.get("bond_stage") or "none")
    bond_line = str(relationship.get("bond_line") or "")

    if bond_path == "bond":
        next_romance = ""
    elif current_romance == "none":
        next_romance = "ambiguous" if caps["romance"] else ""
    elif current_romance == "ambiguous":
        next_romance = "secret_lover" if exclusive is not None else "partner"
    elif current_romance == "partner":
        next_romance = "spouse"
    else:
        next_romance = ""
    romance_requirements = _relationship_requirements(
        relationship, ROMANCE_STAGE_REQUIREMENTS.get(next_romance, {}),
    ) if next_romance else []

    if bond_path == "none":
        next_bond = "partner" if social_rank >= SOCIAL_STAGE_RANK["close_friend"] and (
            caps["sisterhood"] or caps["brotherhood"]
        ) else ""
    elif current_bond == "none":
        next_bond = "partner"
    variant = bond_variant_for(state, relationship)
    if current_bond == "partner":
        next_bond = (
            "kindred" if variant in {"sisterhood", "brotherhood_kindred"}
            else "brother"
        )
    elif current_bond == "kindred":
        next_bond = "best_friend" if variant == "sisterhood" else "brother"
    elif current_bond == "brother":
        next_bond = "sworn_brother" if variant == "brotherhood_direct" else ""
    else:
        next_bond = ""
    bond_requirement_source = dict(BOND_STAGE_REQUIREMENTS.get(next_bond, {}))
    if next_bond == "brother":
        bond_requirement_source["bond_stage"] = (
            "kindred" if variant == "brotherhood_kindred" else "partner"
        )
    bond_requirements = _relationship_requirements(
        relationship, bond_requirement_source,
    ) if next_bond else []

    branch_options: list[dict[str, Any]] = []
    ap_ready = int((state.get("action_points") or {}).get("current") or 0) >= ACTION_COSTS["relationship"]
    if bond_path == "none" and current_romance == "none" and social_rank >= SOCIAL_STAGE_RANK["close_friend"]:
        if caps["romance"]:
            requirements = _relationship_requirements(
                relationship, ROMANCE_STAGE_REQUIREMENTS["ambiguous"],
            )
            branch_options.append({
                "target": "ambiguous", "path": "romance", "line": "",
                "cost": ACTION_COSTS["relationship"], "available": ap_ready,
                "ready": all(row["met"] for row in requirements),
                "requirements": requirements,
            })
        for line, label in (
            ("sisterhood", "bond_partner_sisterhood"),
            ("brotherhood", "bond_partner_brotherhood"),
        ):
            candidate_variant = (
                "brotherhood_kindred" if line == "brotherhood" and caps["brotherhood_kindred"]
                else "sisterhood" if line == "sisterhood" else "brotherhood_direct"
            )
            if not caps[candidate_variant]:
                continue
            requirements = _relationship_requirements(
                relationship, BOND_STAGE_REQUIREMENTS["partner"],
            )
            branch_options.append({
                "target": label, "path": "bond", "line": line,
                "variant": candidate_variant,
                "cost": ACTION_COSTS["relationship"], "available": ap_ready,
                "ready": all(row["met"] for row in requirements),
                "requirements": requirements,
            })

    return {
        "level": relationship_level(relationship),
        "tone": relationship_tone(relationship),
        "social": {
            "current": current_social, "next": next_social,
            "maxed": not next_social, "requirements": social_requirements,
            "ready": bool(social_requirements) and all(
                row["met"] for row in social_requirements
            ),
        },
        "romance": {
            "current": current_romance, "next": next_romance,
            "maxed": not next_romance, "available": bool(caps["romance"]),
            "requirements": romance_requirements,
            "ready": bool(romance_requirements) and all(
                row["met"] for row in romance_requirements
            ),
        },
        "bond": {
            "current": current_bond, "next": next_bond, "line": bond_line,
            "maxed": not next_bond,
            "available": bool(caps["sisterhood"] or caps["brotherhood"]),
            "requirements": bond_requirements,
            "ready": bool(bond_requirements) and all(
                row["met"] for row in bond_requirements
            ),
        },
        "branch": {
            "path": bond_path, "line": bond_line,
            "level": relationship_level(relationship),
            "tone": relationship_tone(relationship),
            "capabilities": caps,
            "options": branch_options,
        },
    }


def _apply_deltas(
    relationship: dict[str, Any], deltas: dict[str, float],
    *, gain_multiplier: float = 1.0,
) -> dict[str, float]:
    applied: dict[str, float] = {}
    for key in DIMENSIONS:
        before = float(relationship.get(key) or 0)
        delta = float(deltas.get(key) or 0)
        if delta > 0:
            delta *= max(1.0, float(gain_multiplier or 1.0))
        after = _clamp(before + delta)
        relationship[key] = round(after, 2)
        applied[key] = round(after - before, 2)
    relationship["updated_at"] = _now()
    return applied


def _daily_count(relationship: dict[str, Any], day: int, kind: str) -> int:
    daily = relationship.setdefault("daily", {})
    row = daily.get(str(int(day))) if isinstance(daily.get(str(int(day))), dict) else {}
    return int(row.get(kind) or 0)


def _bump_daily_count(relationship: dict[str, Any], day: int, kind: str) -> None:
    daily = relationship.setdefault("daily", {})
    key = str(int(day))
    row = daily.get(key) if isinstance(daily.get(key), dict) else {}
    row[kind] = int(row.get(kind) or 0) + 1
    daily[key] = row
    cutoff = int(day) - 30
    for stale_key in list(daily):
        try:
            if int(stale_key) < cutoff:
                daily.pop(stale_key, None)
        except (TypeError, ValueError):
            daily.pop(stale_key, None)


def _social_attribute_value(state: dict[str, Any], field: str) -> int:
    """Return the bounded value used by social maths.

    Profile attributes are intentionally uncapped because later asset levels
    can keep granting points, but gameplay effects must remain bounded.  A
    literal billion-point charisma score must not multiply every interaction
    by ten million.
    """
    profile = state.get("profile") if isinstance(state.get("profile"), dict) else {}
    return _integer(profile.get(field), 1, 100, 1)


def _scaled_attribute(value: int, low: float, high: float) -> float:
    return round(low + max(0, min(100, int(value))) / 100.0 * (high - low), 4)


def _social_calibration(state: dict[str, Any]) -> float:
    """Blend charm and EQ into a bounded multiplier for every social action."""
    charm = _social_attribute_value(state, "charisma")
    eq = _social_attribute_value(state, "eq")
    blended = charm * 0.35 + eq * 0.65
    return round(0.88 + blended / 100.0 * 0.24, 4)


def _attribute_dimension_factors(state: dict[str, Any]) -> dict[str, float]:
    """Map each profile attribute to the relationship dimension it drives."""
    return {
        "familiarity": 1.0,
        "affection": _scaled_attribute(
            _social_attribute_value(state, "charisma"), 0.90, 1.12,
        ),
        "trust": _scaled_attribute(
            _social_attribute_value(state, "eq"), 0.92, 1.10,
        ),
        "attraction": _scaled_attribute(
            _social_attribute_value(state, "appearance"), 0.78, 1.24,
        ),
        "respect": _scaled_attribute(
            _social_attribute_value(state, "ability"), 0.82, 1.20,
        ),
    }


def _scale_social_deltas(
    state: dict[str, Any], base: dict[str, float], multiplier: float = 1.0,
) -> dict[str, float]:
    factors = _attribute_dimension_factors(state)
    return {
        key: round(
            float(value) * float(multiplier or 0.0) * factors.get(key, 1.0), 2,
        )
        for key, value in base.items()
    }


def _action_payload(
    *, kind: str, title: str, deltas: dict[str, float], preference_match: bool,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind, "title": title, "deltas": deltas,
        "preference_match": bool(preference_match),
        "action_cost": int(ACTION_COSTS.get(kind, 0)),
        **(extra or {}),
    }


def _dialogue_payload(
    kind: str, reaction: str, **parameters: Any,
) -> dict[str, Any]:
    """Return a locale-neutral template descriptor for the web client.

    Dialogue is deliberately template-driven in the first release.  The
    backend selects a reaction and supplies stable parameters; the client
    resolves the matching localized sentence.  No free-form text or remote AI
    request is involved, so conversations remain deterministic and offline.
    """
    return {
        "kind": str(kind), "reaction": str(reaction),
        **{key: value for key, value in parameters.items() if value not in (None, "")},
    }


def _dialogue_context(
    state: dict[str, Any], person_id: int, day: int, *, salt: Any,
) -> dict[str, Any]:
    person = (state.get("people") or {}).get(str(int(person_id))) or {}
    traits = person.get("traits") if isinstance(person.get("traits"), dict) else {}
    personality = list(traits.get("personality") or ["warm"])
    values = list(traits.get("values") or ["career"])
    relationship = (state.get("relationships") or {}).get(str(int(person_id))) or {}
    tone = str(personality[0] or "warm")
    value = str(values[0] or "career")
    stage = str(relationship.get("social_stage") or "acquaintance")
    romance_stage = str(relationship.get("romance_stage") or "none")
    tone_rank = PERSONALITY_TRAITS.index(tone) if tone in PERSONALITY_TRAITS else 0
    value_rank = CORE_VALUES.index(value) if value in CORE_VALUES else 0
    stage_rank = SOCIAL_STAGES.index(stage) if stage in SOCIAL_STAGES else 0
    bond = effective_romance_stage(relationship)
    band = intimacy_band(relationship.get("intimacy"))
    variant = 1 + (
        int(_stable_unit("dialogue-variant", person_id, day, salt) * 3)
        + tone_rank * 2 + value_rank * 3 + stage_rank
    ) % 3
    return {
        "variant": variant,
        "tone": tone,
        "second_tone": str(personality[1] if len(personality) > 1 else "grounded"),
        "value": value,
        "stage": stage,
        "romance_stage": romance_stage,
        "bond": bond if bond in {"partner", "secret_lover", "spouse"} else "",
        "intimacy_band": band,
    }


def chat_plan(
    state: dict[str, Any], person_id: int, day: int, topic: str = "",
    message: str = "",
) -> dict[str, Any]:
    relationship = _relationship(state, person_id)
    topic_key = str(topic or "").strip().lower()
    message_text = str(message or "").strip()[:MAX_CHAT_MESSAGE_CHARS]
    _consume_action_points(
        state, day, ACTION_COSTS["chat"], reason="chat",
        person_id=person_id, detail=topic_key,
    )
    preference = relationship.get("preference") or {}
    count = _daily_count(relationship, day, "chat")
    falloff = max(0.12, 1.0 - count * 0.28)
    matched = bool(topic_key and topic_key == str(preference.get("topic") or ""))
    stage_bonus = 1.0 + _stage_rank(relationship) * 0.08
    mood = 0.94 + _stable_unit("chat", relationship["person_id"], int(day), count) * 0.12
    eq_factor = _eq_factor(state)
    multiplier = (
        _social_calibration(state) * stage_bonus
        * mood * (1.25 if matched else 1.0) * falloff
    )
    base = {
        "familiarity": 3.1, "affection": 2.1, "trust": 1.2,
        "attraction": 0.55, "respect": 0.45,
    }
    if not relationship.get("counters", {}).get("chat"):
        base["familiarity"] += 2.0
    deltas = _scale_social_deltas(state, base, multiplier)
    applied = _apply_deltas(
        relationship, deltas,
        gain_multiplier=_relationship_gain_multiplier(state),
    )
    intimacy_gain = _add_intimacy(
        relationship, 0.8 + (0.5 if matched else 0.0),
        gain_multiplier=_relationship_gain_multiplier(state),
    )
    _bump_daily_count(relationship, day, "chat")
    relationship["last_action_day"] = int(day)
    relationship.setdefault("counters", {})["chat"] = int(
        relationship.get("counters", {}).get("chat") or 0
    ) + 1
    upgraded = _upgrade_social_stage(relationship)
    person = state["people"][str(int(person_id))]
    dialogue_context = _dialogue_context(
        state, person_id, day, salt=(topic_key, count),
    )
    dialogue = _dialogue_payload(
        "chat", "preferred" if matched else "neutral", topic=topic_key,
        **dialogue_context,
    )
    timeline = _add_timeline(
        state, day=day, person=person, kind="chat", action="chat",
        result={
            "deltas": applied, "upgraded_stage": upgraded,
            "topic": topic_key, "preference_match": matched,
            "message": message_text, "dialogue": dialogue,
            "reply_mode": "template", "intimacy_gain": intimacy_gain,
            "intimacy_after": relationship.get("intimacy"),
            "eq_factor": eq_factor,
            "attribute_factors": _attribute_dimension_factors(state),
        },
    )
    return _action_payload(
        kind="chat", title="chat", deltas=applied, preference_match=matched,
        extra={
            "timeline": timeline, "upgraded_stage": upgraded,
            "template": "chat-warm" if sum(applied.values()) > 4 else "chat-calm",
            "dialogue": dialogue,
            "message": message_text,
            "reply_mode": "template",
            "intimacy_gain": intimacy_gain,
            "intimacy_after": relationship.get("intimacy"),
            "eq_factor": eq_factor,
            "attribute_factors": _attribute_dimension_factors(state),
        },
    )


def gift_plan(
    state: dict[str, Any], person_id: int, day: int, *,
    item_id: str, sku: str, item_name: str, item_value: float, category: str,
) -> dict[str, Any]:
    relationship = _relationship(state, person_id)
    if not str(item_id).strip():
        raise ValueError("请选择要赠送的物品")
    _consume_action_points(
        state, day, ACTION_COSTS["gift"], reason="gift",
        person_id=person_id, detail=str(item_name or sku),
    )
    if str(sku or "") in {"intimate_condoms", "intimate_pills"}:
        relationship["contraception"] = {
            "sku": str(sku), "day": int(day),
            "until_day": int(day) + (30 if sku == "intimate_pills" else 1),
        }
    preference = relationship.get("preference") or {}
    category_key = str(category or "luxury")
    matched = category_key == str(preference.get("gift") or "")
    disliked = category_key == str(preference.get("disliked_gift") or "")
    value_scale = max(0.0, min(2.2, (math.log10(max(float(item_value or 0), 1000.0)) - 3.0) / 2.2))
    eq_factor = _eq_factor(state)
    multiplier = (
        (1.65 if matched else 0.55 if disliked else 1.0)
        * (0.9 + value_scale * 0.18) * _social_calibration(state)
    )
    base = {
        "familiarity": 2.0 + value_scale * 2.0,
        "affection": 5.0 + value_scale * 8.0,
        "trust": 1.8 + value_scale * 2.4,
        "attraction": 3.2 + value_scale * 5.5,
        "respect": 1.6 + value_scale * 3.2,
    }
    deltas = _scale_social_deltas(state, base, multiplier)
    applied = _apply_deltas(
        relationship, deltas,
        gain_multiplier=_relationship_gain_multiplier(state),
    )
    intimacy_gain = _add_intimacy(
        relationship, 1.0 + value_scale * 1.2 + (0.75 if matched else 0.0),
        gain_multiplier=_relationship_gain_multiplier(state),
    )
    relationship["last_action_day"] = int(day)
    relationship["gifted_value_total"] = round_money(
        float(relationship.get("gifted_value_total") or 0) + float(item_value or 0)
    )
    relationship.setdefault("counters", {})["gift"] = int(
        relationship.get("counters", {}).get("gift") or 0
    ) + 1
    upgraded = _upgrade_social_stage(relationship)
    person = state["people"][str(int(person_id))]
    dialogue_context = _dialogue_context(
        state, person_id, day, salt=(
            "gift", category_key,
            int(relationship.get("counters", {}).get("gift") or 0),
        ),
    )
    timeline = _add_timeline(
        state, day=day, person=person, kind="gift", action="item",
        result={
            "item_id": str(item_id), "sku": str(sku), "item_name": str(item_name),
            "category": category_key, "value": float(item_value or 0),
            "deltas": applied, "upgraded_stage": upgraded,
            "preference_match": matched, "intimacy_gain": intimacy_gain,
            "intimacy_after": relationship.get("intimacy"),
            "eq_factor": eq_factor,
            "attribute_factors": _attribute_dimension_factors(state),
        },
    )
    return _action_payload(
        kind="gift", title="gift", deltas=applied, preference_match=matched,
        extra={
            "timeline": timeline, "upgraded_stage": upgraded,
            "dialogue": _dialogue_payload(
                "gift", "preferred" if matched else "disliked" if disliked else "neutral",
                category=category_key, **dialogue_context,
            ),
            "consumed_item": {
                "id": str(item_id), "sku": str(sku),
                "name": str(item_name), "value": float(item_value or 0),
            },
            "intimacy_gain": intimacy_gain,
            "intimacy_after": relationship.get("intimacy"),
            "eq_factor": eq_factor,
            "attribute_factors": _attribute_dimension_factors(state),
        },
    )


def money_gift_plan(
    state: dict[str, Any], person_id: int, day: int, amount: float,
) -> dict[str, Any]:
    """Send cash. The gain depends on values, personality and the bond."""
    relationship = _relationship(state, person_id)
    try:
        value = float(amount)
    except (TypeError, ValueError) as error:
        raise ValueError("送钱金额无效") from error
    if not math.isfinite(value) or value < MONEY_GIFT_MIN:
        raise ValueError(f"单次送钱不能少于 {MONEY_GIFT_MIN:,}")
    if value > MONEY_GIFT_MAX:
        raise ValueError(f"单次送钱不能超过 {MONEY_GIFT_MAX:,}")
    amount = round_money(value)
    person = state["people"][str(int(person_id))]
    traits = person.get("traits") if isinstance(person.get("traits"), dict) else {}
    personality = {str(item) for item in (traits.get("personality") or [])}
    values = {str(item) for item in (traits.get("values") or [])}
    _consume_action_points(
        state, int(day), ACTION_COSTS["money_gift"], reason="money_gift",
        person_id=person_id, detail=f"amount:{amount:.0f}",
    )
    personality_factor = 1.0
    if "driven" in personality:
        personality_factor += 0.18
    if "warm" in personality:
        personality_factor += 0.05
    if "playful" in personality:
        personality_factor += 0.03
    if "grounded" in personality:
        personality_factor -= 0.03
    if "reserved" in personality:
        personality_factor -= 0.08
    value_factor = 1.0
    if "stability" in values:
        value_factor += 0.20
    if "career" in values:
        value_factor += 0.15
    if "family" in values:
        value_factor += 0.08
    if "loyalty" in values:
        value_factor += 0.05
    if "freedom" in values:
        value_factor -= 0.10
    if "honesty" in values:
        value_factor -= 0.18
    reputation = max(0, int(person.get("world_reputation") or 0))
    reputation_factor = max(0.45, 1.0 - reputation / 25_000.0)
    prior = max(0.0, float(relationship.get("gifted_value_total") or 0.0))
    diminishing = 1.0 / (1.0 + prior / 50_000_000.0)
    stage = effective_romance_stage(relationship)
    stage_factor = {
        "none": 0.75, "ambiguous": 0.9, "partner": 1.12,
        "secret_lover": 1.18, "spouse": 0.9,
    }.get(stage, 0.85)
    normalised = max(0.0, min(1.0, (math.log10(amount) - 5.0) / 4.0))
    base = (1.0 + 7.0 * (normalised ** 0.8)) * personality_factor * value_factor
    base *= reputation_factor * diminishing * stage_factor * _social_calibration(state)
    base = max(0.6, min(14.0, base))
    deltas = _scale_social_deltas(state, {
        "affection": base * 0.55,
        "trust": base * 0.15,
        "respect": base * 0.20,
        "attraction": base * 0.10,
    }, 1.0)
    applied = _apply_deltas(
        relationship, deltas,
        gain_multiplier=_relationship_gain_multiplier(state),
    )
    relationship["gifted_value_total"] = round_money(prior + amount)
    relationship["last_action_day"] = int(day)
    relationship.setdefault("counters", {})["money_gift"] = int(
        relationship.get("counters", {}).get("money_gift") or 0
    ) + 1
    upgraded = _upgrade_social_stage(relationship)
    timeline = _add_timeline(
        state, day=int(day), person=person, kind="money_gift", action="cash",
        result={
            "amount": amount, "deltas": applied, "upgraded_stage": upgraded,
            "personality_factor": round(personality_factor, 3),
            "value_factor": round(value_factor, 3),
            "stage_factor": round(stage_factor, 3),
        },
    )
    return _action_payload(
        kind="money_gift", title="money_gift", deltas=applied, preference_match=False,
        extra={
            "timeline": timeline, "amount": amount,
            "upgraded_stage": upgraded,
            "action_cost": ACTION_COSTS["money_gift"],
            "gain_multiplier": round(base, 3),
            "personality_factor": round(personality_factor, 3),
            "value_factor": round(value_factor, 3),
            "stage_factor": round(stage_factor, 3),
        },
    )


def date_plan(
    state: dict[str, Any], person_id: int, day: int, activity_id: str,
) -> dict[str, Any]:
    relationship = _relationship(state, person_id)
    committed = effective_romance_stage(relationship) in {
        "partner", "secret_lover", "spouse",
    }
    if _stage_rank(relationship) < SOCIAL_STAGE_RANK["friend"] and not committed:
        raise ValueError("成为朋友后才可邀请约会")
    activity = str(activity_id or "").strip().lower()
    if activity not in DATE_ACTIVITIES:
        raise ValueError("约会活动无效")
    if _daily_count(relationship, day, "date"):
        raise ValueError("今天已经与该球员约会过")
    cost = int(DATE_ACTIVITIES[activity]["ap"])
    _consume_action_points(
        state, day, cost, reason="date",
        person_id=person_id, detail=activity,
    )
    preference = relationship.get("preference") or {}
    matched = activity == str(preference.get("activity") or "")
    disliked = activity == str(preference.get("disliked_activity") or "")
    romance_rank = ROMANCE_STAGE_RANK.get(str(relationship.get("romance_stage") or "none"), 0)
    eq_factor = _eq_factor(state)
    multiplier = (
        (1.45 if matched else 0.62 if disliked else 1.0)
        * (1.0 + romance_rank * 0.12) * _social_calibration(state)
    )
    base = {
        "familiarity": 2.4 + cost * 0.7,
        "affection": 3.8 + cost * 1.5,
        "trust": 1.8 + cost * 0.7,
        "attraction": 3.4 + cost * 1.6,
        "respect": 1.2 + cost * 0.5,
    }
    if activity == "trip":
        base["trust"] += 2.0
    deltas = _scale_social_deltas(state, base, multiplier)
    applied = _apply_deltas(
        relationship, deltas,
        gain_multiplier=_relationship_gain_multiplier(state),
    )
    intimacy_gain = _add_intimacy(
        relationship,
        2.0 + cost * 0.8 + (1.0 if matched else 0.0) + (1.2 if activity == "trip" else 0.0),
        gain_multiplier=_relationship_gain_multiplier(state),
    )
    secret_exposure_event = None
    if activity == "trip" and bool(relationship.get("secret_lover")):
        secret_exposure_event = _register_secret_meeting(
            state, relationship, day, 17.0, source="private_trip",
        )
    _bump_daily_count(relationship, day, "date")
    relationship["last_action_day"] = int(day)
    relationship.setdefault("counters", {})["date"] = int(
        relationship.get("counters", {}).get("date") or 0
    ) + 1
    upgraded = _upgrade_social_stage(relationship)
    person = state["people"][str(int(person_id))]
    dialogue_context = _dialogue_context(
        state, person_id, day, salt=("date", activity),
    )
    timeline = _add_timeline(
        state, day=day, person=person, kind="date", action=activity,
        result={
            "deltas": applied, "upgraded_stage": upgraded,
            "preference_match": matched, "intimacy_gain": intimacy_gain,
            "intimacy_after": relationship.get("intimacy"),
            "eq_factor": eq_factor,
            "attribute_factors": _attribute_dimension_factors(state),
        },
    )
    return _action_payload(
        kind="date", title=activity, deltas=applied, preference_match=matched,
        extra={
            "timeline": timeline, "upgraded_stage": upgraded,
            "activity": activity, "action_cost": cost,
            "intimacy_gain": intimacy_gain,
            "intimacy_after": relationship.get("intimacy"),
            "eq_factor": eq_factor,
            "attribute_factors": _attribute_dimension_factors(state),
            "secret_risk": relationship.get("secret_risk"),
            "event_id": secret_exposure_event.get("id") if secret_exposure_event else "",
            "dialogue": _dialogue_payload(
                "date", "preferred" if matched else "disliked" if disliked else "neutral",
                activity=activity, **dialogue_context,
            ),
        },
    )


def _exclusive_relationship(
    state: dict[str, Any], *, excluding_person_id: int = 0,
) -> dict[str, Any] | None:
    for person_id, relationship in (state.get("relationships") or {}).items():
        if int(person_id) == int(excluding_person_id):
            continue
        if str(relationship.get("romance_stage") or "none") in {"partner", "spouse"}:
            return relationship
    return None


def relationship_chance(
    state: dict[str, Any], relationship: dict[str, Any], target: str, *,
    secret: bool,
) -> float:
    profile = state.get("profile") or {}
    charm = min(100.0, max(1.0, float(profile.get("charisma") or 0)))
    eq = min(100.0, max(1.0, float(profile.get("eq") or 0)))
    appearance = min(100.0, max(1.0, float(profile.get("appearance") or 0)))
    ability = min(100.0, max(1.0, float(profile.get("ability") or 0)))
    score = (
        0.18
        + float(relationship.get("affection") or 0) * 0.0022
        + float(relationship.get("trust") or 0) * 0.0018
        + float(relationship.get("attraction") or 0) * 0.0034
        + charm * 0.0012
        + eq * 0.0016
        + appearance * 0.0008
        + ability * 0.0008
        + _stage_rank(relationship) * 0.025
    )
    if target in {"partner", "spouse"}:
        score -= 0.08
    if target == "spouse":
        score -= 0.12
    if secret:
        score -= 0.08
    return round(max(0.12, min(0.92, score)), 4)


def relationship_plan(
    state: dict[str, Any], person_id: int, day: int, target: str, *,
    secret: bool = False, has_ring: bool = False,
) -> dict[str, Any]:
    relationship = _relationship(state, person_id)
    target_key = str(target or "").strip().lower()
    current = str(relationship.get("romance_stage") or "none")
    bond_path = str(relationship.get("bond_path") or "none")
    bond_stage = str(relationship.get("bond_stage") or "none")
    bond_line = str(relationship.get("bond_line") or "")
    exclusive = _exclusive_relationship(state, excluding_person_id=person_id)
    caps = relationship_branch_capabilities(state, relationship)
    if target_key == "ambiguous":
        if bond_path == "bond":
            raise ValueError("已经选择朋友线，无法再进入暧昧")
        if current != "none":
            raise ValueError("当前关系已经越过暧昧阶段")
        if not caps["romance"]:
            raise ValueError("当前性别组合不能进入夫妻线")
        if _stage_rank(relationship) < SOCIAL_STAGE_RANK["close_friend"]:
            raise ValueError("至少要先成为好友")
        if not _requirements_ready(relationship, ROMANCE_STAGE_REQUIREMENTS["ambiguous"]):
            raise ValueError("好感或吸引尚未达到暧昧条件")
        secret = False
    elif target_key == "partner":
        if bond_path == "bond":
            raise ValueError("已经选择朋友线，无法成为情侣")
        if current != "ambiguous":
            raise ValueError("请先进入暧昧阶段")
        if exclusive is not None:
            raise ValueError("已有情侣或配偶，只能发展为情人保密关系")
        secret = False
        if not _requirements_ready(relationship, ROMANCE_STAGE_REQUIREMENTS["partner"]):
            raise ValueError("吸引或好感尚未达到情侣条件")
    elif target_key == "spouse":
        if bond_path == "bond":
            raise ValueError("已经选择朋友线，无法结婚")
        if current != "partner" or bool(relationship.get("secret_lover")):
            raise ValueError("只有公开情侣可以结婚")
        if exclusive is not None:
            raise ValueError("已有情侣或配偶，无法结婚")
        if not _requirements_ready(relationship, ROMANCE_STAGE_REQUIREMENTS["spouse"]):
            raise ValueError("好感或信任尚未达到结婚条件")
        secret = False
    elif target_key == "secret_lover":
        if bond_path == "bond":
            raise ValueError("已经选择朋友线，无法成为保密情人")
        if current != "ambiguous" or bool(relationship.get("secret_lover")):
            raise ValueError("当前关系不能成为情人")
        if exclusive is None:
            raise ValueError("没有其他情侣或配偶时，请公开发展为情侣")
        if not _requirements_ready(relationship, ROMANCE_STAGE_REQUIREMENTS["secret_lover"]):
            raise ValueError("吸引或信任尚未达到保密关系条件")
        secret = True
    elif target_key in {"bond_partner_sisterhood", "bond_partner_brotherhood"}:
        if target_key == "bond_partner_sisterhood":
            line, candidate_variant = "sisterhood", "sisterhood"
        else:
            line = "brotherhood"
            candidate_variant = (
                "brotherhood_kindred" if caps["brotherhood_kindred"]
                else "brotherhood_direct"
            )
        if not caps[candidate_variant]:
            raise ValueError("当前性别组合不能选择这条朋友线")
        if bond_path == "romance" or current != "none":
            raise ValueError("已经选择夫妻线，无法再进入朋友线")
        if bond_stage != "none":
            raise ValueError("朋友线已经开始")
        if _stage_rank(relationship) < SOCIAL_STAGE_RANK["close_friend"]:
            raise ValueError("至少要先成为好友")
        if not _requirements_ready(relationship, BOND_STAGE_REQUIREMENTS["partner"]):
            raise ValueError("熟悉、信任或尊重尚未达到搭档条件")
        secret = False
    elif target_key == "bond_kindred":
        variant = bond_variant_for(state, relationship)
        if bond_path != "bond" or bond_stage != "partner" or variant not in {
            "sisterhood", "brotherhood_kindred",
        }:
            raise ValueError("当前朋友线不能进入同好阶段")
        if not _requirements_ready(relationship, BOND_STAGE_REQUIREMENTS["kindred"]):
            raise ValueError("好感、熟悉或尊重尚未达到同好条件")
        secret = False
    elif target_key == "bond_best_friend":
        if bond_path != "bond" or bond_stage != "kindred" or bond_variant_for(state, relationship) != "sisterhood":
            raise ValueError("当前朋友线不能进入这个阶段")
        if not _requirements_ready(relationship, BOND_STAGE_REQUIREMENTS["best_friend"]):
            raise ValueError("关系条件尚未达到闺蜜阶段")
        secret = False
    elif target_key == "bond_brother":
        variant = bond_variant_for(state, relationship)
        if bond_path != "bond" or variant not in {"brotherhood_direct", "brotherhood_kindred"}:
            raise ValueError("只有兄弟线可以成为兄弟")
        expected_stage = "kindred" if variant == "brotherhood_kindred" else "partner"
        if bond_stage != expected_stage:
            raise ValueError("当前兄弟线还不能进入这一阶段")
        requirements = {
            **BOND_STAGE_REQUIREMENTS["brother"],
            "bond_stage": expected_stage,
        }
        if not _requirements_ready(relationship, requirements):
            raise ValueError("信任、尊重或好感尚未达到兄弟条件")
        secret = False
    elif target_key == "bond_sworn_brother":
        if (bond_path != "bond" or bond_stage != "brother"
                or bond_variant_for(state, relationship) != "brotherhood_direct"):
            raise ValueError("只有直接兄弟线可以成为生死兄弟")
        if not _requirements_ready(relationship, BOND_STAGE_REQUIREMENTS["sworn_brother"]):
            raise ValueError("信任、尊重或好感尚未达到生死兄弟条件")
        secret = False
    elif target_key == "breakup":
        if current == "none":
            raise ValueError("当前没有可分手的关系")
        if current == "spouse":
            raise ValueError("婚姻关系请使用离婚")
        secret = False
    elif target_key == "divorce":
        if current != "spouse":
            raise ValueError("当前没有婚姻关系")
        secret = False
    else:
        raise ValueError("关系操作无效")
    cost = 1 if target_key in {"breakup", "divorce"} else ACTION_COSTS["relationship"]
    _consume_action_points(
        state, day, cost, reason="relationship",
        person_id=person_id, detail=target_key,
    )
    chance = 1.0 if target_key in {"breakup", "divorce"} else relationship_chance(
        state, relationship, target_key, secret=secret,
    )
    ring_used = bool(has_ring) and target_key == "spouse"
    if target_key == "spouse" and not ring_used:
        # A proposal without a ring is still possible, but much less convincing.
        chance = chance * 0.42
    roll = _stable_unit(
        "relationship", relationship["person_id"], int(day), target_key, state.get("seq", 0),
    )
    success = roll <= chance
    person = state["people"][str(int(person_id))]
    applied: dict[str, float] = {}
    if target_key == "spouse" and not success and not ring_used:
        applied = _apply_deltas(
            relationship,
            {"affection": -5.0, "trust": -4.0, "respect": -2.0},
            gain_multiplier=1.0,
        )
    if success:
        if target_key == "ambiguous":
            relationship["romance_stage"] = "ambiguous"
            relationship["bond_path"] = "romance"
            relationship["bond_stage"] = "none"
            relationship["bond_line"] = ""
        elif target_key in {"partner", "spouse", "secret_lover"}:
            relationship["romance_stage"] = (
                "partner" if target_key == "partner"
                else "spouse" if target_key == "spouse" else "ambiguous"
            )
            relationship["bond_path"] = "romance"
            relationship["bond_stage"] = "none"
            relationship["bond_line"] = ""
            relationship["secret_lover"] = target_key == "secret_lover"
            relationship["intimacy"] = max(
                _clamp(relationship.get("intimacy"), 0.0, INTIMACY_MAX),
                _initial_intimacy_for_stage(effective_romance_stage(relationship)),
            )
            applied = _apply_deltas(
                relationship, {"affection": 4.0, "trust": 2.0, "attraction": 3.0},
                gain_multiplier=_relationship_gain_multiplier(state),
            )
        elif target_key in {"bond_partner_sisterhood", "bond_partner_brotherhood"}:
            relationship["bond_path"] = "bond"
            if target_key == "bond_partner_sisterhood":
                relationship["bond_line"] = "sisterhood"
                relationship["bond_variant"] = "sisterhood"
            else:
                relationship["bond_line"] = "brotherhood"
                relationship["bond_variant"] = (
                    "brotherhood_kindred" if caps["brotherhood_kindred"]
                    else "brotherhood_direct"
                )
            relationship["bond_stage"] = "partner"
            applied = _apply_deltas(
                relationship, {
                    "familiarity": 4.0, "affection": 2.0,
                    "trust": 4.0, "respect": 3.0,
                },
                gain_multiplier=_relationship_gain_multiplier(state),
            )
        elif target_key == "bond_kindred":
            relationship["bond_stage"] = "kindred"
            applied = _apply_deltas(
                relationship, {
                    "familiarity": 3.0, "affection": 4.0,
                    "trust": 3.0, "respect": 3.0,
                },
                gain_multiplier=_relationship_gain_multiplier(state),
            )
        elif target_key in {"bond_best_friend", "bond_brother"}:
            relationship["bond_stage"] = (
                "best_friend" if target_key == "bond_best_friend" else "brother"
            )
            applied = _apply_deltas(
                relationship, {
                    "familiarity": 3.0, "affection": 4.0,
                    "trust": 4.0, "respect": 4.0,
                },
                gain_multiplier=_relationship_gain_multiplier(state),
            )
        elif target_key == "bond_sworn_brother":
            relationship["bond_stage"] = "sworn_brother"
            applied = _apply_deltas(
                relationship, {
                    "familiarity": 4.0, "affection": 5.0,
                    "trust": 6.0, "respect": 5.0,
                },
                gain_multiplier=_relationship_gain_multiplier(state),
            )
        elif target_key in {"breakup", "divorce"}:
            relationship["romance_stage"] = "none"
            relationship["bond_path"] = "none"
            relationship["bond_stage"] = "none"
            relationship["bond_line"] = ""
            relationship["secret_lover"] = False
            relationship["intimacy"] = 0.0
            relationship["family_plan_discussed"] = False
            penalty = -8.0 if target_key == "breakup" else -12.0
            applied = _apply_deltas(
                relationship, {
                    "affection": penalty, "trust": penalty * 0.7,
                    "attraction": penalty * 0.5,
                },
                gain_multiplier=_relationship_gain_multiplier(state),
            )
    relationship["last_action_day"] = int(day)
    relationship["last_relationship_day"] = int(day)
    relationship.setdefault("counters", {})["relationship"] = int(
        relationship.get("counters", {}).get("relationship") or 0
    ) + 1
    upgraded = _upgrade_social_stage(relationship)
    dialogue_context = _dialogue_context(
        state, person_id, day, salt=("relationship", target_key, state.get("seq", 0)),
    )
    timeline = _add_timeline(
        state, day=day, person=person, kind="relationship", action=target_key,
        result={
            "success": success, "chance": chance, "roll": round(roll, 4),
            "target": target_key, "secret": secret, "deltas": applied,
            "romance_stage": relationship.get("romance_stage"),
            "bond_stage": relationship.get("bond_stage"),
            "bond_line": relationship.get("bond_line"),
            "intimacy": relationship.get("intimacy"),
            "social_stage": upgraded,
            "level": relationship_level(relationship),
            "tone": relationship_tone(relationship),
            "ring_used": ring_used,
        },
    )
    return {
        "kind": "relationship", "title": target_key, "target": target_key,
        "ring_used": ring_used,
        "success": success, "chance": chance, "roll": round(roll, 4),
        "secret": secret, "deltas": applied, "timeline": timeline,
        "dialogue": _dialogue_payload(
            "relationship", "success" if success else "failure", target=target_key,
            **dialogue_context,
        ),
        "romance_stage": relationship.get("romance_stage"),
        "bond_path": relationship.get("bond_path"),
        "bond_stage": relationship.get("bond_stage"),
        "bond_line": relationship.get("bond_line"),
        "level": relationship_level(relationship),
        "tone": relationship_tone(relationship),
        "social_stage": relationship.get("social_stage"), "action_cost": cost,
        "intimacy": relationship.get("intimacy"),
    }


def _requirements_ready(
    relationship: dict[str, Any], requirements: dict[str, Any],
) -> bool:
    rows = _relationship_requirements(relationship, requirements)
    return bool(rows) and all(row["met"] for row in rows)


def relationship_options(
    state: dict[str, Any], relationship: dict[str, Any],
) -> list[dict[str, Any]]:
    current = str(relationship.get("romance_stage") or "none")
    bond_path = str(relationship.get("bond_path") or "none")
    bond_stage = str(relationship.get("bond_stage") or "none")
    bond_line = str(relationship.get("bond_line") or "")
    variant = bond_variant_for(state, relationship)
    exclusive = _exclusive_relationship(
        state, excluding_person_id=int(relationship["person_id"]),
    )
    social = _stage_rank(relationship)
    caps = relationship_branch_capabilities(state, relationship)
    options: list[dict[str, Any]] = []

    if bond_path != "bond" and (caps["romance"] or current != "none"):
        options.extend([
            {
                "target": "ambiguous",
                "branch": True,
                "available": current == "none" and bond_path == "none"
                and social >= SOCIAL_STAGE_RANK["close_friend"]
                and _requirements_ready(relationship, ROMANCE_STAGE_REQUIREMENTS["ambiguous"]),
                "cost": ACTION_COSTS["relationship"],
            },
            {
                "target": "partner",
                "available": current == "ambiguous" and exclusive is None
                and _requirements_ready(relationship, ROMANCE_STAGE_REQUIREMENTS["partner"]),
                "cost": ACTION_COSTS["relationship"],
            },
            {
                "target": "secret_lover",
                "available": current == "ambiguous" and exclusive is not None
                and not bool(relationship.get("secret_lover"))
                and _requirements_ready(relationship, ROMANCE_STAGE_REQUIREMENTS["secret_lover"]),
                "cost": ACTION_COSTS["relationship"],
            },
            {
                "target": "spouse",
                "available": current == "partner" and exclusive is None
                and not bool(relationship.get("secret_lover"))
                and _requirements_ready(relationship, ROMANCE_STAGE_REQUIREMENTS["spouse"]),
                "cost": ACTION_COSTS["relationship"],
            },
        ])

    if bond_path != "romance":
        if bond_stage == "none" and social >= SOCIAL_STAGE_RANK["close_friend"]:
            for line, target in (
                ("sisterhood", "bond_partner_sisterhood"),
                ("brotherhood", "bond_partner_brotherhood"),
            ):
                candidate_variant = (
                    "brotherhood_kindred" if line == "brotherhood" and caps["brotherhood_kindred"]
                    else "sisterhood" if line == "sisterhood" else "brotherhood_direct"
                )
                if not caps[candidate_variant]:
                    continue
                options.append({
                    "target": target, "branch": True,
                    "variant": candidate_variant,
                    "available": _requirements_ready(
                        relationship, BOND_STAGE_REQUIREMENTS["partner"],
                    ),
                    "cost": ACTION_COSTS["relationship"],
                })
        elif bond_stage == "partner":
            if variant in {"sisterhood", "brotherhood_kindred"}:
                target = "bond_kindred"
                requirements = BOND_STAGE_REQUIREMENTS["kindred"]
            else:
                target = "bond_brother"
                requirements = {
                    **BOND_STAGE_REQUIREMENTS["brother"],
                    "bond_stage": "partner",
                }
            options.append({
                "target": target,
                "available": _requirements_ready(relationship, requirements),
                "cost": ACTION_COSTS["relationship"],
            })
        elif bond_stage == "kindred":
            target = "bond_best_friend" if variant == "sisterhood" else "bond_brother"
            requirements = (
                BOND_STAGE_REQUIREMENTS["best_friend"]
                if variant == "sisterhood"
                else {
                    **BOND_STAGE_REQUIREMENTS["brother"],
                    "bond_stage": "kindred",
                }
            )
            options.append({
                "target": target,
                "available": _requirements_ready(relationship, requirements),
                "cost": ACTION_COSTS["relationship"],
            })
        elif bond_stage == "brother" and variant == "brotherhood_direct":
            options.append({
                "target": "bond_sworn_brother",
                "available": _requirements_ready(
                    relationship, BOND_STAGE_REQUIREMENTS["sworn_brother"],
                ),
                "cost": ACTION_COSTS["relationship"],
            })

    options.extend([
        {"target": "breakup", "available": current in {"ambiguous", "partner"}, "cost": 1},
        {"target": "divorce", "available": current == "spouse", "cost": 1},
    ])
    return options


def _intimacy_action_delta_preview(
    state: dict[str, Any], relationship: dict[str, Any], action: dict[str, Any],
) -> dict[str, float]:
    hypothetical = deepcopy(relationship)
    return _apply_deltas(
        hypothetical,
        _scale_social_deltas(
            state, action.get("deltas") or {}, _social_calibration(state),
        ),
        gain_multiplier=_relationship_gain_multiplier(state),
    )


def intimacy_options(
    state: dict[str, Any], relationship: dict[str, Any], day: int | None = None,
) -> list[dict[str, Any]]:
    """Project the stage gate, AP cost, intimacy cost and capped preview."""
    if day is not None:
        refresh_action_points(state, int(day))
    stage = effective_romance_stage(relationship)
    committed = stage in {"partner", "secret_lover", "spouse"}
    current_ap = int((state.get("action_points") or {}).get("current") or 0)
    current_intimacy = _clamp_intimacy(relationship.get("intimacy"))
    current_obedience = max(0.0, min(100.0, float(relationship.get("obedience") or 0.0)))
    rows: list[dict[str, Any]] = []
    for action_id, action in INTIMATE_ACTIONS.items():
        ap_cost = int(action.get("ap") or 0)
        intimacy_cost = float(action.get("intimacy") or 0.0)
        stage_allowed = not committed or stage in tuple(action.get("stages") or ())
        available = (
            committed and stage_allowed
            and current_ap >= ap_cost and current_intimacy >= intimacy_cost
        )
        if not committed:
            blocked_reason = "commitment_required"
        elif not stage_allowed:
            blocked_reason = "stage"
        elif current_intimacy < intimacy_cost:
            blocked_reason = "intimacy"
        elif current_ap < ap_cost:
            blocked_reason = "action_points"
        else:
            blocked_reason = ""
        rows.append({
            "id": action_id, "icon": str(action.get("icon") or "heart"),
            "ap_cost": ap_cost, "intimacy_cost": intimacy_cost,
            "stages": list(action.get("stages") or ()),
            "family_planning": bool(action.get("family_planning")),
            "requires_item": str(action.get("requires_item") or ""),
            "available": available, "blocked_reason": blocked_reason,
            "intimacy_before": round(current_intimacy, 2),
            "intimacy_after": round(max(INTIMACY_MIN, current_intimacy - intimacy_cost), 2),
            "obedience_before": round(current_obedience, 2),
            "obedience_gain": round(float(action.get("obedience_gain") or 0.0), 2),
            "obedience_after": round(min(100.0, current_obedience + float(action.get("obedience_gain") or 0.0)), 2),
            "delta_preview": _intimacy_action_delta_preview(state, relationship, action),
            "pregnancy_chance": (
                _pregnancy_chance(state, relationship)
                if action.get("pregnancy") else 0.0
            ),
            "secret_risk_gain": (
                13.0 if action_id == "stay_close"
                else 18.0 if action_id == "getaway" else 0.0
            ) if bool(relationship.get("secret_lover")) else 0.0,
        })
    return rows


def intimacy_plan(
    state: dict[str, Any], person_id: int, day: int, action_id: str,
    *, protection: str = "", item_sku: str = "",
) -> dict[str, Any]:
    relationship = _relationship(state, person_id)
    stage = effective_romance_stage(relationship)
    if stage not in {"partner", "secret_lover", "spouse"}:
        raise ValueError("成为情侣、情人或夫妻后才可以进行亲密行为")
    action_key = str(action_id or "").strip().lower()
    action = INTIMATE_ACTIONS.get(action_key)
    if action is None:
        raise ValueError("亲密行为无效")
    if stage not in tuple(action.get("stages") or ()):
        raise ValueError("当前关系阶段不支持该亲密行为")
    required_item = str(action.get("requires_item") or "")
    if required_item and str(item_sku or "") != required_item:
        raise ValueError("该亲密行为需要对应道具")
    protection_key = str(protection or "").strip().lower()
    if protection_key not in {"", "condom", "pill"}:
        raise ValueError("防护方式无效")
    if protection_key and not action.get("pregnancy"):
        raise ValueError("该亲密行为不支持防护选择")
    refresh_action_points(state, day)
    ap_cost = int(action.get("ap") or 0)
    intimacy_cost = float(action.get("intimacy") or 0.0)
    intimacy_before = _clamp_intimacy(relationship.get("intimacy"))
    if intimacy_before < intimacy_cost:
        raise ValueError("亲密度不足")
    current_ap = int((state.get("action_points") or {}).get("current") or 0)
    if current_ap < ap_cost:
        raise ValueError("行动力不足，请等待每周恢复")
    obedience_before = max(0.0, min(100.0, float(relationship.get("obedience") or 0.0)))
    obedience_gain = float(action.get("obedience_gain") or 0.0)
    obedience_after = min(100.0, obedience_before + obedience_gain)
    _consume_action_points(
        state, day, ap_cost, reason="intimacy",
        person_id=person_id, detail=action_key,
    )
    relationship["intimacy"] = round(intimacy_before - intimacy_cost, 2)
    relationship["obedience"] = round(obedience_after, 2)
    relationship["last_intimacy_day"] = int(day)
    if protection_key:
        relationship["contraception"] = {
            "sku": "intimate_condoms" if protection_key == "condom" else "intimate_pills",
            "day": int(day),
            "until_day": int(day) + (1 if protection_key == "condom" else 30),
        }
    item_bonus = {}
    if str(item_sku or "") == "intimate_toy":
        item_bonus = {"affection": 1.2, "attraction": 1.4}
    elif str(item_sku or "") == "intimate_blindfold":
        item_bonus = {"trust": 1.6, "respect": 0.4}
    elif str(item_sku or "") == "intimate_dice":
        item_bonus = {"affection": 0.8, "attraction": 0.8}
    social_deltas = _scale_social_deltas(
        state, {**(action.get("deltas") or {}), **item_bonus},
        _social_calibration(state),
    )
    gain_multiplier = _relationship_gain_multiplier(state)
    applied = _apply_deltas(
        relationship, social_deltas,
        gain_multiplier=gain_multiplier,
    )
    relationship["last_action_day"] = int(day)
    relationship.setdefault("counters", {})["intimacy"] = int(
        relationship.get("counters", {}).get("intimacy") or 0
    ) + 1
    _bump_daily_count(relationship, day, "intimacy")
    if action.get("family_planning"):
        relationship["family_plan_discussed"] = True
        relationship.setdefault("counters", {})["family_plan"] = int(
            relationship.get("counters", {}).get("family_plan") or 0
        ) + 1
    pregnancy_chance = 0.0
    conceived = False
    secret_exposure_event = None
    if action.get("pregnancy"):
        pregnancy_chance, conceived = _maybe_conceive(state, relationship, int(day))
    if action_key in {"stay_close", "getaway"} and bool(relationship.get("secret_lover")):
        secret_exposure_event = _register_secret_meeting(
            state, relationship, int(day),
            13.0 if action_key == "stay_close" else 18.0,
            source=f"intimacy_{action_key}",
        )
    upgraded = _upgrade_social_stage(relationship)
    person = state["people"][str(int(person_id))]
    dialogue_context = _dialogue_context(
        state, person_id, day, salt=("intimacy", action_key),
    )
    dialogue = _dialogue_payload("intimacy", "neutral", action=action_key, **dialogue_context)
    timeline = _add_timeline(
        state, day=day, person=person, kind="intimacy", action=action_key,
        result={
            "deltas": applied, "upgraded_stage": upgraded,
            "action_cost": ap_cost, "intimacy_cost": intimacy_cost,
            "intimacy_before": round(intimacy_before, 2),
            "intimacy_after": relationship.get("intimacy"),
            "intimacy_band": intimacy_band(relationship.get("intimacy")),
            "obedience_before": round(obedience_before, 2),
            "obedience_after": round(obedience_after, 2),
            "obedience_gain": round(obedience_gain, 2),
            "family_planning": bool(action.get("family_planning")),
            "pregnancy_chance": pregnancy_chance,
            "secret_risk": relationship.get("secret_risk"),
            "secret_event_id": (
                secret_exposure_event.get("id") if secret_exposure_event else ""
            ),
            "dialogue": dialogue,
        },
    )
    return _action_payload(
        kind="intimacy", title=action_key, deltas=applied, preference_match=False,
        extra={
            "timeline": timeline, "upgraded_stage": upgraded,
            "action": action_key, "action_cost": ap_cost,
            "intimacy_cost": intimacy_cost,
            "intimacy_before": round(intimacy_before, 2),
            "intimacy_after": relationship.get("intimacy"),
            "intimacy_delta": round(
                float(relationship.get("intimacy") or 0.0) - intimacy_before, 2,
            ),
            "intimacy_band_before": intimacy_band(intimacy_before),
            "intimacy_band_after": intimacy_band(relationship.get("intimacy")),
            "obedience_before": round(obedience_before, 2),
            "obedience_after": round(obedience_after, 2),
            "obedience_gain": round(obedience_gain, 2),
            "family_planning": bool(action.get("family_planning")),
            "protection": protection_key,
            "item_sku": str(item_sku or ""),
            "item_bonus": item_bonus,
            "pregnancy_chance": round(pregnancy_chance, 4),
            "secret_risk": relationship.get("secret_risk"),
            "secret_exposure_event_id": (
                secret_exposure_event.get("id") if secret_exposure_event else ""
            ),
            "eq_factor": _eq_factor(state),
            "attribute_factors": _attribute_dimension_factors(state),
            "dialogue": dialogue,
        },
    )


def residence_capacity(property_record: dict[str, Any]) -> int:
    area = max(0.0, float(property_record.get("area_sqm") or 0))
    level = max(1, int(property_record.get("level") or 1))
    area_slots = 1 + int(max(0.0, area - 40.0) // 45.0)
    level_bonus = (1 if level >= 3 else 0) + (1 if level >= 5 else 0)
    return max(1, min(8, area_slots + level_bonus))


def residence_rows(
    life_state: dict[str, Any], interaction_state: dict[str, Any], day: int,
) -> list[dict[str, Any]]:
    occupants: dict[str, list[str]] = {}
    for person_id, asset_id in (interaction_state.get("residences") or {}).items():
        if asset_id:
            occupants.setdefault(str(asset_id), []).append(str(person_id))
    people = interaction_state.get("people") or {}
    relationships = interaction_state.get("relationships") or {}
    rows: list[dict[str, Any]] = []
    for asset_id, record in (life_state.get("properties") or {}).items():
        if not isinstance(record, dict) or str(record.get("kind") or "") != "residential":
            continue
        if str(record.get("tenure") or "owned") != "owned":
            continue
        if str(record.get("mode") or "") != "self":
            continue
        capacity = residence_capacity(record)
        resident_ids = occupants.get(str(asset_id), [])
        occupant_rows: list[dict[str, Any]] = []
        for person_id in resident_ids:
            person = people.get(str(person_id))
            if not isinstance(person, dict):
                continue
            relationship = relationships.get(str(person_id))
            relationship = relationship if isinstance(relationship, dict) else {}
            occupant_rows.append({
                "person": {
                    "id": int(person.get("id") or person_id),
                    "name": str(person.get("name") or person_id),
                    "team_name": str(person.get("team_name") or ""),
                    "female": person.get("female"),
                },
                "relationship": {
                    "social_stage": str(relationship.get("social_stage") or "acquaintance"),
                    "romance_stage": str(relationship.get("romance_stage") or "none"),
                    "secret_lover": bool(relationship.get("secret_lover")),
                },
            })
        market_value = life_system.parcel_quote({
            "city_id": record.get("city_id"), "kind": record.get("kind"),
            "base_price": record.get("base_price"),
        }, int(day) or date.today().toordinal())
        rows.append({
            "asset_id": str(asset_id),
            "name_zh": str(record.get("name_zh") or ""),
            "name_en": str(record.get("name_en") or ""),
            "city_name_zh": str(record.get("city_name_zh") or ""),
            "city_name_en": str(record.get("city_name_en") or ""),
            "district_name_zh": str(record.get("district_name_zh") or ""),
            "district_name_en": str(record.get("district_name_en") or ""),
            "area_sqm": int(record.get("area_sqm") or 0),
            "level": int(record.get("level") or 1),
            "capacity": capacity, "occupied": len(resident_ids),
            "free": max(0, capacity - len(resident_ids)),
            "resident_ids": resident_ids,
            "occupants": occupant_rows,
            "construction": bool(record.get("construction")),
            "market_value": round_money(float(market_value)),
        })
    rows.sort(key=lambda row: (row["city_name_en"], row["name_en"], row["asset_id"]))
    return rows


def assign_residence_plan(
    interaction_state: dict[str, Any], life_state: dict[str, Any], *,
    person_id: int, asset_id: str, day: int,
) -> dict[str, Any]:
    relationship = _relationship(interaction_state, person_id)
    if _stage_rank(relationship) < SOCIAL_STAGE_RANK["friend"]:
        raise ValueError("成为朋友后才可邀请入住")
    previous = str(relationship.get("residence_asset_id") or "")
    requested = str(asset_id or "").strip()
    if requested == previous:
        return {"person_id": int(person_id), "asset_id": requested, "unchanged": True}
    if not requested:
        relationship["residence_asset_id"] = ""
        interaction_state.setdefault("residences", {}).pop(str(int(person_id)), None)
        person = interaction_state["people"][str(int(person_id))]
        timeline = _add_timeline(
            interaction_state, day=day, person=person, kind="residence",
            action="move_out", result={"previous_asset_id": previous},
        )
        return {
            "person_id": int(person_id), "asset_id": "",
            "previous_asset_id": previous, "unchanged": False,
            "timeline": timeline,
        }
    rows = {row["asset_id"]: row for row in residence_rows(life_state, interaction_state, day)}
    row = rows.get(requested)
    if row is None:
        raise ValueError("只能选择本人持有并设为自住的住宅")
    if row["construction"]:
        raise ValueError("住宅正在建设中，暂时不能入住")
    occupied = set(row["resident_ids"])
    occupied.discard(str(int(person_id)))
    if len(occupied) >= int(row["capacity"]):
        raise ValueError("该住宅入住容量已满")
    relationship["residence_asset_id"] = requested
    interaction_state.setdefault("residences", {})[str(int(person_id))] = requested
    person = interaction_state["people"][str(int(person_id))]
    timeline = _add_timeline(
        interaction_state, day=day, person=person, kind="residence",
        action="move_in", result={
            "asset_id": requested, "capacity": int(row["capacity"]),
            "previous_asset_id": previous,
        },
    )
    return {
        "person_id": int(person_id), "asset_id": requested,
        "previous_asset_id": previous, "capacity": int(row["capacity"]),
        "unchanged": False, "timeline": timeline,
    }


def _property_gift_block_reason(
    life_state: dict[str, Any], interaction_state: dict[str, Any], asset_id: str,
) -> str:
    record = (life_state.get("properties") or {}).get(str(asset_id))
    if not isinstance(record, dict):
        return "住宅或资产不存在"
    if str(record.get("tenure") or "owned") != "owned":
        return "租赁资产不可赠送"
    if isinstance(record.get("construction"), dict):
        return "资产正在建设中，不可赠送"
    if any(
        str(asset_id) == str(person_asset)
        for person_asset in (interaction_state.get("residences") or {}).values()
    ):
        return "资产内仍有 NPC 居住，请先迁出"
    garage_id = str(record.get("garage_id") or "")
    if garage_id and any(
        isinstance(vehicle, dict) and str(vehicle.get("garage_id") or "") == garage_id
        for vehicle in (life_state.get("vehicles") or {}).values()
    ):
        return "资产车库内仍有车辆，请先移走车辆"
    return ""


def _property_gift_block_reason_key(reason: str) -> str:
    return {
        "住宅或资产不存在": "missing",
        "租赁资产不可赠送": "lease",
        "资产正在建设中，不可赠送": "construction",
        "资产内仍有 NPC 居住，请先迁出": "occupied",
        "资产车库内仍有车辆，请先移走车辆": "garage",
    }.get(str(reason or ""), "blocked")


def _asset_gift_deltas(value: Any) -> dict[str, float]:
    value_scale = max(
        0.0,
        min(3.2, (math.log10(max(float(value or 0), 1000.0)) - 4.0) / 2.0),
    )
    multiplier = 1.0 + value_scale * 0.4
    base = {
        "familiarity": 2.0,
        "affection": 8.0 + value_scale * 6.0,
        "trust": 4.0 + value_scale * 3.0,
        "attraction": 7.0 + value_scale * 8.0,
        "respect": 8.0 + value_scale * 10.0,
    }
    return {key: round(value * multiplier, 2) for key, value in base.items()}


def _asset_gift_intimacy_gain(value: Any) -> float:
    value_scale = max(
        0.0,
        min(3.2, (math.log10(max(float(value or 0), 1000.0)) - 4.0) / 2.0),
    )
    return round(2.0 + value_scale * 3.2, 2)


def _asset_gift_relationship_preview(
    relationship: dict[str, Any], deltas: dict[str, float],
    gain_multiplier: float = 1.0,
) -> dict[str, Any]:
    """Return the exact capped effect without mutating the relationship."""
    hypothetical = deepcopy(relationship)
    scaled_deltas = _scale_positive_deltas(deltas, gain_multiplier)
    applied: dict[str, float] = {}
    for key in DIMENSIONS:
        before = _clamp(relationship.get(key) or 0)
        after = _clamp(before + float(scaled_deltas.get(key) or 0))
        hypothetical[key] = round(after, 2)
        applied[key] = round(after - before, 2)
    before_stage = str(relationship.get("social_stage") or "acquaintance")
    target_stage = social_stage_for(hypothetical)
    if SOCIAL_STAGE_RANK.get(target_stage, 0) < SOCIAL_STAGE_RANK.get(before_stage, 0):
        target_stage = before_stage
    return {
        "deltas": applied,
        "affection_gain": applied["affection"],
        "social_stage_before": before_stage,
        "social_stage_after": target_stage,
        "may_upgrade": (
            SOCIAL_STAGE_RANK.get(target_stage, 0)
            > SOCIAL_STAGE_RANK.get(before_stage, 0)
        ),
    }


def _asset_gift_previews(
    relationship: dict[str, Any], assets: dict[str, list[dict[str, Any]]],
    gain_multiplier: float = 1.0,
) -> dict[str, dict[str, Any]]:
    previews: dict[str, dict[str, Any]] = {}
    for group, kind in (("properties", "property"), ("vehicles", "vehicle")):
        for asset in assets.get(group) or []:
            if not asset.get("giftable"):
                continue
            key = f"{kind}:{asset.get('id') or ''}"
            previews[key] = _asset_gift_relationship_preview(
                relationship, asset.get("deltas") or {},
                gain_multiplier=gain_multiplier,
            )
    return previews


def asset_gift_options(
    life_state: dict[str, Any], interaction_state: dict[str, Any], day: int,
) -> dict[str, list[dict[str, Any]]]:
    properties: list[dict[str, Any]] = []
    for asset_id, record in (life_state.get("properties") or {}).items():
        if not isinstance(record, dict):
            continue
        reason = _property_gift_block_reason(life_state, interaction_state, str(asset_id))
        value = life_system.parcel_quote({
            "city_id": record.get("city_id"), "kind": record.get("kind"),
            "base_price": record.get("base_price"),
        }, int(day) or date.today().toordinal())
        deltas = _asset_gift_deltas(value)
        properties.append({
            "id": str(asset_id), "kind": str(record.get("kind") or ""),
            "name_zh": str(record.get("name_zh") or ""),
            "name_en": str(record.get("name_en") or ""),
            "city_id": str(record.get("city_id") or ""),
            "city_name_zh": str(record.get("city_name_zh") or ""),
            "city_name_en": str(record.get("city_name_en") or ""),
            "district_id": str(record.get("district_id") or ""),
            "district_name_zh": str(record.get("district_name_zh") or ""),
            "district_name_en": str(record.get("district_name_en") or ""),
            "tenure": str(record.get("tenure") or "owned"),
            "mode": str(record.get("mode") or ""),
            "area_sqm": int(record.get("area_sqm") or 0),
            "level": int(record.get("level") or 1),
            "market_value": round_money(float(value)),
            "deltas": deltas, "action_cost": ACTION_COSTS["asset_gift"],
            "giftable": not bool(reason), "blocked_reason": reason,
            "blocked_reason_key": _property_gift_block_reason_key(reason) if reason else "",
        })
    properties.sort(key=lambda row: (not row["giftable"], row["city_name_en"], row["name_en"]))
    garages = {
        str(key): value for key, value in (life_state.get("garages") or {}).items()
        if isinstance(value, dict)
    }
    vehicles: list[dict[str, Any]] = []
    for vehicle_id, record in (life_state.get("vehicles") or {}).items():
        if not isinstance(record, dict):
            continue
        value = life_system.vehicle_market_value(
            record, int(day) or date.today().toordinal(),
        )
        deltas = _asset_gift_deltas(value)
        garage_id = str(record.get("garage_id") or "")
        garage = garages.get(garage_id) or {}
        vehicles.append({
            "id": str(vehicle_id), "catalog_id": str(record.get("catalog_id") or ""),
            "name": str(record.get("name") or ""),
            "manufacturer": str(record.get("manufacturer") or ""),
            "class": str(record.get("class") or ""),
            "rarity": str(record.get("rarity") or ""),
            "garage_id": garage_id,
            "garage_name_zh": str(garage.get("name_zh") or ""),
            "garage_name_en": str(garage.get("name_en") or ""),
            "garage_category": str(garage.get("category") or ""),
            "image": str(record.get("image") or ""),
            "market_value": value, "deltas": deltas,
            "action_cost": ACTION_COSTS["asset_gift"],
            "giftable": True, "blocked_reason": "",
        })
    vehicles.sort(key=lambda row: (row["manufacturer"], row["name"], row["id"]))
    return {"properties": properties, "vehicles": vehicles}


def asset_gift_plan(
    interaction_state: dict[str, Any], life_state: dict[str, Any], *,
    person_id: int, asset_type: str, asset_id: str, day: int,
) -> dict[str, Any]:
    relationship = _relationship(interaction_state, person_id)
    if _stage_rank(relationship) < SOCIAL_STAGE_RANK["friend"]:
        raise ValueError("成为朋友后才可赠送地产或车辆")
    kind = str(asset_type or "").strip().lower()
    asset_key = str(asset_id or "").strip()
    if kind == "property":
        record = (life_state.get("properties") or {}).get(asset_key)
        if not isinstance(record, dict):
            raise ValueError("资产不存在")
        reason = _property_gift_block_reason(life_state, interaction_state, asset_key)
        if reason:
            raise ValueError(reason)
        value = life_system.parcel_quote({
            "city_id": record.get("city_id"), "kind": record.get("kind"),
            "base_price": record.get("base_price"),
        }, int(day) or date.today().toordinal())
        name_zh = str(record.get("name_zh") or record.get("name_en") or asset_key)
        name_en = str(record.get("name_en") or record.get("name_zh") or asset_key)
        name = name_zh
        snapshot = deepcopy(record)
    elif kind == "vehicle":
        record = (life_state.get("vehicles") or {}).get(asset_key)
        if not isinstance(record, dict):
            raise ValueError("车辆不存在")
        value = life_system.vehicle_market_value(record, int(day) or date.today().toordinal())
        name_zh = name_en = str(record.get("name") or asset_key)
        name = name_zh
        snapshot = deepcopy(record)
    else:
        raise ValueError("赠送资产类型无效")
    _consume_action_points(
        interaction_state, day, ACTION_COSTS["asset_gift"],
        reason="asset_gift", person_id=person_id,
        detail=f"{kind}:{name_en}",
    )
    gain_multiplier = _relationship_gain_multiplier(interaction_state)
    preview = _asset_gift_relationship_preview(
        relationship, _asset_gift_deltas(value), gain_multiplier=gain_multiplier,
    )
    return {
        "person_id": int(person_id), "asset_type": kind, "asset_id": asset_key,
        "asset_name": name, "asset_name_zh": name_zh,
        "asset_name_en": name_en, "value": round_money(float(value)),
        "snapshot": snapshot, **preview,
        "gain_multiplier": gain_multiplier,
        "action_cost": ACTION_COSTS["asset_gift"],
        "intimacy_gain_preview": (
            round(_asset_gift_intimacy_gain(value) * gain_multiplier, 2)
            if relationship_allows_intimacy(relationship) else 0.0
        ),
        "permanent": True, "recoverable": False,
        "warning": "赠送后资产永久转移给该球员，无法收回，也不能撤销。",
    }


def commit_asset_gift(
    interaction_state: dict[str, Any], life_state: dict[str, Any],
    plan: dict[str, Any], day: int,
) -> dict[str, Any]:
    relationship = _relationship(interaction_state, int(plan["person_id"]))
    kind = str(plan["asset_type"])
    asset_key = str(plan["asset_id"])
    if kind == "property":
        record = (life_state.get("properties") or {}).get(asset_key)
        if not isinstance(record, dict):
            raise ValueError("资产不存在")
        life_state["properties"].pop(asset_key, None)
        garage_id = str(record.get("garage_id") or "")
        if garage_id:
            life_state.setdefault("garages", {}).pop(garage_id, None)
    else:
        record = (life_state.get("vehicles") or {}).get(asset_key)
        if not isinstance(record, dict):
            raise ValueError("车辆不存在")
        life_state["vehicles"].pop(asset_key, None)
    applied = _apply_deltas(
        relationship, plan["deltas"],
        gain_multiplier=float(plan.get("gain_multiplier") or 1.0),
    )
    intimacy_gain = _add_intimacy(
        relationship, _asset_gift_intimacy_gain(plan.get("value")),
        gain_multiplier=float(plan.get("gain_multiplier") or 1.0),
    )
    relationship["gifted_value_total"] = round_money(
        float(relationship.get("gifted_value_total") or 0) + float(plan["value"])
    )
    relationship["last_action_day"] = int(day)
    upgraded = _upgrade_social_stage(relationship)
    person = interaction_state["people"][str(int(plan["person_id"]))]
    dialogue_context = _dialogue_context(
        interaction_state, int(plan["person_id"]), day,
        salt=("asset_gift", kind, asset_key),
    )
    dialogue = _dialogue_payload("gift", "neutral", category="luxury", **dialogue_context)
    ledger = {
        "id": _next_id(interaction_state, "gift"), "day": int(day), "at": _now(),
        "person_id": int(plan["person_id"]),
        "person_name": str(person.get("name") or ""),
        "asset_type": kind, "asset_id": asset_key,
        "asset_name": str(plan.get("asset_name") or ""),
        "asset_name_zh": str(plan.get("asset_name_zh") or plan.get("asset_name") or ""),
        "asset_name_en": str(plan.get("asset_name_en") or plan.get("asset_name") or ""),
        "value": round_money(float(plan.get("value") or 0)),
        "permanent": True, "recoverable": False,
        "snapshot": deepcopy(plan.get("snapshot") or {}),
    }
    interaction_state.setdefault("gifted_assets", []).append(ledger)
    interaction_state["gifted_assets"] = interaction_state["gifted_assets"][-MAX_GIFT_LEDGER_ROWS:]
    timeline = _add_timeline(
        interaction_state, day=day, person=person, kind="asset_gift", action=kind,
        result={
            "asset_id": asset_key, "asset_name": ledger["asset_name"],
            "asset_name_zh": ledger["asset_name_zh"],
            "asset_name_en": ledger["asset_name_en"],
            "value": ledger["value"], "deltas": applied,
            "upgraded_stage": upgraded, "permanent": True,
            "intimacy_gain": intimacy_gain,
            "intimacy_after": relationship.get("intimacy"),
            "dialogue": dialogue,
        },
    )
    return {
        "kind": "asset_gift", "asset_type": kind, "asset_id": asset_key,
        "asset_name": ledger["asset_name"],
        "asset_name_zh": ledger["asset_name_zh"],
        "asset_name_en": ledger["asset_name_en"],
        "value": ledger["value"], "deltas": applied, "timeline": timeline,
        "ledger": ledger, "permanent": True, "recoverable": False,
        "intimacy_gain": intimacy_gain,
        "intimacy_after": relationship.get("intimacy"),
        "action_cost": ACTION_COSTS["asset_gift"], "dialogue": dialogue,
    }


def person_owned_assets(
    state: dict[str, Any], person_id: int,
) -> dict[str, Any]:
    """Project permanent asset gifts into the recipient's own portfolio."""
    rows = [
        deepcopy(row) for row in (state.get("gifted_assets") or [])
        if isinstance(row, dict)
        and int(row.get("person_id") or 0) == int(person_id)
    ]
    properties = [row for row in rows if str(row.get("asset_type") or "") == "property"]
    vehicles = [row for row in rows if str(row.get("asset_type") or "") == "vehicle"]
    total_value = round_money(sum(float(row.get("value") or 0) for row in rows))
    return {
        "properties": properties,
        "vehicles": vehicles,
        "count": len(rows),
        "total_value": total_value,
        "permanent": True,
    }


def remove_person(state: dict[str, Any], person_id: int) -> dict[str, Any]:
    """Remove a cached contact without touching FM or undoing permanent gifts."""
    person_key = str(int(person_id))
    person = (state.get("people") or {}).get(person_key)
    if not isinstance(person, dict):
        raise ValueError("该球员不在互动列表中")
    relationship = (state.get("relationships") or {}).get(person_key) or {}
    preserved_gifts = sum(
        1 for row in (state.get("gifted_assets") or [])
        if isinstance(row, dict) and int(row.get("person_id") or 0) == int(person_id)
    )
    removed_timeline = sum(
        1 for row in (state.get("timeline") or [])
        if isinstance(row, dict) and int(row.get("person_id") or 0) == int(person_id)
    )
    state.get("people", {}).pop(person_key, None)
    state.get("relationships", {}).pop(person_key, None)
    state.get("residences", {}).pop(person_key, None)
    state["timeline"] = [
        row for row in (state.get("timeline") or [])
        if not isinstance(row, dict) or int(row.get("person_id") or 0) != int(person_id)
    ]
    state["updated_at"] = _now()
    return {
        "person_id": int(person_id),
        "person_name": str(person.get("name") or ""),
        "removed": True,
        "preserved_permanent_gifts": preserved_gifts,
        "removed_timeline_entries": removed_timeline,
        "warning": "永久赠与的资产不会因删除联系人而收回。",
    }


def _visible_preferences(relationship: dict[str, Any]) -> dict[str, Any]:
    preference = relationship.get("preference") or {}
    familiarity = float(relationship.get("familiarity") or 0)
    trust = float(relationship.get("trust") or 0)
    return {
        "gift_hint": familiarity >= 15,
        "gift_known": trust >= 30,
        "disliked_gift_known": trust >= 45,
        "activity_known": trust >= 40,
        "topic_known": familiarity >= 25,
        "gift": str(preference.get("gift") or "") if trust >= 30 else "",
        "disliked_gift": str(preference.get("disliked_gift") or "") if trust >= 45 else "",
        "activity": str(preference.get("activity") or "") if trust >= 40 else "",
        "topic": str(preference.get("topic") or "") if familiarity >= 25 else "",
    }


def _disclosure_level(relationship: dict[str, Any]) -> int:
    """Map social progress to the amount of personal information revealed."""
    social = str(relationship.get("social_stage") or "acquaintance")
    romance = str(relationship.get("romance_stage") or "none")
    social_rank = SOCIAL_STAGE_RANK.get(social, 0)
    romance_rank = ROMANCE_STAGE_RANK.get(romance, 0)
    if social_rank >= SOCIAL_STAGE_RANK["confidant"] or romance_rank >= ROMANCE_STAGE_RANK["partner"]:
        return 3
    if social_rank >= SOCIAL_STAGE_RANK["close_friend"] or romance_rank >= ROMANCE_STAGE_RANK["ambiguous"]:
        return 2
    if social_rank >= SOCIAL_STAGE_RANK["friend"]:
        return 1
    familiarity = float(relationship.get("familiarity") or 0)
    trust = float(relationship.get("trust") or 0)
    if familiarity >= 75 and trust >= 70:
        return 3
    if familiarity >= 50 and trust >= 45:
        return 2
    if familiarity >= 25 or trust >= 20:
        return 1
    return 0


def _visible_person_for_relationship(
    person: dict[str, Any], relationship: dict[str, Any],
) -> dict[str, Any]:
    """Project an NPC snapshot down to what the relationship has unlocked.

    Hidden traits are not sent to the browser. This prevents a client-side
    inspection or a stale render from disclosing values before the player has
    earned them through the relationship.
    """
    visible = deepcopy(person)
    traits = deepcopy(person.get("traits") if isinstance(person.get("traits"), dict) else {})
    level = _disclosure_level(relationship)
    personality = list(traits.get("personality") or [])
    values = list(traits.get("values") or [])
    likes = traits.get("likes") if isinstance(traits.get("likes"), dict) else {}
    dislikes = traits.get("dislikes") if isinstance(traits.get("dislikes"), dict) else {}
    personality_limit = 1 if level < 2 else 2
    values_limit = 0 if level == 0 else (1 if level < 3 else 2)
    likes_limit = min(3, level + 1)
    traits["personality"] = personality[:personality_limit]
    traits["values"] = values[:values_limit]
    traits["likes"] = {
        key: list(likes.get(key) or [])[:likes_limit]
        for key in ("topics", "activities", "gifts")
    }
    if level < 2:
        traits["dislikes"] = {}
    elif level == 2:
        traits["dislikes"] = {
            "gifts": list(dislikes.get("gifts") or [])[:1],
            "activities": [],
        }
    else:
        traits["dislikes"] = deepcopy(dislikes)

    measurements = traits.get("measurements") if isinstance(traits.get("measurements"), dict) else {}
    precision = max(0, 3 - level)
    ranges: dict[str, dict[str, int]] = {}
    if measurements:
        person_id = int(person.get("id") or 0)
        for key, raw_value in measurements.items():
            try:
                value = int(raw_value)
            except (TypeError, ValueError):
                continue
            if precision:
                # Asymmetric, deterministic fuzz so the midpoint never reveals
                # the exact value. The true value is always inside the bounds.
                span = precision * 2 + 1 + int(
                    _stable_unit("measurement-span", person_id, key, value, level)
                    * (precision + 2)
                )
                lower = 1 + int(
                    _stable_unit("measurement-lower", person_id, key, value, level)
                    * max(1, span - 2)
                )
                upper = max(1, span - lower)
                if upper == lower:
                    upper += 1
                ranges[key] = {
                    "minimum": max(0, value - lower),
                    "maximum": value + upper,
                }
        traits["measurements"] = {} if precision else deepcopy(measurements)
        traits["measurement_ranges"] = ranges
        traits.pop("measurement_precision_cm", None)
        traits["measurement_exact"] = precision == 0
    else:
        traits["measurement_ranges"] = {}
        traits.pop("measurement_precision_cm", None)
        traits["measurement_exact"] = level >= 3

    traits["disclosure"] = {
        "level": level,
        "personality_visible": len(traits["personality"]),
        "personality_total": len(personality),
        "values_visible": len(traits["values"]),
        "values_total": len(values),
        "likes_visible_per_group": likes_limit,
        "likes_total_per_group": 3,
        "dislikes_visible": level >= 2,
        "dislikes_total": sum(len(value or []) for value in dislikes.values()),
        "measurement_exact": precision == 0,
    }
    visible["traits"] = traits
    return visible


def sync_child_placements(
    state: dict[str, Any], placements: dict[str, dict[str, Any]], day: int,
) -> bool:
    """Mirror native youth-intake progress onto placed children.

    ``placements`` maps a team id (as text or int) to a status row produced by
    the native youth plan, e.g. ``{"status": "armed"|"applied"|"completed",
    "player_id": 123, "player_name": "..."}``.  Children are never changed
    without a matching plan row, so an unloaded save keeps its last status.
    """
    changed = False
    for relationship in (state.get("relationships") or {}).values():
        if not isinstance(relationship, dict):
            continue
        for child in relationship.get("children") or []:
            if not isinstance(child, dict):
                continue
            placement = child.get("placement")
            if not isinstance(placement, dict) or not placement:
                continue
            row = placements.get(str(placement.get("team_id") or ""))
            if not isinstance(row, dict):
                continue
            status = str(row.get("status") or "")
            player_id = int(row.get("player_id") or 0)
            mapped = {
                "armed": "armed", "waiting": "pending", "pending": "pending",
                "applied": "applied", "completed": "playing",
                "completed_with_refund": "rejected", "insufficient": "rejected",
                "disarmed": "rejected", "cancelled": "rejected",
            }.get(status)
            if status == "completed" and player_id <= 0 and int(
                placement.get("player_id") or 0
            ) <= 0:
                mapped = "pending"
            if not mapped:
                continue
            if placement.get("status") != mapped:
                placement["status"] = mapped
                changed = True
            if player_id > 0 and int(placement.get("player_id") or 0) != player_id:
                placement["player_id"] = player_id
                placement["applied_day"] = int(day)
                changed = True
            team_name = str(row.get("team_name") or "").strip()
            if team_name and placement.get("team_name") != team_name:
                placement["team_name"] = team_name[:160]
                changed = True
            player_name = str(row.get("player_name") or "")
            if player_name and placement.get("player_name") != player_name:
                placement["player_name"] = player_name[:life_children.CHILD_NAME_MAX_LENGTH]
                changed = True
            if player_name and not str(child.get("name") or "").strip():
                child["name"] = player_name[:life_children.CHILD_NAME_MAX_LENGTH]
                changed = True
            if mapped in {"applied", "playing"}:
                for field, cast in (("ca", int), ("pa", int)):
                    try:
                        value = cast(row.get(field) or 0)
                    except (TypeError, ValueError):
                        value = 0
                    if value > 0 and int(child.get(field) or 0) != value:
                        child[field] = value
                        changed = True
                if placement.get("ca") != int(row.get("ca") or 0):
                    placement["ca"] = int(row.get("ca") or 0)
                    changed = True
                if placement.get("pa") != int(row.get("pa") or 0):
                    placement["pa"] = int(row.get("pa") or 0)
                    changed = True
                position = str(row.get("position") or "")
                if position and placement.get("position") != position:
                    placement["position"] = position[:8]
                    changed = True
                if position and str(child.get("football_position") or "") != position:
                    child["football_position"] = position[:8]
                    changed = True
            message = (
                "FM 青训计划已完成，但尚未核验到球员 UID；请刷新青训状态。"
                if status == "completed" and player_id <= 0
                and int(placement.get("player_id") or 0) <= 0
                else str(row.get("message") or "")
            )
            if message and placement.get("message") != message:
                placement["message"] = message[:400]
                changed = True
    return changed


def _next_encounter_id(state: dict[str, Any]) -> int:
    people = state.get("people") if isinstance(state.get("people"), dict) else {}
    for _ in range(256):
        candidate = ENCOUNTER_ID_BASE + random.randrange(0, ENCOUNTER_ID_LIMIT - ENCOUNTER_ID_BASE)
        if str(candidate) not in people:
            return candidate
    raise RuntimeError("无法分配新的偶遇人物编号")


def _encounter_name(country: str) -> str:
    code = str(country or "").strip().upper()
    if code == "CN":
        surnames, given = TRAVEL_NAME_POOLS["CN"]
        return f"{random.choice(surnames)}{random.choice(given)}"
    if code == "JP":
        surnames, given = TRAVEL_NAME_POOLS["JP"]
        return f"{random.choice(surnames)} {random.choice(given)}"
    if code == "KR":
        surnames, given = TRAVEL_NAME_POOLS["KR"]
        return f"{random.choice(surnames)} {random.choice(given)}"
    first, last = TRAVEL_NAME_POOLS["LATIN"]
    return f"{random.choice(first)} {random.choice(last)}"


def create_encounter_person(
    state: dict[str, Any], *, country: str, city: str, city_name_zh: str,
    city_name_en: str, place: str, day: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create a save-scoped fictional person for an outside encounter."""
    code = str(country or "CN").strip().upper()
    person_id = _next_encounter_id(state)
    age = random.randint(21, 37)
    persona = random.choice(TRAVEL_PERSONA_KEYS)
    personality = random.choice(TRAVEL_PERSONALITY_KEYS)
    snapshot = {
        "id": person_id,
        "name": _encounter_name(code)[:160],
        "age": age,
        "female": True,
        "nationality": code,
        "nationality_id": None,
        "nationality_code": code,
        "team_id": 0,
        "team_name": "",
        "positions": [],
        "ca": 0,
        "pa": 0,
        "world_reputation": 0,
        "object_type": "encounter",
        "source": "encounter",
        "npc": True,
        "met_country": code,
        "met_city": str(city or city_name_zh or city_name_en or "")[:80],
        "met_place": str(place or "")[:80],
        "persona_key": persona,
        "occupation_key": persona,
        "personality_key": personality,
        "date_of_birth": "",
        "refreshed_day": int(day),
        "refreshed_at": _now(),
    }
    traits = _normalize_person_traits(
        {"personality": [personality]}, person_id, female=True, age=age,
    )
    snapshot["height_cm"] = traits["height_cm"]
    snapshot["weight_kg"] = traits["weight_kg"]
    snapshot["traits"] = traits
    snapshot["snapshot_hash"] = _snapshot_hash(snapshot)
    relationship, _changed = cache_person(state, snapshot, day)
    relationship["contact_known"] = False
    relationship["contact_source"] = "encounter"
    relationship["met_country"] = code
    relationship["met_city"] = snapshot["met_city"]
    relationship["met_place"] = snapshot["met_place"]
    stored = state["people"][str(person_id)]
    stored.update({
        "source": "encounter", "npc": True,
        "met_country": code,
        "met_city": snapshot["met_city"],
        "met_place": snapshot["met_place"],
        "persona_key": persona, "occupation_key": persona,
        "personality_key": personality, "nationality_code": code,
    })
    return stored, relationship


def spend_travel_action(
    state: dict[str, Any], day: int, *, country: str, city: str, place: str,
) -> None:
    _consume_action_points(
        state, int(day), 1, reason="travel",
        detail=f"{country}:{city}:{place}"[:120],
    )


def travel_ask_contact(
    state: dict[str, Any], person_id: int, day: int, *, paparazzi: bool = False,
) -> dict[str, Any]:
    relationship = _relationship(state, int(person_id))
    if bool(relationship.get("contact_known", True)):
        return {
            "success": True, "already": True, "chance": 1.0,
            "message": "你们已经认识。",
        }
    chat_count = int((relationship.get("counters") or {}).get("chat") or 0)
    chance = 0.30 + min(0.28, chat_count * 0.07)
    if str(relationship.get("social_stage") or "") in {"friend", "close_friend", "confidant"}:
        chance += 0.08
    chance = min(0.90, chance)
    success = bool(paparazzi) or random.random() < chance
    if success:
        relationship["contact_known"] = True
        relationship["contact_source"] = str(relationship.get("contact_source") or "encounter")
        _apply_deltas(
            relationship, {"affection": 2.0, "trust": 1.5},
            gain_multiplier=_relationship_gain_multiplier(state),
        )
        relationship["last_action_day"] = int(day)
        return {
            "success": True, "already": False, "chance": round(chance, 4),
            "message": "她存下了你的号码。",
        }
    relationship["affection"] = max(0.0, float(relationship.get("affection") or 0) - 1.5)
    relationship["last_action_day"] = int(day)
    return {
        "success": False, "already": False, "chance": round(chance, 4),
        "message": "她笑了笑，没有把号码给你。",
    }


def travel_goodbye(state: dict[str, Any]) -> bool:
    travel = state.setdefault("travel", _empty_travel())
    pending = travel.get("pending") if isinstance(travel.get("pending"), dict) else None
    travel["pending"] = None
    if not pending:
        return False
    person_id = int(pending.get("person_id") or 0)
    if person_id <= 0:
        return True
    relationship = (state.get("relationships") or {}).get(str(person_id))
    if isinstance(relationship, dict) and not bool(relationship.get("contact_known", True)):
        state.get("people", {}).pop(str(person_id), None)
        state.get("relationships", {}).pop(str(person_id), None)
        state.get("residences", {}).pop(str(person_id), None)
    return True


def asset_level_value(
    state: dict[str, Any], life_state: dict[str, Any] | None, day: int,
) -> dict[str, Any]:
    """Public projection of the asset level used by encounter probability."""
    return _asset_level_snapshot(state, life_state, int(day))


def travel_public_view(
    state: dict[str, Any], asset_level: dict[str, Any] | None, day: int,
) -> dict[str, Any]:
    travel = state.get("travel") if isinstance(state.get("travel"), dict) else _empty_travel()
    pending = travel.get("pending") if isinstance(travel.get("pending"), dict) else None
    pending_view = None
    if pending:
        person_id = int(pending.get("person_id") or 0)
        person = (state.get("people") or {}).get(str(person_id))
        relationship = (state.get("relationships") or {}).get(str(person_id))
        if isinstance(person, dict) and isinstance(relationship, dict):
            visible = _visible_person_for_relationship(person, relationship)
            pending_view = {
                "person": visible,
                "relationship": {
                    "contact_known": bool(relationship.get("contact_known", True)),
                    "contact_source": str(relationship.get("contact_source") or "fm"),
                    "social_stage": str(relationship.get("social_stage") or "acquaintance"),
                    "romance_stage": str(relationship.get("romance_stage") or "none"),
                    "affection": float(relationship.get("affection") or 0),
                    "trust": float(relationship.get("trust") or 0),
                    "attraction": float(relationship.get("attraction") or 0),
                    "respect": float(relationship.get("respect") or 0),
                    "chat_count": int((relationship.get("counters") or {}).get("chat") or 0),
                },
                "country": str(pending.get("country") or ""),
                "city": str(pending.get("city") or ""),
                "city_name_zh": str(pending.get("city_name_zh") or ""),
                "city_name_en": str(pending.get("city_name_en") or ""),
                "place": str(pending.get("place") or ""),
                "source": str(pending.get("source") or "fm"),
                "known": bool(pending.get("known")),
            }
    level = int((asset_level or {}).get("current_level") or 0)
    return {
        "current_country": str(travel.get("current_country") or ""),
        "current_city": str(travel.get("current_city") or ""),
        "current_place": str(travel.get("current_place") or ""),
        "pending": pending_view,
        "asset_bonus": life_travel.asset_bonus(level),
        "encounter_chance": life_travel.encounter_chance(level),
        "visits": list(travel.get("visits") or [])[-20:],
    }


def public_view(
    state: dict[str, Any], *, game_date: str = "", scope_id: str = "",
    life_state: dict[str, Any] | None = None, day: int | None = None,
) -> dict[str, Any]:
    resolved_day = int(day or life_system.day_ordinal(game_date) or date.today().toordinal())
    refresh_action_points(state, resolved_day)
    settle_periodic_events(state, resolved_day)
    relationships: list[dict[str, Any]] = []
    exclusive = _exclusive_relationship(state)
    for person_id, relationship in (state.get("relationships") or {}).items():
        person = (state.get("people") or {}).get(str(person_id))
        if not isinstance(person, dict):
            continue
        if relationship.get("contact_known") is False:
            continue
        effective_stage = effective_romance_stage(relationship)
        committed = effective_stage in {"partner", "secret_lover", "spouse"}
        pregnancy = relationship.get("pregnancy") if isinstance(relationship.get("pregnancy"), dict) else {}
        pregnancy_view = deepcopy(pregnancy)
        if str(pregnancy_view.get("status") or "") == "expecting":
            conceived_day = int(pregnancy_view.get("conceived_day") or 0)
            due_day = int(pregnancy_view.get("due_day") or 0)
            revealed = bool(conceived_day) and resolved_day >= (
                conceived_day + PREGNANCY_DISCOVERY_DAYS
            )
            pregnancy_view["possible"] = True
            pregnancy_view["revealed"] = revealed
            if revealed:
                pregnancy_view["days_remaining"] = max(0, due_day - resolved_day)
                pregnancy_view["days_until_early"] = max(
                    0, int(pregnancy_view.get("due_early") or due_day) - resolved_day,
                )
                pregnancy_view["days_until_late"] = max(
                    0, int(pregnancy_view.get("due_late") or due_day) - resolved_day,
                )
            else:
                # Before the discovery event the player only knows that
                # conception is possible; due dates stay hidden.
                for field in ("due_day", "due_early", "due_late", "days_remaining",
                              "days_until_early", "days_until_late"):
                    pregnancy_view.pop(field, None)
        elif pregnancy_view:
            pregnancy_view["days_remaining"] = max(
                0, int(pregnancy_view.get("due_day") or resolved_day) - resolved_day,
            )
        relationships.append({
            "person": _visible_person_for_relationship(person, relationship),
            "relationship": {
                **deepcopy(relationship),
                "dimensions": {key: float(relationship.get(key) or 0) for key in DIMENSIONS},
                "preferences": _visible_preferences(relationship),
                "options": relationship_options(state, relationship),
                "social_progress": relationship_progress(state, relationship),
                "owned_assets": person_owned_assets(state, int(person_id)),
                "is_exclusive": str(relationship.get("romance_stage") or "none") in {"partner", "spouse"},
                "effective_romance_stage": effective_stage,
                "level": relationship_level(relationship),
                "tone": relationship_tone(relationship),
                "is_intimate": committed,
                "intimacy": round(_clamp_intimacy(relationship.get("intimacy")), 2),
                "intimacy_minimum": INTIMACY_MIN,
                "intimacy_band": intimacy_band(relationship.get("intimacy")),
                "intimacy_options": intimacy_options(state, relationship, resolved_day),
                "pregnancy": pregnancy_view,
                "secret_risk": round(max(0.0, float(relationship.get("secret_risk") or 0.0)), 2),
                "secret_exposure_threshold": SECRET_EXPOSURE_THRESHOLD,
            },
        })
    relationships.sort(key=lambda row: (
        -ROMANCE_STAGE_RANK.get(str(row["relationship"].get("romance_stage") or "none"), 0),
        -float(row["relationship"].get("affection") or 0),
        str(row["person"].get("name") or ""),
    ))
    residences = residence_rows(life_state or {}, state, resolved_day) if life_state is not None else []
    assets = (
        asset_gift_options(life_state or {}, state, resolved_day)
        if life_state is not None else {"properties": [], "vehicles": []}
    )
    if life_state is not None:
        for row in relationships:
            relationship = row["relationship"]
            relationship["asset_gift_previews"] = _asset_gift_previews(
                relationship, assets,
                gain_multiplier=_relationship_gain_multiplier(state),
            )
    children_rows: list[dict[str, Any]] = []
    for person_key, relationship in (state.get("relationships") or {}).items():
        person_row = (state.get("people") or {}).get(str(person_key)) or {}
        for child in relationship.get("children") or []:
            if not isinstance(child, dict):
                continue
            info = life_children.eligibility(child, resolved_day)
            growth_event = next((
                deepcopy(event) for event in (state.get("events") or [])
                if isinstance(event, dict)
                and str(event.get("kind") or "") == "child_football"
                and str(event.get("status") or "") == "pending"
                and str((event.get("data") or {}).get("child_id") or "") == str(child.get("id") or "")
                and int(event.get("available_day") or 0) <= resolved_day
            ), None)
            children_rows.append({
                "id": str(child.get("id") or ""),
                "name": str(child.get("name") or ""),
                "named": bool(str(child.get("name") or "").strip()),
                "gender": str(child.get("gender") or "male"),
                "born_day": int(child.get("born_day") or 0),
                "age": int(info["age"]),
                "adult_age": int(info["adult_age"]),
                "ready_for_academy": bool(info["ready"]),
                "preferred_position": str(child.get("preferred_position") or ""),
                "growth_source": str(child.get("growth_source") or ""),
                "elixirs_used": int(len(child.get("elixirs_used") or [])),
                "ca": int(child.get("ca") or 0),
                "pa": int(child.get("pa") or 0),
                "football_position": str(child.get("football_position") or ""),
                "training_history": deepcopy(child.get("training_history") or []),
                "training_milestones": [
                    int(value) for value in (child.get("training_milestones") or [])
                ],
                "neglected_milestones": [
                    int(value) for value in (child.get("neglected_milestones") or [])
                ],
                "trial_available": bool(info.get("trial_available")),
                "academy": deepcopy(child.get("academy") or {}),
                "growth_event": growth_event,
                "avatar": {
                    "updated_day": int((child.get("avatar") or {}).get("updated_day") or 0),
                    "synced_uid": int((child.get("avatar") or {}).get("synced_uid") or 0),
                    "error": str((child.get("avatar") or {}).get("error") or ""),
                    "preview": (
                        f"data:image/{str((child.get('avatar') or {}).get('extension') or 'png')};base64,"
                        f"{str((child.get('avatar') or {}).get('data') or '')}"
                    ) if str((child.get("avatar") or {}).get("data") or "") else "",
                },
                "placement": deepcopy(child.get("placement") or {}),
                "parent_person_id": _integer(person_key, 1, 2_147_483_647, 0),
                "parent_name": str(person_row.get("name") or relationship.get("person_name") or ""),
            })
    children_rows.sort(key=lambda row: (-int(row["age"]), str(row["name"] or row["id"])))
    pending_events = [
        deepcopy(event) for event in (state.get("events") or [])
        if isinstance(event, dict)
        and str(event.get("status") or "") == "pending"
        and int(event.get("available_day") or 0) <= resolved_day
    ]
    pending_events.sort(key=lambda event: (
        int(event.get("available_day") or 0), str(event.get("id") or ""),
    ))
    recent_events = [
        deepcopy(event) for event in reversed(state.get("events") or [])
        if isinstance(event, dict) and str(event.get("status") or "") == "resolved"
    ][:20]
    asset_level = _asset_level_snapshot(state, life_state, resolved_day)
    visible_person_ids = {
        int(row.get("person", {}).get("id") or 0)
        for row in relationships
        if isinstance(row, dict) and isinstance(row.get("person"), dict)
    }
    return {
        "ready": True,
        "scope_id": str(scope_id or ""),
        "game_date": str(game_date or ""),
        "profile": deepcopy(state.get("profile") or _empty_profile()),
        "profile_rules": {
            "base_points": PROFILE_BASE_POINTS,
            "attribute_minimum": PROFILE_ATTRIBUTE_MIN,
            "attribute_maximum": None,
            "attribute_safe_maximum": PROFILE_ATTRIBUTE_SAFE_MAX,
            "reputation_cost": PROFILE_REPUTATION_COST,
            "reset_cost": 0.0,
            "identity": {
                "anchor_age": PROFILE_IDENTITY_ANCHOR_AGE,
                "anchor_height_cm": PROFILE_IDENTITY_ANCHOR_HEIGHT_CM,
                "anchor_weight_kg": PROFILE_IDENTITY_ANCHOR_WEIGHT_KG,
                "age_rate": PROFILE_AGE_COST_RATE,
                "age_exponent": PROFILE_AGE_COST_EXPONENT,
                "height_rate": PROFILE_HEIGHT_COST_RATE,
                "weight_rate": PROFILE_WEIGHT_COST_RATE,
            },
        },
        "action_points": action_points(state, resolved_day),
        "entitlements": deepcopy(state.get("entitlements") or {}),
        "relationships": relationships,
        "pending_events": pending_events,
        "recent_events": recent_events,
        "asset_level": asset_level,
        "travel": travel_public_view(state, asset_level, resolved_day),
        "children": children_rows,
        "children_rules": {
            "adult_age": life_children.CHILD_ADULT_TRANSFER_AGE,
            "positions": list(life_children.CHILD_POSITIONS),
            "elixirs": life_children.elixir_tiers(),
            "name_max_length": life_children.CHILD_NAME_MAX_LENGTH,
        },
        "summary": {
            "people": len(state.get("people") or {}),
            "relationships": len(relationships),
            "friends": sum(
                1 for row in relationships
                if _stage_rank(row["relationship"]) >= SOCIAL_STAGE_RANK["friend"]
            ),
            "partners": sum(
                1 for row in relationships
                if str(row["relationship"].get("romance_stage") or "") in {"partner", "spouse"}
            ),
            "secret_lovers": sum(
                1 for row in relationships if bool(row["relationship"].get("secret_lover"))
            ),
            "intimate_relationships": sum(
                1 for row in relationships if bool(row["relationship"].get("is_intimate"))
            ),
            "residents": sum(
                1 for value in (state.get("residences") or {}).values() if value
            ),
            "gifted_assets": len(state.get("gifted_assets") or []),
            "children": sum(
                len(row["relationship"].get("children") or []) for row in relationships
            ),
        },
        "exclusive_partner": {
            "person_id": int(exclusive["person_id"]),
            "person_name": str(exclusive.get("person_name") or ""),
            "stage": str(exclusive.get("romance_stage") or ""),
        } if exclusive else None,
        "residences": residences,
        "assets": assets,
        "gifted_assets": list(reversed(state.get("gifted_assets") or []))[:50],
        "timeline": [
            row for row in reversed(state.get("timeline") or [])
            if isinstance(row, dict)
            and (
                not row.get("person_id")
                or int(row.get("person_id") or 0) in visible_person_ids
            )
        ][:120],
        "options": {
            "gift_categories": list(GIFT_CATEGORIES),
            "topics": list(CONVERSATION_TOPICS),
            "date_activities": [
                {"id": key, "cost": value["ap"], "label": value["label"]}
                for key, value in DATE_ACTIVITIES.items()
            ],
            "intimate_actions": [
                {
                    "id": key, "ap_cost": int(value["ap"]),
                    "intimacy_cost": float(value["intimacy"]),
                    "icon": str(value["icon"]), "stages": list(value["stages"]),
                    "family_planning": bool(value.get("family_planning")),
                    "requires_item": str(value.get("requires_item") or ""),
                }
                for key, value in INTIMATE_ACTIONS.items()
            ],
            "intimacy_maximum": INTIMACY_MAX,
            "intimacy_minimum": INTIMACY_MIN,
            "intimacy_bands": [
                {"threshold": threshold, "key": key} for threshold, key in INTIMACY_BANDS
            ],
            "pregnancy_gestation_days": PREGNANCY_GESTATION_DAYS,
            "secret_exposure_threshold": SECRET_EXPOSURE_THRESHOLD,
            "relationship_crisis_threshold": RELATIONSHIP_CRISIS_THRESHOLD,
        },
    }


def grant_profile_points(
    state: dict[str, Any], points: int, *, source: str, reference: str = "",
    day: int = 0,
) -> bool:
    """Add permanent allocation points once for a unique reference."""
    amount = _integer(points, 1, 99, 0)
    if not amount:
        return False
    profile = state.setdefault("profile", _empty_profile())
    ledger = _normalize_profile_point_ledger(profile.get("point_ledger"))
    normalized_reference = str(reference or "").strip()[:160]
    if normalized_reference and any(
        row.get("source") == str(source) and row.get("reference") == normalized_reference
        for row in ledger
    ):
        return False
    ledger.append({
        "id": _next_id(state, "profile-points"),
        "source": str(source or "manual")[:80],
        "reference": normalized_reference,
        "points": amount,
        "at": _now(), "day": int(day or 0),
    })
    profile["point_ledger"] = ledger[-MAX_PROFILE_POINT_LEDGER_ROWS:]
    profile["points_earned"] = sum(int(row["points"]) for row in profile["point_ledger"])
    profile["points_available"] = max(
        0,
        PROFILE_BASE_POINTS + int(profile["points_earned"])
        - int(profile.get("points_spent") or 0),
    )
    return True


def sync_asset_point_rewards(
    state: dict[str, Any], life_state: dict[str, Any], day: int,
) -> bool:
    """Award one-time profile points for owned properties and vehicles.

    The ledger is permanent: selling or gifting an asset never removes points
    that have already been granted.  This keeps later allocation stable while
    still letting new purchases fund character growth.
    """
    if not isinstance(life_state, dict):
        return False
    changed = False
    for asset_id, record in (life_state.get("properties") or {}).items():
        if not isinstance(record, dict) or str(record.get("tenure") or "owned") != "owned":
            continue
        kind = str(record.get("kind") or "residential")
        level = _integer(record.get("level"), 1, 20, 1)
        reward = 1 + min(2, level // 3) + (1 if kind in {"commercial", "industrial"} else 0)
        changed = grant_profile_points(
            state, reward, source="property",
            reference=f"{asset_id}:L{level}", day=day,
        ) or changed
    for vehicle_id, record in (life_state.get("vehicles") or {}).items():
        if not isinstance(record, dict):
            continue
        changed = grant_profile_points(
            state, 1, source="vehicle", reference=str(vehicle_id), day=day,
        ) or changed
    return changed


def _owned_asset_value(
    life_state: dict[str, Any] | None, day: int,
) -> tuple[float, float]:
    """Return owned property value and vehicle value for the level timeline."""
    if not isinstance(life_state, dict):
        return 0.0, 0.0
    property_value = 0.0
    for record in (life_state.get("properties") or {}).values():
        if not isinstance(record, dict) or str(record.get("tenure") or "owned") != "owned":
            continue
        stored = record.get("market_value")
        if stored is not None:
            property_value += max(0.0, float(stored or 0))
            continue
        parcel = {
            "city_id": record.get("city_id"),
            "kind": record.get("kind"),
            "base_price": record.get("base_price"),
        }
        try:
            property_value += max(0.0, float(life_system.parcel_quote(parcel, int(day))))
        except (TypeError, ValueError):
            property_value += max(0.0, float(record.get("base_price") or 0))
    vehicle_value = 0.0
    for record in (life_state.get("vehicles") or {}).values():
        if not isinstance(record, dict):
            continue
        try:
            vehicle_value += max(
                0.0, float(life_system.vehicle_market_value(record, int(day))),
            )
        except (TypeError, ValueError):
            vehicle_value += max(0.0, float(record.get("base_price") or 0))
    return round_money(property_value), round_money(vehicle_value)


def _asset_level_snapshot(
    state: dict[str, Any], life_state: dict[str, Any] | None, day: int,
) -> dict[str, Any]:
    property_value, vehicle_value = _owned_asset_value(life_state, day)
    total_value = round_money(property_value + vehicle_value)
    current_index = 0
    for index, row in enumerate(ASSET_LEVELS):
        if total_value >= int(row.get("threshold") or 0):
            current_index = index
    current = ASSET_LEVELS[current_index]
    next_row = ASSET_LEVELS[current_index + 1] if current_index + 1 < len(ASSET_LEVELS) else None
    if next_row is None:
        progress = 1.0
    else:
        span = max(1, int(next_row["threshold"]) - int(current["threshold"]))
        progress = max(0.0, min(1.0, (total_value - int(current["threshold"])) / span))
    reward_records = state.get("asset_level_rewards") if isinstance(
        state.get("asset_level_rewards"), dict,
    ) else {}
    rows: list[dict[str, Any]] = []
    for row in ASSET_LEVELS:
        level = int(row["level"])
        record = reward_records.get(str(level)) if isinstance(
            reward_records.get(str(level)), dict,
        ) else {}
        car_id = str(row.get("vehicle") or "")
        car = life_system.car_by_id(car_id) if car_id else None
        rows.append({
            "level": level,
            "threshold": int(row["threshold"]),
            "points": int(row.get("points") or 0),
            "unlocked": level <= int(current["level"]),
            "claimed": bool(record.get("points_awarded")) if int(row.get("points") or 0) else True,
            "vehicle": {
                "catalog_id": car_id,
                "name": str((car or {}).get("name") or car_id),
                "manufacturer": str((car or {}).get("manufacturer") or ""),
                "class": str((car or {}).get("class") or ""),
                "rarity": str((car or {}).get("rarity") or ""),
                "image": str((car or {}).get("image") or ""),
                "value": float((car or {}).get("price") or 0),
            } if car_id else None,
            "vehicle_claimed": bool(record.get("vehicle_claimed")) if car_id else True,
            "vehicle_pending": bool(car_id and record.get("points_awarded") and not record.get("vehicle_claimed")),
        })
    return {
        "total_value": total_value,
        "property_value": property_value,
        "vehicle_value": vehicle_value,
        "current_level": int(current["level"]),
        "current_threshold": int(current["threshold"]),
        "next_level": int(next_row["level"]) if next_row else None,
        "next_threshold": int(next_row["threshold"]) if next_row else None,
        "progress": round(progress, 4),
        "levels": rows,
    }


def sync_asset_level_rewards(
    state: dict[str, Any], life_state: dict[str, Any], day: int,
) -> bool:
    """Award achievement points once as levels unlock.

    Vehicle rewards are intentionally *not* granted here: the player must press
    the claim button on the asset-level board.  This keeps a full garage from
    silently blocking a reward and makes the storage-first delivery rule
    explicit.  All point changes remain idempotent.
    """
    if not isinstance(life_state, dict):
        return False
    changed = False
    snapshot = _asset_level_snapshot(state, life_state, int(day))
    current_level = int(snapshot["current_level"])
    records = state.setdefault("asset_level_rewards", {})
    for row in ASSET_LEVELS:
        level = int(row["level"])
        if level > current_level:
            continue
        points = int(row.get("points") or 0)
        car_id = str(row.get("vehicle") or "")
        if not points and not car_id:
            continue
        record = records.get(str(level))
        if not isinstance(record, dict):
            record = {
                "level": level, "points_awarded": False,
                "vehicle_catalog_id": car_id, "vehicle_claimed": False,
                "vehicle_id": "", "claimed_at": "", "awarded_day": 0,
                "last_error": "",
            }
            records[str(level)] = record
            changed = True
        if points and not record.get("points_awarded"):
            if grant_profile_points(
                state, points, source="asset_level",
                reference=f"asset-level:{level}", day=int(day),
            ):
                changed = True
            record["points_awarded"] = True
            record["awarded_day"] = int(day)
            record["claimed_at"] = _now()
            changed = True
        if car_id and str(record.get("vehicle_catalog_id") or "") != car_id:
            # Levels 2-6 gained vehicles in V2.9.3.  Existing saves that already
            # passed those levels get a claim button instead of an automatic
            # grant, so a full garage cannot silently consume the reward.
            record["vehicle_catalog_id"] = car_id
            record.setdefault("vehicle_claimed", False)
            record.setdefault("vehicle_id", "")
            record.setdefault("last_error", "")
            changed = True
    return changed


def claim_asset_level_vehicle(
    state: dict[str, Any], life_state: dict[str, Any], level: int, day: int,
) -> dict[str, Any]:
    """Deliver one unlocked asset-level car reward on explicit request.

    Delivery order is owned by ``life_system.grant_vehicle_award``: storage
    first, then any other garage with a free space.  A full garage set raises
    ValueError and leaves the reward claimable for a later retry.
    """
    try:
        level_number = int(level)
    except (TypeError, ValueError) as error:
        raise ValueError("资产等级无效") from error
    row = next(
        (item for item in ASSET_LEVELS if int(item.get("level") or 0) == level_number),
        None,
    )
    if row is None:
        raise ValueError("资产等级无效")
    car_id = str(row.get("vehicle") or "")
    if not car_id:
        raise ValueError("该等级没有车辆奖励")
    snapshot = _asset_level_snapshot(state, life_state, int(day))
    if level_number > int(snapshot.get("current_level") or 0):
        raise ValueError("尚未达到该资产等级")
    records = state.setdefault("asset_level_rewards", {})
    record = records.get(str(level_number))
    if not isinstance(record, dict):
        record = {
            "level": level_number, "points_awarded": False,
            "vehicle_catalog_id": car_id, "vehicle_claimed": False,
            "vehicle_id": "", "claimed_at": "", "awarded_day": 0,
            "last_error": "",
        }
        records[str(level_number)] = record
    if record.get("vehicle_claimed"):
        raise ValueError("该等级车辆奖励已经领取")
    vehicle = life_system.grant_vehicle_award(
        life_state, car_id, int(day), source="asset_level",
    )
    record["vehicle_catalog_id"] = car_id
    record["vehicle_id"] = str(vehicle.get("id") or "")
    record["vehicle_claimed"] = True
    record["claimed_at"] = _now()
    record["last_error"] = ""
    return {"level": level_number, "vehicle": vehicle, "record": record}


def profile_update_plan(
    state: dict[str, Any], payload: dict[str, Any],
) -> dict[str, Any]:
    """Validate a profile allocation against the current permanent point pool."""
    source = payload if isinstance(payload, dict) else {}
    current = _normalize_profile(state.get("profile"))
    if "surname" in source or "given_name" in source:
        surname = str(source.get("surname") or "").strip()[:40]
        given_name = str(source.get("given_name") or "").strip()[:40]
    else:
        surname, given_name = _split_profile_name(
            source.get("name") or current.get("name") or "",
        )
        if not surname and not given_name:
            surname = str(current.get("surname") or "")
            given_name = str(current.get("given_name") or "")
    name = _compose_profile_name(surname, given_name)
    if not name:
        raise ValueError("请填写玩家姓氏或名字")
    gender = str(source.get("gender") or "male").strip().lower()
    if gender not in {"male", "female", "nonbinary"}:
        raise ValueError("玩家性别无效")
    age = _integer(source.get("age", current.get("age")), MIN_ADULT_AGE, 99, 30)
    if age < MIN_ADULT_AGE:
        raise ValueError("玩家必须年满 18 岁")
    height_cm = _integer(
        source.get("height_cm", current.get("height_cm")), 120, 230, 180,
    )
    weight_kg = _integer(
        source.get("weight_kg", current.get("weight_kg")), 35, 200, 75,
    )
    attributes = {
        key: _integer(
            source.get(key, current.get(key)), PROFILE_ATTRIBUTE_MIN,
            PROFILE_ATTRIBUTE_SAFE_MAX, int(current.get(key) or PROFILE_ATTRIBUTE_MIN),
        )
        for key in PROFILE_ALLOCATABLE_KEYS
    }
    if current.get("completed") and any(
        attributes[key] < int(current.get(key) or 0)
        for key in PROFILE_ALLOCATABLE_KEYS
    ):
        raise ValueError("颜值、能力、魅力、情商与声望只能增加，不能降低")
    identity_cost = profile_identity_cost(age, height_cm, weight_kg)
    spent = sum(int(attributes[key]) for key in PROFILE_ATTRIBUTE_KEYS)
    spent += int(attributes[PROFILE_REPUTATION_KEY]) * PROFILE_REPUTATION_COST
    spent += int(identity_cost["total"])
    available_total = PROFILE_BASE_POINTS + int(current.get("points_earned") or 0)
    if spent > available_total:
        raise ValueError(
            f"可用属性点不足：当前方案需要 {spent} 点，账户共有 {available_total} 点"
        )
    return {
        "name": name[:80], "surname": surname, "given_name": given_name,
        "gender": gender, "age": age, "height_cm": height_cm,
        "weight_kg": weight_kg,
        "bio": str(source.get("bio", current.get("bio")) or "")[:500],
        "attributes": attributes, "identity_cost": identity_cost,
        "points_spent": spent, "points_total": available_total,
        "points_available": max(0, available_total - spent),
        "reset_required": False, "reset_cost": 0.0,
    }


def save_profile(
    state: dict[str, Any], payload: dict[str, Any], day: int, *,
    reset_approved: bool = False,
) -> dict[str, Any]:
    plan = profile_update_plan(state, payload)
    profile = _normalize_profile(state.get("profile"))
    profile.update({
        "name": plan["name"], "surname": plan["surname"],
        "given_name": plan["given_name"], "gender": plan["gender"], "age": plan["age"],
        "height_cm": plan["height_cm"], "weight_kg": plan["weight_kg"],
        **plan["attributes"], "identity_cost": plan["identity_cost"],
        "bio": plan["bio"], "profile_model": PROFILE_IDENTITY_MODEL_VERSION,
        "completed": True, "updated_at": _now(),
    })
    total = PROFILE_BASE_POINTS + int(profile.get("points_earned") or 0)
    profile["points_base"] = PROFILE_BASE_POINTS
    profile["points_spent"] = plan["points_spent"]
    profile["points_available"] = max(0, total - plan["points_spent"])
    state["profile"] = profile
    return deepcopy(profile)









