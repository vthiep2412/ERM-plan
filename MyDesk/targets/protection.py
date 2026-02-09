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
        
        # Create 'Everyone' SID
        everyone_sid = win32security.SID()
        everyone_sid.Initialize(win32security.SECURITY_WORLD_SID_AUTHORITY, 1)
        everyone_sid.SetSubAuthority(0, win32security.SECURITY_WORLD_RID)
        
        # Add Deny ACE for Terminate & Suspend
        # PROCESS_TERMINATE = 0x0001
        # PROCESS_SUSPEND_RESUME = 0x0800
        mask = win32con.PROCESS_TERMINATE | win32con.PROCESS_SUSPEND_RESUME | win32con.PROCESS_VM_OPERATION | win32con.PROCESS_VM_WRITE
        
        dacl.AddAccessDeniedAce(dacl.GetAceCount(), mask, everyone_sid)
        
        # Set the new DACL
        win32security.SetSecurityInfo(
            h_process,
            win32security.SE_KERNEL_OBJECT,
            win32security.DACL_SECURITY_INFORMATION,
            None, None, dacl, None
        )
        return True
    except Exception:
        # print(f"Protection Failed: {e}")
        return False
