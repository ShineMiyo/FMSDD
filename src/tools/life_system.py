"""Save-scoped life assets for FMSDD.

The module owns the life document (property, garages, vehicles, mystery garage
counters and the vehicle collection). It never moves money: the HTTP facade
charges or credits the existing ODD bank and calls the commit helpers here, so
there is still one wallet and one ledger.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
from copy import deepcopy
from datetime import date, datetime
from functools import lru_cache
from types import MappingProxyType
from pathlib import Path
from typing import Any

from tools.account_store import load_document, save_document
from tools.app_paths import ASSET_ROOT, DATA_ROOT
from tools.money import round_money
from tools.storage_io import atomic_write_json, storage_lock


DOCUMENT = "life_system"
SCHEMA_VERSION = 9

LIFE_ASSET_ROOT = ASSET_ROOT / "assets" / "life"
PACK_ROOT = DATA_ROOT / "life_packs"
LAYER_ROOT = PACK_ROOT / "layers"
_LOCK = threading.RLock()
_CITY_PACK_CACHE_LOCK = threading.RLock()
_CITY_PACK_CACHE: dict[str, tuple[tuple[int, int], dict[str, Any]]] = {}

BUY_FEE_RATE = 0.025
SELL_FEE_RATE = 0.030
VEHICLE_DAILY_DECAY = 0.0005
VEHICLE_MIN_VALUE_RATIO = 0.45
MAX_ACTIVITY = 80
STORAGE_RENT_RATE = 0.01
MAX_STORAGE_RENT_HISTORY = 120

KINDS = ("residential", "commercial", "industrial")
PARCEL_KINDS = (*KINDS, "garage")
MAP_LAYER_ZOOMS = {
    "world": (3, 5),
    "country": (6, 9),
    "city": (10, 12),
    "parcel": (13, 15),
}
KIND_LABEL_ZH = {
    "residential": "住宅", "commercial": "商业", "industrial": "工业", "garage": "车库",
}
KIND_LABEL_EN = {
    "residential": "Residential", "commercial": "Commercial", "industrial": "Industrial",
    "garage": "Parking",
}
AREA_RANGES = {
    "residential": (70, 190), "commercial": (120, 540), "industrial": (1200, 5200),
    "garage": (320, 1100),
}
RENT_NET_YIELD = {"residential": 0.031, "commercial": 0.046, "industrial": 0.039}
OPERATE_NET_YIELD = {"residential": 0.026, "commercial": 0.058, "industrial": 0.062}
PARKING_CAPACITY_BY_KIND = {"residential": 1, "commercial": 2, "industrial": 4}
GARAGE_RENT_YIELD = 0.049
MAX_PROPERTY_LEVEL = 5
PROPERTY_LEVEL_RENT_BONUS = 0.20
PROPERTY_LEVEL_OPERATE_BONUS = 0.18
PROPERTY_UPGRADE_RATE = {"residential": 0.042, "commercial": 0.058, "industrial": 0.065}
CITY_TIER_INCOME_FACTOR = {1: 1.18, 2: 1.0, 3: 0.88, 4: 0.78}
BUSINESS_CATALOG = {
    "commercial": (
        {"id": "retail", "name_zh": "精品零售", "name_en": "Boutique retail", "multiplier": 1.00, "wage_factor": 1.00},
        {"id": "dining", "name_zh": "餐饮服务", "name_en": "Dining", "multiplier": 1.12, "wage_factor": 1.12},
        {"id": "office", "name_zh": "商务办公", "name_en": "Office", "multiplier": 1.06, "wage_factor": 1.08},
        {"id": "leisure", "name_zh": "文化娱乐", "name_en": "Leisure", "multiplier": 1.18, "wage_factor": 1.10},
        {"id": "hotel", "name_zh": "精品酒店", "name_en": "Boutique hotel", "multiplier": 1.24, "wage_factor": 1.18},
    ),
    "industrial": (
        {"id": "light_manufacturing", "name_zh": "轻工制造", "name_en": "Light manufacturing", "multiplier": 1.00, "wage_factor": 1.00},
        {"id": "electronics", "name_zh": "电子信息", "name_en": "Electronics", "multiplier": 1.17, "wage_factor": 1.13},
        {"id": "automotive", "name_zh": "汽车零部件", "name_en": "Automotive components", "multiplier": 1.12, "wage_factor": 1.10},
        {"id": "food_processing", "name_zh": "食品加工", "name_en": "Food processing", "multiplier": 0.96, "wage_factor": 0.92},
        {"id": "logistics", "name_zh": "物流仓储", "name_en": "Logistics", "multiplier": 1.08, "wage_factor": 0.98},
    ),
}
PROPERTY_MODE_LABELS = {
    "self": {"name_zh": "自用", "name_en": "Owner use"},
    "rent": {"name_zh": "出租", "name_en": "Lease"},
    "operate": {"name_zh": "经营", "name_en": "Operate"},
}
INITIAL_GARAGE = {
    "id": "club", "kind": "club", "capacity": 2,
    "name_zh": "俱乐部车库", "name_en": "Club garage",
    "purchase_price": 0, "acquired_day": None,
}
STORAGE_GARAGE = {
    "id": "storage", "kind": "storage", "category": "storage", "capacity": 10000,
    "name_zh": "寄存车库", "name_en": "Storage garage",
    "purchase_price": 0, "acquired_day": None, "system": True,
}

CITY_PACK_VERSION = "2.4"
CITY_PROFILE_PATH = LIFE_ASSET_ROOT / "city_profiles.json"
CITY_PROFILE_EXTRA_PATH = LIFE_ASSET_ROOT / "city_profiles_extra.json"
CITY_TERRAIN_PATH = LIFE_ASSET_ROOT / "city_terrain.json"
CITY_EXTRA_PATH = LIFE_ASSET_ROOT / "cities_extra_cn.json"
CITY_GLOBAL_PATH = LIFE_ASSET_ROOT / "cities_global.json"

LEASE_TERM_DAYS = (30, 90, 180, 365)
LEASE_DEPOSIT_MONTHS = 1.5
BUSINESS_SETUP_RATE = {"commercial": 0.018, "industrial": 0.024}
CONSTRUCTION_KINDS = ("business_setup", "upgrade")
DISTRICT_ROLE_COUNTS = {
    "core": {"residential": 4, "commercial": 7, "industrial": 0, "garage": 2},
    "business": {"residential": 5, "commercial": 8, "industrial": 1, "garage": 2},
    "residential": {"residential": 10, "commercial": 4, "industrial": 0, "garage": 2},
    "industrial": {"residential": 4, "commercial": 3, "industrial": 8, "garage": 2},
    "scenic": {"residential": 5, "commercial": 6, "industrial": 0, "garage": 1},
    "suburb": {"residential": 8, "commercial": 3, "industrial": 5, "garage": 2},
    "mixed": {"residential": 6, "commercial": 5, "industrial": 3, "garage": 2},
}
CITY_TYPE_MODIFIERS = {
    "capital": {"residential": 1, "commercial": 1},
    "finance": {"commercial": 2, "industrial": -1},
    "tech": {"residential": 1, "commercial": 2, "industrial": -1},
    "industrial": {"residential": -1, "industrial": 3},
    "port": {"commercial": 1, "industrial": 2},
    "culture": {"residential": 1, "commercial": 1},
    "tourism": {"residential": 2, "commercial": 1, "industrial": -2, "garage": 1},
}
DISTRICT_RADIUS_KM = {
    "core": (0.7, 3.2),
    "business": (0.9, 4.2),
    "residential": (1.1, 6.5),
    "industrial": (4.0, 12.0),
    "scenic": (1.0, 5.0),
    "suburb": (2.5, 11.0),
    "mixed": (1.0, 5.5),
}

GACHA_TIERS = (
    {
        "id": "street", "classes": ("D", "C", "B", "A"),
        "rarities": ("common", "rare", "epic"), "pity": 60,
        "ticket_price": 500_000, "ten_ticket_price": 4_000_000,
        "soft_pity_start": 45, "soft_pity_step": 0.08, "soft_pity_cap": 2.4,
    },
    {
        "id": "performance", "classes": ("C", "B", "A", "S1"),
        "rarities": ("common", "rare", "epic", "legendary"), "pity": 60,
        "ticket_price": 5_000_000, "ten_ticket_price": 45_000_000,
        "soft_pity_start": 45, "soft_pity_step": 0.10, "soft_pity_cap": 2.8,
    },
    {
        "id": "collector", "classes": ("A", "S1", "S2"),
        "rarities": ("rare", "epic", "legendary", "forza edition", "donut edition"),
        "pity": 80, "ticket_price": 20_000_000, "ten_ticket_price": 150_000_000,
        "soft_pity_start": 60, "soft_pity_step": 0.12, "soft_pity_cap": 3.2,
    },
)
GACHA_PROFILES = {
    "street": {
        "class_weights": {"D": 45, "C": 33, "B": 19, "A": 3},
        "rarity_weights": {"common": 65, "rare": 27, "epic": 8},
        "gold_weight_multiplier": 1.8,
    },
    "performance": {
        "class_weights": {"C": 94.241367, "B": 100.0, "A": 50.392284, "S1": 5.329283},
        "rarity_weights": {"common": 9.343356, "rare": 30.596356, "epic": 100.0, "legendary": 8.716902},
        "gold_weight_multiplier": 2.0,
    },
    "collector": {
        "class_weights": {"A": 100.0, "S1": 32.478713, "S2": 76.491592},
        "rarity_weights": {
            "rare": 16.066315, "epic": 97.947804, "legendary": 6.755766,
            "forza edition": 2.420447, "donut edition": 100.0,
        },
        "gold_weight_multiplier": 2.2,
    },
}
CLASS_ORDER = {"D": 0, "C": 1, "B": 2, "A": 3, "S1": 4, "S2": 5}
RARITY_ORDER = {
    "common": 0, "rare": 1, "epic": 2, "legendary": 3,
    "forza edition": 4, "donut edition": 5,
}
PITY_CLASS = {"street": "A", "performance": "S1", "collector": "S2"}
GOLD_RULES = {
    "street": {"class": "A", "rarities": ("epic",)},
    "performance": {"class": "S1", "rarities": ("legendary",)},
    "collector": {
        "class": "S2", "rarities": ("legendary", "forza edition"),
        "any_class_rarities": ("donut edition",),
    },
}
GACHA_STATS_VERSION = 1
GACHA_LUCK_PRIOR_PULLS = 120.0
GACHA_LUCK_MIN_TRACKED_PULLS = 20

# Vehicle prices are deliberately driven by rarity first and class second.
# The old market price is used only as a stable ordering key inside each
# rarity/class band, so collector cars keep their relative cachet without
# leaving legendary cars at ordinary hatchback prices.
CAR_CLASS_PRICE_BANDS = {
    "D": (180_000, 520_000),
    "C": (280_000, 800_000),
    "B": (460_000, 1_400_000),
    "A": (1_000_000, 3_600_000),
    "S1": (2_600_000, 8_500_000),
    "S2": (6_500_000, 20_000_000),
}
RARITY_PRICE_MULTIPLIERS = {
    "common": 0.85,
    "rare": 1.25,
    "epic": 2.4,
    "legendary": 12.0,
    "forza edition": 21.0,
    "donut edition": 18.0,
}
RARITY_PRICE_FLOORS = {
    "common": 18_000,
    "rare": 90_000,
    "epic": 350_000,
    "legendary": 5_000_000,
    "forza edition": 15_000_000,
    "donut edition": 15_000_000,
}
DEALER_DISPLAY_ONLY_RARITIES = {"legendary", "forza edition", "donut edition"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _city_catalog_cached() -> dict[str, Any]:
    base = _read_json(LIFE_ASSET_ROOT / "cities.json")
    extra = _read_json(CITY_EXTRA_PATH)
    global_payload = _read_json(CITY_GLOBAL_PATH)
    if (
        not isinstance(base, dict) or not isinstance(base.get("cities"), list)
        or not isinstance(extra, dict) or not isinstance(extra.get("cities"), list)
        or not isinstance(global_payload, dict) or not isinstance(global_payload.get("countries"), list)
    ):
        raise RuntimeError("生活系统城市目录格式无效")
    cn_code = str(base.get("country") or "CN").upper()
    countries = [{
        "code": cn_code,
        "name_zh": str(base.get("country_name_zh") or "中国"),
        "name_en": str(base.get("country_name_en") or "China"),
        "region": "Asia",
        "cities": [*(base.get("cities") or []), *(extra.get("cities") or [])],
    }]
    for country in global_payload.get("countries") or []:
        if isinstance(country, dict) and isinstance(country.get("cities"), list):
            countries.append(deepcopy(country))
    cities: list[dict[str, Any]] = []
    seen: set[str] = set()
    for country in countries:
        code = str(country.get("code") or "").upper()
        for city in country.get("cities") or []:
            if not isinstance(city, dict):
                continue
            city_id = str(city.get("id") or "").strip()
            if not city_id or city_id in seen:
                continue
            seen.add(city_id)
            enriched = deepcopy(city)
            enriched["country"] = code
            enriched["country_name_zh"] = str(country.get("name_zh") or "")
            enriched["country_name_en"] = str(country.get("name_en") or "")
            cities.append(enriched)
    payload = deepcopy(base)
    payload["cities"] = cities
    payload["countries"] = countries
    return payload


@lru_cache(maxsize=1)
def _car_catalog_cached() -> dict[str, Any]:
    payload = deepcopy(_read_json(LIFE_ASSET_ROOT / "cars.json"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cars"), list):
        raise RuntimeError("生活系统车辆目录格式无效")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for car in payload["cars"]:
        if not isinstance(car, dict):
            continue
        source_price = float(car.get("source_price") or car.get("price") or 0)
        car["source_price"] = int(round(source_price))
        key = (str(car.get("class") or "D"), str(car.get("rarity") or "common"))
        groups.setdefault(key, []).append(car)
    for rows in groups.values():
        rows.sort(key=lambda car: (
            float(car.get("source_price") or 0),
            float(car.get("pi") or 0),
            int(car.get("year") or 0),
            str(car.get("catalog_id") or ""),
        ))
        denominator = max(1, len(rows) - 1)
        for index, car in enumerate(rows):
            position = 0.5 if len(rows) == 1 else index / denominator
            car_class = str(car.get("class") or "D")
            rarity = str(car.get("rarity") or "common").lower()
            low, high = CAR_CLASS_PRICE_BANDS.get(car_class, CAR_CLASS_PRICE_BANDS["D"])
            multiplier = RARITY_PRICE_MULTIPLIERS.get(rarity, 1.0)
            price = max(
                float(RARITY_PRICE_FLOORS.get(rarity, 0)),
                (low + (high - low) * position) * multiplier,
            )
            car["price"] = max(1_000, int(round(price / 1_000.0)) * 1_000)
            car["dealer_status"] = (
                "display_only" if rarity in DEALER_DISPLAY_ONLY_RARITIES else "available"
            )
    payload["schema_version"] = max(2, int(payload.get("schema_version") or 1))
    payload["pricing_model"] = "rarity-class-v2"
    return payload


@lru_cache(maxsize=1)
def _car_catalog_index_cached() -> dict[str, dict[str, Any]]:
    return {
        str(car.get("catalog_id") or ""): car
        for car in _car_catalog_cached()["cars"]
        if str(car.get("catalog_id") or "")
    }


@lru_cache(maxsize=1)
def _city_profiles_cached() -> dict[str, Any]:
    payload = _read_json(CITY_PROFILE_PATH)
    if not isinstance(payload, dict) or not isinstance(payload.get("cities"), dict):
        raise RuntimeError("生活系统城市画像格式无效")
    extra = _read_json(CITY_PROFILE_EXTRA_PATH)
    if not isinstance(extra, dict) or not isinstance(extra.get("cities"), dict):
        raise RuntimeError("生活系统扩展城市画像格式无效")
    payload = deepcopy(payload)
    payload["cities"].update(deepcopy(extra["cities"]))
    return payload


@lru_cache(maxsize=1)
def _city_terrain_cached() -> dict[str, Any]:
    """Load the offline OSM-derived terrain mask used by the plot generator.

    The file is optional so development builds and older installations still
    work.  Circular exclusions in the city profiles remain the compatibility
    fallback when a city has no terrain polygons.
    """
    try:
        payload = _read_json(CITY_TERRAIN_PATH)
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "cities": {}}
    if not isinstance(payload, dict) or not isinstance(payload.get("cities"), dict):
        raise RuntimeError("生活系统城市地形数据格式无效")
    return payload


@lru_cache(maxsize=1)
def _country_catalogs_cached() -> tuple[dict[str, Any], ...]:
    catalog = _city_catalog_cached()
    result: list[dict[str, Any]] = []
    for country in catalog.get("countries") or []:
        if not isinstance(country, dict):
            continue
        code = str(country.get("code") or "").upper()
        cities = [city for city in catalog.get("cities") or [] if str(city.get("country") or "") == code]
        lat = sum(float(city.get("lat") or 0) for city in cities) / max(1, len(cities))
        lng = sum(float(city.get("lng") or 0) for city in cities) / max(1, len(cities))
        result.append({
            "code": code,
            "name_zh": str(country.get("name_zh") or ""),
            "name_en": str(country.get("name_en") or ""),
            "region": str(country.get("region") or ""),
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "cities": deepcopy(cities),
        })
    return tuple(result)


def clear_catalog_cache() -> None:
    _city_catalog_cached.cache_clear()
    _car_catalog_cached.cache_clear()
    _car_catalog_index_cached.cache_clear()
    _city_profiles_cached.cache_clear()
    _city_terrain_cached.cache_clear()
    _country_catalogs_cached.cache_clear()


def city_catalog() -> dict[str, Any]:
    return deepcopy(_city_catalog_cached())


def car_catalog() -> dict[str, Any]:
    return deepcopy(_car_catalog_cached())


def city_by_id(city_id: str) -> dict[str, Any] | None:
    target = str(city_id or "").strip()
    for city in _city_catalog_cached()["cities"]:
        if str(city.get("id") or "") == target:
            return deepcopy(city)
    return None


def car_by_id(catalog_id: str) -> dict[str, Any] | None:
    target = str(catalog_id or "").strip()
    for car in _car_catalog_cached()["cars"]:
        if str(car.get("catalog_id") or "") == target:
            return deepcopy(car)
    return None

def _hash_unit(*parts: Any) -> float:
    raw = "|".join(str(part) for part in parts).encode("utf-8")
    number = int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")
    return number / float(0xFFFFFFFFFFFFFFFF)


def _kind_area(city_id: str, district_id: str, kind: str, index: int) -> int:
    low, high = AREA_RANGES[kind]
    unit = _hash_unit(city_id, district_id, kind, index, "area")
    return int(round(low + (high - low) * unit))


_CITY_PROFILE_VIEW_CACHE: dict[tuple[str, int], dict[str, Any]] = {}
_CITY_PROFILE_VIEW_LOCK = threading.RLock()


def _city_profile(city_id: str) -> dict[str, Any]:
    """Return a read-only-usable city profile.

    Callers only read this payload, and the large batch planners used to deep
    copy the profile (including terrain polygons) hundreds of times, which
    dominated bulk purchase time.  A frozen payload is cached per city and
    re-frozen only when the shared ``MappingProxyType`` read fails.
    """
    key = str(city_id)
    signature = (id(_city_profiles_cached()), id(_city_terrain_cached()))
    cached = _CITY_PROFILE_VIEW_CACHE.get((key, signature))
    if cached is not None:
        return cached
    with _CITY_PROFILE_VIEW_LOCK:
        profile = (_city_profiles_cached().get("cities") or {}).get(key)
        result = dict(profile) if isinstance(profile, dict) else {}
        areas = (_city_terrain_cached().get("cities") or {}).get(key)
        result["terrain_areas"] = areas if isinstance(areas, list) else []
        frozen = MappingProxyType(result)
        _CITY_PROFILE_VIEW_CACHE[(key, signature)] = frozen
        return frozen


def _haversine_m(lat_a: float, lng_a: float, lat_b: float, lng_b: float) -> float:
    radius = 6_371_000.0
    phi_a = math.radians(lat_a)
    phi_b = math.radians(lat_b)
    delta_phi = math.radians(lat_b - lat_a)
    delta_lambda = math.radians(lng_b - lng_a)
    hav = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi_a) * math.cos(phi_b) * math.sin(delta_lambda / 2.0) ** 2
    )
    return radius * 2.0 * math.atan2(math.sqrt(hav), math.sqrt(max(0.0, 1.0 - hav)))


def _project_local_m(lat: float, lng: float, origin_lat: float, origin_lng: float) -> tuple[float, float]:
    x = (float(lng) - float(origin_lng)) * 111_320.0 * max(0.2, math.cos(math.radians(origin_lat)))
    y = (float(lat) - float(origin_lat)) * 111_320.0
    return x, y


def _point_in_ring(x: float, y: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    if len(ring) < 3:
        return False
    previous = ring[-1]
    for current in ring:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            crossing = (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-9) + x1
            if x < crossing:
                inside = not inside
        previous = current
    return inside


def _segment_distance_m(x: float, y: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx = x2 - x1
    dy = y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-9:
        return math.hypot(x - x1, y - y1)
    ratio = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / length_sq))
    return math.hypot(x - (x1 + ratio * dx), y - (y1 + ratio * dy))


def _terrain_parts(area: dict[str, Any]) -> list[dict[str, Any]]:
    """Return polygon parts, supporting old single-ring terrain rows."""
    parts = area.get("parts")
    if isinstance(parts, list) and parts:
        return [part for part in parts if isinstance(part, dict)]
    ring = area.get("ring")
    if isinstance(ring, list):
        return [{"ring": ring, "holes": area.get("holes") or []}]
    return []


def _ring_distance_m(
    ring_rows: list[list[float] | tuple[float, float]], lat: float, lng: float,
    origin_lat: float, origin_lng: float,
) -> tuple[float, bool]:
    ring = [
        _project_local_m(float(point[0]), float(point[1]), origin_lat, origin_lng)
        for point in ring_rows
    ]
    x, y = _project_local_m(lat, lng, origin_lat, origin_lng)
    distance = min(
        _segment_distance_m(
            x, y, ring[index - 1][0], ring[index - 1][1], ring[index][0], ring[index][1],
        )
        for index in range(len(ring))
    )
    return distance, _point_in_ring(x, y, ring)


def _terrain_part_distance_m(
    ring_rows: list[list[float] | tuple[float, float]],
    hole_rows: list[list[list[float] | tuple[float, float]]],
    lat: float, lng: float,
) -> float:
    """Return signed distance to one polygon part, respecting land holes."""
    if len(ring_rows) < 3:
        return float("inf")
    lats = [float(point[0]) for point in ring_rows]
    lngs = [float(point[1]) for point in ring_rows]
    origin_lat = (min(lats) + max(lats)) / 2.0
    origin_lng = (min(lngs) + max(lngs)) / 2.0
    distance, inside = _ring_distance_m(ring_rows, lat, lng, origin_lat, origin_lng)
    if not inside:
        return distance
    hole_distances: list[float] = []
    for hole in hole_rows:
        if len(hole) < 3:
            continue
        hole_distance, inside_hole = _ring_distance_m(hole, lat, lng, origin_lat, origin_lng)
        if inside_hole:
            # A point inside a hole is on land, not in the surrounding water.
            return hole_distance
        hole_distances.append(hole_distance)
    if hole_distances:
        return -min(distance, min(hole_distances))
    return -distance


def _terrain_area_distance_m(area: dict[str, Any], lat: float, lng: float) -> float:
    """Return a signed distance to one water/green polygon in metres."""
    parts = _terrain_parts(area)
    bbox = area.get("bbox") or []
    if len(bbox) != 4 or not parts:
        return float("inf")
    min_lat, min_lng, max_lat, max_lng = (float(value) for value in bbox)
    if lat < min_lat or lat > max_lat or lng < min_lng or lng > max_lng:
        # The caller also uses this value to reject points near an edge, so a
        # cheap bbox distance is enough to avoid loading the full ring.
        nearest_lat = min(max(lat, min_lat), max_lat)
        nearest_lng = min(max(lng, min_lng), max_lng)
        return _haversine_m(lat, lng, nearest_lat, nearest_lng)
    return min(
        _terrain_part_distance_m(
            part.get("ring") or [],
            part.get("holes") or [],
            lat, lng,
        )
        for part in parts
    )


def _excluded_distance_m(
    profile: dict[str, Any], lat: float, lng: float, *,
    parcel_radius_m: float = 0.0, include_green: bool = True,
) -> float:
    """Return clearance from circular exclusions and offline terrain polygons.

    A non-negative value means the plot centre and its configured clearance
    radius are outside every protected zone.  Terrain rings come from the
    bundled OSM-derived mask; the original circular exclusions remain a
    compatibility fallback for profiles without polygon data.
    """
    clearances = []
    for zone in profile.get("exclusions") or []:
        if not isinstance(zone, dict):
            continue
        distance = _haversine_m(
            lat, lng, float(zone.get("lat") or 0), float(zone.get("lng") or 0),
        )
        clearances.append(distance - float(zone.get("radius_m") or 0) - float(parcel_radius_m))
    for area in profile.get("terrain_areas") or []:
        if not isinstance(area, dict):
            continue
        kind = str(area.get("kind") or "")
        if kind == "green" and not include_green:
            continue
        if kind not in {"water", "green"}:
            continue
        edge_clearance = 20.0 if kind == "water" else 15.0
        distance = _terrain_area_distance_m(area, lat, lng)
        clearances.append(distance - edge_clearance - float(parcel_radius_m))
    return min(clearances) if clearances else float("inf")


def _plot_suffix(index: int) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    cycle, offset = divmod(max(0, int(index)), len(alphabet))
    return alphabet[offset] if cycle == 0 else f"{alphabet[offset]}{cycle + 1}"


def _parcel_counts(
    city: dict[str, Any], profile: dict[str, Any], district_id: str,
) -> dict[str, int]:
    roles = profile.get("districts") if isinstance(profile.get("districts"), dict) else {}
    role = str(roles.get(district_id) or "mixed")
    base = DISTRICT_ROLE_COUNTS.get(role, DISTRICT_ROLE_COUNTS["mixed"])
    counts = {kind: int(base.get(kind) or 0) for kind in PARCEL_KINDS}
    if int(profile.get("tier") or 2) <= 1:
        counts["residential"] += 1
        counts["commercial"] += 1
        counts["garage"] += 1
    modifiers = CITY_TYPE_MODIFIERS.get(str(profile.get("city_type") or ""), {})
    for kind, delta in modifiers.items():
        if kind in counts:
            counts[kind] += int(delta)
    if role in {"core", "scenic"}:
        counts["industrial"] = 0
    if role == "business":
        counts["industrial"] = min(counts["industrial"], 1)
    for kind in PARCEL_KINDS:
        counts[kind] = max(0, counts[kind])
    return counts


def _candidate_point(
    city: dict[str, Any], profile: dict[str, Any], district: dict[str, Any],
    role: str, kind: str, index: int,
) -> tuple[float, float] | None:
    city_id = str(city["id"])
    district_id = str(district["id"])
    low_km, high_km = DISTRICT_RADIUS_KM.get(role, DISTRICT_RADIUS_KM["mixed"])
    parcel_radius = max(8.0, math.sqrt(float(_kind_area(city_id, district_id, kind, index))) * 0.5)

    def legal(lat: float, lng: float) -> bool:
        if kind == "industrial":
            center_distance = _haversine_m(
                lat, lng, float(city["lat"]), float(city["lng"]),
            )
            buffer_m = float(profile.get("industrial_buffer_m") or 2_800)
            if center_distance < buffer_m:
                return False
        return _excluded_distance_m(
            profile, lat, lng,
            parcel_radius_m=parcel_radius,
            include_green=True,
        ) >= 0

    for attempt in range(320):
        radial = _hash_unit(city_id, district_id, kind, index, "radius", attempt)
        if kind != "industrial":
            radial = radial ** 1.35
        elif role in {"industrial", "suburb"}:
            radial = 0.55 + radial * 0.45
        angle = _hash_unit(city_id, district_id, kind, index, "angle", attempt) * math.tau
        distance_km = low_km + (high_km - low_km) * radial
        lat = float(district["lat"]) + math.sin(angle) * distance_km / 111.0
        lng = float(district["lng"]) + math.cos(angle) * distance_km / (
            111.0 * max(0.2, math.cos(math.radians(float(district["lat"]))))
        )
        if legal(lat, lng):
            return round(lat, 6), round(lng, 6)

    # Deterministic spiral fallback.  It searches the whole district rather
    # than returning the least-bad illegal point (which previously placed
    # plots in rivers or parks).
    for radial_step in range(1, 13):
        radial = radial_step / 12.0
        if kind == "industrial" and role in {"industrial", "suburb"}:
            radial = 0.55 + radial * 0.45
        distance_km = low_km + (high_km - low_km) * radial
        for angle_step in range(32):
            angle = math.tau * angle_step / 32.0
            lat = float(district["lat"]) + math.sin(angle) * distance_km / 111.0
            lng = float(district["lng"]) + math.cos(angle) * distance_km / (
                111.0 * max(0.2, math.cos(math.radians(float(district["lat"]))))
            )
            if legal(lat, lng):
                return round(lat, 6), round(lng, 6)
    return None


def generate_city_pack(city: dict[str, Any]) -> dict[str, Any]:
    """Build one deterministic on-demand city data pack."""
    city_id = str(city["id"])
    profile = _city_profile(city_id)
    roles = profile.get("districts") if isinstance(profile.get("districts"), dict) else {}
    parcels: list[dict[str, Any]] = []
    skipped_parcels = 0
    for district in city.get("districts") or []:
        role = str(roles.get(str(district["id"])) or "mixed")
        counts = _parcel_counts(city, profile, str(district["id"]))
        for kind in PARCEL_KINDS:
            for index in range(counts.get(kind, 0)):
                area_sqm = _kind_area(city_id, str(district["id"]), kind, index)
                parking_spaces = (
                    int(PARKING_CAPACITY_BY_KIND.get(kind) or 0)
                    if kind != "garage" else 0
                )
                if kind == "garage":
                    choices = (8, 12, 16, 24, 32, 40, 64, 96, 128)
                    if role in {"core", "business", "scenic"}:
                        choices = (8, 12, 16, 24, 32, 48, 64)
                    else:
                        choices = (8, 12, 16, 24, 40, 64, 96, 128)
                    premium = (
                        role in {"suburb", "industrial", "mixed"}
                        and _hash_unit(city_id, district["id"], kind, index, "premium") >= 0.82
                    )
                    if premium:
                        choices = (64, 96, 128)
                    unit = _hash_unit(city_id, district["id"], kind, index, "spaces")
                    # Bias toward smaller lots; premium outer-district plots
                    # can roll the new 64/96/128-space garages.
                    if not premium:
                        unit = unit ** 1.45
                    parking_spaces = choices[min(len(choices) - 1, int(unit * len(choices)))]
                    area_sqm = max(area_sqm, parking_spaces * 32)
                unit_price = (
                    int(round(float(district["commercial"]) * 0.68 + float(district["industrial"]) * 0.25))
                    if kind == "garage"
                    else int(district[kind])
                )
                base_price = int(round(unit_price * area_sqm))
                suffix = _plot_suffix(index)
                point = _candidate_point(city, profile, district, role, kind, index)
                if point is None:
                    skipped_parcels += 1
                    continue
                lat, lng = point
                monthly_rent = round_money(
                    base_price
                    * (GARAGE_RENT_YIELD if kind == "garage" else RENT_NET_YIELD[kind])
                    / 12.0
                )
                monthly_operating_net = (
                    0.0 if kind == "garage"
                    else round_money(base_price * OPERATE_NET_YIELD[kind] / 12.0)
                )
                parcel = {
                    "id": f"{city_id}:{district['id']}:{kind}:{index}",
                    "city_id": city_id,
                    "city_name_zh": str(city["name_zh"]),
                    "city_name_en": str(city["name_en"]),
                    "district_id": str(district["id"]),
                    "district_name_zh": str(district["name_zh"]),
                    "district_name_en": str(district["name_en"]),
                    "kind": kind,
                    "name_zh": f"{district['name_zh']}{KIND_LABEL_ZH[kind]}地块 {suffix}",
                    "name_en": f"{district['name_en']} {KIND_LABEL_EN[kind]} Plot {suffix}",
                    "lat": round(lat, 6),
                    "lng": round(lng, 6),
                    "area_sqm": area_sqm,
                    "unit_price": unit_price,
                    "base_price": base_price,
                    "monthly_rent": monthly_rent,
                    "monthly_operating_net": monthly_operating_net,
                    "district_role": role,
                }
                parcel["parking_spaces"] = parking_spaces
                parcel["garage_capacity_tier"] = (
                    "large" if parking_spaces >= 64
                    else "medium" if parking_spaces >= 24
                    else "standard"
                ) if kind == "garage" else ""
                parcels.append(parcel)
    body = {
        "schema_version": 1,
        "version": CITY_PACK_VERSION,
        "country": str(city.get("country") or "CN").upper(),
        "country_name_zh": str(city.get("country_name_zh") or ""),
        "country_name_en": str(city.get("country_name_en") or ""),
        "city_id": city_id,
        "city_name_zh": str(city["name_zh"]),
        "city_name_en": str(city["name_en"]),
        "city_type": str(profile.get("city_type") or "mixed"),
        "city_tier": int(profile.get("tier") or 2),
        "lat": float(city["lat"]),
        "lng": float(city["lng"]),
        "districts": deepcopy(city.get("districts") or []),
        "parcels": parcels,
        "skipped_parcels": skipped_parcels,
        "terrain": "OpenStreetMap ODbL, simplified offline mask",
    }
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    body["checksum"] = hashlib.sha256(encoded).hexdigest()
    return body


def _layer_checksum(body: dict[str, Any]) -> str:
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def country_catalogs() -> list[dict[str, Any]]:
    return [deepcopy(country) for country in _country_catalogs_cached()]


def _country_catalog(country_code: str = "CN") -> dict[str, Any]:
    target = str(country_code or "CN").upper()
    countries = _country_catalogs_cached()
    for country in countries:
        if str(country.get("code") or "").upper() == target:
            return deepcopy(country)
    if countries:
        return deepcopy(countries[0])
    return {"code": target, "name_zh": "", "name_en": "", "lat": 0.0, "lng": 0.0, "cities": []}


def generate_world_layer_pack() -> dict[str, Any]:
    countries = _country_catalogs_cached()
    body = {
        "schema_version": 1,
        "version": "1.1",
        "layer": "world",
        "countries": [{
            "id": country["code"],
            "name_zh": country["name_zh"],
            "name_en": country["name_en"],
            "region": country.get("region") or "",
            "lat": country["lat"],
            "lng": country["lng"],
            "city_count": len(country["cities"]),
            "district_count": sum(len(city.get("districts") or []) for city in country["cities"]),
        } for country in countries],
    }
    body["checksum"] = _layer_checksum(body)
    return body


def generate_country_layer_pack(country_code: str = "CN") -> dict[str, Any]:
    target = str(country_code or "CN").upper()
    country = _country_catalog(target)
    if target != str(country.get("code") or "").upper():
        raise ValueError("国家不存在")
    body = {
        "schema_version": 1,
        "version": "1.1",
        "layer": "country",
        "country": country["code"],
        "country_name_zh": country["name_zh"],
        "country_name_en": country["name_en"],
        "cities": [{
            "id": str(city["id"]),
            "name_zh": str(city["name_zh"]),
            "name_en": str(city["name_en"]),
            "region": str(city.get("region") or ""),
            "lat": float(city["lat"]),
            "lng": float(city["lng"]),
            "district_count": len(city.get("districts") or []),
        } for city in country["cities"]],
    }
    body["checksum"] = _layer_checksum(body)
    return body


def generate_city_layer_pack(city_id: str) -> dict[str, Any]:
    city = city_by_id(city_id)
    if city is None:
        raise ValueError("城市不存在")
    country = _country_catalog(str(city.get("country") or "CN"))
    body = {
        "schema_version": 1,
        "version": "1.0",
        "layer": "city",
        "country": country["code"],
        "city_id": str(city["id"]),
        "city_name_zh": str(city["name_zh"]),
        "city_name_en": str(city["name_en"]),
        "lat": float(city["lat"]),
        "lng": float(city["lng"]),
        "districts": deepcopy(city.get("districts") or []),
    }
    body["checksum"] = _layer_checksum(body)
    return body


def _layer_pack_path(
    layer: str, city_id: str | None = None, country_code: str | None = None,
) -> Path:
    if layer == "world":
        return LAYER_ROOT / "world.json"
    if layer == "country":
        code = str(country_code or "CN").lower()
        return LAYER_ROOT / f"{code}.json"
    if layer == "city":
        target = str(city_id or "").strip()
        if not target:
            raise ValueError("缺少城市")
        city = city_by_id(target)
        if city is None:
            raise ValueError("城市不存在")
        code = str(city.get("country") or country_code or "CN").lower()
        return LAYER_ROOT / code / f"{target}.json"
    raise ValueError("地图层不存在")


def install_layer_pack(
    layer: str, city_id: str | None = None, country_code: str | None = None,
) -> dict[str, Any]:
    target = str(layer or "").strip().lower()
    if target == "world":
        payload = generate_world_layer_pack()
    elif target == "country":
        payload = generate_country_layer_pack(str(country_code or "CN"))
    elif target == "city":
        payload = generate_city_layer_pack(str(city_id or ""))
        country_code = str(payload.get("country") or country_code or "CN")
    else:
        raise ValueError("地图层不存在")
    path = _layer_pack_path(target, city_id, country_code)
    path.parent.mkdir(parents=True, exist_ok=True)
    with storage_lock(path):
        atomic_write_json(path, payload, indent=2)
    # A city-layer download is the player's request to make that city usable.
    # Keep the plot pack in sync so the next z13-15 view cannot end up with a
    # downloaded city layer but an uninstalled parcel layer.
    if target == "city":
        install_city_pack(str(city_id or payload.get("city_id") or ""))
    return layer_pack_summary(target, city_id, country_code)


def layer_pack_summary(
    layer: str, city_id: str | None = None, country_code: str | None = None,
) -> dict[str, Any]:
    target = str(layer or "").strip().lower()
    try:
        path = _layer_pack_path(target, city_id, country_code)
    except ValueError:
        return {"layer": target, "installed": False, "size_bytes": 0, "checksum": "", "version": "1.0"}
    installed = path.is_file()
    size = 0
    checksum = ""
    if installed:
        try:
            payload = _read_json(path)
            if payload.get("layer") != target:
                installed = False
            else:
                checksum = str(payload.get("checksum") or "")
                size = path.stat().st_size
        except (OSError, json.JSONDecodeError, TypeError, AttributeError):
            installed = False
    return {
        "layer": target,
        "city_id": str(city_id or ""),
        "country": str(country_code or "CN").upper() if target == "country" else str((city_by_id(str(city_id or "")) or {}).get("country") or ""),
        "installed": installed,
        "size_bytes": size,
        "checksum": checksum,
        "version": "1.0",
    }


def layer_pack_summaries() -> dict[str, Any]:
    return {
        "world": layer_pack_summary("world"),
        "country": layer_pack_summary("country"),
        "countries": {
            str(country["code"]): layer_pack_summary("country", country_code=str(country["code"]))
            for country in _country_catalogs_cached()
        },
        "cities": {
            str(city["id"]): layer_pack_summary("city", str(city["id"]))
            for city in _city_catalog_cached()["cities"]
        },
    }


def _location_label(value: Any) -> str:
    return "".join(str(value or "").casefold().split())


def _resolve_property_district(
    city_id: str, record: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    """Resolve a saved property to its canonical district.

    Older records did not persist ``district_id`` and some purchases created a
    separate map node for every plot.  The parcel id is deterministic and keeps
    the district before the first colon, so it is the primary compatibility
    key; names are only a fallback for imported/legacy records.
    """
    city = city_by_id(city_id) or {}
    districts = [row for row in city.get("districts") or [] if isinstance(row, dict)]
    by_id = {str(row.get("id") or ""): row for row in districts}
    candidate = str(record.get("district_id") or "").strip()
    if candidate in by_id:
        return candidate, by_id[candidate]
    parcel_parts = str(record.get("parcel_id") or "").split(":")
    if len(parcel_parts) >= 2 and parcel_parts[0] == str(city_id):
        parcel_district = parcel_parts[1]
        if parcel_district in by_id:
            return parcel_district, by_id[parcel_district]
    names = {
        _location_label(record.get("district_name_zh")),
        _location_label(record.get("district_name_en")),
    }
    names.discard("")
    for district in districts:
        if names & {
            _location_label(district.get("name_zh")),
            _location_label(district.get("name_en")),
        }:
            return str(district.get("id") or ""), district
    return "", None


def property_aggregates(properties: list[dict[str, Any]]) -> dict[str, Any]:
    countries = _country_catalogs_cached()
    country_nodes_by_code: dict[str, list[dict[str, Any]]] = {}
    city_layers: dict[str, list[dict[str, Any]]] = {}
    world_nodes: list[dict[str, Any]] = []
    for country in countries:
        code = str(country.get("code") or "").upper()
        cities = country.get("cities") or []
        city_ids = {str(city.get("id") or "") for city in cities}
        country_properties = [
            item for item in properties
            if isinstance(item, dict) and str(item.get("city_id") or "") in city_ids
        ]
        country_nodes: list[dict[str, Any]] = []
        for city in cities:
            city_id = str(city["id"])
            city_properties = [
                item for item in country_properties
                if str(item.get("city_id") or "") == city_id
            ]
            country_nodes.append({
                "id": city_id, "country": code,
                "name_zh": str(city["name_zh"]), "name_en": str(city["name_en"]),
                "region": str(city.get("region") or ""),
                "lat": float(city["lat"]), "lng": float(city["lng"]),
                "asset_count": len(city_properties),
                "asset_value": round_money(sum(
                    float(item.get("book_value", item.get("market_value")) or 0)
                    for item in city_properties
                )),
            })
            districts = [row for row in city.get("districts") or [] if isinstance(row, dict)]
            district_by_id = {str(row.get("id") or ""): row for row in districts}
            buckets: dict[str, dict[str, Any]] = {}
            for item in city_properties:
                district_id, _district = _resolve_property_district(city_id, item)
                key = district_id or f"{city_id}:other"
                bucket = buckets.setdefault(key, {
                    "count": 0, "value": 0.0, "lat": 0.0, "lng": 0.0,
                })
                bucket["count"] += 1
                bucket["value"] += float(item.get("book_value", item.get("market_value")) or 0)
                bucket["lat"] += float(item.get("lat") or city["lat"])
                bucket["lng"] += float(item.get("lng") or city["lng"])
            district_nodes: list[dict[str, Any]] = []
            for district_id, district in district_by_id.items():
                bucket = buckets.get(district_id)
                if not bucket or bucket["count"] <= 0:
                    continue
                district_nodes.append({
                    "id": district_id, "city_id": city_id,
                    "name_zh": str(district["name_zh"]), "name_en": str(district["name_en"]),
                    "lat": float(district["lat"]), "lng": float(district["lng"]),
                    "asset_count": int(bucket["count"]),
                    "asset_value": round_money(bucket["value"]),
                })
            other = buckets.get(f"{city_id}:other")
            if other and other["count"] > 0:
                district_nodes.append({
                    "id": f"{city_id}:other", "city_id": city_id,
                    "name_zh": "其他区域", "name_en": "Other areas",
                    "lat": other["lat"] / other["count"],
                    "lng": other["lng"] / other["count"],
                    "asset_count": int(other["count"]),
                    "asset_value": round_money(other["value"]),
                })
            city_layers[city_id] = district_nodes
        country_nodes_by_code[code] = country_nodes
        world_nodes.append({
            "id": code, "name_zh": country["name_zh"], "name_en": country["name_en"],
            "lat": country["lat"], "lng": country["lng"], "city_count": len(cities),
            "asset_count": len(country_properties),
            "asset_value": round_money(sum(
                float(item.get("book_value", item.get("market_value")) or 0)
                for item in country_properties
            )),
        })
    return {
        "world": world_nodes,
        "country": country_nodes_by_code.get("CN", []),
        "countries": country_nodes_by_code,
        "cities": city_layers,
    }


def _pack_path(city_id: str) -> Path:
    city = city_by_id(str(city_id))
    country_code = str((city or {}).get("country") or "CN").lower()
    return PACK_ROOT / country_code / f"{city_id}.json"


def pack_summary(city: dict[str, Any]) -> dict[str, Any]:
    path = _pack_path(str(city["id"]))
    installed = path.is_file()
    size = path.stat().st_size if installed else 0
    checksum = ""
    parcels = 0
    if installed:
        payload = load_city_pack(str(city["id"]))
        if payload is None:
            installed = False
            size = 0
        else:
            checksum = str(payload.get("checksum") or "")
            parcels = len(payload.get("parcels") or [])
    return {
        "city_id": str(city["id"]),
        "country": str(city.get("country") or "CN").upper(),
        "country_name_zh": str(city.get("country_name_zh") or ""),
        "country_name_en": str(city.get("country_name_en") or ""),
        "name_zh": str(city["name_zh"]),
        "name_en": str(city["name_en"]),
        "region": str(city.get("region") or ""),
        "lat": float(city["lat"]),
        "lng": float(city["lng"]),
        "installed": installed,
        "size_bytes": size,
        "checksum": checksum,
        "parcels": parcels,
        "version": CITY_PACK_VERSION,
    }


def city_packs() -> list[dict[str, Any]]:
    return [pack_summary(city) for city in _city_catalog_cached()["cities"]]


def install_city_pack(city_id: str) -> dict[str, Any]:
    city = city_by_id(city_id)
    if city is None:
        raise ValueError("城市不存在")
    path = _pack_path(str(city["id"]))
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        with storage_lock(path):
            atomic_write_json(path, generate_city_pack(city), indent=2)
        with _CITY_PACK_CACHE_LOCK:
            _CITY_PACK_CACHE.pop(str(path), None)
    layer_path = _layer_pack_path("city", str(city["id"]))
    if not layer_path.is_file():
        layer_path.parent.mkdir(parents=True, exist_ok=True)
        with storage_lock(layer_path):
            atomic_write_json(layer_path, generate_city_layer_pack(str(city["id"])), indent=2)
    load_city_pack(str(city["id"]))
    return pack_summary(city)


def repair_installed_city_layer_parcels() -> list[str]:
    """Upgrade city layers downloaded before parcel packs were linked.

    Earlier builds wrote only ``layers/<country>/<city>.json`` for the city
    layer.  The parcel layer then looked uninstalled at z13-15 even though the
    player had already downloaded the city.  Rebuild the deterministic parcel
    pack for any installed city layer that lacks one.
    """
    repaired: list[str] = []
    for city in _city_catalog_cached()["cities"]:
        city_id = str(city.get("id") or "")
        if not city_id or _pack_path(city_id).is_file():
            continue
        if layer_pack_summary("city", city_id).get("installed"):
            install_city_pack(city_id)
            repaired.append(city_id)
    return repaired


def load_city_pack(city_id: str) -> dict[str, Any] | None:
    path = _pack_path(str(city_id))
    try:
        stat = path.stat()
    except OSError:
        with _CITY_PACK_CACHE_LOCK:
            _CITY_PACK_CACHE.pop(str(path), None)
        return None
    signature = (int(stat.st_mtime_ns), int(stat.st_size))
    with _CITY_PACK_CACHE_LOCK:
        cached = _CITY_PACK_CACHE.get(str(path))
        if cached is not None and cached[0] == signature:
            return cached[1]
    try:
        payload = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("parcels"), list):
        return None
    if str(payload.get("version") or "") != CITY_PACK_VERSION:
        city = city_by_id(str(city_id))
        if city is None:
            return None
        payload = generate_city_pack(city)
        with storage_lock(path):
            atomic_write_json(path, payload, indent=2)
        try:
            stat = path.stat()
            signature = (int(stat.st_mtime_ns), int(stat.st_size))
        except OSError:
            signature = (0, 0)
    with _CITY_PACK_CACHE_LOCK:
        _CITY_PACK_CACHE[str(path)] = (signature, payload)
        while len(_CITY_PACK_CACHE) > 64:
            _CITY_PACK_CACHE.pop(next(iter(_CITY_PACK_CACHE)))
    return payload


def installed_packs() -> list[dict[str, Any]]:
    result = []
    for summary in city_packs():
        if not summary["installed"]:
            continue
        pack = load_city_pack(summary["city_id"])
        if pack is not None:
            result.append(pack)
    return result


def parcel_index() -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    index: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for pack in installed_packs():
        for parcel in pack.get("parcels") or []:
            if isinstance(parcel, dict):
                index[str(parcel.get("id") or "")] = (pack, parcel)
    return index


def parcel_parking_spaces(parcel: dict[str, Any]) -> int:
    """Return parking capacity for legacy and newly generated parcel rows."""
    kind = str(parcel.get("kind") or "")
    stored = int(parcel.get("parking_spaces") or 0)
    if stored > 0:
        return stored
    if kind == "garage":
        return max(1, int(round(float(parcel.get("area_sqm") or 0) / 110.0)))
    return max(0, int(PARKING_CAPACITY_BY_KIND.get(kind) or 0))


def parcel_entry(
    parcel_id: str, city_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Resolve one parcel directly from its city pack when the caller knows it.

    The full parcel index stays as the compatibility path for older callers,
    but a purchase no longer has to parse every installed city pack.
    """
    target_city = str(city_id or "").strip()
    if target_city:
        pack = load_city_pack(target_city)
        if pack is None:
            return None
        for parcel in pack.get("parcels") or []:
            if isinstance(parcel, dict) and str(parcel.get("id") or "") == str(parcel_id):
                return pack, parcel
        return None
    return parcel_index().get(str(parcel_id))


