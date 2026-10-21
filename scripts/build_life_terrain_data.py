"""Build the bundled offline water/green mask for the life-system map.

OSM geometry is fetched only by this maintenance script.  The runtime reads
the simplified ``src/assets/life/city_terrain.json`` file and never contacts a
map data service.  Source data is © OpenStreetMap contributors, ODbL 1.0.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "src" / "assets" / "life"
OUTPUT = ASSET_ROOT / "city_terrain.json"
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
QUERY_PARTS = (
    'way["natural"="water"]{bbox};',
    'rel["natural"="water"]{bbox};',
    'way["natural"~"^(beach|wetland)$"]{bbox};',
    'rel["natural"~"^(beach|wetland)$"]{bbox};',
    'way["leisure"="beach_resort"]{bbox};',
    'rel["leisure"="beach_resort"]{bbox};',
    'way["waterway"="riverbank"]{bbox};',
    'rel["waterway"="riverbank"]{bbox};',
    'way["water"~"^(sea|ocean|bay|strait|river|canal|lake|pond|reservoir)$"]{bbox};',
    'rel["water"~"^(sea|ocean|bay|strait|river|canal|lake|pond|reservoir)$"]{bbox};',
    'way["natural"~"^(bay|strait)$"]{bbox};',
    'rel["natural"~"^(bay|strait)$"]{bbox};',
    'way["place"~"^(sea|ocean|bay)$"]{bbox};',
    'rel["place"~"^(sea|ocean|bay)$"]{bbox};',
    'way["leisure"="park"]{bbox};',
    'rel["leisure"="park"]{bbox};',
    'way["landuse"~"^(grass|forest|recreation_ground|village_green|meadow)$"]{bbox};',
    'rel["landuse"~"^(grass|forest|recreation_ground|village_green|meadow)$"]{bbox};',
    'way["natural"="wood"]{bbox};',
    'rel["natural"="wood"]{bbox};',
    'way["leisure"="nature_reserve"]{bbox};',
    'rel["leisure"="nature_reserve"]{bbox};',
    'way["boundary"="protected_area"]{bbox};',
    'rel["boundary"="protected_area"]{bbox};',
)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _catalog() -> dict[str, Any]:
    base = _read(ASSET_ROOT / "cities.json")
    extra = _read(ASSET_ROOT / "cities_extra_cn.json")
    global_rows = _read(ASSET_ROOT / "cities_global.json")
    cities = list(base.get("cities") or []) + list(extra.get("cities") or [])
    for country in global_rows.get("countries") or []:
        cities.extend(country.get("cities") or [])
    return {str(city["id"]): city for city in cities}


def _district_bboxes(city: dict[str, Any]) -> list[tuple[float, float, float, float]]:
    boxes = []
    for district in city.get("districts") or []:
        lat = float(district.get("lat") or city.get("lat") or 0)
        lng = float(district.get("lng") or city.get("lng") or 0)
        boxes.append((lat - 0.075, lng - 0.09, lat + 0.075, lng + 0.09))
    if not boxes:
        lat = float(city.get("lat") or 0)
        lng = float(city.get("lng") or 0)
        boxes.append((lat - 0.09, lng - 0.11, lat + 0.09, lng + 0.11))
    return boxes


def _query(city: dict[str, Any]) -> list[dict[str, Any]]:
    statements = []
    for box in _district_bboxes(city):
        bbox = "({:.6f},{:.6f},{:.6f},{:.6f})".format(*box)
        statements.extend(part.format(bbox=bbox) for part in QUERY_PARTS)
    # ``out body geom`` is required for multipolygon relations: ``tags geom``
    # returns the relation tags but omits its member geometry, which silently
    # dropped large lakes and sea inlets in the previous build.
    query = "[out:json][timeout:180];(" + "".join(statements) + ");out body geom;"
    last_error = ""
    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(3):
            request = urllib.request.Request(
                endpoint,
                data=urllib.parse.urlencode({"data": query}).encode("utf-8"),
                method="POST",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                    "User-Agent": "FMSDD/2.9.0 life-terrain-build",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=150) as response:
                    raw = response.read()
                payload = json.loads(raw.decode("utf-8"))
                elements = payload.get("elements")
                if isinstance(elements, list):
                    return elements
                last_error = "response has no elements list"
            except Exception as error:  # Network and overload responses are expected.
                last_error = str(error)
            time.sleep(8 + attempt * 12)
    raise RuntimeError(f"{city['id']}: {last_error}")


def _project(lat: float, lng: float, origin_lat: float, origin_lng: float) -> tuple[float, float]:
    x = (lng - origin_lng) * 111_320.0 * max(0.2, math.cos(math.radians(origin_lat)))
    y = (lat - origin_lat) * 111_320.0
    return x, y


def _area(ring: list[list[float]]) -> float:
    origin_lat = sum(row[0] for row in ring) / len(ring)
    origin_lng = sum(row[1] for row in ring) / len(ring)
    points = [_project(row[0], row[1], origin_lat, origin_lng) for row in ring]
    return abs(sum(
        points[index - 1][0] * points[index][1] - points[index][0] * points[index - 1][1]
        for index in range(len(points))
    )) / 2.0


def _segment_distance(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-9:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    ratio = max(0.0, min(1.0, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_sq))
    return math.hypot(point[0] - (start[0] + ratio * dx), point[1] - (start[1] + ratio * dy))


def _simplify(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return points
    start, end = points[0], points[-1]
    index, distance = 0, -1.0
    for offset, point in enumerate(points[1:-1], 1):
        current = _segment_distance(point, start, end)
        if current > distance:
            index, distance = offset, current
    if distance <= tolerance:
        return [start, end]
    left = _simplify(points[:index + 1], tolerance)
    right = _simplify(points[index:], tolerance)
    return left[:-1] + right


def _ring_rows(points: list[Any]) -> list[list[float]]:
    rows = [
        [round(float(point["lat"]), 6), round(float(point["lon"]), 6)]
        for point in points
        if isinstance(point, dict) and point.get("lat") is not None and point.get("lon") is not None
    ]
    if len(rows) < 4 or rows[0] != rows[-1]:
        return []
    if _area(rows) < 2_500:
        return []
    origin_lat = sum(row[0] for row in rows) / len(rows)
    origin_lng = sum(row[1] for row in rows) / len(rows)
    local = [_project(row[0], row[1], origin_lat, origin_lng) for row in rows]
    simplified = _simplify(local, 8.0)
    if len(simplified) > 180:
        simplified = _simplify(local, 18.0)
    result = [
        [round(origin_lat + y / 111_320.0, 6),
         round(origin_lng + x / (111_320.0 * max(0.2, math.cos(math.radians(origin_lat)))), 6)]
        for x, y in simplified
    ]
    if result[0] != result[-1]:
        result.append(result[0])
    return result if len(result) >= 4 else []


def _ring(element: dict[str, Any]) -> list[list[float]]:
    return _ring_rows(element.get("geometry") or [])


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


def _join_segments(segments: list[list[list[float]]]) -> list[list[list[float]]]:
    """Join multipolygon member ways into closed outer/inner rings."""
    pending = [list(segment) for segment in segments if len(segment) >= 2]
    rings: list[list[list[float]]] = []
    while pending:
        current = pending.pop(0)
        while current[0] != current[-1]:
            matched = False
            for index, segment in enumerate(pending):
                if segment[0] == current[-1]:
                    current.extend(segment[1:])
                    pending.pop(index)
                    matched = True
                    break
                if segment[-1] == current[-1]:
                    current.extend(reversed(segment[:-1]))
                    pending.pop(index)
                    matched = True
                    break
            if not matched:
                break
        if current[0] == current[-1] and len(current) >= 4:
            rings.append(current)
    return rings


def _relation_parts(element: dict[str, Any]) -> list[dict[str, Any]]:
    """Return simplified outer/hole parts from an OSM multipolygon relation."""
    outer: list[list[list[float]]] = []
    inner: list[list[list[float]]] = []
    for member in element.get("members") or []:
        if not isinstance(member, dict) or member.get("type") != "way":
            continue
        geometry = member.get("geometry") or []
        points = [
            [round(float(point["lat"]), 6), round(float(point["lon"]), 6)]
            for point in geometry
            if isinstance(point, dict) and point.get("lat") is not None and point.get("lon") is not None
        ]
        if len(points) < 2:
            continue
        if str(member.get("role") or "outer") == "inner":
            inner.append(points)
        else:
            outer.append(points)
    outer_rings = _join_segments(outer)
    inner_rings = _join_segments(inner)
    simplified_outer = [
        _ring_rows([{"lat": point[0], "lon": point[1]} for point in points])
        for points in outer_rings
    ]
    simplified_inner = [
        _ring_rows([{"lat": point[0], "lon": point[1]} for point in points])
        for points in inner_rings
    ]
    parts: list[dict[str, Any]] = []
    for outer_ring in simplified_outer:
        if not outer_ring:
            continue
        origin_lat = sum(point[0] for point in outer_ring) / len(outer_ring)
        origin_lng = sum(point[1] for point in outer_ring) / len(outer_ring)
        local_outer = [_project(point[0], point[1], origin_lat, origin_lng) for point in outer_ring]
        holes: list[list[list[float]]] = []
        for hole in simplified_inner:
            if not hole:
                continue
            test_x, test_y = _project(hole[0][0], hole[0][1], origin_lat, origin_lng)
            if _point_in_ring(test_x, test_y, local_outer):
                holes.append(hole)
        parts.append({"ring": outer_ring, "holes": holes})
    return parts


def _classify(tags: dict[str, Any]) -> str:
    if (
        tags.get("natural") in {"water", "bay", "strait", "beach", "wetland"}
        or tags.get("waterway") == "riverbank"
        or tags.get("place") in {"sea", "ocean", "bay"}
        or tags.get("leisure") == "beach_resort"
        or str(tags.get("water") or "") in {"sea", "ocean", "bay", "strait", "river", "canal", "lake", "pond", "reservoir"}
    ):
        return "water"
    if (
        tags.get("leisure") in {"park", "nature_reserve"}
        or tags.get("natural") == "wood"
        or tags.get("landuse") in {"grass", "forest", "recreation_ground", "village_green", "meadow"}
        or tags.get("boundary") == "protected_area"
    ):
        return "green"
    return ""


def _areas(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for element in elements:
        tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
        kind = _classify(tags)
        if not kind:
            continue
        parts = _relation_parts(element) if element.get("type") == "relation" else []
        if not parts:
            ring = _ring(element)
            if ring:
                parts = [{"ring": ring, "holes": []}]
        for part in parts:
            ring = part.get("ring") or []
            if not ring:
                continue
            lats = [point[0] for point in ring]
            lngs = [point[1] for point in ring]
            hole_area = sum(_area(hole) for hole in (part.get("holes") or []) if len(hole) >= 4)
            rows.append({
                "kind": kind,
                "name": str(tags.get("name:zh") or tags.get("name") or ""),
                "bbox": [min(lats), min(lngs), max(lats), max(lngs)],
                "ring": ring,
                "holes": part.get("holes") or [],
                "parts": [part],
                "area_sqm": round(max(0.0, _area(ring) - hole_area)),
            })
    rows.sort(key=lambda row: float(row["area_sqm"]), reverse=True)
    water = [row for row in rows if row["kind"] == "water"][:320]
    green = [row for row in rows if row["kind"] == "green"][:260]
    return sorted(water + green, key=lambda row: float(row["area_sqm"]), reverse=True)


def _city_bbox(city: dict[str, Any]) -> tuple[float, float, float, float]:
    boxes = _district_bboxes(city)
    return (
        min(box[0] for box in boxes) - 0.02,
        min(box[1] for box in boxes) - 0.02,
        max(box[2] for box in boxes) + 0.02,
        max(box[3] for box in boxes) + 0.02,
    )


def _mercator(lat: float, lng: float) -> tuple[float, float]:
    radius = 20_037_508.342789244
    x = lng / 180.0 * radius
    y = math.log(math.tan((90.0 + lat) * math.pi / 360.0)) * radius / math.pi
    return x, y


def _lnglat(x: float, y: float) -> tuple[float, float]:
    radius = 20_037_508.342789244
    lng = x / radius * 180.0
    lat = math.degrees(2.0 * math.atan(math.exp(y / radius * math.pi)) - math.pi / 2.0)
    return lng, lat


def _coastline_areas(city: dict[str, Any], reader: Any) -> list[dict[str, Any]]:
    """Clip OSM's global coastline water polygons to one city's district bbox."""
    try:
        from shapely.geometry import box, shape
        from shapely.ops import transform, unary_union
    except ImportError as error:
        raise RuntimeError("coastline mode requires shapely; install it in the build environment") from error
    south, west, north, east = _city_bbox(city)
    x1, y1 = _mercator(south, west)
    x2, y2 = _mercator(north, east)
    clip = box(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
    pieces = []
    for record in reader.shapes():
        bounds = record.bbox
        if bounds[2] < clip.bounds[0] or bounds[0] > clip.bounds[2]:
            continue
        if bounds[3] < clip.bounds[1] or bounds[1] > clip.bounds[3]:
            continue
        geometry = shape(record.__geo_interface__).intersection(clip)
        if not geometry.is_empty:
            pieces.append(geometry)
    if not pieces:
        return []
    geometry = unary_union(pieces)
    geometry = transform(lambda x, y, z=None: _lnglat(x, y), geometry)
    if not geometry.is_valid:
        geometry = geometry.buffer(0)
    geometry = geometry.simplify(0.00003, preserve_topology=True)
    polygons = list(geometry.geoms) if hasattr(geometry, "geoms") else [geometry]
    parts: list[dict[str, Any]] = []
    for polygon in polygons:
        if not hasattr(polygon, "exterior") or polygon.area <= 0:
            continue
        parts.append({
            "ring": [[round(lat, 6), round(lng, 6)] for lng, lat in polygon.exterior.coords],
            "holes": [
                [[round(lat, 6), round(lng, 6)] for lng, lat in hole.coords]
                for hole in polygon.interiors
            ],
        })
    if not parts:
        return []
    lats = [point[0] for part in parts for point in part["ring"]]
    lngs = [point[1] for part in parts for point in part["ring"]]
    area = sum(max(0.0, _area(part["ring"]) - sum(_area(hole) for hole in part["holes"])) for part in parts)
    return [{
        "kind": "water",
        "name": "海岸/海域（OSM coastline）",
        "bbox": [min(lats), min(lngs), max(lats), max(lngs)],
        "ring": parts[0]["ring"],
        "holes": parts[0]["holes"],
        "parts": parts,
        "area_sqm": round(area),
    }]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cities", nargs="*", help="city ids (default: all)")
    parser.add_argument(
        "--coastline-shapefile",
        default="",
        help="OSM simplified-water-polygons-split-3857 .shp path (recommended)",
    )
    parser.add_argument(
        "--skip-osm",
        action="store_true",
        help="preserve existing city polygons and only refresh coastline water",
    )
    args = parser.parse_args()
    catalog = _catalog()
    selected = args.cities or list(catalog)
    coastline_reader = None
    if args.coastline_shapefile:
        try:
            import shapefile  # type: ignore[import-not-found]
        except ImportError as error:
            raise SystemExit("coastline mode requires pyshp (`pip install pyshp shapely`)") from error
        coastline_reader = shapefile.Reader(args.coastline_shapefile)
    result = {
        "schema_version": 1,
        "source": "OpenStreetMap contributors",
        "license": "ODbL 1.0",
        "generated_at": date.today().isoformat(),
        "cities": {},
    }
    if OUTPUT.is_file():
        existing = _read(OUTPUT)
        if isinstance(existing.get("cities"), dict):
            result["cities"].update(existing["cities"])
    for city_id in selected:
        city = catalog.get(str(city_id))
        if city is None:
            raise SystemExit(f"unknown city: {city_id}")
        print(f"building {city_id}...", flush=True)
        if args.skip_osm:
            areas = list(result["cities"].get(str(city_id)) or [])
            elements: list[dict[str, Any]] = []
        else:
            elements = _query(city)
            areas = _areas(elements)
        if coastline_reader is not None:
            before = len(areas)
            areas = [
                row for row in areas
                if str(row.get("name") or "") != "海岸/海域（OSM coastline）"
            ]
            areas.extend(_coastline_areas(city, coastline_reader))
            print(f"  coastline {before} -> {len(areas)} polygons", flush=True)
        result["cities"][str(city_id)] = areas
        print(f"  {len(elements)} elements -> {len(areas)} terrain polygons", flush=True)
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        time.sleep(2.0)
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
