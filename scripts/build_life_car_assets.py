"""Build transparent runtime car images from the downloaded PNG source library.

Usage:
    py -3 -X utf8 scripts\\build_life_car_assets.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SOURCE_MANIFEST = ROOT / "car_images" / "manifest.json"
CATALOG = ROOT / "src" / "assets" / "life" / "cars.json"
OUTPUT = ROOT / "src" / "web" / "assets" / "life" / "cars"


def transparent_render(source: Path, target: Path) -> str:
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGBA")
    alpha = image.getchannel("A")
    bounds = alpha.getbbox()
    if bounds is None:
        raise ValueError(f"source image is fully transparent: {source}")
    image = image.crop(bounds)
    if image.width > 640:
        height = round(image.height * 640 / image.width)
        image = image.resize((640, height), Image.Resampling.LANCZOS)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "WEBP", quality=92, method=6, alpha_quality=100)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def main() -> int:
    manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    sources = {int(row["id"]): row for row in manifest["cars"]}
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    changed = 0
    for car in catalog["cars"]:
        source_id = int(car["source_id"])
        source_row = sources.get(source_id)
        if source_row is None:
            raise SystemExit(f"missing source image metadata for car {source_id}")
        source = ROOT / "car_images" / str(source_row["path"])
        if not source.is_file():
            raise SystemExit(f"missing source image: {source}")
        target = OUTPUT / f"car-{source_id}.webp"
        checksum = transparent_render(source, target)
        image_path = f"/assets/life/cars/{target.name}"
        if car.get("image") != image_path or car.get("image_sha256") != checksum:
            changed += 1
        car["image"] = image_path
        car["image_sha256"] = checksum
    CATALOG.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(f"built {len(catalog['cars'])} transparent WebP images; catalog changed: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
