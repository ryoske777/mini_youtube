@echo off
setlocal

REM ============================================================
REM  Build YTMini (single-file / onefile).
REM  - Run this on a PC that has Python installed.
REM  - Output: dist\YTMini.exe  (single file, no _internal folder needed).
REM    Run dist\YTMini.exe directly. Distribute by copying that one file.
REM  - onefile unpacks to a temp dir (%TEMP%\_MEIxxxx) on each run and
REM    removes it on exit. Older builds used onedir to dodge a bug where
REM    a lingering WebView2 child process ("msedgewebview2.exe") locked
REM    that temp dir and caused "Failed to remove temporary directory".
REM    The app now explicitly kills WebView2 child processes and waits
REM    before exiting (see _kill_descendants() in youtube_mini.py), so
REM    onefile no longer hits that warning.
REM  - Startup is slightly slower than onedir (extraction each launch).
REM    The app's built-in auto-update keeps the code current either way.
REM  - Target PC only needs the WebView2 runtime
REM    (preinstalled on most Windows 10/11 systems).
REM  - Uses "python -m ..." so it also works with Microsoft Store
REM    Python, whose Scripts dir is not on PATH.
REM  NOTE: keep this file ASCII-only. Non-ASCII (e.g. Korean) comments
REM        corrupt cmd parsing on cp949 consoles.
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

REM Show which WebView2 interop DLLs the installed pywebview provides.
REM If this list is empty, WebView2 cannot start ("Cannot find win-...").
echo.
echo Checking bundled WebView2 DLLs in the installed pywebview...
python -c "import os,webview;b=os.path.join(os.path.dirname(webview.__file__),'lib');[print('   ',os.path.relpath(os.path.join(r,f),b)) for r,d,fs in os.walk(b) for f in fs if f.lower().endswith('.dll') and 'webview2' in f.lower()]" 2>nul

set ICON_OPTS=
if exist icon.ico (
    set ICON_OPTS=--icon icon.ico --add-data "icon.ico;."
) else (
    echo NOTE: icon.ico not found - building with default icon.
)

echo.
echo Building YTMini (onefile) ...
python -m PyInstaller --onefile --noconsole --clean --name YTMini %ICON_OPTS% --hidden-import webview.platforms.winforms --hidden-import webview.platforms.edgechromium --collect-all webview --collect-binaries webview youtube_mini.py
if errorlevel 1 goto fail

echo.
echo ============================================
echo  Done!  Output file: dist\YTMini.exe
echo  Run:  dist\YTMini.exe
echo  Distribute: just copy dist\YTMini.exe (no other files needed).
echo ============================================
pause
exit /b 0

:fail
echo.
echo Build FAILED. Check the error messages above.
pause
exit /b 1
