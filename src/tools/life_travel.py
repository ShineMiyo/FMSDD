"""Travel destinations and encounter helpers for the People workspace.

The catalogue reuses the life-system city packs so the outside world and the
property system name the same places.  This module owns only travel metadata
and probabilities; it never reads or writes Football Manager memory.
"""

from __future__ import annotations

import random
from typing import Any

from tools import life_system

# Native nation names used by the world-club cache.  They are display names,
# not stable codes; a miss simply means "no real-player candidate".
COUNTRY_NATIVE_NAMES = {
    "CN": "中国",
    "GB": "英格兰",
    "FR": "法国",
    "DE": "德国",
    "ES": "西班牙",
    "BE": "比利时",
    "NL": "荷兰",
    "JP": "日本",
    "KR": "韩国",
}

COUNTRY_NAMES = {
    "CN": ("中国", "China"),
    "GB": ("英国", "United Kingdom"),
    "FR": ("法国", "France"),
    "DE": ("德国", "Germany"),
    "ES": ("西班牙", "Spain"),
    "BE": ("比利时", "Belgium"),
    "NL": ("荷兰", "Netherlands"),
    "JP": ("日本", "Japan"),
    "KR": ("韩国", "South Korea"),
}

# Fallback pools by country.  City overrides below make the major destinations
# specific without maintaining 68 separate lists.
PLACE_POOLS = {
    "CN": ("老城街区", "滨江步道", "城市美术馆", "茶馆", "夜市", "河畔公园"),
    "GB": ("河畔步道", "旧书店街", "城市美术馆", "中央公园", "火车站钟楼", "周末市集"),
    "FR": ("河畔步道", "街角咖啡馆", "小画廊", "旧城广场", "城市花园", "周末市集"),
    "DE": ("老城广场", "河岸公园", "工业设计馆", "啤酒花园", "周末市集", "城市湖岸"),
    "ES": ("老城广场", "滨水步道", "当代艺术馆", "露天餐桌", "城市公园", "周末市集"),
    "BE": ("老城广场", "运河边", "小画廊", "巧克力店", "城市公园", "周末市集"),
    "NL": ("运河边", "设计商店", "城市公园", "旧书市集", "河畔咖啡馆", "风车步道"),
    "JP": ("神社参道", "樱花河岸", "旧书店街", "居酒屋小巷", "城市庭园", "温泉街"),
    "KR": ("汉江公园", "韩屋小巷", "独立书店", "咖啡街", "夜市", "城郭步道"),
}

CITY_OVERRIDES = {
    "shanghai": ("外滩", "武康路", "西岸美术馆", "豫园", "陆家嘴天桥"),
    "beijing": ("什刹海", "798 艺术区", "国子监街", "三里屯", "景山步道"),
    "guangzhou": ("珠江夜游", "沙面老街", "广东省博物馆", "北京路", "白云山"),
    "shenzhen": ("深圳湾公园", "华侨城创意园", "海上世界", "莲花山", "南头古城"),
    "chengdu": ("宽窄巷子", "锦里", "人民公园茶馆", "太古里", "望江楼"),
    "chongqing": ("洪崖洞", "南滨路", "鹅岭二厂", "解放碑", "长江索道"),
    "hangzhou": ("西湖断桥", "中国美院", "河坊街", "西溪湿地", "京杭大运河"),
    "nanjing": ("夫子庙", "老门东", "先锋书店", "玄武湖", "颐和路"),
    "london": ("泰晤士河畔", "科文特花园", "大英博物馆", "海德公园", "诺丁山"),
    "manchester": ("运河区", "北方角", "约翰·赖兰兹图书馆", "希顿公园", "北区"),
    "paris": ("塞纳河畔", "蒙马特高地", "橘园美术馆", "拉丁区", "杜乐丽花园"),
    "berlin": ("施普雷河畔", "博物馆岛", "东边画廊", "蒂尔加滕公园", "克罗伊茨贝格"),
    "munich": ("英国花园", "玛利亚广场", "现代艺术馆", "伊萨尔河", "维克图阿连市场"),
    "madrid": ("丽池公园", "普拉多大道", "马约尔广场", "拉丁区", "格兰维亚"),
    "barcelona": ("哥特区", "巴塞罗内塔海滩", "毕加索博物馆", "格拉西亚大道", "蒙特惠奇"),
    "brussels": ("大广场", "圣于贝尔长廊", "运河区", "五十周年公园", "马罗勒"),
    "amsterdam": ("运河带", "国立博物馆", "约旦区", "冯德尔公园", "九小街"),
    "tokyo": ("涩谷十字路口", "代代木公园", "国立新美术馆", "神保町旧书店街", "隅田川"),
    "kyoto": ("祇园花见小路", "鸭川", "清水寺", "哲学之道", "锦市场"),
    "osaka": ("道顿堀", "心斋桥", "大阪城公园", "中崎町", "天保山"),
    "seoul": ("汉江公园", "明洞", "北村韩屋村", "圣水洞", "景福宫"),
    "busan": ("海云台", "甘川文化村", "广安里", "釜山电影街", "太宗台"),
}