def _apply_parcel_snapshot(record: dict[str, Any], parcel: dict[str, Any]) -> None:
    """Refresh only geography-derived fields on an owned property.

    A rebuilt city pack can move a plot when the water/green mask changes. The
    purchase price, lease, construction state, staffing, upgrades and accrued
    income belong to the player and must survive that refresh unchanged.
    """
    record["parcel_id"] = str(parcel["id"])
    record["city_id"] = str(parcel["city_id"])
    record["city_name_zh"] = str(parcel.get("city_name_zh") or record.get("city_name_zh") or "")
    record["city_name_en"] = str(parcel.get("city_name_en") or record.get("city_name_en") or "")
    record["district_id"] = str(parcel.get("district_id") or "")
    record["district_name_zh"] = str(parcel.get("district_name_zh") or "")
    record["district_name_en"] = str(parcel.get("district_name_en") or "")
    record["kind"] = str(parcel.get("kind") or record.get("kind") or "residential")
    record["name_zh"] = str(parcel.get("name_zh") or record.get("name_zh") or "")
    record["name_en"] = str(parcel.get("name_en") or record.get("name_en") or "")
    record["lat"] = float(parcel.get("lat") or 0)
    record["lng"] = float(parcel.get("lng") or 0)
    record["area_sqm"] = int(parcel.get("area_sqm") or record.get("area_sqm") or 0)
    record["base_price"] = int(parcel.get("base_price") or record.get("base_price") or 0)
    record["monthly_rent"] = float(parcel.get("monthly_rent") or 0)
    record["monthly_operating_net"] = float(parcel.get("monthly_operating_net") or 0)
    record["parking_spaces"] = int(parcel.get("parking_spaces") or 0)
    record["garage_capacity_tier"] = str(parcel.get("garage_capacity_tier") or "")
    if str(record.get("kind") or "") == "garage":
        record["garage_monthly_rent"] = float(record["monthly_rent"])
    record["parcel_snapshot_version"] = CITY_PACK_VERSION


