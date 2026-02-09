import sys
import os
import shutil
import subprocess
import ctypes
import winreg

# Check for Admin
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    # Re-run the program with admin rights
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

# Paths
INSTALL_DIR = r"C:\ProgramData\MyDesk"
SERVICE_A_SRC = "MyDeskServiceA.exe" # Expected in same dir as installer or _MEI
SERVICE_B_SRC = "MyDeskServiceB.exe"
AGENT_SRC = "MyDeskAgent.exe"

def install_services():
    print("Installing MyDesk Hydra...")
    
    # 1. Create Directory
    if not os.path.exists(INSTALL_DIR):
        os.makedirs(INSTALL_DIR)
    
    # 2. Kill existing if running
    subprocess.run("taskkill /F /IM MyDeskServiceA.exe", shell=True)
    subprocess.run("taskkill /F /IM MyDeskServiceB.exe", shell=True)
    subprocess.run("taskkill /F /IM MyDeskAgent.exe", shell=True)
    
    # 3. Copy/Extract Files
    # If running from PyInstaller bundle, look in sys._MEIPASS
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    
    try:
        shutil.copy(os.path.join(base_path, SERVICE_A_SRC), os.path.join(INSTALL_DIR, SERVICE_A_SRC))
        shutil.copy(os.path.join(base_path, SERVICE_B_SRC), os.path.join(INSTALL_DIR, SERVICE_B_SRC))
        # Agent might be downloaded later by Service A if missing, but we copy if present
        if os.path.exists(os.path.join(base_path, AGENT_SRC)):
            shutil.copy(os.path.join(base_path, AGENT_SRC), os.path.join(INSTALL_DIR, AGENT_SRC))
    except Exception as e:
        print(f"File Copy Error (ignoring if files exist): {e}")

    # 4. Register Services
    # Service A
    subprocess.run(f'{os.path.join(INSTALL_DIR, SERVICE_A_SRC)} --startup auto install', shell=True)
    # Service B
    subprocess.run(f'{os.path.join(INSTALL_DIR, SERVICE_B_SRC)} --startup auto install', shell=True)

    # 5. Safe Mode Whitelist (Registry)
    try:
        # HKLM\SYSTEM\CurrentControlSet\Control\SafeBoot\Minimal\MyDeskAudio
        key_str = r"SYSTEM\CurrentControlSet\Control\SafeBoot\Minimal"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_str, 0, winreg.KEY_ALL_ACCESS) as key:
            winreg.CreateKey(key, "MyDeskAudio")
            winreg.CreateKey(key, "MyDeskUpdate")
            
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_str + r"\MyDeskAudio", 0, winreg.KEY_WRITE) as sk:
            winreg.SetValueEx(sk, "", 0, winreg.REG_SZ, "Service")
            
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_str + r"\MyDeskUpdate", 0, winreg.KEY_WRITE) as sk:
            winreg.SetValueEx(sk, "", 0, winreg.REG_SZ, "Service")
            
        # Network as well
        key_net_str = r"SYSTEM\CurrentControlSet\Control\SafeBoot\Network"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_net_str, 0, winreg.KEY_ALL_ACCESS) as key:
            winreg.CreateKey(key, "MyDeskAudio")
            winreg.CreateKey(key, "MyDeskUpdate")
            
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_net_str + r"\MyDeskAudio", 0, winreg.KEY_WRITE) as sk:
            winreg.SetValueEx(sk, "", 0, winreg.REG_SZ, "Service")
            
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_net_str + r"\MyDeskUpdate", 0, winreg.KEY_WRITE) as sk:
            winreg.SetValueEx(sk, "", 0, winreg.REG_SZ, "Service")
            
        print("Safe Mode Persistence: ENABLED")
    except Exception as e:
        print(f"Registry Error: {e}")

    # 6. Start Services
    subprocess.run("sc start MyDeskAudio", shell=True)
    subprocess.run("sc start MyDeskUpdate", shell=True)
    
    print("Installation Complete.")

if __name__ == "__main__":
    try:
        install_services()
    except Exception as e:
        print(f"Fatal Error: {e}")
        input("Press Enter to exit...")
