"""Read-only resolver for Football Manager face-pack portraits.

Face packs are user-owned files outside FMODD.  This module only exposes a
portrait for a numeric player UID when an XML mapping and an image underneath
the configured Football Manager ``graphics`` directory agree.  It never
returns arbitrary paths to the browser.
"""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Iterable


IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif")
UID_RE = re.compile(r"(?<!\d)(\d{4,})(?!\d)")
PERSON_TARGET_UID_RE = re.compile(
    r"(?:^|/)pictures/person/(\d+)(?:/|$)", re.IGNORECASE,
)
_RECORD_TAG_RE = re.compile(rb"<record\b[^>]*>", re.IGNORECASE | re.DOTALL)
_ATTRIBUTE_RE = re.compile(rb"([A-Za-z_:][\w:.-]*)\s*=\s*([\"'])(.*?)\2", re.DOTALL)
_LOCK = threading.RLock()
_PortraitRecord = tuple[Path, str, str]
_INDEX: dict[tuple[Path, str], tuple[int, dict[int, tuple[_PortraitRecord, ...]]]] = {}
_PATHS: dict[tuple[Path, str, int], tuple[int, tuple[Path, ...]]] = {}
_DIRECT: dict[tuple[Path, int, int], Path | None] = {}


def portrait_roots() -> tuple[Path, ...]:
    try:
        from tools.app_settings import load_settings
        configured_text = str(load_settings().get("portrait_graphics_root") or "").strip()
        configured = Path(configured_text).expanduser() if configured_text else None
        configured_roots = (configured,) if configured is not None and configured.is_dir() else ()
    except (ImportError, OSError, TypeError, ValueError):
        configured_roots = ()
    documents = Path.home() / "Documents" / "Sports Interactive"
    defaults = tuple(
        root for root in (
            documents / "Football Manager 26" / "graphics",
            documents / "Football Manager 2024" / "graphics",
        ) if root.is_dir()
    )
    return tuple(dict.fromkeys((*configured_roots, *defaults)))


def _uid(value: object) -> int | None:
    match = UID_RE.search(str(value or ""))
    if not match:
        return None
    try:
        result = int(match.group(1))
    except ValueError:
        return None
    return result if result > 0 else None


def _mapping_uid(source: str, target: str) -> int | None:
    """Prefer the canonical person UID encoded in an FM mapping target.

    Face-pack source filenames often contain unrelated serial numbers, for
    example ``PacificIslanders/PP1PacificIslanders0338``.  Those digits must
    not override the person UID in ``pictures/person/<uid>/portrait``.
    """
    target_text = str(target or "").replace("\\", "/")
    match = PERSON_TARGET_UID_RE.search(target_text)
    if match:
        try:
            result = int(match.group(1))
        except ValueError:
            result = 0
        if result > 0:
            return result
    return _uid(source) or _uid(target)


def _safe_child(root: Path, candidate: Path) -> Path | None:
    try:
        resolved = candidate.resolve()
        if resolved == root.resolve() or root.resolve() not in resolved.parents:
            return None
        return resolved
    except OSError:
        return None


def _standalone_xml_root(xml_path: Path) -> Path:
    """Prefer the enclosing FM graphics tree, otherwise the XML directory."""
    resolved = xml_path.resolve()
    return next(
        (parent for parent in resolved.parents if parent.name.casefold() == "graphics"),
        resolved.parent,
    )


def _image_candidates(root: Path, xml_path: Path, source: str, target: str, uid: int) -> Iterable[Path]:
    source_path = Path(source.replace("/", "\\"))
    target_text = target.replace("\\", "/").lstrip("/")
    if source_path.suffix.lower() in IMAGE_SUFFIXES:
        yield xml_path.parent / source_path
    else:
        for suffix in IMAGE_SUFFIXES:
            yield xml_path.parent / f"{source_path}{suffix}"

    # FM config.xml targets are virtual paths such as
    # graphics/pictures/person/<uid>/portrait.  Resolve them under the user's
    # graphics directory and try normal image suffixes.
    if target_text.lower().startswith("graphics/"):
        target_text = target_text[9:]
    target_path = root / Path(target_text)
    if target_path.suffix.lower() in IMAGE_SUFFIXES:
        yield target_path
    else:
        for suffix in IMAGE_SUFFIXES:
            yield Path(f"{target_path}{suffix}")

    # Common face-pack layout: pictures/person/<uid>/portrait.ext.
    common = root / "pictures" / "person" / str(uid) / "portrait"
    for suffix in IMAGE_SUFFIXES:
        yield Path(f"{common}{suffix}")