def _property_coordinate_is_legal(record: dict[str, Any]) -> bool:
    try:
        lat = float(record.get("lat"))
        lng = float(record.get("lng"))
        area_sqm = max(0.0, float(record.get("area_sqm") or 0))
    except (TypeError, ValueError):
        return False
    city_id = str(record.get("city_id") or "")
    if not city_id:
        return False
    profile = _city_profile(city_id)
    parcel_radius = max(8.0, math.sqrt(area_sqm) * 0.5)
    return _excluded_distance_m(
        profile, lat, lng, parcel_radius_m=parcel_radius, include_green=True,
    ) >= 0


def _nearest_replacement_parcel(
    pack: dict[str, Any], record: dict[str, Any], claimed: set[str],
) -> dict[str, Any] | None:
    kind = str(record.get("kind") or "")
    district_id = str(record.get("district_id") or "")
    rows = [
        parcel for parcel in pack.get("parcels") or []
        if isinstance(parcel, dict)
        and str(parcel.get("kind") or "") == kind
        and str(parcel.get("district_id") or "") == district_id
    ]
    if not rows:
        rows = [
            parcel for parcel in pack.get("parcels") or []
            if isinstance(parcel, dict) and str(parcel.get("kind") or "") == kind
        ]
    if not rows:
        return None
    available = [parcel for parcel in rows if str(parcel.get("id") or "") not in claimed]
    if available:
        rows = available
    try:
        old_lat = float(record.get("lat"))
        old_lng = float(record.get("lng"))
    except (TypeError, ValueError):
        return rows[0]
    return min(
        rows,
        key=lambda parcel: _haversine_m(
            old_lat, old_lng, float(parcel.get("lat") or 0), float(parcel.get("lng") or 0),
        ),
    )


def _sync_property_parcel_snapshot(
    state: dict[str, Any], asset_id: str, record: dict[str, Any], claimed: set[str],
) -> None:
    if str(record.get("parcel_snapshot_version") or "") == CITY_PACK_VERSION:
        return
    city_id = str(record.get("city_id") or "")
    if not city_id:
        return
    entry = parcel_entry(str(record.get("parcel_id") or ""), city_id)
    parcel = entry[1] if entry is not None else None
    pack = entry[0] if entry is not None else load_city_pack(city_id)
    if pack is None:
        return
    if parcel is None:
        if _property_coordinate_is_legal(record):
            record["parcel_snapshot_version"] = CITY_PACK_VERSION
            return
        parcel = _nearest_replacement_parcel(pack, record, claimed)
        if parcel is None:
            return
    old_parcel_id = str(record.get("parcel_id") or "")
    _apply_parcel_snapshot(record, parcel)
    if old_parcel_id != str(record["parcel_id"]):
        claimed.discard(old_parcel_id)
        claimed.add(str(record["parcel_id"]))
    garage_id = str(record.get("garage_id") or "")
    garage = state.get("garages", {}).get(garage_id) if garage_id else None
    if isinstance(garage, dict) and str(garage.get("property_id") or "") == str(asset_id):
        garage["city_id"] = record["city_id"]
        garage["district_name_zh"] = record["district_name_zh"]
        garage["district_name_en"] = record["district_name_en"]
        garage["lat"] = record["lat"]
        garage["lng"] = record["lng"]
        garage["name_zh"] = f"{record['name_zh']}停车场"
        garage["name_en"] = f"{record['name_en']} Parking"


def day_ordinal(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10]).toordinal()
    except ValueError:
        return None


def _market_factor(city_id: str, kind: str, day: int) -> float:
    seed = _hash_unit(city_id, kind, "market")
    phase = day + int(seed * 100000)
    wave = math.sin(phase / 19.0 + seed * 4.0) * 0.045
    texture = math.sin(phase / 5.7 + seed * 13.0) * 0.018
    return max(0.82, min(1.18, 1.0 + wave + texture))


def parcel_quote(parcel: dict[str, Any], day: int) -> int:
    base = float(parcel.get("base_price") or 0)
    factor = _market_factor(str(parcel.get("city_id") or ""), str(parcel.get("kind") or ""), day)
    return int(round_money(base * factor))

def business_catalog() -> dict[str, Any]:
    return {
        "commercial": deepcopy(BUSINESS_CATALOG["commercial"]),
        "industrial": deepcopy(BUSINESS_CATALOG["industrial"]),
        "modes": deepcopy(PROPERTY_MODE_LABELS),
    }


