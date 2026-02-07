
import ctypes
from ctypes import wintypes
import time
import threading

# Definitions
ULONG_PTR = ctypes.c_void_p
PULONG_PTR = ctypes.POINTER(ULONG_PTR)

# Structs from input_blocker
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p)
    ]

# Structs from input_controller
class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.c_void_p)]

class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]

# Constants
WH_KEYBOARD_LL = 13
HC_ACTION = 0
INPUT_KEYBOARD = 1
WM_KEYDOWN = 0x0100

received_extra_info = None
hook_thread_id = None

def hook_proc(nCode, wParam, lParam):
    global received_extra_info
    if nCode == HC_ACTION:
        kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        # Capture dwExtraInfo
        val = kb.dwExtraInfo
        if val is None:
            received_extra_info = 0
        elif isinstance(val, int):
            received_extra_info = val
        else:
            received_extra_info = val.value if val else 0
        
        # Determine if matches 0xFFC3C3
        print(f"Hook saw dwExtraInfo: {received_extra_info} (Type: {type(received_extra_info)})")
        
    return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)

HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
proc = HOOKPROC(hook_proc)

def install_hook():
    global hook_thread_id
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    h_mod = kernel32.GetModuleHandleW(None)
    hhk = user32.SetWindowsHookExW(WH_KEYBOARD_LL, proc, h_mod, 0)
    print(f"Hook installed: {hhk}")
    
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
    
    user32.UnhookWindowsHookEx(hhk)

def send_input_bad_way():
    print("Sending Input using BAD way (address of variable)...")
    val = 0xFFC3C3
    extra_info = ctypes.c_ulong(val)
    
    ii_ = Input_I()
    # The way it is in input_controller.py:
    # ctypes.cast(ctypes.byref(extra_info), ctypes.c_void_p)
    # This passes the address of extra_info, e.g. 0x000000D4
    
    # We want to see what strict value arrives
    ptr = ctypes.cast(ctypes.byref(extra_info), ctypes.c_void_p)
    print(f"Address being sent: {ptr.value}")
    
    ii_.ki = KeyBdInput(0x41, 0, 0, 0, ptr) # 0x41 = A
    inp = Input(INPUT_KEYBOARD, ii_)
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(Input))

def send_input_good_way():
    print("Sending Input using GOOD way (direct value)...")
    val = 0xFFC3C3
    
    ii_ = Input_I()
    # Passing the value directly as c_void_p
    ii_.ki = KeyBdInput(0x42, 0, 0, 0, ctypes.c_void_p(val)) # 0x42 = B
    inp = Input(INPUT_KEYBOARD, ii_)
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(Input))

def main():
    t = threading.Thread(target=install_hook, daemon=True)
    t.start()
    time.sleep(1) # Wait for hook
    
    send_input_bad_way()
    time.sleep(0.5)
    
    send_input_good_way()
    time.sleep(0.5)
    
    print("Test Complete")

if __name__ == "__main__":
    main()
