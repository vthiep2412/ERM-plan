@echo off
setlocal
pushd "%~dp0..\.."

echo ========================================
echo MyDesk Integration Test Suite
echo ========================================

echo.
echo [*] Phase 1: Global Syntax Check (compileall)...
python -m compileall -q MyDesk/targets
if %ERRORLEVEL% NEQ 0 (
    echo [!] Phase 1 FAILED: Syntax error detected in targets!
    popd
    @REM pause
    exit /b 1
)
echo [OK] Phase 1 Passed.

echo.
echo [*] Phase 2: Logical Component Check (verify_syntax.py)...
pushd Test
python verify_syntax.py
if %ERRORLEVEL% NEQ 0 (
    echo [!] Phase 2 FAILED: Logical validation error!
    popd
    popd
    @REM pause
    exit /b 1
)
popd

echo.
echo ========================================
echo [SUCCESS] All integration tests passed!
echo ========================================
popd
@REM pause
endlocal
