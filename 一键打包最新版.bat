@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title FMSDD - build latest EXE

echo ============================================
echo   FMSDD  latest EXE builder
echo ============================================
echo.

if /I "%~1"=="--no-pause" set "NOPAUSE=1"

set "PY="
where py >nul 2>nul
if not errorlevel 1 (
  py -3.14 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY=py -3.14"
)
if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
    if not errorlevel 1 set "PY=python"
  )
)
if not defined PY (
  echo [ERROR] Python 3.12+ was not found.
  echo         Install Python or make sure the py launcher is on PATH.
  goto :failed
)

if not exist "scripts\build_single_exe.py" (
  echo [ERROR] scripts\build_single_exe.py was not found.
  echo         Run this BAT from the repository root.
  goto :failed
)

echo [1/3] Building the desktop host...
where dotnet >nul 2>nul
if not errorlevel 1 (
  dotnet build "src\desktop\WebViewHost.csproj" -c Release
  if errorlevel 1 (
    echo [ERROR] Desktop host build failed.
    goto :failed
  )
) else (
  echo [WARN] dotnet was not found; reusing the existing desktop host.
)

echo.
echo [2/3] Building the single-file EXE...
%PY% "scripts\build_single_exe.py"
if errorlevel 1 (
  echo [ERROR] EXE build failed.
  goto :failed
)

echo.
echo [3/3] Naming the package and writing the checksum...
%PY% "scripts\package_latest.py"
if errorlevel 1 (
  echo [ERROR] Packaging failed.
  goto :failed
)

echo.
echo [DONE] Latest package is in the dist folder.
echo        Close the running FMSDD app before rebuilding if the EXE is locked.
if not defined NOPAUSE pause
exit /b 0

:failed
echo.
echo [FAILED] Nothing was published.
if not defined NOPAUSE pause
exit /b 1
