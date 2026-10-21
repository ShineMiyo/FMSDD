"""Build the local single-file FMODD executable with PyInstaller.

The official release pipeline (PyInstaller spec, protection configuration and
the private ``tools/_release_integrity`` module) is not part of this public
source tree, and a frozen runtime refuses to load its native cores without
that integrity module. This builder therefore stages the source tree, writes
a minimal ``tools/_release_integrity`` that records the SHA-256 of the two
bundled native libraries at build time, and then runs PyInstaller one-file
with the FMODD icon, the WebView2 desktop host, web assets and runtime data.

The result is a functionally complete single EXE for local/test distribution;
it is a consistency check, not a signed replacement for the official
protected packaging. The staging copy of ``src`` is refreshed on every run.

Usage:
    py scripts\\build_single_exe.py               -> dist\\FMODD.exe
    py scripts\\build_single_exe.py --smoke-web   -> also build a console
        web entry under build\\single_exe\\smoke for headless validation
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "build" / "single_exe"
STAGING_SRC = STAGE / "staging" / "src"
SOURCE_SRC = ROOT / "src"
NATIVE_LIBRARIES = {
    "tools/fmodd_native_core.dll": SOURCE_SRC / "build" / "rust_native" / "fmodd_native_core.dll",
    "tools/fmodd_hook_core.dll": SOURCE_SRC / "build" / "cpp_native" / "fmodd_hook_core.dll",
}
DESKTOP_HOST_EXE = SOURCE_SRC / "desktop_host" / "FMODD.WebViewHost.exe"
DESKTOP_BUILD_EXE = SOURCE_SRC / "desktop" / "bin" / "Release" / "net48" / "FMODD.WebViewHost.exe"
DESKTOP_PROJECT = SOURCE_SRC / "desktop" / "WebViewHost.csproj"
STAGING_SKIP_REL = {
    "src/data",
    "src/desktop/bin",
    "src/desktop/obj",
    "src/FMDataBridge/bin",
    "src/FMDataBridge/obj",
    "src/tools/embedded_web_assets.py",
}


def product_version() -> str:
    text = (SOURCE_SRC / "fm_odds_web.py").read_text(encoding="utf-8")
    match = re.search(r'PRODUCT_VERSION\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("PRODUCT_VERSION not found in src/fm_odds_web.py")
    return match.group(1)


def version_numbers(version: str) -> tuple[int, int, int]:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        return (0, 0, 0)
    return tuple(int(part) for part in match.groups())


def binary_version_numbers(version: str) -> tuple[int, int, int, int]:
    """Match the desktop host's numeric FileVersion instead of resetting revision."""
    try:
        project = DESKTOP_PROJECT.read_text(encoding="utf-8")
    except OSError:
        project = ""
    match = re.search(r"<FileVersion>\s*(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?\s*</FileVersion>", project)
    if match:
        return tuple(int(part or 0) for part in match.groups())
    v0, v1, v2 = version_numbers(version)
    return (v0, v1, v2, 0)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sync_desktop_host(version: str) -> None:
    """Package the freshly built host instead of a stale runtime copy."""
    if not DESKTOP_BUILD_EXE.is_file():
        raise SystemExit(
            "desktop host build missing: run "
            "dotnet build src/desktop/WebViewHost.csproj -c Release first."
        )
    shutil.copy2(DESKTOP_BUILD_EXE, DESKTOP_HOST_EXE)
    title = f"FMSDD {version}".encode("utf-16le")
    if title not in DESKTOP_HOST_EXE.read_bytes():
        raise SystemExit(
            f"desktop host title does not match {version}; rebuild WebViewHost.csproj."
        )
    print(f"desktop host synced: {DESKTOP_HOST_EXE}")