def _quick_image_candidates(root: Path, uid: int) -> Iterable[Path]:
    """Yield conventional face-pack paths before parsing large config XMLs.

    Popular FM packs keep the XML ``from`` stem beside the image, so these
    bounded probes avoid parsing a multi-megabyte config on every first card.
    The XML index remains the fallback for unusual layouts.
    """
    stems = (f"face_{uid}", str(uid))
    directories = (
        root,
        root / "faces",
        root / "iconfaces",
        root / "pictures" / "person" / str(uid),
        root / "sortitoutsi" / "faces",
        root / "sortitoutsi" / "iconfaces",
        root / "NG_Regens" / "faces",
        root / "NG_Regens" / "iconfaces",
        root / "portraits",
        root / "players",
    )
    for directory in directories:
        for stem in stems:
            for suffix in IMAGE_SUFFIXES:
                yield directory / f"{stem}{suffix}"
    for child in root.iterdir():
        if not child.is_dir():
            continue
        for directory in (child, child / "faces", child / "iconfaces", child / "portraits", child / "players"):
            for stem in stems:
                for suffix in IMAGE_SUFFIXES:
                    yield directory / f"{stem}{suffix}"
def _direct_image(root: Path, uid: int) -> Path | None:
    """Resolve a face-pack image by UID stem only, without config.xml."""
    try:
        stamp = root.stat().st_mtime_ns
    except OSError:
        return None
    key = (root, stamp, int(uid))
    with _LOCK:
        if key in _DIRECT:
            return _DIRECT[key]
    found: Path | None = None
    for candidate in _quick_image_candidates(root, uid):
        try:
            if candidate.suffix.lower() in IMAGE_SUFFIXES and candidate.is_file():
                found = _safe_child(root, candidate)
                if found:
                    break
        except OSError:
            continue
    if found is None:
        stems = {str(uid), f"face_{uid}"}
        visited = 0
        try:
            for current, directories, files in os.walk(root):
                depth = len(Path(current).relative_to(root).parts)
                if depth >= 6:
                    directories[:] = []
                for name in files:
                    visited += 1
                    if visited > 300_000:
                        break
                    path = Path(current) / name
                    stem = path.stem.casefold()
                    if stem in stems and path.suffix.lower() in IMAGE_SUFFIXES:
                        found = _safe_child(root, path)
                        break
                if found is not None or visited > 300_000:
                    break
        except OSError:
            found = None
    with _LOCK:
        _DIRECT[key] = found
    return found


