#!/usr/bin/env python3
"""Rename the freshly built FMODD.exe to its release name and write metadata."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
SOURCE = DIST / "FMODD.exe"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def product_version() -> str:
    text = read_text(ROOT / "src" / "fm_odds_web.py")
    match = re.search(r'PRODUCT_VERSION\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("Cannot find PRODUCT_VERSION in src/fm_odds_web.py")
    return match.group(1)


def dev_id() -> str:
    text = read_text(ROOT / "src" / "fm_odds_web.py")
    match = re.search(r'APP_VERSION\s*=.*?else\s+"([^"]+)"', text)
    return match.group(1) if match else ""


def file_version() -> str:
    text = read_text(ROOT / "src" / "desktop" / "WebViewHost.csproj")
    match = re.search(r"<FileVersion>([^<]+)</FileVersion>", text)
    return match.group(1).strip() if match else ""


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest().upper()


def replace_locked(target: Path) -> None:
    """Move a locked/old artifact aside instead of failing the build."""
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = target.with_name(f"{target.stem}.old-{stamp}{target.suffix}")
    try:
        os.replace(target, backup)
        print(f"  moved old package aside: {backup.name}")
    except OSError as error:
        raise SystemExit(f"Cannot replace {target}: {error}")


def main() -> int:
    if not SOURCE.is_file():
        raise SystemExit(f"Build output missing: {SOURCE}")

    version = product_version()
    json_path = DIST / f"FMSDD-{version}-release.json"
    previous = {}
    try:
        previous = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        previous = {}
    target = DIST / f"FMSDD-{version}.exe"
    if target.exists():
        replace_locked(target)
    shutil.move(str(SOURCE), str(target))

    size = target.stat().st_size
    sha = digest(target)
    stamp = dt.datetime.now().astimezone().replace(microsecond=0).isoformat()

    release = {
        "product": "FMSDD",
        "version": version,
        "file_version": file_version(),
        "dev_id": dev_id(),
        "asset": target.name,
        "size": size,
        "sha256": sha,
        "built_at": stamp,
    }
    sums_path = DIST / f"FMSDD-{version}-SHA256SUMS.txt"
    json_path.write_text(
        json.dumps(release, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    sums_path.write_text(f"{sha}  {target.name}\n", encoding="utf-8")

    print("")
    print("Package ready")
    print(f"  {target}")
    print(f"  {size:,} bytes")
    print(f"  SHA-256 {sha}")
    print(f"  {json_path.name}")
    print(f"  {sums_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