def ignore_for_staging(directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        relative = (Path(directory) / name).relative_to(ROOT).as_posix()
        if name == "__pycache__":
            ignored.add(name)
        elif relative in STAGING_SKIP_REL:
            ignored.add(name)
        elif relative.startswith("src/native/") and name == "target":
            ignored.add(name)
    return ignored


def stage_sources() -> None:
    refreshed = STAGING_SRC.exists()
    if refreshed:
        shutil.rmtree(STAGING_SRC)
    shutil.copytree(SOURCE_SRC, STAGING_SRC, ignore=ignore_for_staging)
    print(f"{'refreshed' if refreshed else 'staged'}: {STAGING_SRC}")


INTEGRITY_TEMPLATE = '''"""Locally generated integrity checks for this build.

Written by scripts/build_single_exe.py at packaging time. It records the
SHA-256 of the bundled native libraries and verifies them before load; the
official release pipeline replaces this module with its own protected
implementation.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_NATIVE_LIBRARIES = __MANIFEST__


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_native_library(path: str, packaged_name: str) -> list[str]:
    expected = _NATIVE_LIBRARIES.get(packaged_name)
    if expected is None:
        return [f"unexpected native library: {packaged_name}"]
    candidate = Path(path)
    if not candidate.is_file():
        return [f"missing native library: {packaged_name}"]
    if _sha256(candidate) != expected:
        return [f"native library hash mismatch: {packaged_name}"]
    return []


def verify_packaged_files(root: str) -> list[str]:
    errors: list[str] = []
    base = Path(root)
    for relative, expected in _NATIVE_LIBRARIES.items():
        candidate = base / relative
        if not candidate.is_file():
            errors.append(f"missing packaged file: {relative}")
        elif _sha256(candidate) != expected:
            errors.append(f"packaged file hash mismatch: {relative}")
    return errors
'''


def write_integrity_module() -> None:
    manifest: dict[str, str] = {}
    for packaged_name, path in NATIVE_LIBRARIES.items():
        if not path.is_file():
            raise SystemExit(f"native library missing: {path}")
        manifest[packaged_name] = sha256_file(path)
    target = STAGING_SRC / "tools" / "_release_integrity.py"
    target.write_text(
        INTEGRITY_TEMPLATE.replace("__MANIFEST__", json.dumps(manifest, indent=4)),
        encoding="utf-8", newline="\n",
    )
    print(f"integrity module written: {target}")


VERSION_TEMPLATE = """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({v0}, {v1}, {v2}, {v3}),
    prodvers=({v0}, {v1}, {v2}, {v3}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'FMSDD'),
         StringStruct('FileDescription', 'FMSDD'),
         StringStruct('FileVersion', '{file_version}'),
         StringStruct('InternalName', 'FMODD'),
         StringStruct('OriginalFilename', '{original}'),
         StringStruct('ProductName', 'FMSDD'),
         StringStruct('ProductVersion', '{product}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def write_version_file(name: str, version: str) -> Path:
    v0, v1, v2, v3 = binary_version_numbers(version)
    path = STAGE / f"version_info_{name}.txt"
    path.write_text(
        VERSION_TEMPLATE.format(
            v0=v0, v1=v1, v2=v2, v3=v3,
            file_version=f"{v0}.{v1}.{v2}.{v3}",
            original=f"{name}.exe",
            product=version,
        ),
        encoding="utf-8", newline="\n",
    )
    return path


def run_pyinstaller(entry: Path, name: str, windowed: bool, dist: Path, work: Path) -> None:
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile"]
    if windowed:
        args.append("--windowed")
    args += [
        "--name", name,
        "--icon", str(SOURCE_SRC / "assets" / "desktop" / "fmodd.ico"),
        "--version-file", str(write_version_file(name, product_version())),
        "--hidden-import", "tools._release_integrity",
        "--distpath", str(dist),
        "--workpath", str(work),
        "--specpath", str(work),
        "--add-data", f"{SOURCE_SRC / 'web'};web",
        "--add-data", f"{SOURCE_SRC / 'assets'};assets",
        "--add-data", f"{SOURCE_SRC / 'desktop_host'};desktop_host",
        "--add-binary", f"{NATIVE_LIBRARIES['tools/fmodd_native_core.dll']};tools",
        "--add-binary", f"{NATIVE_LIBRARIES['tools/fmodd_hook_core.dll']};tools",
        str(entry),
    ]
    print("running:", " ".join(args))
    result = subprocess.run(args, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"PyInstaller failed with code {result.returncode}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--smoke-web", action="store_true",
        help="also build the console web entry for headless validation",
    )
    args = parser.parse_args()
    version = product_version()
    sync_desktop_host(version)
    stage_sources()
    write_integrity_module()
    run_pyinstaller(
        STAGING_SRC / "fmodd_desktop.py", "FMODD", True,
        ROOT / "dist", STAGE / "work_desktop",
    )
    if args.smoke_web:
        run_pyinstaller(
            STAGING_SRC / "fm_odds_web.py", "FMODD-web", False,
            STAGE / "smoke", STAGE / "work_web",
        )
    exe = ROOT / "dist" / "FMODD.exe"
    if exe.is_file():
        print(f"built: {exe} ({exe.stat().st_size / 1024 / 1024:.1f} MiB, {version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
