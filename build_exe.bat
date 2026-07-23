@echo off
setlocal

REM ============================================================
REM  Build YTMini (one-folder / onedir).
REM  - Run this on a PC that has Python installed.
REM  - Output: dist\YTMini\  (folder containing YTMini.exe + files)
REM    Run dist\YTMini\YTMini.exe. Distribute by zipping the folder.
REM  - onedir 를 쓰는 이유: onefile 은 실행 때마다 임시폴더(_MEIxxxx)에
REM    풀었다가 종료 시 지우는데, WebView2 자식이 물고 있으면 'Failed to
REM    remove temporary directory' 경고가 뜬다. onedir 은 임시폴더 자체가
REM    없어 그 경고가 원천 발생하지 않고, 시작도 더 빠르다.
REM  - 코드 업데이트는 앱 내장 자동 업데이트로 처리되므로, 폴더 배포는
REM    한 번만 하면 된다 (이후엔 재시작만으로 최신 코드 적용).
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
echo Building YTMini (onedir) ...
python -m PyInstaller --onedir --noconsole --clean --name YTMini %ICON_OPTS% --hidden-import webview.platforms.winforms --hidden-import webview.platforms.edgechromium --collect-all webview --collect-binaries webview youtube_mini.py
if errorlevel 1 goto fail

REM 배포용 zip 생성 (있으면 편함) — PowerShell 로 압축
echo.
echo Zipping dist\YTMini -> dist\YTMini.zip ...
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