def _configured_sources(settings: dict) -> tuple[tuple[Path, int], ...]:
    rows = settings.get("portrait_sources") if isinstance(settings, dict) else None
    if not isinstance(rows, (list, tuple)):
        return ()
    resolved: list[tuple[Path, int]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        text = str(row.get("path") or "").strip()
        if not text:
            continue
        root = Path(text).expanduser()
        if not root.is_dir():
            continue
        try:
            offset = int(row.get("offset") or 0)
        except (TypeError, ValueError):
            offset = 0
        resolved.append((root, max(-999, min(999, offset))))
    return tuple(resolved)


def _iter_portrait_records(
    xml_path: Path, target_uid: int | None = None,
) -> Iterable[tuple[str, str]]:
    """Read config records without building a full XML tree.

    Face packs commonly contain 40MB+ config files.  ``ElementTree.iterparse``
    is correct but disproportionately slow for these flat record lists (and
    makes the first portrait request appear to stop after the first config).
    The FM config dialect uses simple ``record`` tags, so extracting only
    their ``from``/``to`` attributes keeps the scan streaming-friendly while
    still allowing every XML below a graphics root to contribute mappings.
    """
    try:
        raw = xml_path.read_bytes()
    except OSError:
        return
    # Avoid running the attribute regex over unrelated kit/logo configs.  A
    # numeric UID must occur in either the source or target attribute for this
    # file to contain a usable mapping.
    if target_uid is not None and str(target_uid).encode("ascii") not in raw:
        return
    for match in _RECORD_TAG_RE.finditer(raw):
        attrs: dict[str, str] = {}
        for attr_match in _ATTRIBUTE_RE.finditer(match.group(0)):
            key = attr_match.group(1).decode("ascii", "ignore").casefold()
            if key in {"from", "uid", "to", "path"}:
                attrs[key] = attr_match.group(3).decode("utf-8", "ignore")
        source = attrs.get("from") or attrs.get("uid") or ""
        target = attrs.get("to") or attrs.get("path") or ""
        if source or target:
            yield source, target


def _build_index(
    root: Path, xml_path: Path | None = None,
) -> dict[int, tuple[_PortraitRecord, ...]]:
    """Build one shared UID-to-record catalog for a graphics source.

    Resolving image paths is deliberately deferred until a requested UID is
    looked up.  Large face packs can contain hundreds of thousands of records;
    checking every candidate image while building the catalog would trade the
    old repeated scan for one very long first request.
    """
    mapping: dict[int, list[_PortraitRecord]] = {}
    try:
        xml_files = (xml_path,) if xml_path is not None else sorted(
            root.rglob("*.xml"), key=lambda path: (
                0 if any(part.casefold() in {
                    "face", "faces", "iconface", "iconfaces", "portrait", "portraits",
                    "player", "players", "ng_regens",
                } for part in path.relative_to(root).parts[:-1]) else 1,
                str(path).casefold(),
            ),
        )
    except OSError:
        return {}
    for xml_path in xml_files:
        try:
            for source, target in _iter_portrait_records(xml_path):
                uid = _mapping_uid(source, target)
                if not uid:
                    continue
                mapping.setdefault(uid, []).append((xml_path, source, target))
        except (OSError, UnicodeError):
            continue
    return {uid: tuple(records) for uid, records in mapping.items()}


def _index_for(
    root: Path, xml_path: Path | None = None,
) -> tuple[int, dict[int, tuple[_PortraitRecord, ...]]]:
    try:
        stamp = root.stat().st_mtime_ns
        if xml_path is not None:
            stamp ^= xml_path.stat().st_mtime_ns
    except OSError:
        return 0, {}
    with _LOCK:
        key = (root, str(xml_path.resolve()).casefold() if xml_path else "")
        cached = _INDEX.get(key)
        if cached and cached[0] == stamp:
            return cached
        index = _build_index(root, xml_path)
        _INDEX[key] = (stamp, index)
        return stamp, index


def _paths_for(root: Path, uid: int, xml_path: Path | None = None) -> tuple[Path, ...]:
    """Resolve one UID from the shared catalog and cache the safe paths."""
    with _LOCK:
        stamp, index = _index_for(root, xml_path)
        xml_key = str(xml_path.resolve()).casefold() if xml_path else ""
        key = (root, xml_key, uid)
        cached = _PATHS.get(key)
        if cached and cached[0] == stamp:
            return cached[1]
        paths: list[Path] = []
        for record_xml, source, target in index.get(uid) or ():
            for candidate in _image_candidates(root, record_xml, source, target, uid):
                if (
                    candidate.suffix.lower() in IMAGE_SUFFIXES
                    and candidate.is_file()
                ):
                    safe = _safe_child(root, candidate)
                else:
                    safe = None
                if (
                    safe
                    and safe not in paths
                ):
                    paths.append(safe)
        result = tuple(paths)
        _PATHS[key] = (stamp, result)
        return result


def portrait_path(
    player_id: int, roots: Iterable[Path] | None = None,
    xml_path: Path | None = None, uid_offset: int | None = None,
) -> Path | None:
    try:
        uid = int(player_id)
    except (TypeError, ValueError):
        return None
    if uid <= 0:
        return None
    configured_xml_paths: tuple[Path, ...] = (Path(xml_path),) if xml_path is not None else ()
    resolved_offset = 0
    settings: dict = {}
    if roots is None and not configured_xml_paths:
        try:
            from tools.app_settings import load_settings
            settings = load_settings()
            resolved_offset = int(settings.get("portrait_uid_offset") or 0)
            raw_xml_paths = settings.get("portrait_xml_paths") or []
            if not isinstance(raw_xml_paths, (list, tuple)):
                raw_xml_paths = [settings.get("portrait_xml_path")]
            configured_xml_paths = tuple(dict.fromkeys(
                Path(str(raw)).expanduser() for raw in raw_xml_paths if str(raw or "").strip()
            ))
        except (ImportError, OSError, TypeError, ValueError):
            settings = {}
            configured_xml_paths = ()
    sources = _configured_sources(settings) if roots is None and not configured_xml_paths else ()
    if sources:
        for root, offset in sources:
            path = _direct_image(root, uid + offset)
            if path is not None:
                return path
        return None
    if uid_offset is not None:
        try:
            resolved_offset = int(uid_offset)
        except (TypeError, ValueError):
            resolved_offset = 0
    resolved_offset = max(-999, min(999, resolved_offset))
    face_uid = uid + resolved_offset
    if face_uid <= 0:
        return None
    selected_roots = tuple(roots) if roots is not None else portrait_roots()
    if configured_xml_paths:
        # Explicit XML selections are additive.  Preserve selection order so
        # a later XML wins when it supplies a newer portrait for the same UID.
        latest: Path | None = None
        for configured_xml in configured_xml_paths:
            if not configured_xml.is_file():
                continue
            root = _standalone_xml_root(configured_xml)
            for path in _paths_for(root, face_uid, configured_xml):
                if path.is_file():
                    latest = path
        return latest
    for root in selected_roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for candidate in _quick_image_candidates(root, face_uid):
            if candidate.suffix.lower() not in IMAGE_SUFFIXES or not candidate.is_file():
                continue
            safe = _safe_child(root, candidate)
            if safe:
                return safe
        latest: Path | None = None
        paths = _paths_for(root, face_uid)
        for path in paths:
            if path.is_file():
                latest = path
        if latest is not None:
            return latest
    return None


def clear_portrait_cache() -> None:
    with _LOCK:
        _INDEX.clear()
        _PATHS.clear()
        _DIRECT.clear()


__all__ = ["portrait_path", "portrait_roots", "clear_portrait_cache", "write_player_portrait"]


def write_player_portrait(
    graphics_root: Path | str, uid: int, payload: bytes, extension: str = "png",
) -> dict:
    """Write one child portrait and its FM config.xml record atomically.

    The caller must pass an already validated image payload and a UID obtained
    from the native youth intake. Existing config records for the same UID are
    replaced rather than duplicated.
    """
    import os
    from xml.etree import ElementTree as ET

    uid = int(uid or 0)
    if uid <= 0:
        raise ValueError("球员 UID 无效")
    data = bytes(payload or b"")
    if not data:
        raise ValueError("头像文件为空")
    if len(data) > 5 * 1024 * 1024:
        raise ValueError("头像文件不能超过 5 MB")
    suffix = str(extension or "png").lower().lstrip(".")
    if suffix == "jpeg":
        suffix = "jpg"
    if suffix not in {"png", "jpg", "webp"}:
        raise ValueError("头像只支持 PNG、JPG 或 WebP")
    root = Path(graphics_root).expanduser()
    if root.is_file():
        root = root.parent
    if not root.is_dir():
        raise ValueError("FM graphics 目录不存在")
    folder = root / "FMSDD" / "faces"
    folder.mkdir(parents=True, exist_ok=True)
    image = folder / f"{uid}.{suffix}"
    temp_image = folder / f".{uid}.{suffix}.tmp"
    temp_image.write_bytes(data)
    os.replace(temp_image, image)
    config = root / "FMSDD" / "config.xml"
    if config.exists():
        try:
            tree = ET.parse(config)
            records = tree.getroot()
        except ET.ParseError:
            records = ET.Element("records")
            tree = ET.ElementTree(records)
    else:
        records = ET.Element("records")
        tree = ET.ElementTree(records)
    target = f"graphics/pictures/person/{uid}/portrait"
    for record in list(records.findall("record")):
        if str(record.get("to") or "").replace("\\", "/").casefold() == target.casefold():
            records.remove(record)
    ET.SubElement(records, "record", {"from": f"faces/{uid}.{suffix}", "to": target})
    try:
        ET.indent(tree, space="  ")
    except AttributeError:
        pass
    temp_config = root / "FMSDD" / ".config.xml.tmp"
    tree.write(temp_config, encoding="utf-8", xml_declaration=True)
    os.replace(temp_config, config)
    clear_portrait_cache()
    return {"uid": uid, "image": str(image), "config": str(config), "extension": suffix}
