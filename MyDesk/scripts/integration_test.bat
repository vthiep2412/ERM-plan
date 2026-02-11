@echo off
setlocal
pushd "%~dp0..\.."

echo ========================================
echo MyDesk Integration Test Suite
echo ========================================

echo.
echo [*] Phase 1: Global Syntax Check (compileall)...
echo     Checking Targets...
python -m compileall -q MyDesk/targets
if %ERRORLEVEL% NEQ 0 (
    echo [!] Phase 1 FAILED: Syntax error detected in targets!
    goto :fail
)
echo     Checking Viewer...
python -m compileall -q MyDesk/viewer
if %ERRORLEVEL% NEQ 0 (
    echo [!] Phase 1 FAILED: Syntax error detected in viewer!
    goto :fail
)
echo     Checking Core...
python -m compileall -q MyDesk/core
if %ERRORLEVEL% NEQ 0 (
    echo [!] Phase 1 FAILED: Syntax error detected in core!
    goto :fail
)
echo [OK] Phase 1 Passed.

echo.
echo [*] Phase 2: Indentation Audit...
python Test/audit_indentation.py MyDesk
if %ERRORLEVEL% NEQ 0 (
    echo [!] Phase 2 FAILED: Indentation issues detected!
    @REM We don't fail the whole build for indentation, but we warn loudly
    echo [WARN] Please fix indentation before deployment.
) else (
    echo [OK] Phase 2 Passed.
)

echo.
echo [*] Phase 3: Shell Regex Validation...
python Test/test_regex.py
if %ERRORLEVEL% NEQ 0 (
    echo [!] Phase 3 FAILED: Shell output parsing logic is broken!
    goto :fail
)
echo [OK] Phase 3 Passed.

echo.
echo [*] Phase 4: Hardware Acceleration Check (Informational)...
python Test/check_nvenc.py
echo [*] Phase 4 Complete. (Informational only)

echo.
echo [*] Phase 5: Dependency Verification...
if exist "MyDesk\requirements.txt" (
    echo [*] Verifying major packages...
    python -c "import aiortc; import av; import cv2; import mss; import numpy; print('[+] Core dependencies present.')" 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo [!] Phase 5 FAILED: Some core dependencies are missing from your environment!
        echo [TIP] Run: pip install -r MyDesk\requirements.txt
        goto :fail
    )
    echo [OK] Phase 5 Passed.
) else (
    echo [WARN] Phase 5 Skipped: requirements.txt not found.
)

echo.
echo [*] Phase 6: Logical Component Check (verify_syntax.py)...
pushd Test
python verify_syntax.py
if %ERRORLEVEL% NEQ 0 (
    echo [!] Phase 6 FAILED: Logical validation error!
    popd
    goto :fail
)
popd
echo [OK] Phase 6 Passed.

echo.
echo ========================================
echo [SUCCESS] All integration tests passed!
echo ========================================
popd
endlocal
exit /b 0

:fail
echo.
echo ========================================
echo [FAILURE] Integration tests failed!
echo ========================================
popd
endlocal
exit /b 1
