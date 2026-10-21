from __future__ import annotations

import json
import math
import subprocess
from datetime import date
from pathlib import Path

import fm_odds_web as web
import pytest
from tools import life_system
from tools.money import round_money


ROOT = Path(__file__).resolve().parents[1]


def webp_has_alpha(path: Path) -> bool:
    data = path.read_bytes()
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return False
    offset = 12
    while offset + 8 <= len(data):
        chunk = data[offset:offset + 4]
        size = int.from_bytes(data[offset + 4:offset + 8], "little")
        if chunk == b"ALPH":
            return True
        if chunk == b"VP8X" and size >= 1:
            return bool(data[offset + 8] & 0x10)
        offset += 8 + size + (size % 2)
    return False


def test_car_catalog_and_gallery_exclude_unavailable_entries():
    catalog = life_system.car_catalog()
    cars = catalog["cars"]
    assert len(cars) == 425
    assert not any(int(car.get("source_id", -1)) == 899 for car in cars)
    for car in cars:
        image = ROOT / "src" / "web" / str(car["image"]).lstrip("/")
        assert image.is_file(), image
        assert image.suffix == ".webp"
        assert webp_has_alpha(image), image

    manifest = json.loads((ROOT / "car_images" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["count"] == 901
    assert len(manifest["cars"]) == 901
    assert manifest["failed"] == 0
    assert manifest["failures"] == []
    assert manifest["source_failures"] == []
    assert manifest["fallbacks"] == []
    assert not any(int(car.get("id", -1)) == 899 for car in manifest["cars"])


def test_city_pack_is_deterministic_and_uses_city_profile():
    city = life_system.city_catalog()["cities"][0]
    first = life_system.generate_city_pack(city)
    second = life_system.generate_city_pack(city)
    assert first["checksum"] == second["checksum"]
    assert len(first["parcels"]) > 54
    assert {row["kind"] for row in first["parcels"]} == set(life_system.PARCEL_KINDS)
    assert any(int(row.get("parking_spaces") or 0) >= 8 for row in first["parcels"])


def test_city_profile_exclusions_and_industrial_distribution_are_respected():
    for city in life_system.city_catalog()["cities"]:
        pack = life_system.generate_city_pack(city)
        profile = life_system._city_profile(str(city["id"]))
        for parcel in pack["parcels"]:
            assert life_system._excluded_distance_m(
                profile, parcel["lat"], parcel["lng"], include_green=True,
            ) >= 0
        industrial = [row for row in pack["parcels"] if row["kind"] == "industrial"]
        assert industrial
        assert all(
            life_system._haversine_m(row["lat"], row["lng"], city["lat"], city["lng"]) >= 2800
            for row in industrial
        )


def test_city_terrain_pack_covers_every_catalog_city_and_has_valid_rings():
    terrain = json.loads((ROOT / "src" / "assets" / "life" / "city_terrain.json").read_text(encoding="utf-8"))
    expected = {str(city["id"]) for city in life_system.city_catalog()["cities"]}
    assert set(terrain.get("cities") or {}) >= expected
    assert terrain.get("license") == "ODbL 1.0"
    for city_id in expected:
        areas = terrain["cities"][city_id]
        assert isinstance(areas, list)
        for area in areas:
            assert area["kind"] in {"water", "green"}
            assert len(area.get("bbox") or []) == 4
            assert len(area.get("ring") or []) >= 4


def test_terrain_multipart_polygon_treats_inner_holes_as_land():
    outer = [[0.0, 0.0], [0.0, 0.02], [0.02, 0.02], [0.02, 0.0], [0.0, 0.0]]
    hole = [[0.005, 0.005], [0.005, 0.015], [0.015, 0.015], [0.015, 0.005], [0.005, 0.005]]
    area = {
        "kind": "water",
        "bbox": [0.0, 0.0, 0.02, 0.02],
        "parts": [{"ring": outer, "holes": [hole]}],
    }
    assert life_system._terrain_area_distance_m(area, 0.01, 0.01) > 100
    assert life_system._terrain_area_distance_m(area, 0.002, 0.002) < 0


def test_owned_property_legality_includes_the_parcel_radius(monkeypatch):
    monkeypatch.setattr(
        life_system, "_city_profile",
        lambda city_id: {"terrain_areas": [{"kind": "water"}]},
    )
    monkeypatch.setattr(life_system, "_terrain_area_distance_m", lambda area, lat, lng: 36.0)
    record = {"city_id": "hongkong", "lat": 22.3, "lng": 114.17, "area_sqm": 10_000}
    assert life_system._property_coordinate_is_legal(record) is False
    record["area_sqm"] = 4
    assert life_system._property_coordinate_is_legal(record) is True


def test_normalize_state_refreshes_owned_plot_geography_only(monkeypatch):
    parcel = {
        "id": "hongkong:central:residential:0",
        "city_id": "hongkong", "city_name_zh": "香港", "city_name_en": "Hong Kong",
        "district_id": "central", "district_name_zh": "中西区",
        "district_name_en": "Central and Western", "kind": "residential",
        "name_zh": "中西区住宅地块 A", "name_en": "Central and Western Residential Plot A",
        "lat": 22.299199, "lng": 114.175681, "area_sqm": 148,
        "base_price": 30_340_000, "monthly_rent": 78_378.33,
        "monthly_operating_net": 0.0, "parking_spaces": 1,
    }
    pack = {"parcels": [parcel]}
    monkeypatch.setattr(
        life_system, "parcel_entry",
        lambda parcel_id, city_id=None: (pack, parcel) if parcel_id == parcel["id"] else None,
    )
    monkeypatch.setattr(life_system, "load_city_pack", lambda city_id: pack)
    state = life_system._empty_state()
    state["properties"]["property-old"] = {
        "id": "property-old", "parcel_id": parcel["id"], "city_id": "hongkong",
        "city_name_zh": "香港", "city_name_en": "Hong Kong",
        "district_id": "central", "district_name_zh": "中西区",
        "district_name_en": "Central and Western", "kind": "residential",
        "name_zh": "旧地块", "name_en": "Old plot", "lat": 22.29, "lng": 114.169,
        "area_sqm": 120, "base_price": 1_000_000, "purchase_price": 1_234_567,
        "purchase_fees": 30_000, "tenure": "owned", "acquired_day": 10,
        "mode": "rent", "level": 3, "business_type": "", "employees": 0,
        "monthly_rent": 5_000, "monthly_operating_net": 0,
        "income_since_day": 10, "accrued_income": 999.0, "accrued_days": 2,
        "garage_id": "garage-property-old",
    }
    state["garages"]["garage-property-old"] = {
        "id": "garage-property-old", "kind": "property_parking", "category": "property",
        "capacity": 1, "name_zh": "旧车库", "name_en": "Old garage",
        "property_id": "property-old", "city_id": "hongkong",
        "lat": 22.29, "lng": 114.169,
    }
    migrated = life_system.normalize_state(state)
    record = migrated["properties"]["property-old"]
    assert record["parcel_snapshot_version"] == life_system.CITY_PACK_VERSION
    assert (record["lat"], record["lng"]) == (parcel["lat"], parcel["lng"])
    assert record["purchase_price"] == 1_234_567
    assert record["purchase_fees"] == 30_000
    assert record["level"] == 3
    assert record["accrued_income"] == 999.0
    assert record["accrued_days"] == 2
    garage = migrated["garages"]["garage-property-old"]
    assert (garage["lat"], garage["lng"]) == (parcel["lat"], parcel["lng"])


def test_normalize_state_relocates_owned_water_plot_when_parcel_disappears(monkeypatch):
    parcel = {
        "id": "hongkong:central:residential:0",
        "city_id": "hongkong", "city_name_zh": "香港", "city_name_en": "Hong Kong",
        "district_id": "central", "district_name_zh": "中西区",
        "district_name_en": "Central and Western", "kind": "residential",
        "name_zh": "中西区住宅地块 A", "name_en": "Central and Western Residential Plot A",
        "lat": 22.299199, "lng": 114.175681, "area_sqm": 148,
        "base_price": 30_340_000, "monthly_rent": 78_378.33,
        "monthly_operating_net": 0.0, "parking_spaces": 1,
    }
    pack = {"parcels": [parcel]}
    monkeypatch.setattr(life_system, "parcel_entry", lambda parcel_id, city_id=None: None)
    monkeypatch.setattr(life_system, "load_city_pack", lambda city_id: pack)
    state = life_system._empty_state()
    state["properties"]["property-water"] = {
        "id": "property-water", "parcel_id": "hongkong:central:residential:99",
        "city_id": "hongkong", "city_name_zh": "香港", "city_name_en": "Hong Kong",
        "district_id": "central", "district_name_zh": "中西区",
        "district_name_en": "Central and Western", "kind": "residential",
        "name_zh": "旧水岸地块", "name_en": "Old waterfront plot",
        "lat": 22.29, "lng": 114.169, "area_sqm": 120, "base_price": 1_000_000,
        "purchase_price": 1_234_567, "purchase_fees": 30_000, "tenure": "owned",
        "acquired_day": 10, "mode": "rent", "level": 1, "business_type": "",
        "employees": 0, "monthly_rent": 5_000, "monthly_operating_net": 0,
        "income_since_day": 10, "accrued_income": 0.0, "accrued_days": 0,
    }
    migrated = life_system.normalize_state(state)
    record = migrated["properties"]["property-water"]
    assert record["parcel_id"] == parcel["id"]
    assert (record["lat"], record["lng"]) == (parcel["lat"], parcel["lng"])
    assert record["purchase_price"] == 1_234_567


def test_city_type_changes_the_asset_mix():
    industrial_city = next(
        city for city in life_system.city_catalog()["cities"] if city["id"] == "wuhan"
    )
    tourism_city = next(
        city for city in life_system.city_catalog()["cities"] if city["id"] == "hangzhou"
    )
    industrial_pack = life_system.generate_city_pack(industrial_city)
    tourism_pack = life_system.generate_city_pack(tourism_city)
    industrial_counts = {
        kind: sum(1 for row in industrial_pack["parcels"] if row["kind"] == kind)
        for kind in life_system.PARCEL_KINDS
    }
    tourism_counts = {
        kind: sum(1 for row in tourism_pack["parcels"] if row["kind"] == kind)
        for kind in life_system.PARCEL_KINDS
    }
    assert industrial_counts["industrial"] > tourism_counts["industrial"]
    assert tourism_counts["residential"] > industrial_counts["residential"]


def test_map_layer_packs_are_deterministic_and_installable(tmp_path, monkeypatch):
    monkeypatch.setattr(life_system, "LAYER_ROOT", tmp_path / "layers")
    world = life_system.generate_world_layer_pack()
    country = life_system.generate_country_layer_pack()
    city = life_system.generate_city_layer_pack("beijing")
    assert world == life_system.generate_world_layer_pack()
    assert country == life_system.generate_country_layer_pack()
    assert city == life_system.generate_city_layer_pack("beijing")
    assert world["countries"][0]["id"] == "CN"
    assert country["cities"]
    assert city["districts"]

    assert life_system.layer_pack_summary("world")["installed"] is False
    summary = life_system.install_layer_pack("world")
    assert summary["installed"] is True
    assert summary["size_bytes"] > 0
    assert life_system.layer_pack_summary("world")["checksum"] == world["checksum"]


def test_installed_city_layer_repairs_missing_parcel_pack(tmp_path, monkeypatch):
    monkeypatch.setattr(life_system, "LAYER_ROOT", tmp_path / "layers")
    monkeypatch.setattr(life_system, "PACK_ROOT", tmp_path / "packs")
    city = life_system.city_by_id("shantou")
    assert city is not None
    layer_path = life_system._layer_pack_path("city", "shantou")
    layer_path.parent.mkdir(parents=True, exist_ok=True)
    layer_path.write_text(
        json.dumps(life_system.generate_city_layer_pack("shantou")),
        encoding="utf-8",
    )
    assert not life_system._pack_path("shantou").is_file()

    repaired = life_system.repair_installed_city_layer_parcels()

    assert repaired == ["shantou"]
    assert life_system._pack_path("shantou").is_file()
    assert life_system.pack_summary(city)["installed"] is True
    assert life_system.pack_summary(city)["parcels"] > 0


def test_city_layer_download_installs_parcels_immediately(tmp_path, monkeypatch):
    monkeypatch.setattr(life_system, "LAYER_ROOT", tmp_path / "layers")
    monkeypatch.setattr(life_system, "PACK_ROOT", tmp_path / "packs")
    summary = life_system.install_layer_pack("city", city_id="shantou")
    assert summary["installed"] is True
    assert life_system._pack_path("shantou").is_file()

    life_system.install_city_pack("xiamen")
    assert life_system._pack_path("xiamen").is_file()
    assert life_system.layer_pack_summary("city", "xiamen")["installed"] is True


def test_property_aggregates_only_report_owned_asset_totals():
    aggregates = life_system.property_aggregates([
        {
            "city_id": "beijing", "district_id": "chaoyang",
            "district_name_zh": "朝阳", "district_name_en": "Chaoyang",
            "lat": 39.92, "lng": 116.44, "market_value": 12_000_000,
        },
        {
            "city_id": "beijing", "district_id": "chaoyang",
            "district_name_zh": "朝阳", "district_name_en": "Chaoyang",
            "lat": 39.92, "lng": 116.44, "market_value": 8_000_000,
        },
    ])
    beijing = next(row for row in aggregates["country"] if row["id"] == "beijing")
    chaoyang = next(row for row in aggregates["cities"]["beijing"] if row["id"] == "chaoyang")
    assert beijing["asset_count"] == 2
    assert beijing["asset_value"] == 20_000_000
    assert chaoyang["asset_count"] == 2
    assert chaoyang["asset_value"] == 20_000_000
    assert aggregates["world"][0]["asset_count"] == 2


def test_property_aggregates_merge_legacy_district_rows_and_hide_empty_districts():
    aggregates = life_system.property_aggregates([
        {
            "city_id": "beijing", "parcel_id": "beijing:xicheng:garage:1",
            "district_name_zh": "西城", "district_name_en": "Xicheng",
            "lat": 39.91, "lng": 116.36, "market_value": 12_000_000,
        },
        {
            "city_id": "beijing", "parcel_id": "beijing:xicheng:garage:2",
            "district_name_zh": "西城", "district_name_en": "Xicheng",
            "lat": 39.92, "lng": 116.37, "market_value": 8_000_000,
        },
    ])
    xicheng = [row for row in aggregates["cities"]["beijing"] if row["id"] == "xicheng"]
    assert len(xicheng) == 1
    assert xicheng[0]["asset_count"] == 2
    assert xicheng[0]["asset_value"] == 20_000_000
    assert all(int(row["asset_count"]) > 0 for row in aggregates["cities"]["beijing"])


def test_life_map_frontend_locks_trading_and_uses_transparent_contained_images():
    script = (ROOT / "src" / "web" / "life_page.js").read_text(encoding="utf-8")
    styles = (ROOT / "src" / "web" / "life.css").read_text(encoding="utf-8")
    assert "const MIN_ZOOM = 3;" in script
    assert "const MAX_ZOOM = 15;" in script
    assert "const TRADE_MIN_ZOOM = 13;" in script
    assert 'cityId: "", zoom: 13' in script
    assert 'const MAP_PROVIDER_KEY = "fmsdd-life-basemap-v4";' in script
    assert "function effectiveMapProvider()" in script
    assert 'mapProviderMode() === "auto"' in script
    assert 'value="auto"' in script
    assert 'value="bing"' in script
    assert "function bingQuadkey(" in script
    assert "tiles.virtualearth.net" in script
    assert 'country === "CN" ? "amap" : "bing"' in script
    assert 'provider === "amap" || provider === "bing"' in script
    assert "function canTradeMap()" in script
    assert "webrd0${subdomain}.is.autonavi.com" in script
    assert 'saveMapProvider("osm");' not in script
    assert "}, 3000);" in script
    assert 't("life.garage.capacity")' not in script
    assert ".life-vehicle-photo img" in styles
    assert "object-fit: contain" in styles
    assert ".life-vehicle-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));" in styles
    assert "grid-template-columns: minmax(112px, 28%) minmax(0, 1fr)" in styles
    assert ".life-map-marker.owned::after" in styles
    assert "background: linear-gradient(145deg,var(--life-soft-2),var(--life-soft))" in styles
    assert "function renderGaragePage()" in script
    assert "data-life-action=\"sell-vehicle\"" in script
    assert "data-life-action=\"select-garage\"" in script
    assert 'data-map-focus="true"' in script
    assert "state.map.center = {lat:Number(parcel.lat), lng:Number(parcel.lng)};" in script
    assert "state.map.zoom = TRADE_MAX_ZOOM;" in script
    assert "buy-garage" not in script
    assert ".life-garage-workspace" in styles
    assert ".life-parking-bays" in styles
    assert 't("life.garage.parking_spaces")' in script
    assert 't("life.map.buying")' in script
    assert "city_id:parcel.city_id || state.map.cityId" in script


def test_generated_plots_clear_water_and_green_masks_in_dense_water_cities():
    for city_id in ("hongkong", "macau", "shenzhen", "hangzhou", "quanzhou"):
        city = life_system.city_by_id(city_id)
        assert city is not None
        profile = life_system._city_profile(city_id)
        pack = life_system.generate_city_pack(city)
        assert pack["version"] == life_system.CITY_PACK_VERSION
        assert pack["parcels"]
        for parcel in pack["parcels"]:
            radius = max(8.0, math.sqrt(float(parcel["area_sqm"])) * 0.5)
            assert life_system._excluded_distance_m(
                profile,
                float(parcel["lat"]),
                float(parcel["lng"]),
                parcel_radius_m=radius,
                include_green=True,
            ) >= -0.01, parcel["id"]


def test_life_basemap_copy_is_complete_in_every_locale():
    script_path = ROOT / "src" / "web" / "i18n.life.js"
    node_script = f"""
const fs = require('fs');
const vm = require('vm');
global.window = {{}};
vm.runInThisContext(fs.readFileSync({json.dumps(str(script_path))}, 'utf8'));
const messages = window.FMODDI18nModules[0].messages;
const locales = ['en-GB','zh-CN','zh-TW','ko-KR','de-DE','es-ES','fr-FR','ru-RU','ja-JP','pt-BR','pt-PT'];
const keys = ['life.map.basemap_auto','life.map.basemap_bing','life.map.bing_attribution','life.map.basemap_fallback_generic'];
for (const locale of locales) {{
  for (const key of keys) {{
    if (!String(messages[locale]?.[key] || '').trim()) throw new Error(locale + ':' + key);
  }}
}}
console.log('ok');
"""
    result = subprocess.run(
        ["node", "-"], input=node_script, text=True, encoding="utf-8",
        check=True, capture_output=True,
    )
    assert result.stdout.strip() == "ok"


def test_round50_save_collection_and_gacha_delivery_contract():
    index = (ROOT / "src" / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "src" / "web" / "life_page.js").read_text(encoding="utf-8")
    styles = (ROOT / "src" / "web" / "life.css").read_text(encoding="utf-8")
    source = (ROOT / "src" / "tools" / "life_system.py").read_text(encoding="utf-8")

    assert index.count('id="life-collection-dialog"') == 1
    assert '<dialog id="life-collection-dialog"' in index
    assert 'id="life-gacha-collection-open"' in script
    assert 'data-life-action="open-collection"' in script
    assert "state.lastGacha?.draw?.cost" in script
    assert "life.gacha.delivery_cost" in script
    assert "life.gacha.net_value" in script
    assert "car.garage_duplicate" in script
    assert "life.gacha.duplicate_garage" in script
    assert 't("life.gacha.odds_base_note")' not in script
    assert ".life-gacha-delivery-metrics" in styles
    assert ".life-gacha-tool {" in styles
    assert "SCHEMA_VERSION = 9" in source
    assert "COLLECTION_PATH" not in source

    script_path = ROOT / "src" / "web" / "i18n.life.js"
    node_script = f"""
const fs = require('fs');
const vm = require('vm');
global.window = {{}};
vm.runInThisContext(fs.readFileSync({json.dumps(str(script_path))}, 'utf8'));
const messages = window.FMODDI18nModules[0].messages;
const locales = ['en-GB','zh-CN','zh-TW','ko-KR','de-DE','es-ES','fr-FR','ru-RU','ja-JP','pt-BR','pt-PT'];
const keys = ['life.collection.save_scope_short','life.gacha.capacity','life.gacha.delivery_cost','life.gacha.net_value','life.gacha.duplicate_garage','life.garage.sell_confirm'];
for (const locale of locales) {{
  for (const key of keys) {{
    if (!String(messages[locale]?.[key] || '').trim()) throw new Error(locale + ':' + key);
  }}
}}
console.log('ok');
"""
    result = subprocess.run(
        ["node", "-"], input=node_script, text=True, encoding="utf-8",
        check=True, capture_output=True,
    )
    assert result.stdout.strip() == "ok"


def test_round51_collection_close_incremental_draw_and_donut_rule_contract():
    script = (ROOT / "src" / "web" / "life_page.js").read_text(encoding="utf-8")
    styles = (ROOT / "src" / "web" / "life.css").read_text(encoding="utf-8")
    source = (ROOT / "src" / "tools" / "life_system.py").read_text(encoding="utf-8")
    api = (ROOT / "src" / "fm_odds_web.py").read_text(encoding="utf-8")

    assert 'button.closest(".life-page, .life-collection-dialog")' in script
    assert 'dialog.addEventListener("cancel"' in script
    assert 'if (event.target === dialog) close();' in script
    assert "function mergeGachaLifePatch(patch, response)" in script
    assert 't("life.gacha.drawing")' in script
    assert "function gachaGoldCondition(tier)" in script
    assert 't("life.gacha.rule_any_class", {rarities})' in script
    assert 't("life.gacha.rule_or")' in script
    assert "if (state.busy)" in script
    assert "VEHICLE_IMAGE_WARM_CONCURRENCY = 2" in script
    assert ".life-page, .life-collection-dialog {" in styles
    assert ':root[data-theme="dark"] .life-collection-dialog' in styles

    assert '"any_class_rarities": ("donut edition",)' in source
    assert '"life_patch": life_system.gacha_patch(' in api
    collector = next(row for row in life_system.gacha_tiers() if row["id"] == "collector")
    assert collector["gold_rules"] == [
        {"class": "S2", "rarities": ["legendary", "forza edition"]},
        {"class": "", "rarities": ["donut edition"]},
    ]
    donut_cars = [
        car for car in life_system._gacha_tier_cars(life_system.GACHA_TIERS[2])
        if str(car.get("rarity") or "").lower() == "donut edition"
    ]
    assert len(donut_cars) == 1
    assert donut_cars[0]["class"] == "S1"
    assert life_system._gacha_gold_hit(donut_cars[0], "collector") is True

    script_path = ROOT / "src" / "web" / "i18n.life.js"
    node_script = f"""
const fs = require('fs');
const vm = require('vm');
global.window = {{}};
vm.runInThisContext(fs.readFileSync({json.dumps(str(script_path))}, 'utf8'));
const messages = window.FMODDI18nModules[0].messages;
const locales = ['en-GB','zh-CN','zh-TW','ko-KR','de-DE','es-ES','fr-FR','ru-RU','ja-JP','pt-BR','pt-PT'];
const keys = [
  'life.gacha.drawing','life.gacha.rule_any_class','life.gacha.rule_or',
  'life.gacha.result_hint','life.gacha.pity_hint','life.gacha.odds_base_note',
  'life.gacha.odds_soft_note'
];
for (const locale of locales) {{
  for (const key of keys) {{
    if (!String(messages[locale]?.[key] || '').trim()) throw new Error(locale + ':' + key);
  }}
  if (!messages[locale]['life.gacha.pity_hint'].includes('{{condition}}')) throw new Error(locale + ':condition');
  if (messages[locale]['life.gacha.pity_hint'].includes('{{class}}')) throw new Error(locale + ':stale-class');
  if (!messages[locale]['life.gacha.result_hint'].toLowerCase().includes('donut')) throw new Error(locale + ':donut');
  const legendaryTerms = ['legendary','传奇','傳奇','레전더리','legendär','legendario','légendaire','легендарный','レジェンダリー','lendário'];
  const forzaTerms = ['forza','极限竞速','極限競速'];
  for (const key of ['life.gacha.result_hint','life.gacha.odds_base_note']) {{
    const text = messages[locale][key].toLowerCase();
    if (!legendaryTerms.some((term) => text.includes(term))) throw new Error(locale + ':' + key + ':legendary');
    if (!text.includes('s2') || !forzaTerms.some((term) => text.includes(term))) throw new Error(locale + ':' + key + ':collector-rule');
  }}
  if (!messages[locale]['life.gacha.rule_any_class'].includes('{{rarities}}')) throw new Error(locale + ':rarities');
}}
console.log('ok');
"""
    result = subprocess.run(
        ["node", "-"], input=node_script, text=True, encoding="utf-8",
        check=True, capture_output=True,
    )
    assert result.stdout.strip() == "ok"


def test_round53_storage_filters_dialog_polling_and_collector_gold_rule_contract():
    script = (ROOT / "src" / "web" / "life_page.js").read_text(encoding="utf-8")
    styles = (ROOT / "src" / "web" / "life.css").read_text(encoding="utf-8")

    assert "const LIFE_DIALOG_IDS = Object.freeze([" in script
    assert "function anyLifeDialogOpen()" in script
    assert "if (anyLifeDialogOpen()) return;" in script
    assert 'data-life-storage-filter="manufacturer"' in script
    assert 'data-life-storage-search' in script
    assert 'state.storage.rarity === "special"' in script
    assert 'if (action === "storage-select-all") {\n      const vehicles = filteredStorageVehicles();' in script
    assert ".life-storage-photo .life-class-badge {" in styles
    assert ".life-class-badge.is-inline { position: relative;" in styles
    assert ".life-storage-filterbar {" in styles
    assert ".life-gacha-delivery-head {" in styles or ".life-gacha-results > header {" in styles

    assert life_system._gacha_gold_hit(
        {"class": "S2", "rarity": "legendary"}, "collector",
    ) is True
    assert life_system._gacha_gold_hit(
        {"class": "S1", "rarity": "legendary"}, "collector",
    ) is False
    assert life_system._gacha_gold_hit(
        {"class": "D", "rarity": "donut edition"}, "collector",
    ) is True


def test_public_life_passes_the_selected_manager_to_the_view(monkeypatch):
    service = web.LocalOddsState.__new__(web.LocalOddsState)
    service._life_context = lambda: ("scope", "2026-01-11", 11, 77)
    service._life_state = lambda _scope, _day: life_system._empty_state()
    seen = {}

    def view(_state, **kwargs):
        seen.update(kwargs)
        return {"ok": True}

    service._life_view = view
    monkeypatch.setattr(web, "public_economy", lambda: {"balance": 1})

    assert service.public_life() == {"ok": True, "economy": {"balance": 1}}
    assert seen["manager_id"] == 77


def test_buying_a_plot_keeps_parcel_kind_out_of_the_charge_kind(monkeypatch):
    city = life_system.city_catalog()["cities"][0]
    pack = life_system.generate_city_pack(city)
    parcel = pack["parcels"][0]
    state = life_system._empty_state()
    service = web.LocalOddsState.__new__(web.LocalOddsState)
    service._life_context = lambda: ("scope", "2026-01-11", 11, 77)
    service._life_state = lambda _scope, _day: state
    service._life_view = lambda _state, **_kwargs: {}
    monkeypatch.setattr(
        life_system, "parcel_index",
        lambda: {str(parcel["id"]): (pack, parcel)},
    )
    monkeypatch.setattr(life_system, "save_state", lambda _value, _scope: None)
    monkeypatch.setattr(web, "public_economy", lambda: {})
    calls = []

    def charge(amount, kind, *, allow_bank_overdraft=False, **details):
        calls.append((amount, kind, allow_bank_overdraft, details))
        return {"bank": amount, "wallet": 0.0, "total": amount}

    monkeypatch.setattr(web, "charge_combined_funds", charge)
    response = service.buy_life_property({"parcel_id": parcel["id"]})

    assert response["ok"] is True
    assert calls and calls[0][1] == "life_property_buy"
    assert calls[0][3]["parcel_kind"] == parcel["kind"]
    assert "kind" not in calls[0][3]
    assert response["property"]["parcel_id"] == parcel["id"]


def test_buying_a_plot_with_a_city_hint_avoids_the_global_parcel_index(monkeypatch):
    city = life_system.city_catalog()["cities"][0]
    pack = life_system.generate_city_pack(city)
    parcel = pack["parcels"][0]
    state = life_system._empty_state()
    service = web.LocalOddsState.__new__(web.LocalOddsState)
    service._life_context = lambda: ("scope", "2026-01-11", 11, 77)
    service._life_state = lambda _scope, _day: state
    service._life_view = lambda _state, **_kwargs: {}
    monkeypatch.setattr(life_system, "load_city_pack", lambda city_id: pack if city_id == city["id"] else None)
    monkeypatch.setattr(
        life_system, "parcel_index",
        lambda: (_ for _ in ()).throw(AssertionError("global parcel index must not be scanned")),
    )
    monkeypatch.setattr(life_system, "save_state", lambda _value, _scope: None)
    monkeypatch.setattr(web, "public_economy", lambda: {})
    monkeypatch.setattr(
        web, "charge_combined_funds",
        lambda amount, *_args, **_kwargs: {"bank": amount, "wallet": 0.0, "total": amount},
    )

    response = service.buy_life_property({"parcel_id": parcel["id"], "city_id": city["id"]})

    assert response["ok"] is True
    assert response["property"]["parcel_id"] == parcel["id"]


def test_city_pack_cache_reuses_an_unchanged_file(monkeypatch, tmp_path):
    city = life_system.city_catalog()["cities"][0]
    pack = life_system.generate_city_pack(city)
    path = tmp_path / f"{city['id']}.json"
    path.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
    loads = []
    original = life_system._read_json
    monkeypatch.setattr(life_system, "_pack_path", lambda _city_id: path)
    monkeypatch.setattr(
        life_system, "_read_json",
        lambda target: loads.append(target) or original(target),
    )
    life_system._CITY_PACK_CACHE.clear()

    first = life_system.load_city_pack(city["id"])
    second = life_system.load_city_pack(city["id"])

    assert first is second
    assert len(loads) == 1


def test_selling_property_includes_accrued_income():
    state = life_system._empty_state()
    state["income_settled_day"] = 100
    city = life_system.city_catalog()["cities"][0]
    parcel = life_system.generate_city_pack(city)["parcels"][0]
    plan = life_system.buy_property_plan(state, parcel, 100)
    record = life_system.commit_buy_property(state, plan, 100)
    sale = life_system.sell_property_plan(state, record["id"], 110)
    expected_income = round_money(life_system._daily_income(record) * 10)
    assert sale["pending_days"] == 10
    assert sale["pending_income"] == expected_income
    assert sale["credit"] == round_money(sale["net"] + expected_income)


def test_gacha_requires_free_slots_and_keeps_every_duplicate():
    state = life_system._empty_state()
    tier = life_system.gacha_tiers()[0]
    try:
        life_system.gacha_plan(state, tier["id"], 10, "club", 200, "seed")
    except ValueError as error:
        assert "车库车位不足" in str(error)
    else:
        raise AssertionError("ten draws must not fit into the two home spaces")
    state["garages"]["garage-lot"] = {
        "id": "garage-lot", "kind": "standalone", "category": "standalone", "capacity": 20,
        "purchase_price": 15_000_000, "acquired_day": 200,
    }
    plan = life_system.gacha_plan(state, tier["id"], 10, "garage-lot", 200, "seed")
    records = life_system.commit_gacha(state, plan, 200)
    assert len(records) == 10
    assert len({row["id"] for row in records}) == 10
    assert len(state["vehicles"]) == 10


def test_collection_is_save_scoped_and_counts_duplicates_without_converting_them():
    state = life_system._empty_state()
    other_save = life_system._empty_state()
    record = {
        "catalog_id": "car-16", "name": "Aston Martin DB11",
        "manufacturer": "Aston Martin", "class": "A", "rarity": "epic",
        "year": 2017, "image": "/assets/life/cars/car-16.jpg", "source": "dealer",
    }
    life_system.record_collection(state, [record], day=1)
    view = life_system.record_collection(state, [record], day=2)
    assert view["summary"]["unique"] == 1
    assert view["summary"]["total"] == 2
    assert view["cars"][0]["count"] == 2
    assert view["cars"][0]["sources"] == {"dealer": 2}
    assert view["cars"][0]["image"].endswith("car-16.webp")
    assert life_system.collection_view(other_save)["summary"]["unique"] == 0


def test_legacy_save_builds_collection_from_its_existing_vehicles():
    legacy = life_system._empty_state()
    legacy.pop("collection")
    legacy["vehicles"]["vehicle-000001"] = {
        "id": "vehicle-000001", "catalog_id": "car-16", "name": "Aston Martin DB11",
        "manufacturer": "Aston Martin", "class": "A", "rarity": "epic",
        "year": 2017, "image": "/assets/life/cars/car-16.jpg", "source": "gacha",
        "purchase_day": 42, "garage_id": "club",
    }
    migrated = life_system.normalize_state(legacy)
    assert migrated["schema_version"] == life_system.SCHEMA_VERSION == 9
    assert migrated["collection"]["cars"]["car-16"]["count"] == 1
    assert migrated["collection"]["cars"]["car-16"]["last_acquired_day"] == 42


def test_property_purchase_creates_typed_parking_and_blocks_sale_while_occupied():
    state = life_system._empty_state()
    state["income_settled_day"] = 100
    city = life_system.city_catalog()["cities"][0]
    pack = life_system.generate_city_pack(city)
    expected = {"residential": 1, "commercial": 2, "industrial": 4}
    for kind, capacity in expected.items():
        parcel = next(row for row in pack["parcels"] if row["kind"] == kind)
        plan = life_system.buy_property_plan(state, parcel, 100)
        record = life_system.commit_buy_property(state, plan, 100)
        garage = state["garages"][record["garage_id"]]
        assert garage["capacity"] == capacity
        assert record["parking_spaces"] == capacity

    garage_parcel = next(row for row in pack["parcels"] if row["kind"] == "garage")
    garage_plan = life_system.buy_property_plan(state, garage_parcel, 100)
    garage_record = life_system.commit_buy_property(state, garage_plan, 100)
    assert garage_record["parking_spaces"] >= 8
    assert state["garages"][garage_record["garage_id"]]["category"] == "standalone"

    car = life_system.car_by_id("car-16")
    vehicle_plan = life_system.buy_vehicle_plan(
        state, car, garage_record["garage_id"], 100,
    )
    life_system.commit_buy_vehicle(state, vehicle_plan, 100)
    try:
        life_system.sell_property_plan(state, garage_record["id"], 101)
    except ValueError as error:
        assert "迁移" in str(error)
    else:
        raise AssertionError("an occupied garage asset must not be sellable")


def test_normalize_state_migrates_legacy_home_and_vehicle_images():
    legacy = {
        "schema_version": 1,
        "seq": 1,
        "garages": {
            "home": {
                "id": "home", "kind": "home", "capacity": 2,
                "purchase_price": 0, "acquired_day": None,
            },
            "apartment": {
                "id": "apartment", "kind": "apartment", "capacity": 2,
                "purchase_price": 500_000, "acquired_day": 1,
            },
            "premium": {
                "id": "premium", "kind": "premium", "capacity": 6,
                "purchase_price": 3_000_000, "acquired_day": 1,
            },
        },
        "properties": {
            "property-000001": {
                "id": "property-000001", "kind": "residential",
                "area_sqm": 120, "acquired_day": 1,
            },
        },
        "vehicles": {
            "vehicle-000001": {
                "id": "vehicle-000001", "catalog_id": "car-16",
                "garage_id": "home", "image": "/assets/life/cars/car-16.jpg",
                "purchase_day": 1, "base_price": 100_000, "condition": 1.0,
            },
        },
        "gacha": {}, "income_settled_day": 1, "income_lifetime": 0,
        "income_history": [], "activity": [],
    }
    state = life_system.normalize_state(legacy)
    assert "home" not in state["garages"]
    assert state["garages"]["club"]["capacity"] == 2
    assert state["vehicles"]["vehicle-000001"]["garage_id"] == "club"
    assert state["vehicles"]["vehicle-000001"]["image"].endswith("car-16.webp")
    assert state["garages"]["apartment"]["category"] == "legacy"
    assert state["garages"]["premium"]["category"] == "legacy"
    parking = state["garages"][state["properties"]["property-000001"]["garage_id"]]
    assert state["properties"]["property-000001"]["parking_spaces"] == 1
    assert parking["category"] == "property"


def test_vehicle_sell_plan_removes_save_vehicle_and_applies_fee():
    state = life_system._empty_state()
    car = life_system.car_by_id("car-16")
    plan = life_system.buy_vehicle_plan(state, car, "club", 10)
    vehicle = life_system.commit_buy_vehicle(state, plan, 10)
    sale = life_system.sell_vehicle_plan(state, vehicle["id"], 20)
    assert sale["fee"] == round_money(sale["value"] * life_system.SELL_FEE_RATE)
    assert sale["net"] == round_money(sale["value"] - sale["fee"])
    life_system.commit_sell_vehicle(state, sale, 20)
    assert vehicle["id"] not in state["vehicles"]


def test_vehicle_sale_api_credits_bank_and_restores_on_bank_failure(monkeypatch):
    state = life_system._empty_state()
    car = life_system.car_by_id("car-16")
    plan = life_system.buy_vehicle_plan(state, car, "club", 10)
    vehicle = life_system.commit_buy_vehicle(state, plan, 10)

    service = web.LocalOddsState.__new__(web.LocalOddsState)
    service._life_context = lambda: ("scope", "2026-01-11", 11, 77)
    service._life_state = lambda _scope, _day: state
    service._life_view = lambda _state, **_kwargs: {}
    saved = []
    monkeypatch.setattr(
        life_system, "save_state",
        lambda value, _scope: saved.append(value),
    )

    credits = []
    monkeypatch.setattr(
        web, "adjust_bank_balance",
        lambda amount, kind, **metadata: credits.append((amount, kind, metadata)) or {"balance": amount},
    )
    response = service.sell_life_vehicle({"vehicle_id": vehicle["id"]})

    assert credits
    assert credits[0][0] == response["sale"]["net"]
    assert credits[0][1] == "life_vehicle_sell"
    assert vehicle["id"] not in saved[-1]["vehicles"]

    restored_state = life_system._empty_state()
    restored_plan = life_system.buy_vehicle_plan(restored_state, car, "club", 10)
    restored_vehicle = life_system.commit_buy_vehicle(restored_state, restored_plan, 10)
    service._life_state = lambda _scope, _day: restored_state
    saved.clear()

    def reject_credit(*_args, **_kwargs):
        raise RuntimeError("bank unavailable")

    monkeypatch.setattr(web, "adjust_bank_balance", reject_credit)
    try:
        service.sell_life_vehicle({"vehicle_id": restored_vehicle["id"]})
    except RuntimeError as error:
        assert str(error) == "bank unavailable"
    else:
        raise AssertionError("a failed bank credit must abort the sale")
    assert restored_vehicle["id"] in saved[-1]["vehicles"]


def _buy_first_property(state, kind, day, city_id="beijing"):
    city = life_system.city_by_id(city_id)
    assert city is not None
    parcel = next(
        row for row in life_system.generate_city_pack(city)["parcels"]
        if row["kind"] == kind
    )
    plan = life_system.buy_property_plan(state, parcel, day)
    return life_system.commit_buy_property(state, plan, day)


def test_life_city_catalog_expands_to_new_china_and_global_cities():
    catalog = life_system.city_catalog()
    cities = {str(city["id"]): city for city in catalog["cities"]}
    expected_china = {
        "beijing", "shanghai", "guangzhou", "shenzhen", "chengdu", "hangzhou",
        "wuhan", "nanjing", "hongkong", "macau", "shantou", "xiamen", "quanzhou",
        "fuzhou", "ningbo", "suzhou", "qingdao", "jinan", "tianjin", "xian",
        "chongqing", "guiyang", "kunming", "nanning", "shenyang", "changchun",
        "harbin", "dalian", "changsha", "taiyuan", "shijiazhuang", "hohhot",
        "yinchuan", "zhengzhou", "lanzhou", "xining", "nanchang", "yueyang",
        "hengyang", "guilin", "haikou", "sanya", "taipei", "kaohsiung",
        "lhasa", "urumqi", "beihai",
    }
    assert len(cities) == 68
    assert expected_china <= set(cities)
    assert {
        "london", "manchester", "liverpool", "birmingham", "wales",
        "paris", "berlin", "munich", "stuttgart", "frankfurt", "hanover",
        "hamburg", "dusseldorf", "madrid", "brussels", "amsterdam",
        "tokyo", "nagoya", "osaka", "seoul", "busan",
    } <= set(cities)
    assert {str(cities[city_id]["country"]) for city_id in expected_china} == {"CN"}

    countries = {
        str(country["code"]): country for country in life_system.country_catalogs()
    }
    assert set(countries) == {"CN", "GB", "FR", "DE", "ES", "BE", "NL", "JP", "KR"}
    assert len(countries["CN"]["cities"]) == 47
    for code, country in countries.items():
        assert country["cities"]
        assert all(
            str(cities[str(row["id"])]["country"]) == code
            for row in country["cities"]
        )
    assert sum(len(country["cities"]) for country in countries.values()) == 68

    for city in catalog["cities"]:
        profile = life_system._city_profile(str(city["id"]))
        assert int(profile.get("tier") or 0) in {1, 2, 3, 4}
        assert profile.get("city_type")
        first = life_system.generate_city_pack(city)
        second = life_system.generate_city_pack(city)
        assert first["checksum"] == second["checksum"]
        assert str(first["country"]) in {"CN", "GB", "FR", "DE", "ES", "BE", "NL", "JP", "KR"}
        assert any(row["kind"] == "industrial" for row in first["parcels"])


def test_country_layer_packs_are_scoped_and_aggregates_keep_country_totals(tmp_path, monkeypatch):
    monkeypatch.setattr(life_system, "LAYER_ROOT", tmp_path / "layers")
    world = life_system.generate_world_layer_pack()
    assert {row["id"] for row in world["countries"]} == {"CN", "GB", "FR", "DE", "ES", "BE", "NL", "JP", "KR"}

    for code, city_id in (
        ("CN", "beijing"), ("GB", "london"), ("FR", "paris"), ("DE", "berlin"),
        ("ES", "madrid"), ("BE", "brussels"), ("NL", "amsterdam"),
        ("JP", "tokyo"), ("KR", "seoul"),
    ):
        payload = life_system.generate_country_layer_pack(code)
        assert payload["country"] == code
        assert city_id in {str(row["id"]) for row in payload["cities"]}
        summary = life_system.install_layer_pack("country", country_code=code)
        assert summary["installed"] is True
        assert summary["country"] == code

    summaries = life_system.layer_pack_summaries()
    assert all(summaries["countries"][code]["installed"] for code in ("CN", "GB", "FR", "DE", "ES", "BE", "NL", "JP", "KR"))

    aggregates = life_system.property_aggregates([
        {"city_id": "beijing", "district_id": "chaoyang", "market_value": 10_000_000},
        {"city_id": "london", "district_id": "city", "market_value": 20_000_000},
    ])
    assert next(row for row in aggregates["world"] if row["id"] == "GB")["asset_value"] == 20_000_000
    assert next(row for row in aggregates["countries"]["CN"] if row["id"] == "beijing")["asset_count"] == 1
    assert next(row for row in aggregates["countries"]["GB"] if row["id"] == "london")["asset_value"] == 20_000_000


def test_legacy_life_state_migrates_property_income_fields():
    legacy = life_system._empty_state()
    legacy["schema_version"] = 2
    legacy["properties"] = {
        "property-legacy": {
            "id": "property-legacy", "kind": "residential", "city_id": "beijing",
            "district_id": "chaoyang", "base_price": 2_000_000,
            "acquired_day": 10, "monthly_rent": 8_000,
        },
        "commercial-legacy": {
            "id": "commercial-legacy", "kind": "commercial", "city_id": "london",
            "district_id": "city", "base_price": 4_000_000,
            "acquired_day": 10, "monthly_operating_net": 20_000,
        },
    }
    migrated = life_system.normalize_state(legacy)
    residential = migrated["properties"]["property-legacy"]
    commercial = migrated["properties"]["commercial-legacy"]
    assert migrated["schema_version"] == life_system.SCHEMA_VERSION == 9
    assert residential["mode"] == "rent"
    assert residential["level"] == 1
    assert residential["income_since_day"] == 10
    assert residential["accrued_income"] == 0
    assert commercial["mode"] == "rent"
    assert commercial["business_type"] == life_system.BUSINESS_CATALOG["commercial"][0]["id"]
    assert commercial["country"] == "GB"


def test_residential_self_use_and_upgrade_change_income():
    state = life_system._empty_state()
    property_record = _buy_first_property(state, "residential", 100)
    renting = life_system.property_income_breakdown(property_record)
    assert renting["daily_income"] > 0

    self_used = life_system.configure_property(state, property_record["id"], 100, mode="self")
    assert self_used["mode"] == "self"
    assert self_used["monthly_income"] == 0
    assert self_used["daily_income"] == 0

    plan = life_system.property_upgrade_plan(state, property_record["id"], 101)
    assert plan["cost"] > 0
    upgraded = life_system.commit_property_upgrade(state, plan, 101)
    assert upgraded["level"] == 1
    assert upgraded["construction"]["kind"] == "upgrade"
    assert upgraded["monthly_income"] == 0
    assert upgraded["daily_income"] == 0

    completion_day = int(upgraded["construction"]["end_day"])
    assert life_system.advance_lifecycle(state, completion_day)
    completed = state["properties"][property_record["id"]]
    assert completed["level"] == 2
    assert "construction" not in completed

    life_system.configure_property(state, property_record["id"], completion_day, mode="rent")
    rent_upgraded = life_system.property_income_breakdown(state["properties"][property_record["id"]])
    assert rent_upgraded["daily_income"] > renting["daily_income"]


def test_property_purchase_persists_the_parcel_district():
    state = life_system._empty_state()
    city = life_system.city_by_id("beijing")
    parcel = next(
        row for row in life_system.generate_city_pack(city)["parcels"]
        if row["kind"] == "garage"
    )
    plan = life_system.buy_property_plan(state, parcel, 110)
    record = life_system.commit_buy_property(state, plan, 110)
    assert record["district_id"] == parcel["district_id"]
    assert record["district_name_zh"] == parcel["district_name_zh"]


def test_property_upgrade_has_a_meaningful_income_gain():
    state = life_system._empty_state()
    property_record = _buy_first_property(state, "residential", 120)
    level_one = life_system.property_income_breakdown(property_record)
    property_record["level"] = life_system.MAX_PROPERTY_LEVEL
    level_five = life_system.property_income_breakdown(property_record)
    assert life_system.PROPERTY_LEVEL_RENT_BONUS >= 0.20
    assert life_system.PROPERTY_LEVEL_OPERATE_BONUS >= 0.18
    assert level_five["monthly_income"] / level_one["monthly_income"] >= 1.75


def test_managed_property_staffing_and_business_type_change_net_income():
    for kind in ("commercial", "industrial"):
        state = life_system._empty_state()
        property_record = _buy_first_property(state, kind, 200)
        assert property_record["mode"] == "vacant"
        minimum = life_system.property_income_breakdown(property_record)
        optimal_employees = int(minimum["employee_optimal"])
        maximum_employees = int(minimum["employee_max"])
        assert minimum["employee_min"] > 0
        assert optimal_employees > minimum["employee_min"]
        assert minimum["monthly_income"] == 0

        try:
            life_system.configure_property(state, property_record["id"], 200, mode="operate")
        except ValueError as error:
            assert "经营筹备" in str(error)
        else:
            raise AssertionError("starting a business must require a setup project")

        setup = life_system.property_business_plan(
            state, property_record["id"], 200,
            str(life_system.BUSINESS_CATALOG[kind][0]["id"]), employees=optimal_employees,
        )
        assert setup["cost"] > 0
        assert setup["duration_days"] >= 3
        life_system.commit_property_business(state, setup, 200)
        started = state["properties"][property_record["id"]]
        assert started["construction"]["kind"] == "business_setup"
        assert started["mode"] == "vacant"
        assert life_system.property_income_breakdown(started)["monthly_income"] == 0
        ready_day = int(started["construction"]["end_day"])
        assert life_system.advance_lifecycle(state, ready_day)
        optimal = state["properties"][property_record["id"]]
        assert optimal["mode"] == "operate"
        optimal_income = life_system.property_income_breakdown(optimal)
        assert optimal_income["monthly_income"] > 0

        overstaffed = life_system.configure_property(
            state, property_record["id"], ready_day,
            mode="operate", employees=maximum_employees,
        )
        overstaffed_income = life_system.property_income_breakdown(overstaffed)
        assert optimal_income["monthly_income"] > minimum["monthly_income"]
        assert optimal_income["monthly_income"] > overstaffed_income["monthly_income"]

        alternate_business = str(life_system.BUSINESS_CATALOG[kind][-1]["id"])
        change_plan = life_system.property_business_plan(
            state, property_record["id"], ready_day,
            alternate_business, employees=optimal_employees,
        )
        life_system.commit_property_business(state, change_plan, ready_day)
        changed_day = int(state["properties"][property_record["id"]]["construction"]["end_day"])
        assert life_system.advance_lifecycle(state, changed_day)
        changed = state["properties"][property_record["id"]]
        changed_income = life_system.property_income_breakdown(changed)
        assert changed_income["business_type"] == alternate_business
        assert changed_income["monthly_gross"] != optimal_income["monthly_gross"]


def test_rented_garage_loses_parking_capacity_and_generates_income():
    state = life_system._empty_state()
    garage = _buy_first_property(state, "garage", 300)
    garage_id = str(garage["garage_id"])
    assert garage["parking_spaces"] > 0
    state["vehicles"]["vehicle-parked"] = {
        "id": "vehicle-parked", "garage_id": garage_id,
    }
    try:
        life_system.configure_property(state, garage["id"], 300, mode="rent")
    except ValueError as error:
        assert "迁移" in str(error)
    else:
        raise AssertionError("an occupied garage must not be leased out")
    assert state["properties"][garage["id"]]["mode"] == "self"

    state["vehicles"].pop("vehicle-parked")
    leased = life_system.configure_property(state, garage["id"], 300, mode="rent")
    assert leased["monthly_income"] > 0
    row = next(item for item in life_system._garage_rows(state) if item["id"] == garage_id)
    assert row["rented"] is True
    assert row["free"] == 0
    try:
        life_system._allocate_garage_slots(state, garage_id, 1)
    except ValueError as error:
        assert "车位不足" in str(error)
    else:
        raise AssertionError("a leased garage must not provide parking slots")


def test_property_reconfiguration_keeps_accrued_income_segments():
    state = life_system._empty_state()
    property_record = _buy_first_property(state, "residential", 400)
    daily_income = float(life_system.property_income_breakdown(property_record)["daily_income"])
    configured = life_system.configure_property(state, property_record["id"], 410, mode="self")
    assert configured["accrued_days"] == 10
    assert configured["accrued_income"] == round_money(daily_income * 10)
    assert life_system.collect_income_plan(state, 410)["amount"] == configured["accrued_income"]

    changed_again = life_system.configure_property(state, property_record["id"], 410, mode="rent")
    assert changed_again["accrued_income"] == configured["accrued_income"]
    assert life_system.collect_income_plan(state, 410)["amount"] == configured["accrued_income"]


def test_property_upgrade_refunds_payment_when_commit_fails(monkeypatch):
    state = life_system._empty_state()
    property_record = _buy_first_property(state, "residential", 500)
    service = web.LocalOddsState.__new__(web.LocalOddsState)
    service._life_context = lambda: ("scope", "2026-01-11", 500, 77)
    service._life_state = lambda _scope, _day: state
    service._life_view = lambda _state, **_kwargs: {}
    payment = {"bank": 10_000.0, "wallet": 0.0, "total": 10_000.0}
    refunds = []
    monkeypatch.setattr(web, "charge_combined_funds", lambda *_args, **_kwargs: payment)
    monkeypatch.setattr(
        web, "refund_combined_funds",
        lambda amount, kind, **metadata: refunds.append((amount, kind, metadata)),
    )

    def fail_commit(*_args, **_kwargs):
        raise RuntimeError("upgrade commit failed")

    monkeypatch.setattr(life_system, "commit_property_upgrade", fail_commit)
    try:
        service.upgrade_life_property({"asset_id": property_record["id"]})
    except RuntimeError as error:
        assert str(error) == "upgrade commit failed"
    else:
        raise AssertionError("a failed upgrade commit must abort the purchase")
    assert refunds and refunds[0][0] == payment
    assert refunds[0][1] == "life_property_upgrade_rollback"


def test_property_lease_deposit_renewal_expiry_and_release():
    state = life_system._empty_state()
    city = life_system.city_by_id("beijing")
    parcel = next(
        row for row in life_system.generate_city_pack(city)["parcels"]
        if row["kind"] == "residential"
    )
    quote = life_system.lease_quote(parcel, 90)
    assert quote["prepaid_rent"] == round_money(quote["monthly_rent"] * 3)
    assert quote["deposit"] == round_money(quote["monthly_rent"] * 1.5)
    assert quote["total"] == round_money(quote["prepaid_rent"] + quote["deposit"])

    plan = life_system.lease_property_plan(state, parcel, 600, 90)
    record = life_system.commit_lease_property(state, plan, 600)
    assert record["tenure"] == "lease"
    assert record["mode"] == "self"
    assert record["lease"]["status"] == "active"
    assert record["lease"]["end_day"] == 690
    assert life_system.property_income_breakdown(record)["monthly_income"] == 0
    try:
        life_system.sell_property_plan(state, record["id"], 610)
    except ValueError as error:
        assert "租赁资产不能出售" in str(error)
    else:
        raise AssertionError("a leased asset must not be sold")

    renewal = life_system.lease_renewal_plan(state, record["id"], 620, 30)
    assert renewal["new_start_day"] == 690
    assert renewal["new_end_day"] == 720
    renewed = life_system.commit_lease_renewal(state, renewal, 620)
    assert renewed["lease"]["renewals"] == 1
    assert renewed["lease"]["end_day"] == 720
    assert life_system.advance_lifecycle(state, 721)
    expired = state["properties"][record["id"]]
    assert expired["lease"]["status"] == "expired"
    assert expired["monthly_income"] == 0

    release = life_system.release_lease_plan(state, record["id"], 722)
    assert release["deposit_refund"] == quote["deposit"]
    released = life_system.commit_release_lease(state, release, 722)
    assert released["lease"]["status"] == "terminated"
    assert record["id"] not in state["properties"]
    assert record["garage_id"] not in state["garages"]


def test_leased_property_is_not_counted_as_owned_net_worth():
    state = life_system._empty_state()
    city = life_system.city_by_id("beijing")
    parcel = next(
        row for row in life_system.generate_city_pack(city)["parcels"]
        if row["kind"] == "residential"
    )
    plan = life_system.lease_property_plan(state, parcel, 730, 30)
    life_system.commit_lease_property(state, plan, 730)
    view = life_system.public_view(state, game_date=date.fromordinal(731).isoformat())
    assert view["totals"]["properties"] == 1
    assert view["totals"]["owned_properties"] == 0
    assert view["totals"]["leased_properties"] == 1
    assert view["totals"]["property_value"] == 0
    assert view["totals"]["net_worth"] == 0
    assert view["properties"][0]["lease_days_remaining"] > 0


def test_construction_blocks_repeat_work_and_resumes_income_by_game_day():
    state = life_system._empty_state()
    record = _buy_first_property(state, "residential", 800)
    plan = life_system.property_upgrade_plan(state, record["id"], 800)
    started = life_system.commit_property_upgrade(state, plan, 800)
    assert started["daily_income"] == 0
    assert started["construction"]["duration_days"] == plan["duration_days"]
    try:
        life_system.property_upgrade_plan(state, record["id"], 801)
    except ValueError as error:
        assert "工程" in str(error)
    else:
        raise AssertionError("a second project must not start during construction")

    end_day = int(started["construction"]["end_day"])
    assert not life_system.advance_lifecycle(state, end_day - 1)
    assert "construction" in state["properties"][record["id"]]
    assert life_system.advance_lifecycle(state, end_day)
    completed = state["properties"][record["id"]]
    assert "construction" not in completed
    assert completed["level"] == plan["to_level"]
    life_system.configure_property(state, record["id"], end_day, mode="rent")
    assert life_system.property_income_breakdown(
        state["properties"][record["id"]], as_of_day=end_day + 1,
    )["daily_income"] > 0


def test_life_property_frontend_exposes_country_and_management_controls():
    script = (ROOT / "src" / "web" / "life_page.js").read_text(encoding="utf-8")
    styles = (ROOT / "src" / "web" / "life.css").read_text(encoding="utf-8")
    translations = (ROOT / "src" / "web" / "i18n.life.js").read_text(encoding="utf-8")
    assert "data-life-map-country" in script
    assert "function selectMapCountry(countryCode)" in script
    assert 'state.map.countryCode === "CN" ? state.packs?.layers?.country : null' in script
    assert "/api/life/property/configure" in script
    assert "/api/life/property/upgrade" in script
    assert "/api/life/property/lease" in script
    assert "/api/life/property/renew-lease" in script
    assert "/api/life/property/release-lease" in script
    assert 'data-life-action="property-mode"' in script
    assert 'data-life-action="save-property-config"' in script
    assert 'data-life-action="lease-plot"' in script
    assert 'data-life-action="asset-filter"' in script
    assert "data-life-lease-days" in script
    assert 'data-life-action="upgrade-property"' in script
    assert "function propertyModeLabel(mode)" in script
    assert "function confirmBusinessConfiguration(property, card)" in script
    assert '"life.properties.mode_self": "Owner use"' in translations
    assert '"nav.life_properties": "我的资产"' in translations
    assert '"life.map.lease_confirm"' in translations
    assert ".life-property-config" in styles
    assert ".life-config-fields" in styles
    assert ".life-config-submit" in styles
    assert ".life-property-actions" in styles
    assert ".life-property-deed" in styles
    assert ".life-asset-filter" in styles
    assert ".life-construction-panel" in styles
    assert ".life-lease-panel" in styles
    assert ".life-map-purchase-grid" in styles
    assert ".life-income-breakdown" in styles
    assert ".life-map-country-field" in styles
    assert "const daily = Number(income.daily_income" in script
    assert 'class="daily"' in script
    assert "Monthly gross revenue" in translations
    assert "月营业额（税前）" in translations
    assert "font-size: 13px" in styles


def test_vehicle_pricing_puts_rarity_first_and_locks_legendary_showroom_cars():
    catalog = life_system.car_catalog()
    cars = catalog["cars"]
    assert catalog["pricing_model"] == "rarity-class-v2"
    assert catalog["schema_version"] >= 2
    assert all(int(car["source_price"]) > 0 for car in cars)

    by_rarity = {}
    for car in cars:
        by_rarity.setdefault(str(car["rarity"]).lower(), []).append(int(car["price"]))
    assert min(by_rarity["legendary"]) >= life_system.RARITY_PRICE_FLOORS["legendary"]
    assert min(by_rarity["forza edition"]) >= life_system.RARITY_PRICE_FLOORS["forza edition"]
    assert min(by_rarity["donut edition"]) >= life_system.RARITY_PRICE_FLOORS["donut edition"]

    ordered = ("common", "rare", "epic", "legendary")
    for car_class in ("D", "C", "B", "A", "S1", "S2"):
        medians = []
        for rarity in ordered:
            prices = sorted(
                int(car["price"]) for car in cars
                if str(car["class"]) == car_class and str(car["rarity"]).lower() == rarity
            )
            if prices:
                medians.append(prices[len(prices) // 2])
        assert medians == sorted(medians), (car_class, medians)

    display_only = [car for car in cars if car["dealer_status"] == "display_only"]
    assert len(display_only) == 106
    assert {str(car["rarity"]).lower() for car in display_only} == {
        "legendary", "forza edition", "donut edition",
    }
    assert all(
        car["dealer_status"] == "display_only"
        for car in cars
        if str(car["rarity"]).lower() in life_system.DEALER_DISPLAY_ONLY_RARITIES
    )


def test_vehicle_dealer_rejects_a_display_only_catalog_model():
    car = next(
        row for row in life_system.car_catalog()["cars"]
        if row["dealer_status"] == "display_only"
    )
    state = life_system._empty_state()
    try:
        life_system.buy_vehicle_plan(state, car, "club", 100)
    except ValueError as error:
        assert "展厅陈列" in str(error)
    else:
        raise AssertionError("display-only vehicles must not reach a purchase plan")


def test_collector_gacha_publishes_probabilities_and_curbs_top_tier_results():
    tiers = {tier["id"]: tier for tier in life_system.gacha_tiers()}
    street = tiers["street"]
    performance = tiers["performance"]
    collector = tiers["collector"]
    assert (street["ticket_price"], street["ten_ticket_price"]) == (500_000, 4_000_000)
    assert (performance["ticket_price"], performance["ten_ticket_price"]) == (5_000_000, 45_000_000)
    assert (collector["ticket_price"], collector["ten_ticket_price"]) == (20_000_000, 150_000_000)
    assert (street["top_class"], performance["top_class"], collector["top_class"]) == ("A", "S1", "S2")
    for tier in tiers.values():
        assert math.isclose(sum(tier["odds"]["class"].values()), 1.0, rel_tol=1e-9)
        assert math.isclose(sum(tier["odds"]["rarity"].values()), 1.0, rel_tol=1e-9)
        assert tier["odds"]["class"]
        assert tier["odds"]["rarity"]

    performance_class = performance["odds"]["class"]
    assert set(performance_class) == {"C", "B", "A", "S1"}
    assert math.isclose(performance_class["C"], 0.24, abs_tol=1e-7)
    assert math.isclose(performance_class["B"], 0.38, abs_tol=1e-7)
    assert math.isclose(performance_class["A"], 0.33, abs_tol=1e-7)
    assert math.isclose(performance_class["S1"], 0.05, abs_tol=1e-7)
    assert performance_class["S1"] == min(performance_class.values())
    assert math.isclose(performance["odds"]["rarity"]["legendary"], 0.025, abs_tol=1e-7)

    assert math.isclose(collector["odds"]["class"]["S1"], 0.32, abs_tol=1e-7)
    assert math.isclose(collector["odds"]["class"]["S2"], 0.08, abs_tol=1e-7)
    assert math.isclose(collector["odds"]["rarity"]["legendary"], 0.05, abs_tol=1e-7)
    assert math.isclose(collector["odds"]["rarity"]["forza edition"], 0.0025, abs_tol=1e-7)
    assert math.isclose(collector["odds"]["rarity"]["donut edition"], 0.005, abs_tol=1e-7)


def test_gold_boost_preserves_public_marginals_and_reduces_guarantee_reliance():
    tiers = {tier["id"]: tier for tier in life_system.gacha_tiers()}
    minimum_base = {"street": 0.006, "performance": 0.0035, "collector": 0.0015}
    for tier_id, tier in tiers.items():
        assert tier["gold_rate"] >= minimum_base[tier_id]
        assert tier["expected_pulls_per_gold"] < tier["pity_limit"] * 0.95
        assert math.isclose(sum(tier["odds"]["class"].values()), 1.0, rel_tol=1e-9)
        assert math.isclose(sum(tier["odds"]["rarity"].values()), 1.0, rel_tol=1e-9)
    performance = tiers["performance"]
    assert math.isclose(performance["odds"]["class"]["S1"], 0.05, abs_tol=1e-7)
    assert math.isclose(performance["odds"]["rarity"]["legendary"], 0.025, abs_tol=1e-7)
    collector = tiers["collector"]
    assert math.isclose(collector["odds"]["rarity"]["forza edition"], 0.0025, abs_tol=1e-7)
    assert math.isclose(collector["odds"]["rarity"]["donut edition"], 0.005, abs_tol=1e-7)


def test_gacha_duplicate_flag_uses_the_garage_before_each_draw():
    state = life_system._empty_state()
    state["garages"]["garage-lot"] = {
        "id": "garage-lot", "kind": "standalone", "category": "standalone",
        "capacity": 20, "purchase_price": 15_000_000, "acquired_day": 100,
    }
    first_plan = life_system.gacha_plan(
        state, "street", 1, "garage-lot", 100, "garage-duplicate-seed",
    )
    first = first_plan["records"][0]
    assert first["garage_duplicate"] is False
    assert first["garage_copies_before"] == 0
    state["vehicles"]["vehicle-existing"] = {
        "id": "vehicle-existing", "catalog_id": first["catalog_id"],
        "name": first["name"], "manufacturer": first["manufacturer"],
        "class": first["class"], "rarity": first["rarity"], "year": first["year"],
        "image": first["image"], "source": "dealer", "garage_id": "club",
    }
    second_plan = life_system.gacha_plan(
        state, "street", 1, "garage-lot", 101, "garage-duplicate-seed",
    )
    second = second_plan["records"][0]
    assert second["catalog_id"] == first["catalog_id"]
    assert second["garage_duplicate"] is True
    assert second["garage_copies_before"] == 1


def test_gacha_keeps_every_draw_and_marks_exact_gold_hits():
    state = life_system._empty_state()
    state["garages"]["garage-lot"] = {
        "id": "garage-lot", "kind": "standalone", "category": "standalone",
        "capacity": 100, "purchase_price": 15_000_000, "acquired_day": 100,
    }
    for _cycle in range(6):
        plan = life_system.gacha_plan(state, "street", 10, "garage-lot", 100, "archive-seed")
        assert plan["total_value"] == pytest.approx(
            sum(record["value"] for record in plan["records"])
        )
        assert all(record["value"] > 0 for record in plan["records"])
        life_system.commit_gacha(state, plan, 100)
    assert len(state["gacha"]["street"]["history"]) == 60

    view = life_system.public_view(state, game_date="2000-04-10")
    street = next(row for row in view["gacha_tiers"] if row["id"] == "street")
    assert street["history_count"] == 60
    assert len(street["history"]) == 60

    guaranteed_state = life_system._empty_state()
    guaranteed_state["garages"]["garage-lot"] = {
        "id": "garage-lot", "kind": "standalone", "category": "standalone",
        "capacity": 10, "purchase_price": 15_000_000, "acquired_day": 100,
    }
    guaranteed_state["gacha"]["street"] = {"pulls": 10, "pity": 59, "history": []}
    plan = life_system.gacha_plan(
        guaranteed_state, "street", 1, "garage-lot", 100, "guaranteed-seed",
    )
    record = plan["records"][0]
    history = plan["history"][0]
    assert record["gacha_top_hit"] is True
    assert record["gacha_gold_hit"] is True
    assert record["gacha_guaranteed"] is True
    assert record["gacha_top_class"] == "A"
    assert record["rarity"] == "epic"
    assert record["gacha_top_rarities"] == ["epic"]
    assert history["top_hit"] is True
    assert history["guaranteed"] is True
    assert history["pity_before"] == 59
    assert history["pity_after"] == 0
    assert plan["pity_end"] == 0


def test_gold_requires_both_the_top_class_and_top_rarity():
    cases = (
        ("street", "A", "epic", True),
        ("street", "A", "rare", False),
        ("street", "B", "epic", False),
        ("performance", "S1", "legendary", True),
        ("performance", "S1", "epic", False),
        ("performance", "A", "legendary", False),
        ("collector", "S2", "forza edition", True),
        ("collector", "S2", "donut edition", True),
        ("collector", "S2", "legendary", True),
        ("collector", "S1", "forza edition", False),
        ("collector", "A", "donut edition", True),
        ("collector", "S1", "donut edition", True),
    )
    for tier_id, car_class, rarity, expected in cases:
        assert life_system._gacha_gold_hit(
            {"class": car_class, "rarity": rarity}, tier_id,
        ) is expected


@pytest.mark.parametrize("tier_id", ["street", "performance", "collector"])
def test_hard_pity_always_returns_the_exact_gold_combination(tier_id):
    tier = next(row for row in life_system.gacha_tiers() if row["id"] == tier_id)
    state = life_system._empty_state()
    state["garages"]["garage-lot"] = {
        "id": "garage-lot", "kind": "standalone", "category": "standalone",
        "capacity": 10, "purchase_price": 15_000_000, "acquired_day": 100,
    }
    state["gacha"][tier_id] = {
        "pulls": tier["pity_limit"] - 1,
        "pity": tier["pity_limit"] - 1,
        "history": [],
    }
    plan = life_system.gacha_plan(
        state, tier_id, 1, "garage-lot", 100, f"round49-{tier_id}",
    )
    record = plan["records"][0]
    assert record["gacha_guaranteed"] is True
    assert record["gacha_gold_hit"] is True
    assert life_system._gacha_gold_hit(record, tier_id) is True
    assert plan["gold_count"] == 1


def test_gacha_patch_returns_only_the_draw_delta_and_collection():
    state = life_system._empty_state()
    state["garages"]["garage-lot"] = {
        "id": "garage-lot", "kind": "standalone", "category": "standalone",
        "capacity": 20, "purchase_price": 15_000_000, "acquired_day": 100,
    }
    plan = life_system.gacha_plan(
        state, "street", 1, "garage-lot", 100, "round51-delta",
    )
    records = life_system.commit_gacha(state, plan, 100)
    patch = life_system.gacha_patch(
        state, records, game_date="2000-04-10", scope_id="scope-51", manager_id=77,
    )

    assert "life" not in patch
    assert "state" not in patch
    assert "vehicles" not in patch
    assert [row["id"] for row in patch["vehicles_added"]] == [records[0]["id"]]
    assert patch["vehicles_added_value"] == pytest.approx(
        sum(row["market_value"] for row in patch["vehicles_added"])
    )
    assert patch["garage_summary"]["used"] == 1
    assert patch["collection"]["summary"]["total"] == 1
    assert patch["gacha_status"][0]["pulls"] == 1
    assert patch["gacha_status"][0]["history_count"] == 1
    assert patch["scope_id"] == "scope-51"
    assert patch["manager_id"] == 77

    view = life_system.public_view(
        state, game_date="2000-04-10", scope_id="scope-51", manager_id=77,
    )
    assert "state" not in view
    assert view["collection"]["summary"]["total"] == 1


def test_gacha_statistics_accumulate_spend_gold_and_vehicle_value():
    state = life_system._empty_state()
    state["garages"]["garage-lot"] = {
        "id": "garage-lot", "kind": "standalone", "category": "standalone",
        "capacity": 40, "purchase_price": 15_000_000, "acquired_day": 100,
    }
    plans = []
    for _index in range(2):
        plan = life_system.gacha_plan(
            state, "street", 10, "garage-lot", 100, "round49-stats",
        )
        life_system.commit_gacha(state, plan, 100)
        plans.append(plan)

    counter = state["gacha"]["street"]
    expected_spend = sum(plan["cost"] for plan in plans)
    expected_gold = sum(plan["gold_count"] for plan in plans)
    expected_value = sum(plan["total_value"] for plan in plans)
    assert counter["spent"] == expected_spend == 8_000_000
    assert counter["gold_count"] == expected_gold
    assert counter["total_value"] == pytest.approx(expected_value)
    assert sum(row["cost"] for row in counter["history"]) == expected_spend

    view = life_system.public_view(state, game_date="2000-04-10")
    street = next(row for row in view["gacha_tiers"] if row["id"] == "street")
    stats = street["stats"]
    assert stats["tracked_pulls"] == 20
    assert stats["stats_started_pull"] == 0
    assert stats["tracking_complete"] is True
    assert stats["spent"] == expected_spend
    assert stats["gold_count"] == expected_gold
    assert stats["total_value"] == pytest.approx(expected_value)
    assert stats["observed_gold_rate"] == pytest.approx(expected_gold / 20)
    assert stats["expected_gold_rate"] == pytest.approx(street["expected_gold_rate"])
    assert stats["expected_pulls_per_gold"] == pytest.approx(street["expected_pulls_per_gold"])
    assert stats["luck"]["key"] != "empty"


def test_legacy_gacha_history_recomputes_exact_gold_and_marks_partial_statistics():
    state = life_system._empty_state()
    gold_car = next(
        car for car in life_system._gacha_tier_cars(life_system.GACHA_TIERS[0])
        if life_system._gacha_gold_hit(car, "street")
    )
    state["gacha"]["street"] = {
        "pulls": 5, "pity": 2,
        "history": [{
            "day": 99, "tier": "street", "catalog_id": gold_car["catalog_id"],
            "name": gold_car["name"], "class": gold_car["class"],
            "garage_id": "club", "top_hit": False,
        }],
    }
    view = life_system.public_view(state, game_date="2000-04-10")
    street = next(row for row in view["gacha_tiers"] if row["id"] == "street")
    assert street["history"][0]["rarity"] == "epic"
    assert street["history"][0]["gold_hit"] is True
    assert street["history"][0]["top_hit"] is True
    assert street["stats"]["tracked_pulls"] == 0
    assert street["stats"]["stats_started_pull"] == 5
    assert street["stats"]["tracking_complete"] is False
    assert street["stats"]["spent"] == 0


def test_gacha_luck_exposes_multiple_lucky_and_unlucky_grades():
    assert life_system._gacha_luck(10, 0, 0.02)["key"] == "provisional"
    assert life_system._gacha_luck(200, 20, 0.01)["key"] == "ou_3"
    assert life_system._gacha_luck(200, 2, 0.01)["key"] == "balanced"
    assert life_system._gacha_luck(200, 0, 0.01)["key"] == "fei_3"


def test_garage_collection_moves_into_a_full_dialog_with_all_locales():
    index = (ROOT / "src" / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "src" / "web" / "life_page.js").read_text(encoding="utf-8")
    styles = (ROOT / "src" / "web" / "life.css").read_text(encoding="utf-8")
    assert 'data-life-action="open-collection"' in index
    assert '<dialog id="life-collection-dialog"' in index
    assert "life-collection-strip" not in script
    assert "async function openCollectionDialog()" in script
    assert "if (!state.catalog) await refreshLife({catalog: true});" in script
    assert "function collectionManufacturerStats()" in script
    assert "life.collection.tab_legendary" in script
    assert 'String(car.dealer_status || "") === "display_only"' in script
    assert "life-catalog-grid" in styles
    assert "life-collection-dialog" in styles
    assert "life-gacha-odds" in styles
    assert "is-display-only" in styles

    script_path = ROOT / "src" / "web" / "i18n.life.js"
    node_script = f"""
const fs = require('fs');
const vm = require('vm');
global.window = {{}};
vm.runInThisContext(fs.readFileSync({json.dumps(str(script_path))}, 'utf8'));
const messages = window.FMODDI18nModules[0].messages;
const locales = ['en-GB','zh-CN','zh-TW','ko-KR','de-DE','es-ES','fr-FR','ru-RU','ja-JP','pt-BR','pt-PT'];
    const keys = ['life.collection.title','life.collection.open','life.collection.tab_legendary','life.dealer.display_only_message','life.gacha.odds_title','life.gacha.odds_soft_note','life.storage.title','life.storage.move_confirm','life.garage.group_storage','life.gacha.history_title','life.gacha.history_button'];
for (const locale of locales) {{
  for (const key of keys) {{
    if (!String(messages[locale]?.[key] || '').trim()) throw new Error(locale + ':' + key);
  }}
}}
console.log('ok');
"""
    result = subprocess.run(
        ["node", "-"], input=node_script, text=True, encoding="utf-8",
        check=True, capture_output=True,
    )
    assert result.stdout.strip() == "ok"


def test_storage_garage_is_created_for_new_and_legacy_saves():
    state = life_system._empty_state()
    assert state["garages"]["storage"]["kind"] == "storage"
    assert state["garages"]["storage"]["category"] == "storage"
    assert state["garages"]["storage"]["capacity"] == 10000

    legacy = life_system.normalize_state({
        "garages": {
            "club": {
                "id": "club", "kind": "club", "capacity": 2,
                "name_zh": "俱乐部车库", "name_en": "Club garage",
            },
        },
        "vehicles": {}, "properties": {}, "gacha": {},
    })
    assert legacy["garages"]["storage"]["capacity"] == 10000
    assert legacy["garages"]["storage"]["system"] is True


def test_ensure_state_persists_storage_garage_for_existing_saves(monkeypatch):
    legacy = life_system._empty_state()
    legacy["schema_version"] = life_system.SCHEMA_VERSION
    legacy["garages"].pop("storage", None)
    legacy["income_settled_day"] = 10
    monkeypatch.setattr(life_system, "load_document", lambda *_args, **_kwargs: legacy)

    state, changed = life_system.ensure_state("scope", 10)

    assert changed is True
    assert state["garages"]["storage"]["capacity"] == 10000


def test_storage_garage_accepts_moves_and_rejects_the_101st_car():
    state = life_system._empty_state()
    car = life_system.car_by_id("car-16")
    plan = life_system.buy_vehicle_plan(state, car, "club", 10)
    vehicle = life_system.commit_buy_vehicle(state, plan, 10)

    moved = life_system.move_vehicle(state, vehicle["id"], "storage", 11)
    assert moved["garage_id"] == "storage"
    returned = life_system.move_vehicle(state, vehicle["id"], "club", 12)
    assert returned["garage_id"] == "club"

    state["vehicles"][vehicle["id"]]["garage_id"] = "club"
    state["garages"]["storage"]["capacity"] = 100
    for index in range(100):
        state["vehicles"][f"stored-{index:03d}"] = {
            "id": f"stored-{index:03d}", "garage_id": "storage",
        }
    with pytest.raises(ValueError, match="车库车位不足"):
        life_system.move_vehicle(state, vehicle["id"], "storage", 13)


def test_storage_rent_is_one_percent_per_day_and_settles_the_marker():
    state = life_system._empty_state()
    car = life_system.car_by_id("car-16")
    plan = life_system.buy_vehicle_plan(state, car, "club", 100)
    vehicle = life_system.commit_buy_vehicle(state, plan, 100)
    life_system.move_vehicle(state, vehicle["id"], "storage", 100)
    state["storage_rent_settled_day"] = 100

    rent = life_system.storage_rent_plan(state, 103)
    expected_due = round_money(sum(
        round_money(
            life_system.vehicle_market_value(state["vehicles"][vehicle["id"]], day)
            * life_system.STORAGE_RENT_RATE
        )
        for day in (101, 102, 103)
    ))
    expected_daily = round_money(
        life_system.vehicle_market_value(state["vehicles"][vehicle["id"]], 103)
        * life_system.STORAGE_RENT_RATE
    )
    assert rent["days_due"] == 3
    assert rent["vehicle_count"] == 1
    assert rent["due_amount"] == expected_due
    assert rent["daily_amount"] == expected_daily

    life_system.commit_storage_rent(state, rent, 103, {"transaction_id": "rent-tx"})
    assert state["storage_rent_settled_day"] == 103
    assert state["storage_rent_lifetime"] == expected_due
    assert state["storage_rent_history"][-1]["transaction_id"] == "rent-tx"
    assert life_system.storage_rent_plan(state, 103)["due_amount"] == 0


def test_storage_rent_migration_does_not_charge_old_storage_vehicles(monkeypatch):
    legacy = life_system._empty_state()
    legacy["schema_version"] = 7
    legacy["storage_rent_settled_day"] = None
    legacy["vehicles"] = {
        "old-stored": {"id": "old-stored", "garage_id": "storage", "base_price": 1_000_000},
    }
    monkeypatch.setattr(life_system, "load_document", lambda *_args, **_kwargs: legacy)

    state, changed = life_system.ensure_state("scope", 50)

    assert changed is True
    assert state["storage_rent_settled_day"] == 50
    assert state["vehicles"]["old-stored"]["storage_entered_day"] == 50
    assert life_system.storage_rent_plan(state, 50)["due_amount"] == 0


def test_storage_rent_uses_the_shared_ledger_and_refunds_a_failed_save(monkeypatch):
    state = life_system._empty_state()
    car = life_system.car_by_id("car-16")
    plan = life_system.buy_vehicle_plan(state, car, "club", 100)
    vehicle = life_system.commit_buy_vehicle(state, plan, 100)
    life_system.move_vehicle(state, vehicle["id"], "storage", 100)
    state["storage_rent_settled_day"] = 100
    expected = life_system.storage_rent_plan(state, 103)["due_amount"]

    service = web.LocalOddsState.__new__(web.LocalOddsState)
    monkeypatch.setattr(life_system, "ensure_state", lambda *_args, **_kwargs: (state, False))
    monkeypatch.setattr(life_system, "save_state", lambda *_args, **_kwargs: None)
    charges = []
    refunds = []
    payment = {"transaction_id": "rent-payment", "bank": expected, "wallet": 0.0, "total": expected}

    def charge(amount, kind, *, allow_bank_overdraft=False, **details):
        charges.append((amount, kind, allow_bank_overdraft, details))
        return payment

    monkeypatch.setattr(web, "charge_combined_funds", charge)
    monkeypatch.setattr(
        web, "refund_combined_funds",
        lambda original, kind, **details: refunds.append((original, kind, details)),
    )
    result = service._life_state("scope", 103)

    assert result["storage_rent_settled_day"] == 103
    assert charges and charges[0][0] == expected
    assert charges[0][1] == "life_storage_rent"
    assert charges[0][2] is True

    rollback_state = life_system._empty_state()
    rollback_plan = life_system.buy_vehicle_plan(rollback_state, car, "club", 100)
    rollback_vehicle = life_system.commit_buy_vehicle(rollback_state, rollback_plan, 100)
    life_system.move_vehicle(rollback_state, rollback_vehicle["id"], "storage", 100)
    rollback_state["storage_rent_settled_day"] = 100
    monkeypatch.setattr(life_system, "ensure_state", lambda *_args, **_kwargs: (rollback_state, False))

    def fail_save(*_args, **_kwargs):
        raise RuntimeError("life save unavailable")

    monkeypatch.setattr(life_system, "save_state", fail_save)
    with pytest.raises(RuntimeError, match="life save unavailable"):
        service._life_state("scope", 103)
    assert refunds and refunds[-1][0] == payment
    assert refunds[-1][1] == "life_storage_rent_rollback"


def test_batch_vehicle_sale_credits_one_total_and_clears_every_selected_car(monkeypatch):
    state = life_system._empty_state()
    car = life_system.car_by_id("car-16")
    vehicles = []
    for day in (10, 11):
        plan = life_system.buy_vehicle_plan(state, car, "club", day)
        vehicles.append(life_system.commit_buy_vehicle(state, plan, day))

    service = web.LocalOddsState.__new__(web.LocalOddsState)
    service._life_context = lambda: ("scope", "2026-01-11", 11, 77)
    service._life_state = lambda _scope, _day: state
    service._life_view = lambda _state, **_kwargs: {}
    saved = []
    monkeypatch.setattr(life_system, "save_state", lambda value, _scope: saved.append(value))
    credits = []
    monkeypatch.setattr(
        web, "adjust_bank_balance",
        lambda amount, kind, **metadata: credits.append((amount, kind, metadata)) or {"balance": amount},
    )

    response = service.sell_life_vehicles({
        "vehicle_ids": [vehicle["id"] for vehicle in vehicles],
    })

    assert response["count"] == 2
    assert credits[0][1] == "life_vehicle_batch_sell"
    assert credits[0][0] == round_money(sum(row["net"] for row in response["sales"]))
    assert all(vehicle["id"] not in saved[-1]["vehicles"] for vehicle in vehicles)


def test_round46_vehicle_cache_storage_gallery_and_draw_history_frontend():
    index = (ROOT / "src" / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "src" / "web" / "life_page.js").read_text(encoding="utf-8")
    styles = (ROOT / "src" / "web" / "life.css").read_text(encoding="utf-8")

    assert 'const VEHICLE_IMAGE_CACHE_NAME = "fmsdd-life-car-images-v1";' in script
    assert "caches.open(VEHICLE_IMAGE_CACHE_NAME)" in script
    assert "data-life-vehicle-image" in script
    assert "function warmVehicleImageCache()" in script
    assert "function scheduleVehicleImageHydration(" in script
    assert "requestIdleCallback(start" in script
    assert "const previousScrollTop = host.scrollTop;" in script
    assert "const historyCount = (tier.history || []).length;" in script
    assert '<img src="${esc(car.image)}"' not in script
    assert '<img src="${esc(vehicle.image)}"' not in script

    assert 'id="life-storage-open"' in index
    assert '<dialog id="life-storage-dialog"' in index
    assert 'data-life-action="storage-move-selected"' in script
    assert 'data-life-action="storage-sell-selected"' in script
    assert 'data-life-storage-select=' in script
    assert '/api/life/vehicle/move-batch' in script
    assert '/api/life/vehicle/sell-batch' in script
    assert ".life-storage-row" in styles
    assert ".life-storage-dialog" in styles

    assert '<dialog id="life-gacha-history-dialog"' in index
    assert 'data-life-action="open-gacha-history"' in script
    assert "life-gacha-history-button" in script
    assert 'class="life-gacha-history"' not in script
    assert ".life-gacha-tier { display: flex; flex-direction: column;" in styles
    assert ".life-gacha-actions { margin-top: auto; }" in styles


def test_round47_dealer_images_top_hits_and_storage_entry_frontend():
    script = (ROOT / "src" / "web" / "life_page.js").read_text(encoding="utf-8")
    styles = (ROOT / "src" / "web" / "life.css").read_text(encoding="utf-8")

    dealer_start = script.index("function paintDealerResults()")
    dealer_end = script.index("function dealerCarCard", dealer_start)
    dealer_renderer = script[dealer_start:dealer_end]
    assert "scheduleVehicleImageHydration(host);" in dealer_renderer
    assert "function gachaTopHit(record)" in script
    assert "function gachaTopBadge(record)" in script
    assert "life.gacha.gold_summary" in script
    assert 'id="life-gacha-storage-open"' in script
    assert "dialog.parentElement !== document.body" in script
    assert "data-life-storage-rent" in script
    assert ".life-gacha-top-mark" in styles
    assert ".life-gacha-top-summary" in styles
    assert ".life-storage-overview { display: grid; grid-template-columns: repeat(4" in styles

    script_path = ROOT / "src" / "web" / "i18n.life.js"
    node_script = f"""
const fs = require('fs');
const vm = require('vm');
global.window = {{}};
vm.runInThisContext(fs.readFileSync({json.dumps(str(script_path))}, 'utf8'));
const messages = window.FMODDI18nModules[0].messages;
const locales = ['en-GB','zh-CN','zh-TW','ko-KR','de-DE','es-ES','fr-FR','ru-RU','ja-JP','pt-BR','pt-PT'];
const keys = ['life.storage.daily_rent','life.storage.rent_hint','life.storage.daily_short','life.gacha.top_hit','life.gacha.guaranteed_hit','life.gacha.top_summary','life.gacha.top_hit_toast','life.gacha.history_count'];
for (const locale of locales) {{
  for (const key of keys) {{
    if (!String(messages[locale]?.[key] || '').trim()) throw new Error(locale + ':' + key);
  }}
}}
console.log('ok');
"""
    result = subprocess.run(
        ["node", "-"], input=node_script, text=True, encoding="utf-8",
        check=True, capture_output=True,
    )
    assert result.stdout.strip() == "ok"


def test_round48_gacha_total_value_contract_and_translations():
    script = (ROOT / "src" / "web" / "life_page.js").read_text(encoding="utf-8")
    styles = (ROOT / "src" / "web" / "life.css").read_text(encoding="utf-8")
    api = (ROOT / "src" / "fm_odds_web.py").read_text(encoding="utf-8")

    assert '"total_value": plan["total_value"]' in api
    assert "totalValue: Number(response.total_value" in script
    assert 'class="life-gacha-total-value"' in script
    assert ".life-gacha-total-value" in styles

    script_path = ROOT / "src" / "web" / "i18n.life.js"
    node_script = f"""
const fs = require('fs');
const vm = require('vm');
global.window = {{}};
vm.runInThisContext(fs.readFileSync({json.dumps(str(script_path))}, 'utf8'));
const messages = window.FMODDI18nModules[0].messages;
const locales = ['en-GB','zh-CN','zh-TW','ko-KR','de-DE','es-ES','fr-FR','ru-RU','ja-JP','pt-BR','pt-PT'];
for (const locale of locales) {{
  if (!String(messages[locale]?.['life.gacha.total_value'] || '').trim()) throw new Error(locale);
}}
console.log('ok');
"""
    result = subprocess.run(
        ["node", "-"], input=node_script, text=True, encoding="utf-8",
        check=True, capture_output=True,
    )
    assert result.stdout.strip() == "ok"


def test_round49_exact_gold_statistics_and_luck_contract_and_translations():
    source = (ROOT / "src" / "tools" / "life_system.py").read_text(encoding="utf-8")
    script = (ROOT / "src" / "web" / "life_page.js").read_text(encoding="utf-8")
    styles = (ROOT / "src" / "web" / "life.css").read_text(encoding="utf-8")
    api = (ROOT / "src" / "fm_odds_web.py").read_text(encoding="utf-8")

    assert '"high_classes"' not in source
    assert '"high_rarities"' not in source
    assert '"ticket_price": 500_000, "ten_ticket_price": 4_000_000' in source
    assert '"ticket_price": 20_000_000, "ten_ticket_price": 150_000_000' in source
    assert "def _gacha_expected_pulls_per_gold(tier_id: str)" in source
    assert 'APP_VERSION = PRODUCT_VERSION if FROZEN else "74-dev"' in api

    assert "record?.gacha_gold_hit ?? record?.gold_hit" in script
    assert "function gachaRate(value, digits = 2)" in script
    assert "life.gacha.stats_spent" in script
    assert "life.gacha.stats_gold" in script
    assert "life.gacha.stats_value" in script
    assert 't("life.gacha.luck_" + key)' in script
    assert "life.gacha.gold_condition" in script
    assert 'class="life-gacha-history-economics"' in script
    assert ".life-gacha-luck-scale { display: grid; grid-template-columns: repeat(7" in styles
    assert ".life-gacha-pool-stats" in styles
    assert ".life-gacha-gold-rule" in styles

    script_path = ROOT / "src" / "web" / "i18n.life.js"
    node_script = f"""
const fs = require('fs');
const vm = require('vm');
global.window = {{}};
vm.runInThisContext(fs.readFileSync({json.dumps(str(script_path))}, 'utf8'));
const messages = window.FMODDI18nModules[0].messages;
const locales = ['en-GB','zh-CN','zh-TW','ko-KR','de-DE','es-ES','fr-FR','ru-RU','ja-JP','pt-BR','pt-PT'];
const keys = [
  'life.gacha.gold_hit','life.gacha.guaranteed_gold_hit','life.gacha.gold_summary',
  'life.gacha.gold_hit_toast','life.gacha.gold_condition','life.gacha.gold_rate_base',
  'life.gacha.gold_rate_expected','life.gacha.stats_spent','life.gacha.stats_gold',
  'life.gacha.stats_value','life.gacha.stats_tracked','life.gacha.stats_observed',
  'life.gacha.stats_expected','life.gacha.stats_started','life.gacha.stats_pending',
  'life.gacha.luck_title','life.gacha.luck_score','life.gacha.luck_hint',
  'life.gacha.luck_empty','life.gacha.luck_provisional','life.gacha.luck_ou_3',
  'life.gacha.luck_ou_2','life.gacha.luck_ou_1','life.gacha.luck_balanced',
  'life.gacha.luck_fei_1','life.gacha.luck_fei_2','life.gacha.luck_fei_3',
  'life.gacha.history_cost','life.gacha.history_value'
];
for (const locale of locales) {{
  for (const key of keys) {{
    if (!String(messages[locale]?.[key] || '').trim()) throw new Error(locale + ':' + key);
  }}
}}
console.log('ok');
"""
    result = subprocess.run(
        ["node", "-"], input=node_script, text=True, encoding="utf-8",
        check=True, capture_output=True,
    )
    assert result.stdout.strip() == "ok"


def test_round52_preload_pool_catalogue_class_badges_and_draw_confirmation():
    app = (ROOT / "src" / "web" / "app.js").read_text(encoding="utf-8")
    script = (ROOT / "src" / "web" / "life_page.js").read_text(encoding="utf-8")
    styles = (ROOT / "src" / "web" / "life.css").read_text(encoding="utf-8")
    page = (ROOT / "src" / "web" / "index.html").read_text(encoding="utf-8")

    tiers = life_system.gacha_tiers()
    catalog_ids = {str(car["catalog_id"]) for car in life_system.car_catalog()["cars"]}
    expected_counts = {"street": 236, "performance": 325, "collector": 241}
    for tier in tiers:
        ids = [str(value) for value in tier["car_ids"]]
        assert len(ids) == tier["car_count"] == expected_counts[tier["id"]]
        assert len(ids) == len(set(ids))
        assert set(ids) <= catalog_ids

    assert "let lifePreloadPromise = null;" in script
    assert "async function preload({announce = false} = {})" in script
    assert "state.catalog && !state.error" in script
    assert 't("life.preload.started")' in script
    assert 't("life.preload.ready")' in script
    assert 't("life.preload.failed")' in script
    assert "lifePreloadSignature" in app
    assert "maybePreloadLifeData({announce:true});" in app
    assert 'document.addEventListener("DOMContentLoaded", () => maybePreloadLifeData({announce:true}), {once:true});' in app
    assert "Date.now() - app.lifePreloadFailureAt < 30_000" in app

    assert "function gachaPoolCars(tier = gachaPoolTier())" in script
    assert "tier.car_ids" in script
    assert 'data-life-action="open-gacha-catalog"' in script
    assert 'id="life-gacha-catalog-dialog"' in page
    assert "life.gacha.catalog_button" in script
    assert ".life-gacha-catalog-dialog" in styles

    assert "function vehicleClassBadge(value, inline = false)" in script
    for class_key in ("d", "c", "b", "a", "s1", "s2"):
        assert f".life-class-badge.life-class-{class_key}" in styles
    assert "font-size: 16px" in styles
    assert "animation: life-class-s2-sheen" in styles
    assert script.count("${vehicleClassBadge(") >= 6

    assert 'id="gacha-confirm" checked' in page
    assert 'GACHA_CONFIRM_STORAGE_KEY = "fmsdd-gacha-confirm"' in app
    assert "gachaConfirmEnabled: () => app.gachaConfirm !== false" in app
    assert 'bridge().gachaConfirmEnabled?.() !== false' in script

    script_path = ROOT / "src" / "web" / "i18n.life.js"
    node_script = f"""
const fs = require('fs');
const vm = require('vm');
global.window = {{}};
vm.runInThisContext(fs.readFileSync({json.dumps(str(script_path))}, 'utf8'));
const messages = window.FMODDI18nModules[0].messages;
const locales = ['en-GB','zh-CN','zh-TW','ko-KR','de-DE','es-ES','fr-FR','ru-RU','ja-JP','pt-BR','pt-PT'];
const keys = [
  'life.preload.started','life.preload.ready','life.preload.failed',
  'life.gacha.catalog_button','life.gacha.catalog_eyebrow','life.gacha.catalog_title',
  'life.gacha.catalog_pool','life.gacha.catalog_owned','life.gacha.catalog_gold_pool',
  'life.gacha.catalog_gold_hint','life.gacha.catalog_search','life.gacha.catalog_results',
  'life.gacha.catalog_empty','life.gacha.catalog_gold',
  'settings.gacha_confirm','settings.gacha_confirm_note'
];
for (const locale of locales) {{
  for (const key of keys) {{
    if (!String(messages[locale]?.[key] || '').trim()) throw new Error(locale + ':' + key);
  }}
  if (!messages[locale]['life.gacha.catalog_button'].includes('{{count}}')) throw new Error(locale + ':count');
  if (!messages[locale]['life.gacha.catalog_title'].includes('{{tier}}')) throw new Error(locale + ':tier');
}}
console.log('ok');
"""
    result = subprocess.run(
        ["node", "-"], input=node_script, text=True, encoding="utf-8",
        check=True, capture_output=True,
    )
    assert result.stdout.strip() == "ok"