def _business_definition(kind: str, business_type: str) -> dict[str, Any] | None:
    for row in BUSINESS_CATALOG.get(str(kind or "")) or ():
        if str(row.get("id") or "") == str(business_type or ""):
            return deepcopy(row)
    return None


def _employee_policy(kind: str, level: int) -> dict[str, int]:
    resolved_level = max(1, min(MAX_PROPERTY_LEVEL, int(level or 1)))
    if kind == "commercial":
        optimal = 2 + resolved_level * 2
    elif kind == "industrial":
        optimal = 4 + resolved_level * 3
    else:
        return {"min": 0, "optimal": 0, "max": 0}
    minimum = max(1, int(round(optimal * 0.25)))
    maximum = max(minimum + 1, int(round(optimal * 1.8)))
    return {"min": minimum, "optimal": optimal, "max": maximum}


def _city_tier_for_record(record: dict[str, Any]) -> int:
    stored = int(record.get("city_tier") or 0)
    if stored:
        return stored
    city = city_by_id(str(record.get("city_id") or ""))
    return int((_city_profile(str((city or {}).get("id") or "")) or {}).get("tier") or 2)


def _property_level(record: dict[str, Any]) -> int:
    return max(1, min(MAX_PROPERTY_LEVEL, int(record.get("level") or 1)))


def _level_income_multiplier(kind: str, level: int, mode: str) -> float:
    rate = PROPERTY_LEVEL_OPERATE_BONUS if mode == "operate" else PROPERTY_LEVEL_RENT_BONUS
    return 1.0 + rate * (max(1, int(level or 1)) - 1)


def _construction_active(record: dict[str, Any]) -> bool:
    construction = record.get("construction")
    return isinstance(construction, dict) and str(construction.get("kind") or "") in CONSTRUCTION_KINDS


def _lease_active(record: dict[str, Any], day: int | None = None) -> bool:
    if str(record.get("tenure") or "owned") != "lease":
        return True
    lease = record.get("lease") if isinstance(record.get("lease"), dict) else {}
    if str(lease.get("status") or "active") != "active":
        return False
    end_day = int(lease.get("end_day") or 0)
    return day is None or end_day <= 0 or int(day) <= end_day


def property_income_breakdown(record: dict[str, Any], as_of_day: int | None = None) -> dict[str, Any]:
    kind = str(record.get("kind") or "residential")
    mode = str(record.get("mode") or "rent")
    if mode == "parking":
        mode = "self"
    level = _property_level(record)
    policy = _employee_policy(kind, level)
    employees = max(0, min(policy["max"], int(record.get("employees") or 0))) if policy["max"] else 0
    tier = _city_tier_for_record(record)
    tier_factor = float(CITY_TIER_INCOME_FACTOR.get(tier, 0.9))
    level_factor = _level_income_multiplier(kind, level, mode)
    business = _business_definition(kind, str(record.get("business_type") or ""))
    business_factor = float((business or {}).get("multiplier") or 1.0)
    staffing_factor = 0.0
    monthly_gross = 0.0
    monthly_payroll = 0.0
    if mode == "rent":
        monthly_base = (
            float(record.get("garage_monthly_rent") or record.get("monthly_rent") or 0)
            if kind == "garage"
            else float(record.get("monthly_rent") or 0)
        )
        monthly_gross = monthly_base * level_factor
    elif mode == "operate" and kind in BUSINESS_CATALOG:
        monthly_base = float(record.get("monthly_operating_net") or 0)
        if employees > 0 and policy["optimal"] > 0:
            staffing_factor = 0.35 + 0.65 * min(1.0, employees / policy["optimal"])
            if employees > policy["optimal"]:
                over = (employees - policy["optimal"]) / max(1, policy["max"] - policy["optimal"])
                staffing_factor = max(0.55, staffing_factor - 0.12 * over)
            monthly_gross = monthly_base * business_factor * tier_factor * level_factor * 1.35 * staffing_factor
            monthly_payroll = monthly_base * 0.22 * (employees / policy["optimal"]) * float((business or {}).get("wage_factor") or 1.0)
    monthly_income = max(0.0, monthly_gross - monthly_payroll)
    paused_reason = ""
    if _construction_active(record):
        paused_reason = "construction"
    elif not _lease_active(record, as_of_day):
        paused_reason = "lease_expired"
    if paused_reason:
        monthly_gross = 0.0
        monthly_payroll = 0.0
        monthly_income = 0.0
    return {
        "mode": mode,
        "level": level,
        "city_tier": tier,
        "tier_factor": tier_factor,
        "level_factor": level_factor,
        "business_type": str((business or {}).get("id") or ""),
        "business_name_zh": str((business or {}).get("name_zh") or ""),
        "business_name_en": str((business or {}).get("name_en") or ""),
        "business_factor": business_factor,
        "employees": employees,
        "employee_min": policy["min"],
        "employee_optimal": policy["optimal"],
        "employee_max": policy["max"],
        "staffing_factor": round(staffing_factor, 4),
        "monthly_gross": round_money(monthly_gross),
        "monthly_payroll": round_money(monthly_payroll),
        "monthly_income": round_money(monthly_income),
        "daily_income": round_money(monthly_income * 12.0 / 365.0),
        "paused_reason": paused_reason,
        "construction": _construction_active(record),
        "lease_active": _lease_active(record, as_of_day),
    }


def _daily_income(asset: dict[str, Any], day: int | None = None) -> float:
    return float(property_income_breakdown(asset, as_of_day=day)["daily_income"])


def _income_start_day(state: dict[str, Any], record: dict[str, Any]) -> int:
    return max(
        int(record.get("acquired_day") or 0),
        int(record.get("income_since_day") or state.get("income_settled_day") or record.get("acquired_day") or 0),
    )


def _close_income_segment(state: dict[str, Any], record: dict[str, Any], day: int) -> float:
    start = _income_start_day(state, record)
    elapsed = max(0, int(day) - start)
    amount = round_money(_daily_income(record, day) * elapsed)
    record["accrued_income"] = round_money(float(record.get("accrued_income") or 0) + amount)
    record["accrued_days"] = int(record.get("accrued_days") or 0) + elapsed
    record["income_since_day"] = int(day)
    record["daily_income"] = _daily_income(record, day)
    record["monthly_income"] = float(property_income_breakdown(record, as_of_day=day)["monthly_income"])
    return amount


def _record_pending_income(state: dict[str, Any], record: dict[str, Any], day: int) -> dict[str, Any]:
    start = _income_start_day(state, record)
    current_days = max(0, int(day) - start)
    current = round_money(_daily_income(record, day) * current_days)
    amount = round_money(float(record.get("accrued_income") or 0) + current)
    return {
        "days": int(record.get("accrued_days") or 0) + current_days,
        "daily": _daily_income(record, day),
        "amount": amount,
    }


def property_upgrade_cost(record: dict[str, Any]) -> float:
    level = _property_level(record)
    if level >= MAX_PROPERTY_LEVEL or str(record.get("kind") or "") == "garage":
        return 0.0
    reference = max(float(record.get("purchase_price") or 0), float(record.get("base_price") or 0))
    rate = float(PROPERTY_UPGRADE_RATE.get(str(record.get("kind") or ""), 0.05))
    return round_money(reference * rate * (1.55 ** (level - 1)))


def property_upgrade_duration_days(record: dict[str, Any]) -> int:
    kind = str(record.get("kind") or "residential")
    base = {"residential": 4, "commercial": 6, "industrial": 8}.get(kind, 5)
    level = _property_level(record)
    return max(3, min(30, base + (level - 1) * 2))


def property_business_setup_cost(record: dict[str, Any], business_type: str) -> float:
    kind = str(record.get("kind") or "")
    business = _business_definition(kind, business_type)
    if business is None or kind not in BUSINESS_CATALOG:
        return 0.0
    reference = max(float(record.get("purchase_price") or 0), float(record.get("base_price") or 0))
    rate = float(BUSINESS_SETUP_RATE.get(kind, 0.02))
    multiplier = 1.0 + max(0.0, float(business.get("multiplier") or 1.0) - 1.0) * 0.45
    return round_money(reference * rate * multiplier * (1.0 + (_property_level(record) - 1) * 0.18))


def property_business_setup_days(record: dict[str, Any], business_type: str) -> int:
    kind = str(record.get("kind") or "")
    business = _business_definition(kind, business_type)
    if business is None or kind not in BUSINESS_CATALOG:
        return 0
    base = 4 if kind == "commercial" else 6
    complexity = max(0.0, float(business.get("multiplier") or 1.0) - 0.9)
    return max(3, min(14, int(round(base + complexity * 8.0 + (_property_level(record) - 1) * 1.2))))


def property_business_quotes(record: dict[str, Any]) -> list[dict[str, Any]]:
    kind = str(record.get("kind") or "")
    rows = []
    for business in BUSINESS_CATALOG.get(kind) or ():
        rows.append({
            "id": str(business["id"]),
            "cost": property_business_setup_cost(record, str(business["id"])),
            "days": property_business_setup_days(record, str(business["id"])),
        })
    return rows


def lease_quote(parcel: dict[str, Any], days: int) -> dict[str, Any]:
    term = int(days or 0)
    if term not in LEASE_TERM_DAYS:
        raise ValueError("租期无效")
    monthly = max(
        0.0,
        float(parcel.get("monthly_rent") or 0)
        or round_money(float(parcel.get("base_price") or 0) * RENT_NET_YIELD["residential"] / 12.0),
    )
    prepaid = round_money(monthly * term / 30.0)
    deposit = round_money(monthly * LEASE_DEPOSIT_MONTHS)
    return {
        "days": term,
        "monthly_rent": round_money(monthly),
        "prepaid_rent": prepaid,
        "deposit": deposit,
        "total": round_money(prepaid + deposit),
    }


def lease_options(parcel: dict[str, Any]) -> list[dict[str, Any]]:
    return [lease_quote(parcel, days) for days in LEASE_TERM_DAYS]


def _collection_empty() -> dict[str, Any]:
    return {
        "updated_at": _now(),
        "cars": {},
        "total_acquired": 0,
    }


def _empty_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "updated_at": _now(),
        "seq": 0,
        "garages": {
            "club": deepcopy(INITIAL_GARAGE),
            "storage": deepcopy(STORAGE_GARAGE),
        },
        "properties": {},
        "vehicles": {},
        "gacha": {},
        "collection": _collection_empty(),
        "storage_rent_settled_day": None,
        "storage_rent_lifetime": 0.0,
        "storage_rent_history": [],
        "income_settled_day": None,
        "income_lifetime": 0.0,
        "income_history": [],
        "activity": [],
    }


def _normalized_vehicle_image(vehicle: dict[str, Any]) -> str:
    catalog_id = str(vehicle.get("catalog_id") or "").strip()
    if catalog_id:
        car = car_by_id(catalog_id)
        if car and car.get("image"):
            return str(car["image"])
    image = str(vehicle.get("image") or "").strip()
    lower = image.lower()
    if lower.endswith((".jpg", ".jpeg")):
        return f"{image.rsplit('.', 1)[0]}.webp"
    return image


def _property_garage_identity(
    asset_id: str, record: dict[str, Any],
) -> tuple[str, int, str, str, str]:
    kind = str(record.get("kind") or "")
    standalone = kind == "garage"
    capacity = int(record.get("parking_spaces") or 0)
    if not capacity:
        capacity = (
            max(1, int(round(float(record.get("area_sqm") or 0) / 110.0)))
            if standalone
            else int(PARKING_CAPACITY_BY_KIND.get(kind) or 0)
        )
    capacity = max(1, capacity)
    garage_id = str(record.get("garage_id") or f"garage-{asset_id}")
    name_zh = str(record.get("garage_name_zh") or f"{record.get('name_zh') or asset_id}停车库")
    name_en = str(record.get("garage_name_en") or f"{record.get('name_en') or asset_id} Parking")
    category = "standalone" if standalone else "property"
    return garage_id, capacity, name_zh, name_en, category


def _ensure_property_garage(
    state: dict[str, Any], asset_id: str, record: dict[str, Any], day: Any = None,
) -> dict[str, Any] | None:
    kind = str(record.get("kind") or "")
    if kind not in {*PARKING_CAPACITY_BY_KIND, "garage"}:
        return None
    garage_id, capacity, name_zh, name_en, category = _property_garage_identity(
        asset_id, record,
    )
    record["garage_id"] = garage_id
    record["parking_spaces"] = capacity
    garage = state.setdefault("garages", {}).get(garage_id)
    if not isinstance(garage, dict):
        garage = {
            "id": garage_id,
            "kind": "property_parking" if category == "property" else "standalone",
            "category": category,
            "capacity": capacity,
            "name_zh": name_zh,
            "name_en": name_en,
            "property_id": asset_id,
            "city_id": str(record.get("city_id") or ""),
            "district_name_zh": str(record.get("district_name_zh") or ""),
            "district_name_en": str(record.get("district_name_en") or ""),
            "lat": record.get("lat"),
            "lng": record.get("lng"),
            "purchase_price": float(record.get("purchase_price") or 0),
            "acquired_day": record.get("acquired_day") if day is None else day,
        }
        state["garages"][garage_id] = garage
    else:
        garage["capacity"] = max(1, int(garage.get("capacity") or capacity))
        garage.setdefault("name_zh", name_zh)
        garage.setdefault("name_en", name_en)
        garage.setdefault("category", category)
        garage.setdefault("property_id", asset_id)
    return garage


def normalize_state(payload: Any) -> dict[str, Any]:
    state = deepcopy(payload) if isinstance(payload, dict) else _empty_state()
    state["schema_version"] = SCHEMA_VERSION
    state.setdefault("created_at", _now())
    state.setdefault("updated_at", _now())
    state["seq"] = max(0, int(state.get("seq") or 0))
    for key in ("garages", "properties", "vehicles", "gacha"):
        if not isinstance(state.get(key), dict):
            state[key] = {}
    state["storage_rent_lifetime"] = max(0.0, float(state.get("storage_rent_lifetime") or 0))
    if not isinstance(state.get("storage_rent_history"), list):
        state["storage_rent_history"] = []
    legacy_home = state["garages"].get("home")
    if isinstance(legacy_home, dict) and "club" not in state["garages"]:
        state["garages"].pop("home", None)
        legacy_home.update({
            "id": "club", "kind": "club", "category": "club",
            "capacity": max(2, int(legacy_home.get("capacity") or 2)),
            "name_zh": INITIAL_GARAGE["name_zh"], "name_en": INITIAL_GARAGE["name_en"],
        })
        state["garages"]["club"] = legacy_home
        for vehicle in state["vehicles"].values():
            if isinstance(vehicle, dict) and str(vehicle.get("garage_id") or "") == "home":
                vehicle["garage_id"] = "club"
    if "club" not in state["garages"]:
        state["garages"]["club"] = deepcopy(INITIAL_GARAGE)
    if not isinstance(state["garages"].get("storage"), dict):
        state["garages"]["storage"] = deepcopy(STORAGE_GARAGE)
    for garage_id, garage in state["garages"].items():
        if isinstance(garage, dict):
            garage["id"] = str(garage.get("id") or garage_id)
            garage["capacity"] = max(1, int(garage.get("capacity") or 2))
            kind = str(garage.get("kind") or "")
            if kind == "home":
                garage["kind"] = "club"
                kind = "club"
            if str(garage_id) == "club":
                garage["kind"] = "club"
                garage["category"] = "club"
                garage.setdefault("name_zh", INITIAL_GARAGE["name_zh"])
                garage.setdefault("name_en", INITIAL_GARAGE["name_en"])
            elif str(garage_id) == "storage":
                garage.update({
                    "kind": "storage", "category": "storage", "capacity": 10000,
                    "name_zh": STORAGE_GARAGE["name_zh"],
                    "name_en": STORAGE_GARAGE["name_en"],
                    "purchase_price": 0, "system": True,
                })
                garage.setdefault("acquired_day", None)
            elif kind in {"apartment", "premium", "warehouse"}:
                garage["legacy"] = True
                garage["category"] = "legacy"
            elif not garage.get("category"):
                garage["category"] = "property" if garage.get("property_id") else "standalone"
    claimed_parcels = {
        str(row.get("parcel_id") or "")
        for row in state["properties"].values()
        if isinstance(row, dict) and row.get("parcel_id")
    }
    for asset_id, record in state["properties"].items():
        if isinstance(record, dict):
            _sync_property_parcel_snapshot(state, str(asset_id), record, claimed_parcels)
            kind = str(record.get("kind") or "residential")
            tenure = "lease" if str(record.get("tenure") or "owned") == "lease" else "owned"
            record["tenure"] = tenure
            mode = str(record.get("mode") or "rent")
            if mode == "parking":
                mode = "self" if kind == "garage" else "rent"
            if tenure == "lease":
                allowed = {"self"} if kind in {"residential", "garage"} else {"vacant", "operate"}
            else:
                allowed = {"self", "rent"} if kind == "residential" else {"vacant", "rent", "operate"} if kind in BUSINESS_CATALOG else {"self", "rent"}
            if mode not in allowed:
                mode = (
                    "self" if kind in {"residential", "garage"}
                    else "vacant" if tenure == "lease"
                    else "rent"
                )
            record["mode"] = mode
            record["level"] = max(1, min(MAX_PROPERTY_LEVEL, int(record.get("level") or 1)))
            if kind in BUSINESS_CATALOG:
                valid_business = _business_definition(kind, str(record.get("business_type") or ""))
                record["business_type"] = str((valid_business or BUSINESS_CATALOG[kind][0])["id"])
            else:
                record["business_type"] = ""
            construction = record.get("construction")
            if isinstance(construction, dict) and str(construction.get("kind") or "") in CONSTRUCTION_KINDS:
                construction["kind"] = str(construction["kind"])
                started_day = max(0, int(construction.get("started_day") or record.get("acquired_day") or 0))
                duration_days = max(1, int(construction.get("duration_days") or construction.get("days") or 1))
                end_day = max(started_day + 1, int(construction.get("end_day") or started_day + duration_days))
                construction.update({
                    "started_day": started_day,
                    "duration_days": max(1, end_day - started_day),
                    "end_day": end_day,
                    "cost": max(0.0, float(construction.get("cost") or 0)),
                })
                if construction["kind"] == "upgrade":
                    construction["from_level"] = max(1, min(MAX_PROPERTY_LEVEL - 1, int(construction.get("from_level") or record["level"])))
                    construction["target_level"] = max(
                        construction["from_level"] + 1,
                        min(MAX_PROPERTY_LEVEL, int(construction.get("target_level") or record["level"] + 1)),
                    )
                elif construction["kind"] == "business_setup":
                    target_business = str(construction.get("target_business_type") or record.get("business_type") or "")
                    valid_target = _business_definition(kind, target_business)
                    construction["target_business_type"] = str(
                        (valid_target or BUSINESS_CATALOG.get(kind, ({"id": ""},))[0])["id"]
                    )
                    construction["target_mode"] = "operate"
                record["construction"] = construction
            else:
                record.pop("construction", None)
            lease_raw = record.get("lease") if isinstance(record.get("lease"), dict) else None
            if tenure == "lease":
                lease_raw = lease_raw or {}
                start_day = max(0, int(lease_raw.get("start_day") or record.get("acquired_day") or 0))
                term_days = max(1, int(lease_raw.get("days") or 90))
                end_day = max(start_day + 1, int(lease_raw.get("end_day") or start_day + term_days))
                status = str(lease_raw.get("status") or "active")
                if status not in {"active", "expired", "terminated"}:
                    status = "active"
                record["lease"] = {
                    "status": status,
                    "start_day": start_day,
                    "end_day": end_day,
                    "days": max(1, end_day - start_day),
                    "monthly_rent": max(0.0, float(lease_raw.get("monthly_rent") or record.get("monthly_rent") or 0)),
                    "prepaid_rent": max(0.0, float(lease_raw.get("prepaid_rent") or 0)),
                    "deposit": max(0.0, float(lease_raw.get("deposit") or 0)),
                    "renewals": max(0, int(lease_raw.get("renewals") or 0)),
                }
            else:
                record.pop("lease", None)
            policy = _employee_policy(kind, int(record["level"]))
            employees = int(record.get("employees") or 0) if policy["max"] else 0
            record["employees"] = max(0, min(policy["max"], employees))
            if mode == "operate" and record["employees"] < policy["min"]:
                record["employees"] = policy["min"]
            if mode != "operate":
                record["employees"] = 0
            city = city_by_id(str(record.get("city_id") or "")) or {}
            record.setdefault("country", str(city.get("country") or "CN").upper())
            record.setdefault("city_tier", int(_city_profile(str(record.get("city_id") or "")).get("tier") or 2))
            district_id, district = _resolve_property_district(
                str(record.get("city_id") or ""), record,
            )
            record["district_id"] = district_id
            if district:
                record["district_name_zh"] = str(district.get("name_zh") or record.get("district_name_zh") or "")
                record["district_name_en"] = str(district.get("name_en") or record.get("district_name_en") or "")
            record.setdefault("income_since_day", max(int(record.get("acquired_day") or 0), int(state.get("income_settled_day") or record.get("acquired_day") or 0)))
            record["accrued_income"] = max(0.0, float(record.get("accrued_income") or 0))
            record["accrued_days"] = max(0, int(record.get("accrued_days") or 0))
            if kind == "garage":
                record["garage_monthly_rent"] = max(
                    float(record.get("garage_monthly_rent") or 0),
                    float(record.get("monthly_rent") or 0),
                    round_money(float(record.get("base_price") or 0) * GARAGE_RENT_YIELD / 12.0),
                )
            income = property_income_breakdown(record)
            record["daily_income"] = float(income["daily_income"])
            record["monthly_income"] = float(income["monthly_income"])
            _ensure_property_garage(state, str(asset_id), record)
            garage_id = str(record.get("garage_id") or "")
            garage = state["garages"].get(garage_id) if garage_id else None
            if isinstance(garage, dict) and str(garage.get("property_id") or "") == str(asset_id):
                garage["city_id"] = record.get("city_id")
                garage["district_name_zh"] = record.get("district_name_zh")
                garage["district_name_en"] = record.get("district_name_en")
                garage["lat"] = record.get("lat")
                garage["lng"] = record.get("lng")
    garage_ids = {
        str(garage_id) for garage_id, garage in state["garages"].items()
        if isinstance(garage, dict)
    }
    for vehicle in state["vehicles"].values():
        if not isinstance(vehicle, dict):
            continue
        vehicle["image"] = _normalized_vehicle_image(vehicle)
        if str(vehicle.get("garage_id") or "") not in garage_ids:
            vehicle["garage_id"] = "club"
    for key in ("income_history", "activity"):
        if not isinstance(state.get(key), list):
            state[key] = []
    state["income_lifetime"] = max(0.0, float(state.get("income_lifetime") or 0))
    if not isinstance(state.get("collection"), dict):
        state["collection"] = _collection_empty()
        record_collection(
            state,
            [vehicle for vehicle in state["vehicles"].values() if isinstance(vehicle, dict)],
            day=max(
                (
                    int(vehicle.get("purchase_day") or 0)
                    for vehicle in state["vehicles"].values()
                    if isinstance(vehicle, dict)
                ),
                default=0,
            ) or None,
        )
    else:
        collection = state["collection"]
        if not isinstance(collection.get("cars"), dict):
            collection["cars"] = {}
        collection["total_acquired"] = max(
            int(collection.get("total_acquired") or 0),
            sum(
                int(row.get("count") or 0)
                for row in collection["cars"].values() if isinstance(row, dict)
            ),
        )
        collection.setdefault("updated_at", _now())
    return state


