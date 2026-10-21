"""Player children: naming, growth elixirs and academy placement.

A child is created when a pregnancy event resolves with ``keep_child``.  The
record lives inside its relationship and gains three capabilities here:

* an explicit, player-chosen name (plus optional preferred role);
* growth elixirs that advance the child to a target age for a steep price;
* an academy placement at age 15 that hands the child to the existing native
  youth-intake plan (``academy_son``) of the chosen club.

The module never touches Football Manager memory.  Placement hands the plan to
the native hook already used by ``tools.youth_intake`` and reports its status.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
from typing import Any

from tools.money import round_money

CHILD_NAME_MAX_LENGTH = 40
CHILD_NAME_MIN_LENGTH = 1
CHILD_AGE_DAYS = 365
CHILD_ADULT_TRANSFER_AGE = 15
CHILD_MAX_AGE = 99
CHILD_POSITIONS = (
    "GK", "SW", "DL", "DC", "DR", "DM", "ML", "MC", "MR",
    "AML", "AMC", "AMR", "ST", "WBL", "WBR",
)
CHILD_PLACEMENT_STATUSES = {
    "pending", "armed", "applied", "playing", "recommended", "rejected",
    "trial", "trial_passed",
}
CHILD_SOURCE_NATURAL = "natural"
CHILD_SOURCE_ELIXIR = "elixir"
CHILD_ADULT_AGE = 15
CHILD_TRAINING_AGES = (3, 6, 9, 12)
CHILD_START_CA = 22
CHILD_START_PA = 92
CHILD_MAX_CA = 200
CHILD_TRAINING_OPTIONS: dict[str, dict[str, Any]] = {
    "finisher": {
        "position": "ST", "ca": 4, "pa": 6,
        "name_zh": "前锋特训", "name_en": "Finishing school",
    },
    "creator": {
        "position": "AMC", "ca": 3, "pa": 7,
        "name_zh": "组织核心", "name_en": "Playmaker path",
    },
    "winger": {
        "position": "AML", "ca": 4, "pa": 5,
        "name_zh": "边路突破", "name_en": "Winger path",
    },
    "defender": {
        "position": "DC", "ca": 4, "pa": 4,
        "name_zh": "防守基石", "name_en": "Defensive path",
    },
    "goalkeeper": {
        "position": "GK", "ca": 3, "pa": 5,
        "name_zh": "门将特训", "name_en": "Goalkeeper path",
    },
    "balanced": {
        "position": "", "ca": 2, "pa": 3,
        "name_zh": "全面陪伴", "name_en": "Balanced upbringing",
    },
    "street": {
        "position": "AMC", "ca": 3, "pa": 7,
        "name_zh": "街头足球", "name_en": "Street football",
    },
    "athletic": {
        "position": "", "ca": 5, "pa": 1,
        "name_zh": "体能特训", "name_en": "Athletic training",
    },
    "risky": {
        "position": "ST", "ca": 6, "pa": -3,
        "name_zh": "冒险踢法", "name_en": "Risky style",
    },
    "rest": {
        "position": "", "ca": -1, "pa": 5,
        "name_zh": "保护性成长", "name_en": "Protected growth",
    },
    "mentor": {
        "position": "", "ca": 3, "pa": 4,
        "name_zh": "名师指导", "name_en": "Mentor guidance",
    },
    "late": {
        "position": "", "ca": 1, "pa": 9,
        "name_zh": "晚成型培养", "name_en": "Late bloomer",
    },
    "team": {
        "position": "MC", "ca": 2, "pa": 4,
        "name_zh": "团队型培养", "name_en": "Team-first path",
    },
}

# Growth elixirs: each tier jumps the child forward by a fixed number of days.
# Prices scale far above every other consumable because the effect is permanent
# and bypasses a real career's ageing curve.
CHILD_ELIXIR_TIERS: dict[str, dict[str, Any]] = {
    "apprentice": {
        "tier": 1, "days": 365, "price": 250_000_000,
        "name_zh": "孩童成长丹", "name_en": "Childhood Elixir",
    },
    "adept": {
        "tier": 2, "days": 1095, "price": 900_000_000,
        "name_zh": "少年成长丹", "name_en": "Youth Elixir",
    },
    "master": {
        "tier": 3, "days": 2190, "price": 3_200_000_000,
        "name_zh": "天才成长丹", "name_en": "Prodigy Elixir",
    },
    "immortal": {
        "tier": 4, "days": 5040, "price": 12_000_000_000,
        "name_zh": "一步登天丹", "name_en": "Ascension Elixir",
    },
}


def elixir_tiers() -> list[dict[str, Any]]:
    return [
        {
            "id": key, **deepcopy(spec),
            "target_days": int(spec["days"]),
        }
        for key, spec in CHILD_ELIXIR_TIERS.items()
    ]


def child_age(child: dict[str, Any], day: int) -> int:
    born = int((child or {}).get("born_day") or 0)
    if born <= 0:
        return 0
    return max(0, min(CHILD_MAX_AGE, (int(day) - born) // CHILD_AGE_DAYS))


def _clamped_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def normalize_child(row: dict[str, Any], day: int) -> dict[str, Any]:
    source = row if isinstance(row, dict) else {}
    born = max(0, int(source.get("born_day") or 0))
    height = source.get("current_height_cm")
    try:
        height_value = int(height) if height is not None else None
    except (TypeError, ValueError):
        height_value = None
    preferred = str(source.get("preferred_position") or "").upper()
    placement = source.get("placement")
    normalized_placement: dict[str, Any] = {}
    if isinstance(placement, dict) and placement:
        status = str(placement.get("status") or "pending")
        # Older builds used ``training`` for a simulated trial pass, before
        # any native FM player existed. Keep those saves actionable.
        if status == "training":
            status = (
                "playing" if int(placement.get("player_id") or 0)
                else "trial_passed"
            )
        normalized_placement = {
            "status": status if status in CHILD_PLACEMENT_STATUSES else "pending",
            "team_id": int(placement.get("team_id") or 0),
            "team_name": str(placement.get("team_name") or "")[:120],
            "mode": str(placement.get("mode") or "own")[:24],
            "player_id": int(placement.get("player_id") or 0),
            "armed_day": int(placement.get("armed_day") or 0),
            "applied_day": int(placement.get("applied_day") or 0),
            "message": str(placement.get("message") or "")[:400],
            "recommend_target_id": int(placement.get("recommend_target_id") or 0),
            "recommend_target_name": str(placement.get("recommend_target_name") or "")[:120],
            "trial_score": int(placement.get("trial_score") or 0),
            "trial_day": int(placement.get("trial_day") or 0),
            "club_level": int(placement.get("club_level") or 0),
            "ca": int(placement.get("ca") or 0),
            "pa": int(placement.get("pa") or 0),
            "position": str(placement.get("position") or "")[:8],
            "player_name": str(placement.get("player_name") or "")[:CHILD_NAME_MAX_LENGTH],
        }
    surname = str(source.get("surname") or "").strip()[:20]
    given_name = str(source.get("given_name") or "").strip()[:CHILD_NAME_MAX_LENGTH]
    full_name = str(source.get("name") or "").strip()[:CHILD_NAME_MAX_LENGTH]
    if not given_name and full_name:
        given_name = full_name[len(surname):] if surname and full_name.startswith(surname) else full_name
    ca = _clamped_int(source.get("ca"), CHILD_START_CA, 1, CHILD_MAX_CA)
    pa = _clamped_int(source.get("pa"), CHILD_START_PA, ca, CHILD_MAX_CA)
    if (
        ca == CHILD_START_CA and pa == CHILD_START_PA
        and not (source.get("training_history") or source.get("training_milestones"))
    ):
        # Legacy/default children all shared 22/92; give them a stable,
        # varied starting profile without touching developed children.
        ca = 16 + int(_unit(source.get("id"), "legacy-ca") * 12)
        pa = max(ca + 18, 80 + int(_unit(source.get("id"), "legacy-pa") * 26))
    child = {
        "id": str(source.get("id") or ""),
        "name": (surname + given_name)[:CHILD_NAME_MAX_LENGTH]
        if surname and given_name else (full_name or given_name),
        "surname": surname,
        "given_name": given_name[:CHILD_NAME_MAX_LENGTH],
        "ca": ca,
        "pa": pa,
        "football_position": str(source.get("football_position") or "")[:8],
        "training_history": [
            {
                "age": int(row.get("age") or 0),
                "option": str(row.get("option") or "")[:24],
                "position": str(row.get("position") or "")[:8],
                "ca": int(row.get("ca") or 0),
                "pa": int(row.get("pa") or 0),
                "day": int(row.get("day") or 0),
            }
            for row in (source.get("training_history") or [])
            if isinstance(row, dict)
        ][-20:],
        "training_milestones": [
            int(value) for value in (source.get("training_milestones") or [])
            if str(value).isdigit()
        ][-12:],
        "avatar": {
            "data": str((source.get("avatar") or {}).get("data") or "")[:3_000_000]
            if isinstance(source.get("avatar"), dict) else "",
            "extension": str((source.get("avatar") or {}).get("extension") or "png")[:8]
            if isinstance(source.get("avatar"), dict) else "png",
            "updated_day": int((source.get("avatar") or {}).get("updated_day") or 0)
            if isinstance(source.get("avatar"), dict) else 0,
            "synced_uid": int((source.get("avatar") or {}).get("synced_uid") or 0)
            if isinstance(source.get("avatar"), dict) else 0,
            "synced_at": str((source.get("avatar") or {}).get("synced_at") or "")
            if isinstance(source.get("avatar"), dict) else "",
            "error": str((source.get("avatar") or {}).get("error") or "")[:200]
            if isinstance(source.get("avatar"), dict) else "",
        },
        "neglected_milestones": [
            int(value) for value in (source.get("neglected_milestones") or [])
            if str(value).isdigit()
        ][-12:],
        "born_day": born,
        "gender": "female" if str(source.get("gender") or "") == "female" else "male",
        "preferred_position": preferred if preferred in CHILD_POSITIONS else "",
        "current_height_cm": height_value,
        "growth_source": str(source.get("growth_source") or CHILD_SOURCE_NATURAL),
        "elixirs_used": [
            {
                "tier": str(item.get("tier") or "")[:24],
                "day": int(item.get("day") or 0),
                "age_after": int(item.get("age_after") or 0),
                "price": float(item.get("price") or 0),
            }
            for item in (source.get("elixirs_used") or [])
            if isinstance(item, dict)
        ][-40:],
        "placement": normalized_placement,
        "retired": bool(source.get("retired")),
    }
    if child["growth_source"] not in {CHILD_SOURCE_NATURAL, CHILD_SOURCE_ELIXIR}:
        child["growth_source"] = CHILD_SOURCE_NATURAL
    return child


def create_child(state: dict[str, Any], person_id: int, day: int) -> dict[str, Any]:
    """Create a named placeholder child; the player names it afterwards."""
    sequence = int(state.get("seq") or 0)
    child_id = f"child-{sequence + 1:06d}"
    state["seq"] = sequence + 1
    return normalize_child({
        "id": child_id, "name": "", "born_day": int(day),
        "gender": "female" if int(day) % 2 else "male",
    }, day)


def find_child(state: dict[str, Any], child_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    for relationship in (state.get("relationships") or {}).values():
        if not isinstance(relationship, dict):
            continue
        for child in relationship.get("children") or []:
            if isinstance(child, dict) and str(child.get("id") or "") == str(child_id):
                return relationship, child
    return None


def name_child(
    state: dict[str, Any], child_id: str, name: str, day: int,
    *, preferred_position: str = "",
) -> dict[str, Any]:
    resolved = str(name or "").strip()
    if len(resolved) < CHILD_NAME_MIN_LENGTH:
        raise ValueError("请为孩子填写名字")
    if len(resolved) > CHILD_NAME_MAX_LENGTH:
        raise ValueError(f"孩子名字最多 {CHILD_NAME_MAX_LENGTH} 个字符")
    position = str(preferred_position or "").strip().upper()
    if position and position not in CHILD_POSITIONS:
        raise ValueError("首选位置无效")
    found = find_child(state, child_id)
    if found is None:
        raise ValueError("子女记录不存在")
    _relationship, child = found
    if str(child.get("name") or "").strip() and child_age(child, day) >= CHILD_ADULT_TRANSFER_AGE:
        raise ValueError("孩子满 15 岁后不可改名，请谨慎")
    profile = state.get("profile") if isinstance(state.get("profile"), dict) else {}
    surname = str(profile.get("surname") or "").strip()[:20]
    if not surname:
        full = str(profile.get("name") or "").strip()
        surname, _given = (full[:2], full[2:]) if len(full) > 2 else ("", full)
    given = resolved
    if surname and given.startswith(surname):
        given = given[len(surname):].strip()
    child["surname"] = surname
    child["given_name"] = given[:CHILD_NAME_MAX_LENGTH]
    child["name"] = f"{surname}{given}"[:CHILD_NAME_MAX_LENGTH] if surname else given
    child["preferred_position"] = position
    child["named_day"] = int(day)
    return child


def elixir_quote(child: dict[str, Any], tier_id: str, day: int) -> dict[str, Any]:
    spec = CHILD_ELIXIR_TIERS.get(str(tier_id or ""))
    if spec is None:
        raise ValueError("成长丹药档位无效")
    current = child_age(child, day)
    if current >= CHILD_MAX_AGE:
        raise ValueError("该子女年龄已达上限")
    target = min(CHILD_MAX_AGE, current + int(spec["days"]) // CHILD_AGE_DAYS)
    if target <= current:
        raise ValueError("该丹药不足以让子女成长一岁")
    price = round_money(float(spec["price"]))
    return {
        "tier": str(tier_id), "days": int(spec["days"]),
        "price": price, "current_age": current, "target_age": target,
        "crosses_adult_age": current < CHILD_ADULT_TRANSFER_AGE <= target,
        "name_zh": str(spec["name_zh"]), "name_en": str(spec["name_en"]),
    }


def apply_elixir(
    state: dict[str, Any], child_id: str, tier_id: str, day: int,
    *, payment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    found = find_child(state, child_id)
    if found is None:
        raise ValueError("子女记录不存在")
    _relationship, child = found
    quote = elixir_quote(child, tier_id, day)
    shift = int(quote["target_age"]) - int(quote["current_age"])
    child["born_day"] = int(child["born_day"]) - shift * CHILD_AGE_DAYS
    child["growth_source"] = CHILD_SOURCE_ELIXIR
    child.setdefault("elixirs_used", []).append({
        "tier": quote["tier"], "day": int(day),
        "age_after": int(quote["target_age"]),
        "price": float(quote["price"]),
        "transaction_id": str((payment or {}).get("transaction_id") or ""),
    })
    child["elixirs_used"] = child["elixirs_used"][-40:]
    if not child.get("country"):
        child["country"] = "CN"
    return {
        "child": child, "quote": quote,
        "age": child_age(child, day),
    }


def elixir_affordable(available: float, price: float) -> bool:
    return float(available) + 1e-9 >= float(price)


def _unit(*parts: Any) -> float:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def seed_child_football(
    child: dict[str, Any], state: dict[str, Any], relationship: dict[str, Any],
) -> dict[str, Any]:
    """Give a newborn a stable starting CA/PA influenced by the parents."""
    person = (state.get("people") or {}).get(str(int(relationship.get("person_id") or 0))) or {}
    profile = state.get("profile") if isinstance(state.get("profile"), dict) else {}
    parent_ca = max(1, int(person.get("ca") or profile.get("ca") or 30))
    parent_pa = max(parent_ca + 20, int(person.get("pa") or profile.get("pa") or 100))
    ca = 14 + int(_unit(child.get("id"), "birth-ca") * 13) + int(parent_ca * 0.5)
    pa = 72 + int(_unit(child.get("id"), "birth-pa") * 28) + int(parent_pa * 0.5)
    child["ca"] = max(10, min(120, ca))
    child["pa"] = max(child["ca"] + 18, min(199, pa))
    return child


def training_options(child: dict[str, Any], age: int) -> list[dict[str, Any]]:
    """Return 3–5 deterministic football-path choices for one age milestone."""
    ids = list(CHILD_TRAINING_OPTIONS)
    # Balanced upbringing is always available; rotate the other paths so each
    # child gets a different but stable menu.
    rotating = [key for key in ids if key != "balanced"]
    offset = int(_unit(child.get("id"), "training", age) * len(rotating))
    count = 2 + int(_unit(child.get("id"), "training-count", age) * 3)
    selected = [rotating[(offset + index) % len(rotating)] for index in range(count)]
    selected.append("balanced")
    rows = []
    for key in selected:
        spec = CHILD_TRAINING_OPTIONS[key]
        rows.append({
            "id": key,
            "position": str(spec["position"]),
            "ca": int(spec["ca"]),
            "pa": int(spec["pa"]),
            "name_zh": str(spec["name_zh"]),
            "name_en": str(spec["name_en"]),
        })
    return rows


def training_event_day(child: dict[str, Any], milestone: int) -> int:
    born = int(child.get("born_day") or 0)
    if born <= 0:
        return 0
    # Growth events unlock when the child reaches the age, so the card can
    # offer the event immediately instead of hiding it for weeks.
    return born + int(milestone) * CHILD_AGE_DAYS


def training_due(child: dict[str, Any], day: int) -> int:
    """Return the football milestone age due, or 0 when nothing is due."""
    age = child_age(child, day)
    if age >= CHILD_ADULT_AGE:
        return 0
    completed = {int(value) for value in (child.get("training_milestones") or [])}
    for milestone in CHILD_TRAINING_AGES:
        # A growth event belongs to the exact age band. If the child is aged
        # past it with elixirs before it is resolved, it is a missed event and
        # cannot be re-rolled later.
        if (
            age == milestone
            and milestone not in completed
            and int(day) >= training_event_day(child, milestone)
        ):
            return milestone
    return 0


def apply_training(
    child: dict[str, Any], option_id: str, day: int, *, milestone: int = 0,
) -> dict[str, Any]:
    spec = CHILD_TRAINING_OPTIONS.get(str(option_id or ""))
    if spec is None:
        raise ValueError("足球培养方向无效")
    age = child_age(child, day)
    target = int(milestone or training_due(child, day) or age)
    if age >= CHILD_ADULT_AGE:
        raise ValueError("孩子已经成年，不能再进行童年培养")
    ca_before = int(child.get("ca") or CHILD_START_CA)
    pa_before = int(child.get("pa") or CHILD_START_PA)
    ca = max(1, min(CHILD_MAX_CA, ca_before + int(spec["ca"])))
    pa = max(ca, min(CHILD_MAX_CA, pa_before + int(spec["pa"])))
    child["ca"] = ca
    child["pa"] = pa
    if spec.get("position"):
        child["football_position"] = str(spec["position"])
    child.setdefault("training_milestones", []).append(int(target))
    child["training_milestones"] = sorted({
        int(value) for value in child["training_milestones"]
    })[-12:]
    child.setdefault("training_history", []).append({
        "age": int(target), "option": str(option_id),
        "position": str(spec.get("position") or ""),
        "ca": ca, "pa": pa, "day": int(day),
    })
    child["training_history"] = child["training_history"][-20:]
    return {
        "option": str(option_id), "age": int(target),
        "ca": ca, "pa": pa, "ca_gain": ca - ca_before, "pa_gain": pa - pa_before,
        "position": str(spec.get("position") or ""),
    }


def apply_neglect_penalty(
    child: dict[str, Any], milestone: int, day: int,
) -> dict[str, Any]:
    """Apply a one-time penalty when a milestone was missed by over a year."""
    completed = {int(value) for value in (child.get("training_milestones") or [])}
    neglected = {int(value) for value in (child.get("neglected_milestones") or [])}
    if milestone in completed or milestone in neglected:
        return {}
    ca_before = int(child.get("ca") or CHILD_START_CA)
    pa_before = int(child.get("pa") or CHILD_START_PA)
    child["ca"] = max(1, ca_before - 4)
    child["pa"] = max(child["ca"], pa_before - 6)
    neglected.add(int(milestone))
    child["neglected_milestones"] = sorted(neglected)[-12:]
    return {
        "milestone": int(milestone), "age": int(milestone),
        "ca": child["ca"], "pa": child["pa"],
        "ca_change": child["ca"] - ca_before, "pa_change": child["pa"] - pa_before,
    }


def apply_elixir_years(
    child: dict[str, Any], years: int, day: int, *, source: str = "inventory",
) -> dict[str, Any]:
    """Advance a child by one or more years without crossing the adult cap."""
    count = max(0, int(years or 0))
    if count <= 0:
        raise ValueError("丹药数量无效")
    current = child_age(child, day)
    if current >= CHILD_ADULT_AGE:
        raise ValueError("孩子已经成年，不能继续使用成长仙丹")
    allowed = max(0, CHILD_ADULT_AGE - current)
    if count > allowed:
        raise ValueError(f"最多只能再使用 {allowed} 颗成长仙丹")
    child["born_day"] = int(child["born_day"]) - count * CHILD_AGE_DAYS
    child["growth_source"] = CHILD_SOURCE_ELIXIR
    child.setdefault("elixirs_used", []).append({
        "tier": "growth_elixir", "day": int(day),
        "age_after": child_age(child, day), "price": 0.0,
        "quantity": count, "source": str(source),
    })
    child["elixirs_used"] = child["elixirs_used"][-40:]
    return {"child": child, "age": child_age(child, day), "years": count}


def placement_label(child: dict[str, Any]) -> str:
    placement = child.get("placement") or {}
    status = str(placement.get("status") or "")
    if not status:
        return ""
    return status


def child_academy_plan_config(child: dict[str, Any], surname: str) -> dict[str, Any]:
    """Build the native ``academy_son`` config from a named child.

    The configured value is the generated player's given name; the native
    writer combines it with the manager's surname.  The accepted grammar
    follows ``youth_intake.ACADEMY_SON_NAME_PATTERN`` (letters, including CJK
    letters); the older reference build used a narrower ASCII-only pattern.
    ``preserve_ca`` keeps the youth intake player's native CA and only applies
    the child's PA band and position.
    """
    name = str(child.get("given_name") or child.get("name") or "").strip()
    given = name[:30] if name else "Junior"
    position = str(
        child.get("preferred_position") or child.get("football_position") or ""
    ).upper()
    # The native academy plan accepts preset PA bands only.  Pick the band
    # containing the child's current potential so development events and
    # neglect penalties reach the generated youth player.
    target_pa = max(80, min(200, int(child.get("pa") or CHILD_START_PA)))
    bands = ((110, 140), (120, 150), (130, 160), (140, 170),
             (150, 180), (160, 190), (170, 200))
    band = next((row for row in bands if row[0] <= target_pa <= row[1]), bands[0])
    config: dict[str, Any] = {
        "count": 1, "name": given, "preserve_ca": True,
        "min_pa": band[0], "max_pa": band[1],
    }
    if position:
        config["primary_position"] = position
    return config


def _ascii_given_name(name: str) -> str:
    cleaned = "".join(char for char in str(name or "") if char.isascii() and char.isalpha())
    if len(cleaned) >= 2:
        return cleaned[:30]
    surrogate = " ".join(str(name or "")).encode("ascii", "ignore").decode("ascii")
    surrogate = "".join(char for char in surrogate if char.isalpha())
    if len(surrogate) >= 2:
        return surrogate[:30]
    return "Junior"


def apply_child_placement_plan(
    child: dict[str, Any], day: int, *, team_id: int, team_name: str,
    mode: str, status: str = "armed", message: str = "",
) -> dict[str, Any]:
    placement = {
        "status": status if status in CHILD_PLACEMENT_STATUSES else "pending",
        "team_id": int(team_id), "team_name": str(team_name)[:120],
        "mode": "recommend" if str(mode) == "recommend" else "own",
        "armed_day": int(day), "applied_day": 0, "player_id": 0,
        "message": str(message)[:400],
    }
    child["placement"] = placement
    return placement


def set_child_avatar(
    child: dict[str, Any], data: str, extension: str, day: int,
) -> dict[str, Any]:
    payload = str(data or "").strip()
    if not payload:
        raise ValueError("请选择头像文件")
    if payload.startswith("data:"):
        try:
            payload = payload.split(",", 1)[1]
        except IndexError:
            raise ValueError("头像数据无效") from None
    if len(payload) > 3_000_000:
        raise ValueError("头像文件过大，请选择 2 MB 以内的图片")
    suffix = str(extension or "png").lower().lstrip(".")
    if suffix == "jpeg":
        suffix = "jpg"
    if suffix not in {"png", "jpg", "webp"}:
        raise ValueError("头像只支持 PNG、JPG 或 WebP")
    child["avatar"] = {
        "data": payload, "extension": suffix, "updated_day": int(day),
        "synced_uid": 0, "synced_at": "", "error": "",
    }
    return child["avatar"]


def sync_child_avatar(
    child: dict[str, Any], graphics_root: Path | str, day: int,
) -> bool:
    import base64
    from tools.player_portraits import write_player_portrait
    avatar = child.get("avatar") if isinstance(child.get("avatar"), dict) else {}
    placement = child.get("placement") if isinstance(child.get("placement"), dict) else {}
    uid = int(placement.get("player_id") or 0)
    data = str(avatar.get("data") or "")
    if not data or uid <= 0 or int(avatar.get("synced_uid") or 0) == uid:
        return False
    try:
        write_player_portrait(
            graphics_root, uid, base64.b64decode(data), str(avatar.get("extension") or "png"),
        )
    except Exception as error:
        avatar["error"] = str(error)[:200]
        child["avatar"] = avatar
        return True
    avatar.update({
        "synced_uid": uid, "synced_at": str(day), "error": "",
    })
    child["avatar"] = avatar
    return True


def can_start_trial(child: dict[str, Any], day: int) -> bool:
    age = child_age(child, day)
    placement = child.get("placement") if isinstance(child.get("placement"), dict) else {}
    status = str(placement.get("status") or "")
    if age < CHILD_ADULT_TRANSFER_AGE:
        return False
    if status in {"training", "trial", "trial_passed", "armed", "applied", "playing"}:
        return False
    if status == "rejected" and int(day) < int(placement.get("trial_day") or 0) + 90:
        return False
    return True


def start_academy_trial(
    child: dict[str, Any], day: int, *, team_id: int, team_name: str,
    club_level: int = 3,
) -> dict[str, Any]:
    """Give the child a youth trial instead of an instant academy decision."""
    age = child_age(child, day)
    if age < CHILD_ADULT_TRANSFER_AGE:
        raise ValueError("孩子满 15 岁后才能参加青训试训")
    if not can_start_trial(child, day):
        raise ValueError("当前不能再次试训，请等待或先完成现有培养")
    level = max(1, min(5, int(club_level or 3)))
    ca = max(1, int(child.get("ca") or CHILD_START_CA))
    pa = max(ca, int(child.get("pa") or CHILD_START_PA))
    # Lower-level clubs give more room to a high-potential child; elite clubs
    # demand a stronger current level.  The roll keeps repeated trials varied.
    score = ca * 0.45 + pa * 0.35 + (6 - level) * 4 + int(
        _unit(child.get("id"), "trial", day, team_id) * 16
    )
    required = 42 + level * 8
    success = score >= required
    placement = {
        "status": "trial_passed" if success else "rejected",
        "team_id": int(team_id or 0), "team_name": str(team_name or "")[:120],
        "mode": "trial", "armed_day": int(day), "applied_day": int(day) if success else 0,
        "player_id": 0, "trial_day": int(day), "trial_score": int(score),
        "club_level": level,
        "message": (
            f"试训通过，进入 {team_name} 青训营。" if success
            else f"试训未通过（评分 {score}/{required}），90 天后可再试。"
        ),
    }
    child["placement"] = placement
    child["academy"] = {
        "status": placement["status"], "team_id": placement["team_id"],
        "team_name": placement["team_name"], "trial_score": score,
        "required_score": required, "club_level": level, "trial_day": int(day),
    }
    return placement


def eligibility(child: dict[str, Any], day: int) -> dict[str, Any]:
    age = child_age(child, day)
    status = str((child.get("placement") or {}).get("status") or "")
    # A rejected/refunded placement is retryable; an armed or completed one is not.
    placed = bool(status) and status not in {
        "rejected", "cancelled", "trial_passed", "training",
    }
    return {
        "age": age,
        "ready": age >= CHILD_ADULT_TRANSFER_AGE and not placed and not child.get("retired"),
        "trial_available": can_start_trial(child, day) and not child.get("retired"),
        "adult_age": CHILD_ADULT_TRANSFER_AGE,
        "placed": placed,
    }


def day_from_game_date(game_date: str | None) -> int:
    value = str(game_date or "").strip()
    if value:
        try:
            return date.fromisoformat(value[:10]).toordinal()
        except ValueError:
            return 0
    return 0
