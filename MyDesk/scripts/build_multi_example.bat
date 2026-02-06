@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo    MyDesk MULTI-BUILDER EXAMPLE
echo ==========================================

:: 1. Cleanup first
if exist ..\dist rmdir /s /q ..\dist
mkdir ..\dist

:: 2. Build 3 Variants
:: Usage: build_variant.bat <Name> <IconPath> <VersionFile>

echo.
echo [1/3] Building Work Agent...
call build_variant.bat "WorkAgent" "scripts\icon.ico" "scripts\version_work.txt"

echo.
echo [2/3] Building Home Service...
call build_variant.bat "HomeService" "scripts\icon.ico" "scripts\version_home.txt"

echo.
echo [3/3] Building NVIDIA Container...
call build_variant.bat "nvcontainer" "scripts\icon.ico" "scripts\version_stealth.txt"

echo.
echo ==========================================
echo    ALL VARIANTS BUILT!
echo ==========================================
pause