def load_state(scope_id: str) -> dict[str, Any]:
    with _LOCK:
        payload = load_document(DOCUMENT, None, scope_id)
    return normalize_state(payload)


def save_state(
    state: dict[str, Any], scope_id: str, *, normalized: bool = False,
) -> None:
    """Persist life state.

    ``normalized=True`` is used by bulk callers whose payload was already
    produced by ``normalize_state``/``ensure_state``; re-normalizing copied the
    entire save (and every nested property dict) a second time and dominated
    bulk purchase latency.
    """
    if not normalized:
        state = normalize_state(state)
    state["updated_at"] = _now()
    with _LOCK:
        save_document(DOCUMENT, state, scope_id)


def _complete_construction(state: dict[str, Any], record: dict[str, Any], day: int) -> bool:
    construction = record.get("construction")
    if not isinstance(construction, dict):
        return False
    kind = str(construction.get("kind") or "")
    end_day = int(construction.get("end_day") or day)
    if int(day) < end_day:
        return False
    record.pop("construction", None)
    if kind == "upgrade":
        record["level"] = max(
            _property_level(record),
            min(MAX_PROPERTY_LEVEL, int(construction.get("target_level") or _property_level(record) + 1)),
        )
    elif kind == "business_setup":
        target_business = str(construction.get("target_business_type") or record.get("business_type") or "")
        if _business_definition(str(record.get("kind") or ""), target_business) is not None:
            record["business_type"] = target_business
        record["mode"] = "operate"
        policy = _employee_policy(str(record.get("kind") or ""), _property_level(record))
        target_employees = int(construction.get("target_employees") or policy["min"])
        record["employees"] = max(policy["min"], min(policy["max"], target_employees))
    else:
        return False
    policy = _employee_policy(str(record.get("kind") or ""), _property_level(record))
    if str(record.get("mode") or "") == "operate" and int(record.get("employees") or 0) < policy["min"]:
        record["employees"] = policy["min"]
    record["income_since_day"] = min(int(day), end_day)
    income = property_income_breakdown(record, as_of_day=end_day)
    record["daily_income"] = float(income["daily_income"])
    record["monthly_income"] = float(income["monthly_income"])
    _log(state, f"property_{kind}_complete", end_day, asset_id=record.get("id"))
    return True


def advance_lifecycle(state: dict[str, Any], day: int) -> bool:
    """Complete due works and expire leases without relying on UI refreshes."""
    changed = False
    for record in state.get("properties", {}).values():
        if not isinstance(record, dict):
            continue
        construction = record.get("construction")
        if isinstance(construction, dict) and int(day) >= int(construction.get("end_day") or 0):
            changed = _complete_construction(state, record, int(day)) or changed
        lease = record.get("lease") if isinstance(record.get("lease"), dict) else None
        if (
            str(record.get("tenure") or "owned") == "lease" and lease
            and str(lease.get("status") or "") == "active"
            and int(day) > int(lease.get("end_day") or 0)
        ):
            end_day = int(lease.get("end_day") or day)
            _close_income_segment(state, record, end_day)
            lease["status"] = "expired"
            record["daily_income"] = 0.0
            record["monthly_income"] = 0.0
            _log(state, "property_lease_expired", end_day, asset_id=record.get("id"))
            changed = True
    return changed


def ensure_state(scope_id: str, day: int) -> tuple[dict[str, Any], bool]:
    raw = load_document(DOCUMENT, None, scope_id)
    state = normalize_state(raw)
    changed = (
        not isinstance(raw, dict)
        or raw.get("schema_version") != SCHEMA_VERSION
        or not isinstance((raw.get("garages") or {}).get("storage"), dict)
        or (raw.get("storage_rent_settled_day") if isinstance(raw, dict) else None) is None
    )
    if state.get("storage_rent_settled_day") is None:
        state["storage_rent_settled_day"] = int(day)
        changed = True
    for vehicle in state.get("vehicles", {}).values():
        if (
            isinstance(vehicle, dict)
            and str(vehicle.get("garage_id") or "") == "storage"
            and vehicle.get("storage_entered_day") is None
        ):
            vehicle["storage_entered_day"] = int(day)
            changed = True
    if state.get("income_settled_day") is None:
        state["income_settled_day"] = day
        changed = True
    changed = advance_lifecycle(state, day) or changed
    return state, changed


def _next_id(state: dict[str, Any], prefix: str) -> str:
    state["seq"] = int(state.get("seq") or 0) + 1
    return f"{prefix}-{state['seq']:06d}"


def _log(state: dict[str, Any], kind: str, day: int, **details: Any) -> None:
    row = {"kind": kind, "at": _now(), "day": day, **details}
    state.setdefault("activity", []).append(row)
    state["activity"] = state["activity"][-MAX_ACTIVITY:]


def garage_used(state: dict[str, Any], garage_id: str) -> int:
    return sum(
        1 for vehicle in state.get("vehicles", {}).values()
        if isinstance(vehicle, dict) and str(vehicle.get("garage_id") or "") == garage_id
    )


def _rented_garage_ids(state: dict[str, Any]) -> set[str]:
    return {
        str(record.get("garage_id") or "")
        for record in state.get("properties", {}).values()
        if isinstance(record, dict)
        and str(record.get("kind") or "") == "garage"
        and str(record.get("mode") or "") == "rent"
        and str(record.get("garage_id") or "")
    }


def garage_capacity(state: dict[str, Any]) -> tuple[int, int]:
    rented = _rented_garage_ids(state)
    capacity = sum(
        int(item.get("capacity") or 0)
        for garage_id, item in state.get("garages", {}).items()
        if isinstance(item, dict) and str(garage_id) not in rented
    )
    used = sum(1 for item in state.get("vehicles", {}).values() if isinstance(item, dict))
    return used, capacity


def _allocate_garage_slots(state: dict[str, Any], requested: str, count: int) -> list[str]:
    if count <= 0:
        return []
    garages = {
        str(key): value for key, value in state.get("garages", {}).items()
        if isinstance(value, dict)
    }
    if requested and requested not in garages:
        raise ValueError("车库不存在")
    order = [requested] if requested else sorted(
        (key for key in garages if key != "storage"),
        key=lambda key: (key != "club", key),
    )
    rented = _rented_garage_ids(state)
    slots: list[str] = []
    for garage_id in order:
        if garage_id in rented:
            continue
        free = max(0, int(garages[garage_id].get("capacity") or 0) - garage_used(state, garage_id))
        slots.extend([garage_id] * min(free, count - len(slots)))
        if len(slots) >= count:
            return slots
    raise ValueError("车库车位不足，请先购买或扩容车库")


def property_owned(state: dict[str, Any], parcel_id: str) -> bool:
    """Compatibility name: a parcel cannot be bought or leased twice."""
    return any(
        str(item.get("parcel_id") or "") == str(parcel_id)
        for item in state.get("properties", {}).values()
        if isinstance(item, dict)
    )