def _city_key(city: dict[str, Any]) -> str:
    return str(city.get("id") or "").strip().lower()


def _city_name(city: dict[str, Any]) -> tuple[str, str]:
    return (
        str(city.get("name_zh") or city.get("name") or city.get("id") or ""),
        str(city.get("name_en") or city.get("name") or city.get("id") or ""),
    )


def places_for_city(city: dict[str, Any]) -> list[str]:
    key = _city_key(city)
    if key in CITY_OVERRIDES:
        return list(CITY_OVERRIDES[key])
    country = str(city.get("country") or "CN").upper()
    return list(PLACE_POOLS.get(country, PLACE_POOLS["CN"]))


def catalog() -> list[dict[str, Any]]:
    """Return all nine destinations, their cities and place names."""
    payload = life_system.city_catalog()
    rows: list[dict[str, Any]] = []
    for country in payload.get("countries") or []:
        code = str(country.get("code") or "").upper()
        if not code:
            continue
        name_zh, name_en = COUNTRY_NAMES.get(
            code,
            (
                str(country.get("name_zh") or code),
                str(country.get("name_en") or code),
            ),
        )
        cities = []
        for city in country.get("cities") or []:
            if not isinstance(city, dict):
                continue
            city_zh, city_en = _city_name(city)
            if not city_zh and not city_en:
                continue
            cities.append({
                "id": str(city.get("id") or ""),
                "name_zh": city_zh,
                "name_en": city_en,
                "country": code,
                "places": places_for_city(city),
            })
        if cities:
            rows.append({
                "code": code,
                "name_zh": name_zh,
                "name_en": name_en,
                "native_nation": COUNTRY_NATIVE_NAMES.get(code, name_zh),
                "cities": cities,
            })
    return rows


def find_country(code: str) -> dict[str, Any] | None:
    target = str(code or "").strip().upper()
    return next((row for row in catalog() if row["code"] == target), None)


def find_city(country_code: str, city_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    country = find_country(country_code)
    if not country:
        return None
    target = str(city_id or "").strip()
    city = next(
        (
            row for row in country.get("cities") or []
            if target in {str(row.get("id") or ""), str(row.get("name_zh") or ""), str(row.get("name_en") or "")}
        ),
        None,
    )
    return (country, city) if city else None


def resolve_destination(
    country_code: str, city_id: str, place: str = "",
) -> tuple[dict[str, Any], dict[str, Any], str] | None:
    resolved = find_city(country_code, city_id)
    if not resolved:
        return None
    country, city = resolved
    places = list(city.get("places") or [])
    chosen = str(place or "").strip()
    if chosen and chosen not in places:
        return None
    if not chosen:
        chosen = random.choice(places) if places else ""
    return country, city, chosen


def asset_bonus(level: Any) -> float:
    """Asset level is the only encounter bonus; vehicles and planes do not count."""
    try:
        value = int(level or 0)
    except (TypeError, ValueError):
        value = 0
    return round(min(0.24, max(0, value - 1) * 0.02), 4)


FICTIONAL_ENCOUNTER_SHARE = 0.30


def prefer_fictional_encounter() -> bool:
    """Keep a share of encounters fictional even when real players exist."""
    return random.random() < FICTIONAL_ENCOUNTER_SHARE


def encounter_chance(asset_level: Any) -> float:
    return round(min(0.80, 0.45 + asset_bonus(asset_level)), 4)


def public_catalog() -> dict[str, Any]:
    countries = catalog()
    return {
        "countries": countries,
        "city_count": sum(len(row.get("cities") or []) for row in countries),
        "place_count": sum(
            len(city.get("places") or [])
            for row in countries
            for city in row.get("cities") or []
        ),
    }
