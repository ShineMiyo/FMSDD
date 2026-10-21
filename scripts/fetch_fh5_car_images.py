"""Download every Forza Horizon 5 car render from fh5.wikylyu.xyz.

Usage:
    py -3 -X utf8 scripts\\fetch_fh5_car_images.py [--out car_images] [--workers 10]

The public site exposes a JSON catalogue at /api/cars (902 entries) and renders at
/assets/images/cars/<id>.png. Entries without an upstream render are excluded.
Files are organised as
``<out>/<Manufacturer>/<Class>/<Name> (<Year>) [<id>].png`` and a manifest.json
records the full metadata for later use.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

API_CARS = "https://fh5.wikylyu.xyz/api/cars"
IMAGE_URL = "https://fh5.wikylyu.xyz/assets/images/cars/{id}.png"
USER_AGENT = "FMSDD-car-asset-fetch/1.0 (+local development)"
INVALID = re.compile(r'[<>:"/\\\\|?*\x00-\x1f]')
EXCLUDED_CAR_IDS = {899}


def sanitize(value: str, fallback: str = "unknown") -> str:
    text = INVALID.sub("_", str(value or "")).strip().rstrip(". ")
    text = re.sub(r"\s+", " ", text)
    return text or fallback


def fetch(url: str, timeout: int = 40) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def download_one(car: dict, out: Path) -> dict:
    car_id = int(car["id"])
    manufacturer = sanitize(car.get("manufacturer"), "Unknown")
    klass = sanitize(car.get("pi_class") or "Unclassified", "Unclassified")
    name = sanitize(car.get("name"), f"Car {car_id}")
    year = car.get("year") or ""
    label = f"{name} ({year}) [{car_id}]" if year else f"{name} [{car_id}]"
    target = out / manufacturer / klass / f"{label}.png"

    if target.is_file() and target.stat().st_size > 1024:
        data = target.read_bytes()
        status = "cached"
    else:
        last_error = None
        data = b""
        for attempt in range(3):
            try:
                data = fetch(IMAGE_URL.format(id=car_id))
                if data[:8] == b"\x89PNG\r\n\x1a\n":
                    break
                last_error = f"not a PNG ({data[:16]!r})"
                data = b""
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                last_error = str(error)
            time.sleep(0.6 * (attempt + 1))
        if not data:
            return {"id": car_id, "ok": False, "error": last_error, "path": None}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        status = "downloaded"

    record = {
        "id": car_id,
        "name": car.get("name"),
        "year": car.get("year"),
        "manufacturer": car.get("manufacturer"),
        "class": car.get("pi_class"),
        "pi": car.get("pi"),
        "rarity": car.get("rarity"),
        "country": car.get("country"),
        "dlc": car.get("dlc"),
        "type": car.get("type"),
        "path": target.relative_to(out).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "status": status,
    }
    return {"id": car_id, "ok": True, "record": record}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="car_images", help="output folder (default: car_images)")
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    out = (root / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    cars = json.loads(fetch(API_CARS, timeout=60))
    if not isinstance(cars, list) or not cars:
        raise SystemExit("the catalogue endpoint returned no cars")
    cars = [car for car in cars if int(car["id"]) not in EXCLUDED_CAR_IDS]
    print(f"catalogue: {len(cars)} usable cars", flush=True)

    records, failures = [], []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(download_one, car, out): car for car in cars}
        done = 0
        for future in as_completed(futures):
            result = future.result()
            done += 1
            if result["ok"]:
                records.append(result["record"])
            else:
                failures.append(result)
                print(f"  FAILED {futures[future]['name']} [{result['id']}]: {result['error']}", flush=True)
            if done % 50 == 0 or done == len(cars):
                print(f"  {done}/{len(cars)} processed", flush=True)

    records.sort(key=lambda item: (item["manufacturer"] or "", item["class"] or "", item["name"] or ""))
    class_counts = Counter(item["class"] or "Unclassified" for item in records)
    manifest = {
        "source": "https://fh5.wikylyu.xyz/cars",
        "api": API_CARS,
        "image_pattern": IMAGE_URL,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "count": len(records),
        "failed": len(failures),
        "classes": sorted({item["class"] or "Unclassified" for item in records}),
        "manufacturers": sorted({item["manufacturer"] or "Unknown" for item in records}),
        "cars": records,
        "failures": failures,
        "source_failures": [],
        "fallbacks": [],
        "class_counts": dict(sorted(class_counts.items())),
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n",
    )
    print(f"done: {len(records)} images, {len(failures)} failures -> {out}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
