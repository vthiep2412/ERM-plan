"""
Remote Input Controller for MyDesk Agent
Handles mouse and keyboard simulation from Viewer commands.
"""
import struct

try:
    from pynput.mouse import Button, Controller as MouseController
    from pynput.keyboard import Key, Controller as KeyboardController
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False
    print("[-] pynput not available, remote input disabled")

class InputController:
    def __init__(self, screen_width=None, screen_height=None):
        self.mouse = None
        self.keyboard = None
        
        if HAS_PYNPUT:
            try:
                self.mouse = MouseController()
                self.keyboard = KeyboardController()
            except Exception as e:
                print(f"[-] Input Controller Init Failed: {e}")
                
        # Auto-detect screen size
        if screen_width is None or screen_height is None:
            screen_width, screen_height = self._detect_screen_size()
            
        self.screen_width = screen_width
        self.screen_height = screen_height
        print(f"[+] InputController: Screen {screen_width}x{screen_height}")

    def _detect_screen_size(self):
        try:
            import mss
            with mss.mss() as sct:
                mon = sct.monitors[1]  # Primary monitor
                return mon['width'], mon['height']
        except Exception:
            pass
            
        try:
            import ctypes
            user32 = ctypes.windll.user32
            return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        except Exception:
            return 1920, 1080
    
    def set_screen_size(self, width, height):
        """Update screen dimensions for coordinate mapping"""
        self.screen_width = width
        self.screen_height = height
    
    def move_mouse(self, x_norm, y_norm):
        """Move mouse to normalized coordinates (0.0-1.0)"""
        if not self.mouse:
            return
        try:
            x = int(x_norm * self.screen_width)
            y = int(y_norm * self.screen_height)
            self.mouse.position = (x, y)
        except Exception:
            pass
    
    def click_mouse(self, button, pressed):
        """
        Click mouse button.
        button: 1=Left, 2=Right, 4=Middle
        pressed: True=down, False=up
        """
        if not self.mouse:
            return
        
        try:
            btn_map = {
                1: Button.left,
                2: Button.right,
                4: Button.middle
            }
            btn = btn_map.get(button, Button.left)
            
            if pressed:
                self.mouse.press(btn)
            else:
                self.mouse.release(btn)
        except Exception as e:
            print(f"[-] Mouse Click Error: {e}")
    
    def scroll(self, dx, dy):
        """Scroll mouse wheel"""
        if not self.mouse:
            return
        try:
            self.mouse.scroll(dx, dy)
        except Exception:
            pass
    
    def press_key(self, key_code, pressed):
        """
        Press or release a key.
        key_code: Qt key code or character
        """
        if not self.keyboard:
            return
            
        try:
            key = self._map_qt_key(key_code)
            if key is None:
                return

            if pressed:
                self.keyboard.press(key)
            else:
                self.keyboard.release(key)
        except Exception as e:
            print(f"[-] Key Error: {e}")

    def _map_qt_key(self, key_code):
        """Map Qt key code to pynput Key"""
        if not HAS_PYNPUT:
            return None
            
        # Helper to safely get Key attribute
        def get_key(name):
            try:
                return getattr(Key, name)
            except AttributeError:
                return None

        special_keys = {
            16777216: get_key('escape'),
            16777217: get_key('tab'),
            16777219: get_key('backspace'),
            16777220: get_key('enter'),
            16777221: get_key('enter'),
            16777222: get_key('insert'),
            16777223: get_key('delete'),
            16777232: get_key('home'),
            16777233: get_key('end'),
            16777234: get_key('left'),
            16777235: get_key('up'),
            16777236: get_key('right'),
            16777237: get_key('down'),
            16777238: get_key('page_up'),
            16777239: get_key('page_down'),
            16777248: get_key('shift'),
            16777249: get_key('ctrl'),
            16777251: get_key('alt'),
            16777252: get_key('caps_lock'),
            16777264: get_key('f1'),
            16777265: get_key('f2'),
            16777266: get_key('f3'),
            16777267: get_key('f4'),
            16777268: get_key('f5'),
            16777269: get_key('f6'),
            16777270: get_key('f7'),
            16777271: get_key('f8'),
            16777272: get_key('f9'),
            16777273: get_key('f10'),
            16777274: get_key('f11'),
            16777275: get_key('f12'),
            16777299: get_key('cmd'),
        }
        
        if key_code in special_keys:
            return special_keys[key_code]
        elif 32 <= key_code <= 126:
            return chr(key_code).lower()
        
        return None
    
    def type_text(self, text):
        """Type a string of text (for buffered input)"""
        if not self.keyboard:
            return
        try:
            self.keyboard.type(text)
        except Exception as e:
            print(f"[-] Type Error: {e}")


def parse_mouse_move(payload):
    """Parse mouse move payload: 2 floats (x, y) normalized 0.0-1.0"""
    if len(payload) >= 8:
        x, y = struct.unpack('!ff', payload[:8])
        return x, y
    return None, None

def parse_mouse_click(payload):
    """Parse mouse click payload: button (1 byte) + pressed (1 byte)"""
    if len(payload) >= 2:
        button = payload[0]
        pressed = payload[1] == 1
        return button, pressed
    return None, None

def parse_key_press(payload):
    """Parse key press payload: key_code (4 bytes) + pressed (1 byte)"""
    if len(payload) >= 5:
        key_code = struct.unpack('!I', payload[:4])[0]
        pressed = payload[4] == 1
        return key_code, pressed
    return None, None

