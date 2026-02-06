@echo off
setlocal
cd /d "%~dp0.."

echo ==========================================
echo    MyDesk CLEAN BUILD (WebRTC Optimized)
echo ==========================================

:: 1. Create clean virtual environment
echo [*] Creating clean virtual environment...
if exist .venv_build rmdir /s /q .venv_build
python -m venv .venv_build
call .venv_build\Scripts\activate.bat

:: 2. Install minimal dependencies
echo [*] Installing minimal dependencies...
pip install --no-cache-dir ^
    opencv-python-headless ^
    aiortc ^
    websockets ^
    pynput ^
    mss ^
    numpy ^
    msgpack ^
    pillow ^
    pyaudio ^
    requests ^
    psutil ^
    dxcam ^
    zstandard ^
    pyinstaller

if %errorlevel% neq 0 (
    echo [!] Failed to install dependencies!
    pause
    exit /b 1
)

:: 3. Build Agent
echo.
echo [*] Building Agent with clean dependencies...
python -m PyInstaller MyDeskAgent.spec --clean --noconfirm

if %errorlevel% neq 0 (
    echo [!] BUILD FAILED!
    pause
    exit /b 1
)

:: 4. Report size
echo.
echo ==========================================
echo         BUILD COMPLETE!
echo ==========================================
for %%I in (dist\MyDeskAgent.exe) do echo Size: %%~zI bytes (%%~zI / 1048576 = MB)
dir dist\*.exe
echo.

:: Deactivate venv
deactivate