def _new_property_record(
    state: dict[str, Any], parcel: dict[str, Any], day: int, *,
    tenure: str, price: float, fees: float, lease: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    kind = str(parcel["kind"])
    city = city_by_id(str(parcel["city_id"])) or {}
    profile = _city_profile(str(parcel["city_id"]))
    if tenure == "lease":
        mode = "self" if kind in {"residential", "garage"} else "vacant"
    else:
        mode = "self" if kind == "garage" else "rent" if kind == "residential" else "vacant"
    business_type = str(BUSINESS_CATALOG[kind][0]["id"]) if kind in BUSINESS_CATALOG else ""
    policy = _employee_policy(kind, 1)
    record = {
        "id": _next_id(state, "property"),
        "parcel_id": str(parcel["id"]),
        "city_id": str(parcel["city_id"]),
        "city_name_zh": str(parcel["city_name_zh"]),
        "city_name_en": str(parcel["city_name_en"]),
        "country": str(city.get("country") or "CN").upper(),
        "city_tier": int(profile.get("tier") or 2),
        "district_id": str(parcel.get("district_id") or ""),
        "district_name_zh": str(parcel["district_name_zh"]),
        "district_name_en": str(parcel["district_name_en"]),
        "kind": kind,
        "name_zh": str(parcel["name_zh"]),
        "name_en": str(parcel["name_en"]),
        "lat": float(parcel["lat"]),
        "lng": float(parcel["lng"]),
        "area_sqm": int(parcel["area_sqm"]),
        "base_price": int(parcel["base_price"]),
        "purchase_price": price,
        "purchase_fees": fees,
        "tenure": tenure,
        "acquired_day": day,
        "acquired_at": _now(),
        "mode": mode,
        "level": 1,
        "business_type": business_type,
        "employees": policy["min"] if mode == "operate" else 0,
        "income_since_day": day,
        "accrued_income": 0.0,
        "accrued_days": 0,
        "monthly_rent": float(parcel["monthly_rent"]),
        "monthly_operating_net": float(parcel["monthly_operating_net"]),
        "garage_monthly_rent": float(parcel["monthly_rent"]) if kind == "garage" else 0.0,
        "parking_spaces": int(parcel.get("parking_spaces") or 0),
        "parcel_snapshot_version": CITY_PACK_VERSION,
    }
    if lease is not None:
        record["lease"] = {**deepcopy(lease), "status": "active", "renewals": 0}
    garage = None
    if str(parcel["kind"]) in {*PARKING_CAPACITY_BY_KIND, "garage"}:
        garage_id, capacity, name_zh, name_en, category = _property_garage_identity(
            str(record["id"]), record,
        )
        record["garage_id"] = garage_id
        record["parking_spaces"] = capacity
        garage = {
            "id": garage_id,
            "kind": "property_parking" if category == "property" else "standalone",
            "category": category,
            "capacity": capacity,
            "name_zh": name_zh,
            "name_en": name_en,
            "property_id": str(record["id"]),
            "city_id": str(record["city_id"]),
            "district_name_zh": str(record["district_name_zh"]),
            "district_name_en": str(record["district_name_en"]),
            "lat": record["lat"],
            "lng": record["lng"],
            "purchase_price": price,
            "acquired_day": day,
        }
    income = property_income_breakdown(record, as_of_day=day)
    record["daily_income"] = float(income["daily_income"])
    record["monthly_income"] = float(income["monthly_income"])
    return record, garage


def buy_property_plan(state: dict[str, Any], parcel: dict[str, Any], day: int) -> dict[str, Any]:
    if property_owned(state, str(parcel.get("id") or "")):
        raise ValueError("该地块已被购买或租用")
    price = parcel_quote(parcel, day)
    fees = round_money(price * BUY_FEE_RATE)
    record, garage = _new_property_record(
        state, parcel, day, tenure="owned", price=price, fees=fees,
    )
    return {
        "record": record, "garage": garage, "price": price, "fees": fees,
        "total": round_money(price + fees),
    }


def lease_property_plan(
    state: dict[str, Any], parcel: dict[str, Any], day: int, days: int,
) -> dict[str, Any]:
    if property_owned(state, str(parcel.get("id") or "")):
        raise ValueError("该地块已被购买或租用")
    quote = lease_quote(parcel, int(days))
    lease = {
        "start_day": int(day),
        "end_day": int(day) + int(quote["days"]),
        "days": int(quote["days"]),
        "monthly_rent": float(quote["monthly_rent"]),
        "prepaid_rent": float(quote["prepaid_rent"]),
        "deposit": float(quote["deposit"]),
    }
    record, garage = _new_property_record(
        state, parcel, day, tenure="lease", price=0.0, fees=0.0, lease=lease,
    )
    return {
        "record": record, "garage": garage, "lease": quote,
        "price": float(quote["prepaid_rent"]),
        "deposit": float(quote["deposit"]),
        "total": float(quote["total"]),
    }


def commit_buy_property(state: dict[str, Any], plan: dict[str, Any], day: int) -> dict[str, Any]:
    record = deepcopy(plan["record"])
    state.setdefault("properties", {})[record["id"]] = record
    garage = plan.get("garage")
    if isinstance(garage, dict):
        state.setdefault("garages", {})[str(garage["id"])] = deepcopy(garage)
    _log(state, "property_buy", day, asset_id=record["id"], amount=plan["price"])
    return record


def commit_lease_property(state: dict[str, Any], plan: dict[str, Any], day: int) -> dict[str, Any]:
    record = deepcopy(plan["record"])
    state.setdefault("properties", {})[record["id"]] = record
    garage = plan.get("garage")
    if isinstance(garage, dict):
        state.setdefault("garages", {})[str(garage["id"])] = deepcopy(garage)
    _log(
        state, "property_lease", day, asset_id=record["id"],
        amount=float(plan["total"]), days=int(plan["lease"]["days"]),
    )
    return record


def sell_property_plan(state: dict[str, Any], asset_id: str, day: int) -> dict[str, Any]:
    record = state.get("properties", {}).get(str(asset_id))
    if not isinstance(record, dict):
        raise ValueError("房产不存在")
    if str(record.get("tenure") or "owned") != "owned":
        raise ValueError("租赁资产不能出售，请办理续租或退租")
    if _construction_active(record):
        raise ValueError("资产正在建设中，暂时不能出售")
    garage_id = str(record.get("garage_id") or "")
    if garage_id and garage_used(state, garage_id) > 0:
        raise ValueError("请先将该房产车库中的车辆迁移到其他车库，再出售房产")
    parcel = {
        "city_id": record.get("city_id"),
        "kind": record.get("kind"),
        "base_price": record.get("base_price"),
    }
    value = parcel_quote(parcel, day)
    fee = round_money(value * SELL_FEE_RATE)
    pending = _record_pending_income(state, record, day)
    pending_days = int(pending["days"])
    pending_income = float(pending["amount"])
    return {
        "record": deepcopy(record), "value": value, "fee": fee,
        "net": round_money(value - fee),
        "pending_income": pending_income,
        "pending_days": pending_days,
        "credit": round_money(value - fee + pending_income),
    }


def commit_sell_property(state: dict[str, Any], plan: dict[str, Any], day: int) -> dict[str, Any]:
    record = state.get("properties", {}).pop(str(plan["record"]["id"]), None)
    if record is None:
        raise ValueError("房产不存在")
    garage_id = str(record.get("garage_id") or "")
    if garage_id:
        state.setdefault("garages", {}).pop(garage_id, None)
    _log(
        state, "property_sell", day, asset_id=record["id"],
        amount=plan["net"], pending_income=float(plan.get("pending_income") or 0),
    )
    return record


def lease_renewal_plan(state: dict[str, Any], asset_id: str, day: int, days: int) -> dict[str, Any]:
    record = state.get("properties", {}).get(str(asset_id))
    if not isinstance(record, dict):
        raise ValueError("房产不存在")
    lease = record.get("lease") if isinstance(record.get("lease"), dict) else None
    if str(record.get("tenure") or "owned") != "lease" or lease is None:
        raise ValueError("该资产不是租赁资产")
    if _construction_active(record):
        raise ValueError("资产正在建设中，暂时不能续租")
    term = int(days or 0)
    if term not in LEASE_TERM_DAYS:
        raise ValueError("租期无效")
    monthly = max(0.0, float(lease.get("monthly_rent") or 0))
    amount = round_money(monthly * term / 30.0)
    start_day = max(int(day), int(lease.get("end_day") or day))
    return {
        "record": deepcopy(record), "asset_id": str(asset_id), "days": term,
        "amount": amount, "new_start_day": start_day,
        "new_end_day": start_day + term,
    }


def commit_lease_renewal(state: dict[str, Any], plan: dict[str, Any], day: int) -> dict[str, Any]:
    record = state.get("properties", {}).get(str(plan["asset_id"]))
    if not isinstance(record, dict):
        raise ValueError("房产不存在")
    lease = record.get("lease") if isinstance(record.get("lease"), dict) else None
    if lease is None:
        raise ValueError("该资产不是租赁资产")
    was_expired = str(lease.get("status") or "") != "active"
    lease["end_day"] = int(plan["new_end_day"])
    lease["days"] = max(1, int(lease["end_day"]) - int(lease.get("start_day") or day))
    lease["status"] = "active"
    lease["renewals"] = int(lease.get("renewals") or 0) + 1
    lease["prepaid_rent"] = round_money(float(lease.get("prepaid_rent") or 0) + float(plan["amount"]))
    if was_expired:
        record["income_since_day"] = int(day)
    income = property_income_breakdown(record, as_of_day=day)
    record["daily_income"] = float(income["daily_income"])
    record["monthly_income"] = float(income["monthly_income"])
    _log(state, "property_lease_renew", day, asset_id=record.get("id"), days=int(plan["days"]), amount=float(plan["amount"]))
    return deepcopy(record)


def release_lease_plan(state: dict[str, Any], asset_id: str, day: int) -> dict[str, Any]:
    record = state.get("properties", {}).get(str(asset_id))
    if not isinstance(record, dict):
        raise ValueError("房产不存在")
    lease = record.get("lease") if isinstance(record.get("lease"), dict) else None
    if str(record.get("tenure") or "owned") != "lease" or lease is None:
        raise ValueError("该资产不是租赁资产")
    if _construction_active(record):
        raise ValueError("资产正在建设中，暂时不能退租")
    garage_id = str(record.get("garage_id") or "")
    if garage_id and garage_used(state, garage_id) > 0:
        raise ValueError("请先将该资产车库中的车辆迁移到其他车库，再退租")
    pending = _record_pending_income(state, record, day)
    refund = float(lease.get("deposit") or 0)
    return {
        "record": deepcopy(record), "asset_id": str(asset_id),
        "deposit_refund": round_money(refund),
        "pending_income": float(pending["amount"]),
        "credit": round_money(refund + float(pending["amount"])),
    }


def commit_release_lease(state: dict[str, Any], plan: dict[str, Any], day: int) -> dict[str, Any]:
    record = state.get("properties", {}).pop(str(plan["asset_id"]), None)
    if record is None:
        raise ValueError("房产不存在")
    garage_id = str(record.get("garage_id") or "")
    if garage_id:
        state.setdefault("garages", {}).pop(garage_id, None)
    record["lease"]["status"] = "terminated"
    _log(state, "property_lease_release", day, asset_id=record.get("id"), deposit_refund=float(plan["deposit_refund"]))
    return record


def configure_property(
    state: dict[str, Any], asset_id: str, day: int, *, mode: str | None = None,
    business_type: str | None = None, employees: int | None = None,
) -> dict[str, Any]:
    record = state.get("properties", {}).get(str(asset_id))
    if not isinstance(record, dict):
        raise ValueError("房产不存在")
    if _construction_active(record):
        raise ValueError("资产正在建设或升级中")
    if not _lease_active(record, int(day)):
        raise ValueError("租约已到期，请先续租")
    kind = str(record.get("kind") or "residential")
    if str(record.get("tenure") or "owned") == "lease":
        allowed = {"self"} if kind in {"residential", "garage"} else {"vacant", "operate"}
    else:
        allowed = (
            {"self", "rent"} if kind in {"residential", "garage"}
            else {"vacant", "rent", "operate"} if kind in BUSINESS_CATALOG
            else set()
        )
    resolved_mode = str(mode if mode is not None else record.get("mode") or "rent")
    if resolved_mode not in allowed:
        raise ValueError("经营模式无效")
    if resolved_mode == "operate" and str(record.get("mode") or "") != "operate":
        raise ValueError("开展经营前必须先提交经营筹备")
    if kind == "garage" and resolved_mode == "rent" and garage_used(state, str(record.get("garage_id") or "")) > 0:
        raise ValueError("请先将该车库中的车辆迁移到其他车库，再出租车库")
    changed = resolved_mode != str(record.get("mode") or "")
    next_business = str(business_type if business_type is not None else record.get("business_type") or "")
    if (
        resolved_mode == "operate" and business_type is not None
        and next_business != str(record.get("business_type") or "")
    ):
        raise ValueError("变更经营业态前必须先提交经营筹备")
    if resolved_mode == "operate":
        if kind not in BUSINESS_CATALOG or _business_definition(kind, next_business) is None:
            raise ValueError("经营业态无效")
    else:
        next_business = str(record.get("business_type") or "") if kind in BUSINESS_CATALOG else ""
    policy = _employee_policy(kind, _property_level(record))
    next_employees = int(record.get("employees") or 0) if employees is None else int(employees)
    next_employees = max(0, min(policy["max"], next_employees)) if policy["max"] else 0
    if resolved_mode == "operate" and next_employees < policy["min"]:
        next_employees = policy["min"]
    if resolved_mode != "operate":
        next_employees = 0
    changed = changed or next_business != str(record.get("business_type") or "")
    changed = changed or next_employees != int(record.get("employees") or 0)
    if changed:
        _close_income_segment(state, record, int(day))
    record["mode"] = resolved_mode
    record["business_type"] = next_business
    record["employees"] = next_employees
    income = property_income_breakdown(record, as_of_day=int(day))
    record["daily_income"] = float(income["daily_income"])
    record["monthly_income"] = float(income["monthly_income"])
    return deepcopy(record)


def set_property_mode(
    state: dict[str, Any], asset_id: str, mode: str, day: int | None = None,
) -> dict[str, Any]:
    record = state.get("properties", {}).get(str(asset_id)) or {}
    resolved_day = int(day or record.get("income_since_day") or record.get("acquired_day") or 0)
    return configure_property(state, asset_id, resolved_day, mode=mode)


def property_upgrade_plan(state: dict[str, Any], asset_id: str, day: int) -> dict[str, Any]:
    record = state.get("properties", {}).get(str(asset_id))
    if not isinstance(record, dict):
        raise ValueError("房产不存在")
    if str(record.get("kind") or "") == "garage":
        raise ValueError("车库资产不支持升级")
    if _construction_active(record):
        raise ValueError("资产已有工程正在进行")
    if not _lease_active(record, int(day)):
        raise ValueError("租约已到期，请先续租")
    level = _property_level(record)
    if level >= MAX_PROPERTY_LEVEL:
        raise ValueError("该资产已达到最高等级")
    cost = property_upgrade_cost(record)
    if cost <= 0:
        raise ValueError("该资产无法升级")
    duration_days = property_upgrade_duration_days(record)
    if str(record.get("tenure") or "owned") == "lease":
        remaining = int((record.get("lease") or {}).get("end_day") or day) - int(day)
        if remaining < duration_days:
            raise ValueError("租约剩余时间不足以完成本次升级")
    return {
        "record": deepcopy(record), "asset_id": str(asset_id),
        "from_level": level, "to_level": level + 1, "cost": cost,
        "duration_days": duration_days, "end_day": int(day) + duration_days,
    }


def commit_property_upgrade(state: dict[str, Any], plan: dict[str, Any], day: int) -> dict[str, Any]:
    record = state.get("properties", {}).get(str(plan["asset_id"]))
    if not isinstance(record, dict):
        raise ValueError("房产不存在")
    if _property_level(record) != int(plan["from_level"]):
        raise ValueError("资产等级已变化，请刷新后重试")
    if _construction_active(record):
        raise ValueError("资产已有工程正在进行")
    _close_income_segment(state, record, int(day))
    duration_days = max(1, int(plan.get("duration_days") or property_upgrade_duration_days(record)))
    record["construction"] = {
        "kind": "upgrade",
        "started_day": int(day),
        "end_day": int(day) + duration_days,
        "duration_days": duration_days,
        "from_level": int(plan["from_level"]),
        "target_level": int(plan["to_level"]),
        "cost": float(plan["cost"]),
        "started_at": _now(),
    }
    record["income_since_day"] = int(day)
    record["daily_income"] = 0.0
    record["monthly_income"] = 0.0
    _log(state, "property_upgrade_start", day, asset_id=record.get("id"), duration=duration_days, cost=float(plan["cost"]))
    return deepcopy(record)


def property_business_change_required(record: dict[str, Any], business_type: str) -> bool:
    return (
        str(record.get("mode") or "") != "operate"
        or str(record.get("business_type") or "") != str(business_type or "")
    )


def property_business_plan(
    state: dict[str, Any], asset_id: str, day: int, business_type: str,
    employees: int | None = None,
) -> dict[str, Any]:
    record = state.get("properties", {}).get(str(asset_id))
    if not isinstance(record, dict):
        raise ValueError("房产不存在")
    kind = str(record.get("kind") or "")
    if kind not in BUSINESS_CATALOG:
        raise ValueError("该资产不支持经营业态")
    if _construction_active(record):
        raise ValueError("资产已有工程正在进行")
    if not _lease_active(record, int(day)):
        raise ValueError("租约已到期，请先续租")
    business = _business_definition(kind, business_type)
    if business is None:
        raise ValueError("经营业态无效")
    cost = property_business_setup_cost(record, business_type)
    duration_days = property_business_setup_days(record, business_type)
    if str(record.get("tenure") or "owned") == "lease":
        remaining = int((record.get("lease") or {}).get("end_day") or day) - int(day)
        if remaining < duration_days:
            raise ValueError("租约剩余时间不足以完成本次经营筹备")
    policy = _employee_policy(kind, _property_level(record))
    target_employees = policy["min"] if employees is None else max(policy["min"], min(policy["max"], int(employees)))
    return {
        "record": deepcopy(record), "asset_id": str(asset_id),
        "business_type": str(business_type), "business_name_zh": str(business.get("name_zh") or ""),
        "business_name_en": str(business.get("name_en") or ""),
        "cost": cost, "duration_days": duration_days,
        "end_day": int(day) + duration_days, "employees": target_employees,
    }


def commit_property_business(state: dict[str, Any], plan: dict[str, Any], day: int) -> dict[str, Any]:
    record = state.get("properties", {}).get(str(plan["asset_id"]))
    if not isinstance(record, dict):
        raise ValueError("房产不存在")
    if _construction_active(record):
        raise ValueError("资产已有工程正在进行")
    _close_income_segment(state, record, int(day))
    duration_days = max(1, int(plan.get("duration_days") or 1))
    record["construction"] = {
        "kind": "business_setup",
        "started_day": int(day),
        "end_day": int(day) + duration_days,
        "duration_days": duration_days,
        "target_business_type": str(plan["business_type"]),
        "target_mode": "operate",
        "target_employees": int(plan.get("employees") or 0),
        "cost": float(plan["cost"]),
        "started_at": _now(),
    }
    record["income_since_day"] = int(day)
    record["daily_income"] = 0.0
    record["monthly_income"] = 0.0
    _log(
        state, "property_business_start", day, asset_id=record.get("id"),
        business_type=str(plan["business_type"]), duration=duration_days, cost=float(plan["cost"]),
    )
    return deepcopy(record)


def _pending_income(state: dict[str, Any], day: int) -> tuple[float, list[dict[str, Any]]]:
    rows = []
    total = 0.0
    for record in state.get("properties", {}).values():
        if not isinstance(record, dict):
            continue
        pending = _record_pending_income(state, record, day)
        days = int(pending["days"])
        amount = float(pending["amount"])
        total += amount
        rows.append({
            "asset_id": record.get("id"), "days": days,
            "daily": float(pending["daily"]), "amount": amount,
        })
    return round_money(total), rows


def collect_income_plan(state: dict[str, Any], day: int) -> dict[str, Any]:
    total, rows = _pending_income(state, day)
    return {"amount": total, "rows": rows, "settle_day": day}


def commit_income(state: dict[str, Any], plan: dict[str, Any], day: int) -> None:
    state["income_settled_day"] = day
    for record in state.get("properties", {}).values():
        if isinstance(record, dict):
            record["accrued_income"] = 0.0
            record["accrued_days"] = 0
            record["income_since_day"] = int(day)
    state["income_lifetime"] = round_money(
        float(state.get("income_lifetime") or 0) + float(plan["amount"])
    )
    state.setdefault("income_history", []).append({
        "at": _now(), "day": day, "amount": plan["amount"], "rows": plan["rows"],
    })
    state["income_history"] = state["income_history"][-60:]
    _log(state, "income_collect", day, amount=plan["amount"])


def sell_vehicle_plan(
    state: dict[str, Any], vehicle_id: str, day: int,
) -> dict[str, Any]:
    vehicle = state.get("vehicles", {}).get(str(vehicle_id))
    if not isinstance(vehicle, dict):
        raise ValueError("车辆不存在")
    value = vehicle_market_value(vehicle, day)
    fee = round_money(value * SELL_FEE_RATE)
    return {
        "vehicle": deepcopy(vehicle),
        "value": value,
        "fee": fee,
        "net": round_money(value - fee),
    }


def duplicate_vehicle_sales(
    state: dict[str, Any], garage_id: str, day: int,
) -> dict[str, Any]:
    """Plan selling every duplicate in one garage while keeping its best copy.

    A duplicate group is the same catalog model (or manufacturer/name/year when
    the catalog id is missing). The retained car is the one with the highest
    current sale value; ties prefer the newer purchase and then the stable id.
    """
    garage_key = str(garage_id or "").strip()
    if not garage_key:
        raise ValueError("缺少车库")
    vehicles = [
        vehicle for vehicle in state.get("vehicles", {}).values()
        if isinstance(vehicle, dict)
        and str(vehicle.get("garage_id") or "") == garage_key
    ]
    groups: dict[str, list[dict[str, Any]]] = {}
    for vehicle in vehicles:
        catalog_id = str(vehicle.get("catalog_id") or "").strip()
        key = catalog_id or "|".join([
            str(vehicle.get("manufacturer") or "").strip().casefold(),
            str(vehicle.get("name") or "").strip().casefold(),
            str(vehicle.get("year") or ""),
        ])
        groups.setdefault(key, []).append(vehicle)
    kept: list[dict[str, Any]] = []
    plans: list[dict[str, Any]] = []
    for group in groups.values():
        if len(group) < 2:
            continue
        ranked = sorted(
            group,
            key=lambda vehicle: (
                vehicle_market_value(vehicle, day),
                int(vehicle.get("purchase_day") or 0),
                str(vehicle.get("id") or ""),
            ),
            reverse=True,
        )
        kept.append(deepcopy(ranked[0]))
        for vehicle in ranked[1:]:
            plans.append(sell_vehicle_plan(state, str(vehicle["id"]), day))
    plans.sort(key=lambda plan: str(plan["vehicle"].get("id") or ""))
    return {
        "garage_id": garage_key,
        "kept": kept,
        "plans": plans,
        "count": len(plans),
        "total_net": round_money(sum(float(plan["net"]) for plan in plans)),
    }


def commit_sell_vehicle(
    state: dict[str, Any], plan: dict[str, Any], day: int,
) -> dict[str, Any]:
    vehicle = state.get("vehicles", {}).pop(str(plan["vehicle"]["id"]), None)
    if not isinstance(vehicle, dict):
        raise ValueError("车辆不存在")
    _log(
        state, "vehicle_sell", day, vehicle_id=vehicle["id"],
        catalog_id=vehicle.get("catalog_id"), amount=plan["net"],
    )
    return deepcopy(vehicle)


def vehicle_market_value(vehicle: dict[str, Any], day: int) -> float:
    days = max(0, day - int(vehicle.get("purchase_day") or day))
    factor = max(VEHICLE_MIN_VALUE_RATIO, (1.0 - VEHICLE_DAILY_DECAY) ** days)
    condition = max(0.35, min(1.0, float(vehicle.get("condition") or 1.0)))
    return round_money(float(vehicle.get("base_price") or 0) * condition * factor)


def storage_rent_plan(state: dict[str, Any], day: int) -> dict[str, Any]:
    """Quote daily storage rent without moving money or mutating the save."""
    current_day = int(day)
    stored = [
        vehicle for vehicle in state.get("vehicles", {}).values()
        if isinstance(vehicle, dict) and str(vehicle.get("garage_id") or "") == "storage"
    ]
    stored_value = round_money(sum(vehicle_market_value(vehicle, current_day) for vehicle in stored))
    settled_raw = state.get("storage_rent_settled_day")
    settled_day = current_day if settled_raw is None else int(settled_raw)
    days_due = max(0, current_day - settled_day)
    due_amount = 0.0
    for rent_day in range(settled_day + 1, current_day + 1):
        day_value = sum(
            vehicle_market_value(vehicle, rent_day)
            for vehicle in stored
            if int(vehicle.get("storage_entered_day") or settled_day) < rent_day
        )
        due_amount += round_money(day_value * STORAGE_RENT_RATE)
    return {
        "settled_day": settled_day,
        "calculated_day": current_day,
        "days_due": days_due,
        "vehicle_count": len(stored),
        "stored_value": stored_value,
        "daily_amount": round_money(stored_value * STORAGE_RENT_RATE),
        "due_amount": round_money(due_amount),
        "rate": STORAGE_RENT_RATE,
        "needs_settlement": current_day > settled_day,
    }


def commit_storage_rent(
    state: dict[str, Any], plan: dict[str, Any], day: int,
    payment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Advance the storage-rent marker after the facade has charged funds."""
    current_day = int(day)
    amount = round_money(float(plan.get("due_amount") or 0))
    state["storage_rent_settled_day"] = current_day
    if amount > 0:
        state["storage_rent_lifetime"] = round_money(
            float(state.get("storage_rent_lifetime") or 0) + amount
        )
        history = state.setdefault("storage_rent_history", [])
        history.append({
            "at": _now(),
            "day": current_day,
            "amount": amount,
            "days": int(plan.get("days_due") or 0),
            "vehicles": int(plan.get("vehicle_count") or 0),
            "transaction_id": str((payment or {}).get("transaction_id") or ""),
        })
        state["storage_rent_history"] = history[-MAX_STORAGE_RENT_HISTORY:]
        _log(
            state, "storage_rent_charge", current_day, amount=amount,
            days=int(plan.get("days_due") or 0),
            vehicles=int(plan.get("vehicle_count") or 0),
        )
    return storage_rent_status(state, current_day)


def storage_rent_status(state: dict[str, Any], day: int) -> dict[str, Any]:
    plan = storage_rent_plan(state, day)
    history = state.get("storage_rent_history") or []
    last = history[-1] if history and isinstance(history[-1], dict) else {}
    return {
        **plan,
        "paid_lifetime": round_money(float(state.get("storage_rent_lifetime") or 0)),
        "last_charged_day": last.get("day"),
        "last_charged_amount": round_money(float(last.get("amount") or 0)),
    }


def _vehicle_purchase_record(
    state: dict[str, Any], car: dict[str, Any], garage_id: str, day: int,
) -> dict[str, Any]:
    return {
        "id": _next_id(state, "vehicle"),
        "catalog_id": str(car["catalog_id"]),
        "name": str(car["name"]),
        "manufacturer": str(car["manufacturer"]),
        "class": str(car["class"]),
        "rarity": str(car["rarity"]),
        "year": int(car["year"]),
        "image": str(car["image"]),
        "base_price": float(car["price"]),
        "purchase_price": float(car["price"]),
        "purchase_day": day,
        "purchased_at": _now(),
        "garage_id": garage_id,
        "source": "dealer",
        "mileage_km": 0,
        "condition": 1.0,
    }


def buy_vehicle_plan(
    state: dict[str, Any], car: dict[str, Any], garage_id: str, day: int,
) -> dict[str, Any]:
    if str(car.get("dealer_status") or "") == "display_only":
        raise ValueError("该车型仅作展厅陈列，暂不出售")
    slots = _allocate_garage_slots(state, garage_id, 1)
    record = _vehicle_purchase_record(state, car, slots[0], day)
    return {"record": record, "price": float(car["price"]), "garage_id": slots[0]}


def buy_vehicle_batch_plan(
    state: dict[str, Any], cars: list[dict[str, Any]], garage_id: str, day: int,
) -> dict[str, Any]:
    """Prepare an all-or-nothing dealer purchase for the current filter."""
    if not cars:
        raise ValueError("没有可购买的车辆")
    for car in cars:
        if str(car.get("dealer_status") or "") == "display_only":
            raise ValueError("筛选结果包含仅展示车型，请先排除")
    slots = _allocate_garage_slots(state, garage_id, len(cars))
    plans = [
        {
            "record": _vehicle_purchase_record(state, car, slots[index], day),
            "price": float(car["price"]),
            "garage_id": slots[index],
        }
        for index, car in enumerate(cars)
    ]
    return {
        "plans": plans,
        "total": round_money(sum(float(plan["price"]) for plan in plans)),
        "count": len(plans),
    }


def commit_buy_vehicle(state: dict[str, Any], plan: dict[str, Any], day: int) -> dict[str, Any]:
    record = deepcopy(plan["record"])
    state.setdefault("vehicles", {})[record["id"]] = record
    record_collection(state, [record], day=day)
    _log(state, "vehicle_buy", day, vehicle_id=record["id"], catalog_id=record["catalog_id"], amount=plan["price"])
    return record


def grant_vehicle_award(
    state: dict[str, Any], catalog_id: str, day: int, *, source: str = "asset_level",
) -> dict[str, Any]:
    """Grant a catalogue vehicle without charging the wallet.

    Achievement rewards prefer storage, then the club garage, and finally any
    other owned garage with a free space.  The caller
    owns persistence and can retry later when every garage is full.
    """
    car = car_by_id(str(catalog_id or "").strip())
    if not car:
        raise ValueError("奖励车辆不存在")
    garage_id = ""
    for requested in ("storage", "club", ""):
        try:
            garage_id = _allocate_garage_slots(state, requested, 1)[0]
            break
        except ValueError:
            continue
    if not garage_id:
        raise ValueError("所有车库都没有空位，无法领取奖励车辆，请先腾出车位")
    record = {
        "id": _next_id(state, "vehicle"),
        "catalog_id": str(car["catalog_id"]),
        "name": str(car["name"]),
        "manufacturer": str(car["manufacturer"]),
        "class": str(car["class"]),
        "rarity": str(car["rarity"]),
        "year": int(car["year"]),
        "image": str(car["image"]),
        "base_price": float(car["price"]),
        "purchase_price": 0.0,
        "purchase_day": int(day),
        "purchased_at": _now(),
        "garage_id": garage_id,
        "source": str(source or "asset_level")[:80],
        "mileage_km": 0,
        "condition": 1.0,
    }
    state.setdefault("vehicles", {})[record["id"]] = record
    record_collection(state, [record], day=int(day))
    _log(
        state, "vehicle_award", int(day), vehicle_id=record["id"],
        catalog_id=record["catalog_id"], garage_id=garage_id,
        source=record["source"],
    )
    return deepcopy(record)


def move_vehicle(state: dict[str, Any], vehicle_id: str, garage_id: str, day: int) -> dict[str, Any]:
    vehicle = state.get("vehicles", {}).get(str(vehicle_id))
    if not isinstance(vehicle, dict):
        raise ValueError("车辆不存在")
    if garage_id not in state.get("garages", {}):
        raise ValueError("车库不存在")
    probe = {
        **state,
        "vehicles": {
            key: value for key, value in state.get("vehicles", {}).items()
            if key != str(vehicle_id)
        },
    }
    _allocate_garage_slots(probe, garage_id, 1)
    vehicle["garage_id"] = garage_id
    if str(garage_id) == "storage":
        vehicle["storage_entered_day"] = int(day)
    else:
        vehicle.pop("storage_entered_day", None)
    _log(state, "vehicle_move", day, vehicle_id=vehicle_id, garage_id=garage_id)
    return deepcopy(vehicle)


def _gacha_tier_cars(tier: dict[str, Any]) -> list[dict[str, Any]]:
    classes = set(tier.get("classes") or ())
    rarities = {str(value).lower() for value in (tier.get("rarities") or ())}
    return [
        car for car in _car_catalog_cached()["cars"]
        if str(car.get("class") or "D") in classes
        and str(car.get("rarity") or "common").lower() in rarities
    ]


def _gacha_gold_hit(car: dict[str, Any], tier_id: str) -> bool:
    rule = GOLD_RULES.get(str(tier_id or ""))
    if not rule:
        return False
    rarity = str(car.get("rarity") or "").lower()
    if rarity in set(rule.get("any_class_rarities") or ()):
        return True
    return (
        str(car.get("class") or "") == str(rule.get("class") or "")
        and rarity in set(rule.get("rarities") or ())
    )


def _gacha_public_rules(rule: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [{
        "class": str(rule.get("class") or ""),
        "rarities": list(rule.get("rarities") or ()),
    }]
    rows.extend({
        "class": "", "rarities": [str(rarity)]
    } for rarity in rule.get("any_class_rarities") or ())
    return rows


def _gacha_rule_rarities(rule: dict[str, Any]) -> list[str]:
    return list(dict.fromkeys([
        *(str(value) for value in rule.get("rarities") or ()),
        *(str(value) for value in rule.get("any_class_rarities") or ()),
    ]))


def _gacha_history_rarity(row: dict[str, Any]) -> str:
    rarity = str(row.get("rarity") or "").lower()
    if rarity:
        return rarity
    car = _car_catalog_index_cached().get(str(row.get("catalog_id") or ""))
    return str((car or {}).get("rarity") or "").lower()


def _gacha_luck(tracked_pulls: int, gold_count: int, expected_rate: float) -> dict[str, Any]:
    if tracked_pulls <= 0:
        return {
            "key": "empty", "score": 1.0, "observed_rate": 0.0,
            "expected_rate": float(expected_rate or 0),
        }
    expected = max(0.0, float(expected_rate or 0))
    observed = max(0, int(gold_count)) / max(1, int(tracked_pulls))
    score = 1.0
    if expected > 0:
        smoothed = (max(0, int(gold_count)) + expected * GACHA_LUCK_PRIOR_PULLS) / (
            int(tracked_pulls) + GACHA_LUCK_PRIOR_PULLS
        )
        score = smoothed / expected
    if tracked_pulls < GACHA_LUCK_MIN_TRACKED_PULLS:
        key = "provisional"
    elif score >= 1.60:
        key = "ou_3"
    elif score >= 1.35:
        key = "ou_2"
    elif score >= 1.15:
        key = "ou_1"
    elif score >= 0.85:
        key = "balanced"
    elif score >= 0.68:
        key = "fei_1"
    elif score >= 0.50:
        key = "fei_2"
    else:
        key = "fei_3"
    return {
        "key": key, "score": round(score, 3), "observed_rate": observed,
        "expected_rate": expected,
    }


def gacha_tiers() -> list[dict[str, Any]]:
    result = []
    for tier in GACHA_TIERS:
        cars = _gacha_tier_cars(tier)
        prices = [float(car["price"]) for car in cars]
        average = sum(prices) / len(prices) if prices else 0
        tier_id = str(tier["id"])
        odds = _gacha_probabilities(cars, tier_id)
        rule = GOLD_RULES[tier_id]
        weighted_cars = [(car, _gacha_weight(car, tier_id)) for car in cars]
        total_weight = sum(weight for _car, weight in weighted_cars)
        gold_rate = (
            sum(weight for car, weight in weighted_cars if _gacha_gold_hit(car, tier_id))
            / total_weight
            if total_weight > 0 else 0.0
        )
        expected_pulls_per_gold = _gacha_expected_pulls_per_gold(tier_id)
        result.append({
            "id": tier["id"],
            "car_count": len(cars),
            "car_ids": [str(car.get("catalog_id") or "") for car in cars if car.get("catalog_id")],
            "min_catalog_value": min(prices) if prices else 0,
            "max_catalog_value": max(prices) if prices else 0,
            "average_catalog_value": round(average),
            "ticket_price": int(tier["ticket_price"]),
            "ten_ticket_price": int(tier["ten_ticket_price"]),
            "pity_limit": int(tier["pity"]),
            "top_class": rule["class"],
            "top_rarities": _gacha_rule_rarities(rule),
            "gold_rules": _gacha_public_rules(rule),
            "gold_rate": gold_rate,
            "expected_gold_rate": (
                1.0 / expected_pulls_per_gold if expected_pulls_per_gold > 0 else 0.0
            ),
            "expected_pulls_per_gold": expected_pulls_per_gold,
            "odds": odds,
            "soft_pity": {
                "start_after": int(tier["soft_pity_start"]),
                "step": float(tier["soft_pity_step"]),
                "cap": float(tier["soft_pity_cap"]),
            },
        })
    return result


@lru_cache(maxsize=8)
def _gacha_cell_scales(tier_id: str) -> dict[tuple[str, str], float]:
    """Boost gold cars while preserving published class and rarity odds.

    A plain multiplier on gold cars would silently change the public class and
    rarity percentages. Iterative proportional fitting keeps both marginal
    distributions fixed and concentrates the extra weight on the exact gold
    combination instead.
    """
    tier = next(item for item in GACHA_TIERS if item["id"] == tier_id)
    profile = GACHA_PROFILES[tier_id]
    cars = _gacha_tier_cars(tier)
    classes = sorted(
        {str(car.get("class") or "D") for car in cars},
        key=lambda value: CLASS_ORDER.get(value, len(CLASS_ORDER)),
    )
    rarities = sorted(
        {str(car.get("rarity") or "common").lower() for car in cars},
        key=lambda value: RARITY_ORDER.get(value, len(RARITY_ORDER)),
    )
    counts = {
        (str(car.get("class") or "D"), str(car.get("rarity") or "common").lower()): sum(
            1 for row in cars
            if str(row.get("class") or "D") == str(car.get("class") or "D")
            and str(row.get("rarity") or "common").lower()
            == str(car.get("rarity") or "common").lower()
        )
        for car in cars
    }
    matrix = {
        car_class: {
            rarity: float((profile.get("class_weights") or {}).get(car_class, 0))
            * float((profile.get("rarity_weights") or {}).get(rarity, 0))
            * int(counts.get((car_class, rarity), 0))
            for rarity in rarities
        }
        for car_class in classes
    }
    row_targets = {car_class: sum(matrix[car_class].values()) for car_class in classes}
    column_targets = {
        rarity: sum(matrix[car_class][rarity] for car_class in classes)
        for rarity in rarities
    }
    total = sum(row_targets.values())
    if total <= 0:
        return {}
    multiplier = float(profile.get("gold_weight_multiplier") or 1.0)
    for car_class in classes:
        for rarity in rarities:
            if _gacha_gold_hit({"class": car_class, "rarity": rarity}, tier_id):
                matrix[car_class][rarity] *= multiplier
    for _iteration in range(24):
        for car_class in classes:
            row_total = sum(matrix[car_class].values())
            if row_total <= 0:
                continue
            factor = row_targets[car_class] / row_total
            for rarity in rarities:
                matrix[car_class][rarity] *= factor
        for rarity in rarities:
            column_total = sum(matrix[car_class][rarity] for car_class in classes)
            if column_total <= 0:
                continue
            factor = column_targets[rarity] / column_total
            for car_class in classes:
                matrix[car_class][rarity] *= factor
    scales: dict[tuple[str, str], float] = {}
    for car_class in classes:
        for rarity in rarities:
            base = float((profile.get("class_weights") or {}).get(car_class, 0)) * float(
                (profile.get("rarity_weights") or {}).get(rarity, 0)
            ) * int(counts.get((car_class, rarity), 0))
            if base > 0:
                scales[(car_class, rarity)] = matrix[car_class][rarity] / base
    return scales


def _gacha_base_weight(car: dict[str, Any], tier_id: str) -> float:
    profile = GACHA_PROFILES[tier_id]
    car_class = str(car.get("class") or "D")
    rarity = str(car.get("rarity") or "common").lower()
    class_weight = float((profile.get("class_weights") or {}).get(car_class, 0))
    rarity_weight = float((profile.get("rarity_weights") or {}).get(rarity, 0))
    return (
        class_weight
        * rarity_weight
        * float(_gacha_cell_scales(tier_id).get((car_class, rarity), 1.0))
    )


def _gacha_weight(car: dict[str, Any], tier_id: str, pity: int = 0) -> float:
    weight = _gacha_base_weight(car, tier_id)
    if weight <= 0:
        return 0.0
    tier = next(item for item in GACHA_TIERS if item["id"] == tier_id)
    start = int(tier["soft_pity_start"])
    if pity < start:
        return weight
    if not _gacha_gold_hit(car, tier_id):
        return weight
    multiplier = min(
        float(tier["soft_pity_cap"]),
        1.0 + (pity - start + 1) * float(tier["soft_pity_step"]),
    )
    return weight * multiplier


@lru_cache(maxsize=8)
def _gacha_expected_pulls_per_gold(tier_id: str) -> float:
    """Expected pulls per gold result, including soft and hard pity."""
    tier = next(item for item in GACHA_TIERS if item["id"] == tier_id)
    cars = _gacha_tier_cars(tier)
    limit = max(1, int(tier["pity"]))
    survival = 1.0
    expected = 0.0
    for pull in range(1, limit + 1):
        weighted = [(car, _gacha_weight(car, tier_id, pull - 1)) for car in cars]
        total = sum(weight for _car, weight in weighted)
        gold_probability = (
            sum(weight for car, weight in weighted if _gacha_gold_hit(car, tier_id)) / total
            if total > 0 else 0.0
        )
        if pull == limit:
            gold_probability = 1.0
        expected += pull * survival * gold_probability
        survival *= max(0.0, 1.0 - gold_probability)
    return expected if expected > 0 else 0.0


def _gacha_probabilities(cars: list[dict[str, Any]], tier_id: str) -> dict[str, dict[str, float]]:
    class_totals: dict[str, float] = {}
    rarity_totals: dict[str, float] = {}
    total = 0.0
    for car in cars:
        weight = _gacha_weight(car, tier_id)
        if weight <= 0:
            continue
        car_class = str(car.get("class") or "D")
        rarity = str(car.get("rarity") or "common").lower()
        class_totals[car_class] = class_totals.get(car_class, 0.0) + weight
        rarity_totals[rarity] = rarity_totals.get(rarity, 0.0) + weight
        total += weight
    if total <= 0:
        return {"class": {}, "rarity": {}}
    return {
        "class": {
            key: class_totals[key] / total
            for key in sorted(class_totals, key=lambda value: CLASS_ORDER.get(value, 99))
        },
        "rarity": {
            key: rarity_totals[key] / total
            for key in sorted(rarity_totals, key=lambda value: RARITY_ORDER.get(value, 99))
        },
    }


def _weighted_pick(
    cars: list[dict[str, Any]], tier_id: str, key: str, pity: int = 0,
) -> dict[str, Any]:
    weighted = [(car, _gacha_weight(car, tier_id, pity)) for car in cars]
    total = sum(weight for _car, weight in weighted)
    if total <= 0:
        return cars[int(_hash_unit(key, "fallback") * len(cars)) % len(cars)]
    target = _hash_unit(key, "car") * total
    for car, weight in weighted:
        if weight <= 0:
            continue
        target -= weight
        if target <= 0:
            return car
    return weighted[-1][0]


def _pity_pick(cars: list[dict[str, Any]], tier_id: str, key: str) -> dict[str, Any]:
    pool = [car for car in cars if _gacha_gold_hit(car, tier_id)]
    if not pool:
        target_class = str((GOLD_RULES.get(tier_id) or {}).get("class") or PITY_CLASS[tier_id])
        pool = [car for car in cars if str(car.get("class") or "") == target_class]
    if not pool:
        pool = cars
    return pool[int(_hash_unit(key, "pity") * len(pool)) % len(pool)]


def _garage_catalog_counts(state: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for vehicle in (state.get("vehicles") or {}).values():
        if not isinstance(vehicle, dict):
            continue
        catalog_id = str(vehicle.get("catalog_id") or "").strip()
        if catalog_id:
            counts[catalog_id] = counts.get(catalog_id, 0) + 1
    return counts


def gacha_plan(
    state: dict[str, Any], tier_id: str, draws: int, garage_id: str, day: int, seed: str,
) -> dict[str, Any]:
    draws = int(draws)
    if not 1 <= draws <= 1000:
        raise ValueError("神秘车库单次可抽取 1 至 1000 次")
    tier = next((item for item in gacha_tiers() if item["id"] == tier_id), None)
    if tier is None:
        raise ValueError("卡池不存在")
    raw_tier = next(item for item in GACHA_TIERS if item["id"] == tier_id)
    cars = _gacha_tier_cars(raw_tier)
    if not cars:
        raise ValueError("卡池没有可用车辆")
    rule = GOLD_RULES[tier_id]
    ten_packs, remainder = divmod(draws, 10)
    cost = (
        ten_packs * int(tier["ten_ticket_price"])
        + remainder * int(tier["ticket_price"])
    )
    slots = _allocate_garage_slots(state, garage_id, draws)
    counters = state.setdefault("gacha", {}).setdefault(
        tier_id, {"pulls": 0, "pity": 0, "history": []},
    )
    pulls = int(counters.get("pulls") or 0)
    pity = int(counters.get("pity") or 0)
    if not counters.get("stats_version"):
        counters["stats_version"] = GACHA_STATS_VERSION
        counters["stats_started_pull"] = pulls
        counters["spent"] = 0.0
        counters["gold_count"] = 0
        counters["total_value"] = 0.0
    else:
        counters.setdefault("stats_started_pull", 0)
        counters.setdefault("spent", 0.0)
        counters.setdefault("gold_count", 0)
        counters.setdefault("total_value", 0.0)
    records = []
    history = []
    garage_catalog_counts = _garage_catalog_counts(state)
    for offset in range(draws):
        serial = pulls + offset + 1
        key = f"{seed}:{tier_id}:{serial}"
        force = pity + 1 >= int(tier["pity_limit"])
        car = _pity_pick(cars, tier_id, key) if force else _weighted_pick(cars, tier_id, key, pity)
        gold_hit = _gacha_gold_hit(car, tier_id)
        pity_before = pity
        if force:
            pity = 0
        elif gold_hit:
            pity = 0
        else:
            pity += 1
        condition = round(0.78 + _hash_unit(key, "condition") * 0.20, 3)
        mileage = int(round(_hash_unit(key, "mileage") * 60000))
        allocated_cost = cost // draws + (1 if offset < cost % draws else 0)
        catalog_id = str(car["catalog_id"])
        garage_copies_before = int(garage_catalog_counts.get(catalog_id, 0))
        record = {
            "id": _next_id(state, "vehicle"),
            "catalog_id": catalog_id,
            "name": str(car["name"]),
            "manufacturer": str(car["manufacturer"]),
            "class": str(car["class"]),
            "rarity": str(car["rarity"]),
            "year": int(car["year"]),
            "image": str(car["image"]),
            "base_price": float(car["price"]),
            "purchase_price": float(car["price"]) * 0.85,
            "purchase_day": day,
            "purchased_at": _now(),
            "garage_id": slots[offset],
            "source": "gacha",
            "mileage_km": mileage,
            "condition": condition,
            "gacha_tier": tier_id,
            "gacha_top_hit": gold_hit,
            "gacha_gold_hit": gold_hit,
            "gacha_guaranteed": bool(force),
            "garage_duplicate": garage_copies_before > 0,
            "garage_copies_before": garage_copies_before,
        }
        record["value"] = vehicle_market_value(record, day)
        record["gacha_top_class"] = PITY_CLASS[tier_id]
        record["gacha_top_rarities"] = _gacha_rule_rarities(rule)
        records.append(record)
        history.append({
            "at": _now(), "day": day, "tier": tier_id,
            "catalog_id": record["catalog_id"], "name": record["name"],
            "class": record["class"], "rarity": record["rarity"],
            "garage_id": record["garage_id"],
            "cost": allocated_cost, "value": record["value"],
            "top_class": PITY_CLASS[tier_id],
            "top_rarities": _gacha_rule_rarities(rule),
            "gold_rules": _gacha_public_rules(rule),
            "top_hit": bool(gold_hit),
            "gold_hit": bool(gold_hit),
            "guaranteed": bool(force),
            "pity_before": int(pity_before),
            "pity_after": int(pity),
        })
        garage_catalog_counts[catalog_id] = garage_copies_before + 1
    total_value = round_money(sum(float(record["value"]) for record in records))
    gold_count = sum(1 for row in history if row["gold_hit"])
    return {
        "tier": tier_id, "draws": draws, "cost": cost,
        "tickets": int(tier["ticket_price"]), "records": records,
        "history": history, "pulls_end": pulls + draws, "pity_end": pity,
        "total_value": total_value, "gold_count": gold_count,
        "gold_rate": float(tier["gold_rate"]),
        "top_rarities": _gacha_rule_rarities(rule),
        "gold_rules": _gacha_public_rules(rule),
    }


def commit_gacha(state: dict[str, Any], plan: dict[str, Any], day: int) -> dict[str, Any]:
    counter = state.setdefault("gacha", {}).setdefault(
        plan["tier"], {"pulls": 0, "pity": 0, "history": []},
    )
    counter["pulls"] = int(plan["pulls_end"])
    counter["pity"] = int(plan["pity_end"])
    counter.setdefault("stats_version", GACHA_STATS_VERSION)
    counter.setdefault(
        "stats_started_pull",
        max(0, int(plan.get("pulls_end") or 0) - int(plan.get("draws") or 0)),
    )
    counter.setdefault("spent", 0.0)
    counter.setdefault("gold_count", 0)
    counter.setdefault("total_value", 0.0)
    counter["spent"] = round_money(float(counter.get("spent") or 0) + float(plan["cost"]))
    counter["gold_count"] = int(counter.get("gold_count") or 0) + int(plan.get("gold_count") or 0)
    counter["total_value"] = round_money(
        float(counter.get("total_value") or 0) + float(plan.get("total_value") or 0)
    )
    counter.setdefault("history", []).extend(deepcopy(plan["history"]))
    for record in plan["records"]:
        state.setdefault("vehicles", {})[record["id"]] = deepcopy(record)
    record_collection(state, plan["records"], day=day)
    _log(state, "gacha_draw", day, amount=plan["cost"], tier=plan["tier"], draws=plan["draws"])
    return deepcopy(plan["records"])


def _gacha_counter_stats(counter: dict[str, Any], tier: dict[str, Any]) -> dict[str, Any]:
    pulls = max(0, int(counter.get("pulls") or 0))
    tracked = bool(counter.get("stats_version"))
    started = int(counter.get("stats_started_pull") or 0) if tracked else pulls
    tracked_pulls = max(0, pulls - max(0, started)) if tracked else 0
    spent = round_money(float(counter.get("spent") or 0)) if tracked else 0.0
    gold_count = max(0, int(counter.get("gold_count") or 0)) if tracked else 0
    total_value = round_money(float(counter.get("total_value") or 0)) if tracked else 0.0
    base_rate = float(tier.get("gold_rate") or 0)
    expected_rate = float(tier.get("expected_gold_rate") or 0)
    expected_pulls = float(tier.get("expected_pulls_per_gold") or 0)
    return {
        "pulls": pulls,
        "stats_started_pull": max(0, started),
        "tracked_pulls": tracked_pulls,
        "spent": spent,
        "gold_count": gold_count,
        "total_value": total_value,
        "gold_rate": base_rate,
        "expected_gold_rate": expected_rate,
        "expected_pulls_per_gold": expected_pulls,
        "observed_gold_rate": gold_count / tracked_pulls if tracked_pulls else 0.0,
        "luck": _gacha_luck(tracked_pulls, gold_count, expected_rate),
        "luck_min_pulls": GACHA_LUCK_MIN_TRACKED_PULLS,
        "tracking_complete": tracked and max(0, started) == 0,
    }


def life_lock() -> threading.RLock:
    """Return the process-wide re-entrant lock used by the life facade."""
    return _LOCK


def record_collection(
    state: dict[str, Any], records: list[dict[str, Any]], *, day: int | None = None,
) -> dict[str, Any]:
    """Record acquired models in the collection owned by this save."""
    collection = state.get("collection")
    if not isinstance(collection, dict):
        collection = state["collection"] = _collection_empty()
    cars = collection.get("cars")
    if not isinstance(cars, dict):
        cars = collection["cars"] = {}
    if not records:
        return collection_view(state)
    for record in records:
        catalog_id = str(record.get("catalog_id") or "").strip()
        if not catalog_id:
            continue
        row = cars.get(catalog_id)
        if not isinstance(row, dict):
            row = {
                "catalog_id": catalog_id,
                "name": str(record.get("name") or ""),
                "manufacturer": str(record.get("manufacturer") or ""),
                "class": str(record.get("class") or ""),
                "rarity": str(record.get("rarity") or ""),
                "year": int(record.get("year") or 0),
                "image": _normalized_vehicle_image(record),
                "count": 0,
                "first_acquired_at": _now(),
                "last_acquired_at": _now(),
                "first_acquired_day": day,
                "last_acquired_day": day,
                "sources": {},
            }
            cars[catalog_id] = row
        row["count"] = int(row.get("count") or 0) + 1
        row["last_acquired_at"] = _now()
        row["last_acquired_day"] = day
        source = str(record.get("source") or "unknown")
        sources = row.setdefault("sources", {})
        sources[source] = int(sources.get(source) or 0) + 1
        collection["total_acquired"] = int(collection.get("total_acquired") or 0) + 1
    collection["updated_at"] = _now()
    return collection_view(state)


def collection_view(state: dict[str, Any]) -> dict[str, Any]:
    collection = state.get("collection") if isinstance(state.get("collection"), dict) else {}
    cars = collection.get("cars") if isinstance(collection.get("cars"), dict) else {}
    rows = sorted(
        (
            {
                **deepcopy(row),
                "image": _normalized_vehicle_image(row),
            }
            for row in cars.values() if isinstance(row, dict)
        ),
        key=lambda row: (
            -int(row.get("count") or 0),
            str(row.get("manufacturer") or ""),
            str(row.get("name") or ""),
        ),
    )
    unique = len(rows)
    total = sum(int(row.get("count") or 0) for row in rows)
    manufacturers = len({
        str(row.get("manufacturer") or "") for row in rows if row.get("manufacturer")
    })
    return {
        "cars": rows,
        "summary": {
            "unique": unique,
            "total": total,
            "manufacturers": manufacturers,
            "catalog_size": len(_car_catalog_cached()["cars"]),
        },
    }


def _garage_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    rented = _rented_garage_ids(state)
    for garage_id, garage in (state.get("garages") or {}).items():
        if not isinstance(garage, dict):
            continue
        used = garage_used(state, str(garage_id))
        capacity = max(0, int(garage.get("capacity") or 0))
        category = str(garage.get("category") or "")
        if not category:
            category = (
                "club" if str(garage_id) == "club"
                else "legacy" if garage.get("legacy")
                else "property" if garage.get("property_id")
                else "standalone"
            )
        rows.append({
            **deepcopy(garage),
            "id": str(garage_id),
            "category": category,
            "rented": str(garage_id) in rented,
            "used": used,
            "free": 0 if str(garage_id) in rented else max(0, capacity - used),
        })
    order = {"club": 0, "storage": 1, "property": 2, "standalone": 3, "legacy": 4}
    rows.sort(key=lambda row: (order.get(str(row.get("category")), 4), row["id"]))
    return rows


def public_view(
    state: dict[str, Any], *, game_date: str = "", scope_id: str = "",
    manager_id: Any = 0,
) -> dict[str, Any]:
    """Return one non-mutating projection for the life pages."""
    day = day_ordinal(game_date)
    today = day or date.today().toordinal()
    pending, pending_rows = _pending_income(state, today) if day else (0.0, [])
    pending_by_asset = {
        str(row.get("asset_id") or ""): row for row in pending_rows
    }
    properties = []
    property_value = 0.0
    leased_property_value = 0.0
    lease_deposit_total = 0.0
    owned_count = 0
    leased_count = 0
    construction_count = 0
    for asset_id, record in (state.get("properties") or {}).items():
        if not isinstance(record, dict):
            continue
        parcel = {
            "city_id": record.get("city_id"),
            "kind": record.get("kind"),
            "base_price": record.get("base_price"),
        }
        quote = parcel_quote(parcel, today)
        tenure = str(record.get("tenure") or "owned")
        is_owned = tenure == "owned"
        book_value = quote if is_owned else 0.0
        if is_owned:
            property_value += quote
            owned_count += 1
        else:
            leased_property_value += quote
            leased_count += 1
        lease = record.get("lease") if isinstance(record.get("lease"), dict) else {}
        lease_deposit_total += float(lease.get("deposit") or 0)
        construction = record.get("construction") if isinstance(record.get("construction"), dict) else {}
        if construction:
            construction_count += 1
        income = property_income_breakdown(record, as_of_day=today)
        lease_end = int(lease.get("end_day") or 0)
        lease_remaining = max(0, lease_end - today) if lease_end else 0
        properties.append({
            **deepcopy(record), "id": str(asset_id), "market_value": quote,
            "book_value": round_money(book_value), "tenure": tenure,
            "is_owned": is_owned,
            "income_breakdown": income,
            "monthly_income": float(income["monthly_income"]),
            "daily_income": float(income["daily_income"]),
            "upgrade_cost": property_upgrade_cost(record),
            "upgrade_days": property_upgrade_duration_days(record),
            "business_setup_quotes": property_business_quotes(record),
            "lease_days_remaining": lease_remaining,
            "lease_renew_options": [
                {
                    "days": term,
                    "amount": round_money(float(lease.get("monthly_rent") or 0) * term / 30.0),
                }
                for term in LEASE_TERM_DAYS
            ] if tenure == "lease" else [],
            "construction_days_remaining": max(
                0, int(construction.get("end_day") or today) - today
            ) if construction else 0,
            "is_construction": bool(construction),
            "pending_income": float((pending_by_asset.get(str(asset_id)) or {}).get("amount") or 0),
            "pending_days": int((pending_by_asset.get(str(asset_id)) or {}).get("days") or 0),
        })
    properties.sort(key=lambda row: (str(row.get("city_id") or ""), str(row.get("id") or "")))

    vehicles = []
    vehicle_value = 0.0
    for vehicle_id, vehicle in (state.get("vehicles") or {}).items():
        if not isinstance(vehicle, dict):
            continue
        value = vehicle_market_value(vehicle, today)
        vehicle_value += value
        vehicles.append({
            **deepcopy(vehicle), "id": str(vehicle_id), "market_value": value,
            "image": _normalized_vehicle_image(vehicle),
        })
    vehicles.sort(key=lambda row: (str(row.get("garage_id") or ""), str(row.get("name") or "")))

    used, capacity = garage_capacity(state)
    gacha = []
    for tier in gacha_tiers():
        counter = (state.get("gacha") or {}).get(tier["id"]) or {}
        history = []
        for raw_row in counter.get("history") or []:
            if not isinstance(raw_row, dict):
                continue
            row = deepcopy(raw_row)
            rarity = _gacha_history_rarity(row)
            if rarity:
                row["rarity"] = rarity
            row.setdefault("top_class", tier.get("top_class"))
            row.setdefault("top_rarities", list(tier.get("top_rarities") or ()))
            gold_hit = _gacha_gold_hit(row, str(tier["id"]))
            row["gold_hit"] = gold_hit
            row["top_hit"] = gold_hit
            history.append(row)
        gacha.append({
            **tier,
            "pulls": int(counter.get("pulls") or 0),
            "pity": int(counter.get("pity") or 0),
            "history": history,
            "history_count": len(history),
            "stats": _gacha_counter_stats(counter, tier),
        })
    return {
        "ready": True,
        "scope_id": str(scope_id or ""),
        "game_date": str(game_date or ""),
        "garages": _garage_rows(state),
        "garage_summary": {"used": used, "capacity": capacity, "free": max(0, capacity - used)},
        "properties": properties,
        "vehicles": vehicles,
        "gacha_tiers": gacha,
        "storage_rent": storage_rent_status(state, today),
        "garage_types": [],
        "business_catalog": business_catalog(),
        "collection": collection_view(state),
        "income": {
            "pending": float(pending),
            "settled_day": state.get("income_settled_day"),
            "lifetime": float(state.get("income_lifetime") or 0),
            "history": list(state.get("income_history") or [])[-20:],
        },
        "activity": list(state.get("activity") or [])[-40:],
        "totals": {
            "property_value": round_money(property_value),
            "leased_property_value": round_money(leased_property_value),
            "lease_deposit": round_money(lease_deposit_total),
            "vehicle_value": round_money(vehicle_value),
            "net_worth": round_money(property_value + vehicle_value),
            "properties": len(properties),
            "owned_properties": owned_count,
            "leased_properties": leased_count,
            "construction_properties": construction_count,
            "vehicles": len(vehicles),
        },
    }


def gacha_patch(
    state: dict[str, Any], records: list[dict[str, Any]], *,
    game_date: str = "", scope_id: str = "", manager_id: Any = 0,
) -> dict[str, Any]:
    """Return only the life fields changed by a completed gacha draw.

    The draw response used to repeat the complete state, vehicle catalogue and
    every historical pull. That made the WebView parse and repaint megabytes of
    unchanged data after each click. The client already owns those fields and
    only needs the new cars plus the counters that can change.
    """
    day = day_ordinal(game_date)
    today = day or date.today().toordinal()
    added: list[dict[str, Any]] = []
    for record in records:
        row = deepcopy(record)
        row["market_value"] = vehicle_market_value(record, today)
        row["image"] = _normalized_vehicle_image(record)
        added.append(row)
    used, capacity = garage_capacity(state)
    tiers = []
    for tier in gacha_tiers():
        counter = (state.get("gacha") or {}).get(tier["id"]) or {}
        tiers.append({
            "id": str(tier["id"]),
            "pulls": int(counter.get("pulls") or 0),
            "pity": int(counter.get("pity") or 0),
            "history_count": len(counter.get("history") or []),
            "stats": _gacha_counter_stats(counter, tier),
        })
    return {
        "scope_id": str(scope_id or ""),
        "game_date": str(game_date or ""),
        "manager_id": manager_id,
        "vehicles_added": added,
        "garages": _garage_rows(state),
        "garage_summary": {
            "used": used, "capacity": capacity, "free": max(0, capacity - used),
        },
        "storage_rent": storage_rent_status(state, today),
        "collection": collection_view(state),
        "gacha_status": tiers,
        "vehicles_added_value": round_money(
            sum(float(row.get("market_value") or 0) for row in added)
        ),
    }