def parse_scroll(payload):
    """Parse scroll payload: dx, dy (2 signed shorts). 
    Requires at least 4 bytes; trailing bytes are ignored for consistency with other parsers.
    """
    if len(payload) < 4:
        print(f"[!] parse_scroll: Short payload ({len(payload)} bytes, expected 4)")
        return 0, 0
    dx, dy = struct.unpack('!hh', payload[:4])
    return dx, dy


# ============================================================================
#  DIRECT INPUT (Low-Level Windows Injection)
# ============================================================================
import ctypes

# C Structs for SendInput
PUL = ctypes.POINTER(ctypes.c_ulong)
class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.c_void_p)]  # ULONG_PTR
class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]
class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.c_void_p)]  # ULONG_PTR
class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput),
                ("mi", MouseInput),
                ("hi", HardwareInput)]
class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]

# Constants
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_UNICODE = 0x0004
MAPVK_VK_TO_VSC_EX = 0x04  # Extended scan code mapping

# Scan Code Mapping (REMOVED: Using MapVirtualKeyW instead)

def press_key_direct(hexKeyCode, pressed):
    """
    Uses SendInput with ScanCodes for DirectX compatibility.
    hexKeyCode: Virtual Key Code (VK)
    """
    # Platform Guard
    if not (hasattr(ctypes, "windll") and hasattr(ctypes.windll, "user32")):
        return False

    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    
    # Flags
    flags = 0
    if not pressed:
        flags |= KEYEVENTF_KEYUP
    
    # We use Virtual Key codes (VK) -> Scan Code conversion by Windows
    # to avoid manual mapping hell
    # MAPVK_VK_TO_VSC_EX handles extended keys better (numpad, arrows)
    scan_code = ctypes.windll.user32.MapVirtualKeyW(hexKeyCode, MAPVK_VK_TO_VSC_EX)
    
    # Error Check for MapVirtualKeyW
    if scan_code == 0:
        # Some keys (like PrtSc) might fail or need special handling, but unexpected failures should be logged
        print(f"[-] MapVirtualKeyW failed for VK: 0x{hexKeyCode:02X}")
        # We can try to proceed if it's a known key that doesn't strictly need mapping (rare), 
        # or just abort. Aborting is safer to avoid sending garbage.
        return False
    
    # If MapVirtualKey fails or it's a special extended key (arrows)
    # 0x25=Left, 0x26=Up, 0x27=Right, 0x28=Down
    # 0x2D=Ins, 0x2E=Del, 0x21=PgUp, 0x22=PgDn, 0x23=End, 0x24=Home
    if hexKeyCode in [0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x21, 0x22, 0x23, 0x24]: 
        flags |= KEYEVENTF_EXTENDEDKEY

    # Use Scan Code mode for games
    flags |= KEYEVENTF_SCANCODE

    ii_.ki = KeyBdInput(0, scan_code, flags, 0, extra.value)
    x = Input(INPUT_KEYBOARD, ii_)
    
    result = ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))
    if result == 0:
        error_code = ctypes.windll.kernel32.GetLastError()
        print(f"[-] SendInput Failed! Error Code: {error_code}, VK: 0x{hexKeyCode:02X}, Scan: 0x{scan_code:02X}")
        return False
    
    return True

# Monkey Patch InputController to use Direct Input if on Windows
if HAS_PYNPUT and hasattr(ctypes, 'windll'):
    print("[+] Enhanced DirectInput (ctypes) Enabled")
    
    # Add VK mapping helper
    # Maps Qt key codes to Windows VK Codes
    def qt_to_vk(key_code):
        # Alphanumerics only (A-Z, a-z, 0-9)
        # These map directly to VK codes. Symbols are handled by pynput fallback.
        if ord('0') <= key_code <= ord('9'):
            return key_code  # 0-9 match VK
        if ord('A') <= key_code <= ord('Z'):
            return key_code  # A-Z match VK
        if ord('a') <= key_code <= ord('z'):
            return key_code - 32  # Convert to uppercase VK
        
        qt_vk_map = {
            32: 0x20,       # Space
            16777216: 0x1B, # Esc
            16777217: 0x09, # Tab
            16777219: 0x08, # Backspace
            16777220: 0x0D, # Enter
            16777221: 0x0D, # Enter Num
            16777248: 0x10, # Shift
            16777249: 0x11, # Ctrl
            16777251: 0x12, # Alt
            16777252: 0x14, # Caps Lock
            16777235: 0x26, # Up
            16777237: 0x28, # Down
            16777234: 0x25, # Left
            16777236: 0x27, # Right
            16777222: 0x2D, # Insert
            16777223: 0x2E, # Delete
            16777232: 0x24, # Home
            16777233: 0x23, # End
            16777238: 0x21, # Page Up
            16777239: 0x22, # Page Down
            16777264: 0x70, # F1
            16777265: 0x71, # F2
            16777266: 0x72, # F3
            16777267: 0x73, # F4
            16777268: 0x74, # F5
            16777269: 0x75, # F6
            16777270: 0x76, # F7
            16777271: 0x77, # F8
            16777272: 0x78, # F9
            16777273: 0x79, # F10
            16777274: 0x7A, # F11
            16777275: 0x7B, # F12
            16777299: 0x5B, # Win / Meta (Left Win)
        }
        return qt_vk_map.get(key_code, 0)

    # Override the method
    original_press = InputController.press_key
    
    def press_key_enhanced(self, key_code, pressed):
        vk = qt_to_vk(key_code)
        if vk > 0:
            try:
                if press_key_direct(vk, pressed):
                    return
            except Exception as e:
                print(f"[-] DirectInput Error: {e}, falling back to pynput")
        
        # Fallback to pynput if vk=0 or DirectInput failed/returned False
        original_press(self, key_code, pressed)
            
    InputController.press_key = press_key_enhanced
