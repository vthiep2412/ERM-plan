import win32api
import win32security
from ctypes import windll, c_bool


def is_safe_mode():
    """Check if the system is in Safe Mode."""
    # SM_CLEANBOOT (0x43)
    # 0 = Normal, 1 = Safe Mode, 2 = Safe Mode with Network
    return windll.user32.GetSystemMetrics(0x43) != 0


def set_critical_status(is_critical):
    """Set process as Critical (BSOD on termination)."""
    if is_safe_mode():
        # NEVER set critical in Safe Mode to avoid bricking
        return False

    try:
        # RtlSetProcessIsCritical
        ntdll = windll.ntdll
        # args: NewValue, OldValue(out), NeedSystemPrivilege
        # We need SeDebugPrivilege enabled first usually, but services have it.
        ret = ntdll.RtlSetProcessIsCritical(c_bool(is_critical), None, c_bool(False))
        return ret == 0
    except Exception:
        return False


def protect_process():
    """
    Modify the DACL of the current process to deny termination.
    """
    if is_safe_mode():
        print("[-] Protection: Skipped (Safe Mode)")
        return False

    h_process = None
    try:
        # Use a real handle with READ_CONTROL (0x20000) and WRITE_DAC (0x40000)
        # READ_CONTROL + WRITE_DAC + PROCESS_QUERY_INFORMATION = 0x60400
        current_pid = win32api.GetCurrentProcessId()
        h_process = win32api.OpenProcess(0x60400, False, current_pid)

        # 1. Create a brand NEW ACL
        dacl = win32security.ACL()

        # 2. Add an explicit 'Deny Everyone' ACE
        # This is more robust than an empty DACL.
        # PROCESS_ALL_ACCESS (0x1FFFFF) covers terminate, thread, vm, query, etc.
        everyone_sid = win32security.CreateWellKnownSid(win32security.WinWorldSid, None)
        dacl.AddAccessDeniedAce(win32security.ACL_REVISION, 0x1FFFFF, everyone_sid)

        # 3. Set the security info with PROTECTED flag
        # This stops all inheritance and applies our 'Absolute Deny' wall.
        win32security.SetSecurityInfo(
            h_process,
            win32security.SE_KERNEL_OBJECT,
            win32security.DACL_SECURITY_INFORMATION
            | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
            None,
            None,
            dacl,
            None,
        )

        print("[+] Process Protection Applied (Absolute Deny DACL)")
        return True
    except Exception as e:
        print(f"[-] Protection Failed: {e}")
        return False
    finally:
        if h_process:
            win32api.CloseHandle(h_process)
