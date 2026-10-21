"""Build the FMSDD source-runtime package under dist/.

The package bundles the current source tree, the built native cores and
desktop host, and a pinned Python embeddable runtime plus launcher, so
testers can run the app without installing Python themselves. It is a
development/test distribution and does not replace the official protected
release pipeline.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_EMBED_VERSION = "3.14.6"
PYTHON_EMBED_URL = (
    "https://www.python.org/ftp/python/"
    f"{PYTHON_EMBED_VERSION}/python-{PYTHON_EMBED_VERSION}-embed-amd64.zip"
)
PYTHON_EMBED_SHA256 = "df901e84a896ff1ee720ad03377e0c8d8c2244fda79808aeeaff6316df1cb75c"
EMBED_ZIP = (
    Path(os.environ.get("TEMP", ""))
    / f"python-{PYTHON_EMBED_VERSION}-embed-amd64.zip"
)

ROOT_SKIP = {
    ".github",
    ".pytest_cache",
    "__pycache__",
    "build",
    "car_images",
    "data",
    "dist",
    "logs",
    "ODD.ico",
}
SRC_SKIP_REL = {
    "src/data",
    "src/desktop/bin",
    "src/desktop/obj",
    "src/FMDataBridge/bin",
    "src/FMDataBridge/obj",
}


def product_version() -> str:
    text = (ROOT / "src" / "fm_odds_web.py").read_text(encoding="utf-8")
    match = re.search(r'PRODUCT_VERSION\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("PRODUCT_VERSION not found in src/fm_odds_web.py")
    return match.group(1)


def ensure_embed_archive() -> None:
    if EMBED_ZIP.is_file():
        digest = hashlib.sha256(EMBED_ZIP.read_bytes()).hexdigest()
        if digest == PYTHON_EMBED_SHA256:
            return
    with urllib.request.urlopen(PYTHON_EMBED_URL, timeout=120) as response:
        payload = response.read()
    if hashlib.sha256(payload).hexdigest() != PYTHON_EMBED_SHA256:
        raise SystemExit("Python embeddable archive checksum mismatch; nothing was written.")
    EMBED_ZIP.write_bytes(payload)


def ignore_for(base: Path):
    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for name in names:
            relative = (Path(directory) / name).relative_to(base).as_posix()
            if name == "__pycache__":
                ignored.add(name)
            elif relative in SRC_SKIP_REL:
                ignored.add(name)
            elif relative.startswith("src/native/") and name == "target":
                ignored.add(name)
        return ignored
    return ignore


def copy_source_tree(pkg: Path) -> None:
    for entry in sorted(ROOT.iterdir()):
        if entry.name in ROOT_SKIP or entry.name == "dist":
            continue
        target = pkg / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, ignore=ignore_for(ROOT))
        elif entry.is_file():
            shutil.copy2(entry, target)


def build_embedded_runtime(pkg: Path) -> None:
    runtime = pkg / "runtime"
    runtime.mkdir()
    with zipfile.ZipFile(EMBED_ZIP) as archive:
        archive.extractall(runtime)
    pth = runtime / "python314._pth"
    lines = pth.read_text(encoding="utf-8").splitlines()
    if r"..\src" not in lines:
        lines.append(r"..\src")
    pth.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8", newline="")


LAUNCHER = '''@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "FMSDD_ENTRY=%~dp0src\\fmodd_desktop.py"
if not exist "%FMSDD_ENTRY%" (
    echo Entry script not found. Please extract the archive completely.
    pause
    exit /b 1
)
if exist "%~dp0runtime\\pythonw.exe" (
    start "FMSDD" "%~dp0runtime\\pythonw.exe" "%FMSDD_ENTRY%"
    exit /b 0
)
where pyw.exe >nul 2>nul
if %errorlevel%==0 (
    start "FMSDD" pyw.exe "%FMSDD_ENTRY%"
    exit /b 0
)
where pythonw.exe >nul 2>nul
if %errorlevel%==0 (
    start "FMSDD" pythonw.exe "%FMSDD_ENTRY%"
    exit /b 0
)
echo Python was not found. Install Python 3.10+ or keep the bundled runtime folder.
pause
exit /b 1
'''

README_TEXT = '''FMSDD {version} 源码运行包（Windows）

一、运行
1. 将压缩包完整解压到任意目录（建议路径不含特殊字符）。
2. 双击“Start-FMSDD.cmd”。程序会打开桌面窗口，并自动启动本机服务。
3. 桌面窗口依赖 WebView2 运行时；Windows 10/11 一般已自带，缺失时请从微软官网安装：
   https://developer.microsoft.com/microsoft-edge/webview2/

二、自带运行时
包内 runtime\\ 已附带 Python 3.14.6 嵌入版，无需另装 Python；
若文件夹缺失，启动脚本会回退使用本机 PATH 中的 pyw / pythonw。

三、数据与自定义字体
数据目录位于 src\\data\\（存档隔离、账户、日志等）。
自定义界面字体：将字体文件（.ttf/.otf/.ttc/.woff/.woff2）放入
  src\\data\\fonts\\chinese  —— 简体中文字体
  src\\data\\fonts\\latin    —— 英文与数字字体
然后在“设置 → 界面字体”中点击“刷新字体列表”。

四、浏览器模式（开发预览）
双击 src\\run_fm_odds_web_preview.bat（需 PATH 中有 Python），或运行：
  runtime\\python.exe src\\fm_odds_web.py --port 7857 --keep-alive
然后访问 http://127.0.0.1:7857

五、说明
本包为源码运行形态，供测试与开发使用；正式 EXE 成品请从官网获取。
本包不包含任何游戏文件；内存读取与 Hook 功能仅在连接 Football Manager 并按版本校验后启用。
'''


def write_launchers(pkg: Path, version: str) -> None:
    (pkg / "Start-FMSDD.cmd").write_text(LAUNCHER, encoding="utf-8", newline="\r\n")
    (pkg / "README-运行说明.txt").write_text(
        README_TEXT.format(version=version), encoding="utf-8", newline="\r\n",
    )


def main() -> None:
    version = product_version()
    pkg = ROOT / "dist" / f"FMSDD-{version}-source-runtime"
    if pkg.exists():
        raise SystemExit(
            f"package directory already exists: {pkg}\n"
            "Remove or rename it first to rebuild."
        )
    ensure_embed_archive()
    pkg.mkdir(parents=True)
    copy_source_tree(pkg)
    build_embedded_runtime(pkg)
    write_launchers(pkg, version)
    files = [path for path in pkg.rglob("*") if path.is_file()]
    total = sum(path.stat().st_size for path in files)
    print(f"package: {pkg}")
    print(f"files: {len(files)}  size: {total / 1024 / 1024:.1f} MiB")


if __name__ == "__main__":
    main()
