from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from tools.app_paths import DATA_ROOT


# User-supplied interface fonts live outside the application tree so they
# survive upgrades: one folder for Simplified Chinese faces, one for Latin
# letters and digits. The folders are created on demand by the settings scan.
USER_FONT_ROOT = DATA_ROOT / "fonts"
USER_FONT_FOLDERS = {
    "chinese": USER_FONT_ROOT / "chinese",
    "latin": USER_FONT_ROOT / "latin",
}
USER_FONT_SUFFIXES = (".ttf", ".otf", ".ttc", ".woff", ".woff2")
USER_FONT_CONTENT_TYPES = {
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".ttc": "font/collection",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}
USER_FONT_CSS_FORMATS = {
    ".ttf": "truetype",
    ".otf": "opentype",
    ".woff": "woff",
    ".woff2": "woff2",
}
USER_FONT_ID_PATTERN = re.compile(r"^(?:chinese|latin)-[0-9a-f]{20}$")
MAX_USER_FONT_BYTES = 128 * 1024 * 1024


def _font_id(scope: str, path: Path) -> str:
    digest = hashlib.sha256(f"{scope}/{path.name}".encode("utf-8")).hexdigest()
    return f"{scope}-{digest[:20]}"


def _font_files(folder: Path) -> list[Path]:
    try:
        children = sorted(folder.iterdir(), key=lambda item: item.name.casefold())
    except OSError:
        return []
    return [
        path for path in children
        if path.is_file() and path.suffix.casefold() in USER_FONT_SUFFIXES
    ]


def scan_user_fonts() -> dict[str, Any]:
    """Ensure the drop-in folders exist and list every usable font file."""
    folders: dict[str, str] = {}
    fonts: list[dict[str, Any]] = []
    for scope, folder in USER_FONT_FOLDERS.items():
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        folders[scope] = str(folder)
        for path in _font_files(folder):
            suffix = path.suffix.casefold()
            font_id = _font_id(scope, path)
            fonts.append({
                "id": font_id,
                "scope": scope,
                "name": path.stem,
                "suffix": suffix.removeprefix("."),
                "css_format": USER_FONT_CSS_FORMATS.get(suffix, ""),
                "url": f"/api/font-file?id={font_id}",
            })
    return {"folders": folders, "fonts": fonts}


def resolve_user_font(font_id: Any) -> Path | None:
    """Map a scanned font id back to its file inside the drop-in folders."""
    value = str(font_id or "")
    if not USER_FONT_ID_PATTERN.fullmatch(value):
        return None
    scope = value.split("-", 1)[0]
    folder = USER_FONT_FOLDERS.get(scope)
    if folder is None:
        return None
    for path in _font_files(folder):
        if _font_id(scope, path) == value:
            return path
    return None


def user_font_content_type(path: Path) -> str:
    return USER_FONT_CONTENT_TYPES.get(path.suffix.casefold(), "application/octet-stream")
