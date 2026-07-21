@echo off
setlocal

REM ============================================================
REM  Build single-file YTMini.exe
REM  - Run this on a PC that has Python installed.
REM  - Output: dist\YTMini.exe  (standalone, no console window)
REM  - Target PC only needs the WebView2 runtime
REM    (preinstalled on most Windows 10/11 systems).
REM  - Uses "python -m ..." so it also works with Microsoft
REM    Store Python, whose Scripts dir is not on PATH.
REM ============================================================

python -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    python -m pip install pyinstaller
    if errorlevel 1 goto fail
)

python -m pip show pywebview >nul 2>nul
if errorlevel 1 (
    echo Installing pywebview...
    python -m pip install pywebview
    if errorlevel 1 goto fail
)

REM --- Show which WebView2 interop DLLs pywebview provides -------------
REM  If this list is empty, the exe will NOT be able to start WebView2
REM  ("Cannot find win-arm64" / init failure). Reinstall pywebview.
echo.
echo Checking bundled WebView2 DLLs in the installed pywebview...
python -c "import os,webview;base=os.path.join(os.path.dirname(webview.__file__),'lib');[print('   ',os.path.relpath(os.path.join(r,f),base)) for r,d,fs in os.walk(base) for f in fs if f.lower().endswith('.dll') and ('webview2' in f.lower())]" 2>nul

set ICON_OPTS=
if exist icon.ico (
    set ICON_OPTS=--icon icon.ico --add-data "icon.ico;."
) else (
    echo NOTE: icon.ico not found - building with default icon.
    echo       Copy icon.ico next to this file to use the custom icon.
)

REM  --collect-all pulls in every pywebview data/binary file (all arch
REM  WebView2 loaders). --collect-binaries is added explicitly so the
REM  native WebView2Loader.dll copies are never skipped by data-only
REM  collection. The running app also self-heals arch mismatches
REM  (x64 build under ARM emulation) at startup.
echo.
echo Building YTMini.exe ...
python -m PyInstaller --onefile --noconsole --clean --name YTMini %ICON_OPTS% --hidden-import webview.platforms.winforms --hidden-import webview.platforms.edgechromium --collect-all webview --collect-binaries webview youtube_mini.py
if errorlevel 1 goto fail

echo.
echo ============================================
echo  Done!  Output: dist\YTMini.exe
echo  Copy this single file to any PC and run it.
echo ============================================
pause
exit /b 0

:fail
echo.
echo Build FAILED. Check the error messages above.
pause
exit /b 1
