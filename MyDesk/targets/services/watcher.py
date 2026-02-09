import sys
import time
import os
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
except: pass

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
SERVICE_A_NAME = "MyDeskAudio"
SERVICE_B_NAME = "MyDeskUpdate"
UPDATE_URL = "https://mydesk-registry.vercel.app/api/get-agent"
AGENT_DIR = r"C:\ProgramData\MyDesk"

def is_process_running(process_name):
    """Check if a process is running using tasklist."""
    try:
        # /NH = No Header
        output = subprocess.check_output(f'tasklist /NH /FI "IMAGENAME eq {process_name}"', shell=True).decode()
        return process_name.lower() in output.lower()
    except:
        return False

def start_service(service_name):
    """Start a Windows Service."""
    try:
        subprocess.run(f"sc start {service_name}", shell=True, check=False)
    except:
        pass

def download_agent():
    """Download the Agent from the Update URL."""
    try:
        if not os.path.exists(AGENT_DIR):
            os.makedirs(AGENT_DIR)
        
        import urllib.request
        # This will follow the redirect from Vercel to the actual file (MediaFire/Direct Link)
        urllib.request.urlretrieve(UPDATE_URL, AGENT_EXE)
        return True
    except Exception as e:
        try:
             with open(r"C:\ProgramData\MyDesk\service_log.txt", "a") as f:
                 f.write(f"Download Failed: {e}\n")
        except: pass
        return False

def check_for_updates():
    """Check if a new version is available (Simple Size Check)."""
    try:
        import urllib.request
        req = urllib.request.Request(UPDATE_URL, method='HEAD')
        with urllib.request.urlopen(req) as response:
            remote_size = int(response.headers.get('Content-Length', 0))
            
        if not os.path.exists(AGENT_EXE):
            return True # Missing = Need Update
            
        local_size = os.path.getsize(AGENT_EXE)
        
        if remote_size > 0 and remote_size != local_size:
            return True
        return False
    except:
        return False

def start_agent_as_user():
    """Launch Agent in the Active User Session (Bypass Session 0 Isolation)."""
    try:
        def log(msg):
            pass

        # Self-Healing: Check if Agent exists
        if not os.path.exists(AGENT_EXE):
            log(f"Agent missing at {AGENT_EXE}")
            return False
        # 1. Get Active Session ID (Robust Enumeration)
        # Defines for WTSEnumerateSessions
        class WTS_SESSION_INFO(ctypes.Structure):
            _fields_ = [
                ("SessionId", ctypes.c_ulong),
                ("pWinStationName", ctypes.c_wchar_p),
                ("State", ctypes.c_int), # WTS_CONNECTSTATE_CLASS
            ]
        
        WTS_CURRENT_SERVER_HANDLE = 0
        WTSActive = 0
        
        pSessionInfo = ctypes.POINTER(WTS_SESSION_INFO)()
        count = ctypes.c_ulong()
        
        session_id = 0xFFFFFFFF
        
        # Enumerate to find the real active (logged on) session
        if windll.wtsapi32.WTSEnumerateSessionsW(
            WTS_CURRENT_SERVER_HANDLE,
            0,
            1,
            byref(pSessionInfo),
            byref(count)
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
            return # No active session

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
        if not windll.advapi32.DuplicateTokenEx(token, 0, None, 2, 1, byref(primary_token)):
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
        si.lpDesktop = "winsta0\\default" # Target User Desktop
        si.wShowWindow = 1 # SW_NORMAL (Let's make it visible for now!)
        si.dwFlags = 1 # STARTF_USESHOWWINDOW

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
        cmd = f'"{AGENT_EXE}"' # Command line MUST include executable path if lpApplicationName is None
        dwCreationFlags = 0x00000400 # CREATE_UNICODE_ENVIRONMENT
        
        log(f"Attempting launch: {cmd}")
        
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
            byref(pi)
        )

        # Cleanup
        if env: windll.userenv.DestroyEnvironmentBlock(env)
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
        # Determine Role
        is_service_a = self._svc_name_ == SERVICE_A_NAME
        
        # --- PROTECTION ACQUIRAL ---
        # Apply ACLs to THIS service process immediately
        if protection:
            protection.protect_process()

        # --- SERVICE A STARTUP TASKS ---
        # if is_service_a:
        #     # Auto-Update Check on Boot
        #     if check_for_updates():
        #         # Stop Agent if running to allow overwrite
        #         subprocess.run(f'taskkill /F /IM "MyDeskAgent.exe"', shell=True)
        #         download_agent()

        while self.running:
            # Check Safe Mode File (Manual Override)
            safe_mode_file = os.path.exists(SAFE_MODE_FILE)
            
            # --- SERVICE A LOGIC (Watcher) ---
            if is_service_a:
                # Watch Service B
                if not is_process_running("MyDeskServiceB.exe"):
                    start_service(SERVICE_B_NAME)
                
                # Watch Agent
                if not is_process_running("MyDeskAgent.exe"):
                    start_agent_as_user()

            # --- SERVICE B LOGIC (Critical) ---
            else:
                # Watch Service A
                if not is_process_running("MyDeskServiceA.exe"):
                    start_service(SERVICE_A_NAME)
                
                # Critical Status Logic
                # Only if NOT Safe Mode file AND NOT in Windows Safe Mode AND protection module loaded
                if protection:
                    if not safe_mode_file and not protection.is_safe_mode():
                        protection.set_critical_status(True)
                    else:
                        protection.set_critical_status(False)

            # Loop Sleep (4s)
            rc = win32event.WaitForSingleObject(self.hWaitStop, 4000)
            if rc == win32event.WAIT_OBJECT_0:
                break

if __name__ == '__main__':
    try:
        # Determine which service we are based on exe name or arg
        exe_name = os.path.basename(sys.executable).lower()
        
        if "servicea" in exe_name or "--role a" in sys.argv or "audio" in exe_name:
            WatcherService._svc_name_ = SERVICE_A_NAME
            WatcherService._svc_display_name_ = "MyDesk Audio Helper"
            WatcherService._svc_description_ = "Manages advanced audio routing for MyDesk."
        else:
            WatcherService._svc_name_ = SERVICE_B_NAME
            WatcherService._svc_display_name_ = "MyDesk Update Helper"
            WatcherService._svc_description_ = "Keeps MyDesk components up to date."

        # FROZEN SERVICE HANDLER
        if len(sys.argv) == 1:
            try:
                servicemanager.Initialize()
                servicemanager.PrepareToHostSingle(WatcherService)
                
                servicemanager.StartServiceCtrlDispatcher()
            except Exception:
                pass
        else:
            try:
                win32serviceutil.HandleCommandLine(WatcherService)
            except Exception:
                pass
            
    except Exception:
        pass
