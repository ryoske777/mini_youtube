@echo off
setlocal

REM ============================================================
REM  Build YTMini (one-folder / onedir).
REM  - Run this on a PC that has Python installed.
REM  - Output: dist\YTMini\  (folder with YTMini.exe + files)
REM    Run dist\YTMini\YTMini.exe. Distribute by zipping the folder.
REM  - Why onedir: onefile unpacks to a temp dir (_MEIxxxx) each run
REM    and deletes it on exit; a lingering WebView2 child makes that
REM    delete fail with "Failed to remove temporary directory".
REM    onedir has no temp dir, so that warning never happens, and it
REM    starts faster. The app's built-in auto-update keeps the code
REM    current, so you only distribute the folder once.
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
echo Building YTMini (onedir) ...
python -m PyInstaller --onedir --noconsole --clean --name YTMini %ICON_OPTS% --hidden-import webview.platforms.winforms --hidden-import webview.platforms.edgechromium --collect-all webview --collect-binaries webview youtube_mini.py
if errorlevel 1 goto fail

echo.
echo Zipping dist\YTMini into dist\YTMini.zip ...
powershell -NoProfile -Command "if (Test-Path 'dist\YTMini') { Compress-Archive -Path 'dist\YTMini\*' -DestinationPath 'dist\YTMini.zip' -Force }" 2>nul

echo.
echo ============================================
echo  Done!  Output folder: dist\YTMini\
echo  Run:  dist\YTMini\YTMini.exe
echo  Distribute: dist\YTMini.zip  (unzip, run YTMini.exe)
echo ============================================
pause
exit /b 0

:fail
echo.
echo Build FAILED. Check the error messages above.
pause
exit /b 1
