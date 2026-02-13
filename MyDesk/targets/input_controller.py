"""
Remote Input Controller for MyDesk Agent
Handles mouse and keyboard simulation using native SendInput for Hook compatibility.
"""

import struct
import ctypes

try:
    from targets.input_blocker import block_input as hook_block_input
except ImportError:
    hook_block_input = None

# We no longer use pynput because it doesn't reliably set LLKHF_INJECTED flags for our hooks.
HAS_PYNPUT = False

INJECTED_SIGNATURE = 0xFFC3C3
DEBUG = False


def debug_log(msg):
    if DEBUG:
        print(f"[DEBUG][InputController] {msg}")


class InputController:
    def __init__(self, screen_width=None, screen_height=None):
        self.screen_width = screen_width
        self.screen_height = screen_height

        # Caching for Desktop Switching
        self.cached_h_desktop = None
        self.last_desktop_name = None

        # Auto-detect screen size
        if screen_width is None or screen_height is None:
            self.screen_width, self.screen_height = self._detect_screen_size()

        print(
            f"[+] InputController (Native SendInput): Screen {self.screen_width}x{self.screen_height}"
        )

    def __del__(self):
        """Cleanup any cached desktop handles to prevent leaks."""
        if hasattr(self, "cached_h_desktop") and self.cached_h_desktop:
            try:
                # Close the handle using user32.CloseDesktop
                ctypes.windll.user32.CloseDesktop(self.cached_h_desktop)
            except Exception:
                pass
            self.cached_h_desktop = None

    def block_input(self, block: bool):
        """
        Block physical input devices using LowLevel Hooks.
        Allows injected input (SendInput) to pass through.
        """
        if hook_block_input:
            hook_block_input(block)
        else:
            print("[-] Hook Blocker not available.")

    def _detect_screen_size(self):
        try:
            import mss

            with mss.mss() as sct:
                mon = sct.monitors[1]
                return mon["width"], mon["height"]
        except:
            user32 = ctypes.windll.user32
            return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

    def set_screen_size(self, width, height):
        self.screen_width = width
        self.screen_height = height

    # =========================================================================
    # NATIVE INJECTION HELPERS (SendInput)
    # =========================================================================

    def _get_current_input_desktop_name(self):
        """Helper to get name of current input desktop for change detection."""
        h_desk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x0100) # READOBJECTS
        if not h_desk:
            return None
            
        name = None
        try:
            # Get name length first
            needed = ctypes.c_ulong()
            ctypes.windll.user32.GetUserObjectInformationW(h_desk, 2, None, 0, ctypes.byref(needed))
            
            if needed.value:
                # Get name
                buff = ctypes.create_unicode_buffer(needed.value)
                if ctypes.windll.user32.GetUserObjectInformationW(h_desk, 2, buff, needed.value, ctypes.byref(needed)):
                    name = buff.value
        except:
            pass
        finally:
            ctypes.windll.user32.CloseDesktop(h_desk)
        return name

    def _switch_to_input_desktop(self):
        """
        CRITICAL: Switch calling thread to the Active Input Desktop (Default or Winlogon).
        Now Optimized with Caching to avoid OpenInputDesktop on every move.
        """
        try:
            user32 = ctypes.windll.user32
            
            current_name = self._get_current_input_desktop_name()
            if not current_name:
                return # Open failed, maybe access denied or transient
                
            # If name matches cached, do nothing (we likely are already set, or reused handle is fine)
            if self.cached_h_desktop and self.last_desktop_name == current_name:
                # We assume thread is still attached. 
                # (SetThreadDesktop is per-thread, so if we did it once, we stay there unless changed)
                return

            # Desktop Changed!
            # Close old
            if self.cached_h_desktop:
                user32.CloseDesktop(self.cached_h_desktop)
                self.cached_h_desktop = None
            
            self.last_desktop_name = current_name
            # print(f"[*] Attaching Input to Desktop: {self.last_desktop_name}")
            
            # 1. Open the active input desktop
            ACCESS_FLAGS = 0x01FF 
            h_desktop = user32.OpenInputDesktop(0, False, ACCESS_FLAGS)
            
            if not h_desktop:
                # print(f"[-] OpenInputDesktop Failed: {ctypes.GetLastError()}")
                return

            # 2. Set the current thread to this desktop
            if not user32.SetThreadDesktop(h_desktop):
                 print(f"[-] SetThreadDesktop Failed: {ctypes.GetLastError()}")
                 user32.CloseDesktop(h_desktop)
                 return
            
            # 3. Cache it (DO NOT CLOSE IT yet)
            self.cached_h_desktop = h_desktop
            
            # NOTE: usage of cached handle implies we keep it open.
            # We must close it on cleanup or new switch.

        except Exception as e:
            print(f"[-] Desktop Switch Error: {e}")

    def _send_input(self, input_struct):
        # Switch if needed (handled internally)
        self._switch_to_input_desktop()
        
        ctypes.windll.user32.SendInput(
            1, ctypes.byref(input_struct), ctypes.sizeof(Input)
        )

    def move_mouse(self, x_norm, y_norm):
        """Move mouse using MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE"""
        if not self.screen_width:
            return

        # Windows Absolute Coords are 0-65535
        x = int(x_norm * 65535)
        y = int(y_norm * 65535)

        ii_ = Input_I()
        # Flags: MOVE | ABSOLUTE | VIRTUALDESK (optional)
        ii_.mi = MouseInput(
            x,
            y,
            0,
            MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
            0,
            ctypes.c_void_p(INJECTED_SIGNATURE),
        )

        # debug_log(f"Move Mouse: {x}, {y} (Sig: {hex(INJECTED_SIGNATURE)})")

        command = Input(ctypes.c_ulong(0), ii_)  # 0 = INPUT_MOUSE
        self._send_input(command)

    def click_mouse(self, button, pressed):
        """Click mouse button using SendInput"""
        ii_ = Input_I()

        flags = 0
        if button == 1:  # Left
            flags = MOUSEEVENTF_LEFTDOWN if pressed else MOUSEEVENTF_LEFTUP
        elif button == 2:  # Right
            flags = MOUSEEVENTF_RIGHTDOWN if pressed else MOUSEEVENTF_RIGHTUP
        elif button == 4:  # Middle
            flags = MOUSEEVENTF_MIDDLEDOWN if pressed else MOUSEEVENTF_MIDDLEUP

        ii_.mi = MouseInput(0, 0, 0, flags, 0, ctypes.c_void_p(INJECTED_SIGNATURE))
        # debug_log(f"Click Mouse: Btn={button}, Pressed={pressed} (Sig: {hex(INJECTED_SIGNATURE)})")
        command = Input(ctypes.c_ulong(0), ii_)
        self._send_input(command)

    def scroll(self, dx, dy):
        """Scroll using MOUSEEVENTF_WHEEL and MOUSEEVENTF_HWHEEL"""
        # Standard Scroll Amount (1 notch = 120)
        WHEEL_DELTA = 120

        # Vertical Scroll
        if dy != 0:
            ii_ = Input_I()
            ii_.mi = MouseInput(
                0,
                0,
                dy * WHEEL_DELTA,
                MOUSEEVENTF_WHEEL,
                0,
                ctypes.c_void_p(INJECTED_SIGNATURE),
            )
            command = Input(ctypes.c_ulong(0), ii_)
            self._send_input(command)

        # Horizontal Scroll
        if dx != 0:
            ii_ = Input_I()
            # 0x01000 = MOUSEEVENTF_HWHEEL
            ii_.mi = MouseInput(
                0, 0, dx * WHEEL_DELTA, 0x1000, 0, ctypes.c_void_p(INJECTED_SIGNATURE)
            )
            command = Input(ctypes.c_ulong(0), ii_)
            self._send_input(command)

    def press_key(self, key_code, pressed):
        """Press key using ScanCode or VirtualKey"""
        # Mapping Qt/Protocol KeyCode to VK is assumed handled or raw VK passed?
        # For simplicity, if key_code < 255 we assume it's VK.
        # But our protocol sends weird large ints for special keys.
        # We need the mapping logic back, or update it.

        vk = self._map_qt_to_vk(key_code)
        if vk is None:
            return

        ii_ = Input_I()

        flags = 0
        if not pressed:
            flags |= KEYEVENTF_KEYUP

        # Magic Signature: 0xFFC3C3 to identify our injected events
        # CRITICAL FIX: Pass value directly as void pointer, not address of variable
        ii_.ki = KeyBdInput(vk, 0, flags, 0, ctypes.c_void_p(INJECTED_SIGNATURE))
        debug_log(
            f"Press Key: VK={hex(vk) if vk else 'None'}, Pressed={pressed} (Sig: {hex(INJECTED_SIGNATURE)})"
        )
        command = Input(ctypes.c_ulong(1), ii_)  # 1 = INPUT_KEYBOARD
        self._send_input(command)

    def _map_qt_to_vk(self, key_code):
        # Manual mapping for common VK codes
        # 0x08 = BACK, 0x09 = TAB, 0x0D = RETURN, etc.
        # This is a partial map.
        if 32 <= key_code <= 126:  # ASCII
            # Convert char to VK (e.g. 'A' is 0x41)
            char = chr(key_code).upper()
            val = ord(char)

            # Direct Map Letters (A-Z) and Numbers (0-9)
            if (0x41 <= val <= 0x5A) or (0x30 <= val <= 0x39):
                debug_log(f"KeyMap Direct: {key_code} -> {hex(val)}")
                return val

            # Manual Punctuation Map (US Layout fallback)
            punct_map = {
                46: 0xBE,  # .
                44: 0xBC,  # ,
                45: 0xBD,  # -
                61: 0xBB,  # =
                91: 0xDB,  # [
                93: 0xDD,  # ]
                59: 0xBA,  # ;
                39: 0xDE,  # '
                47: 0xBF,  # /
                92: 0xDC,  # \
                96: 0xC0,  # `
                32: 0x20,  # Space
            }
            if val in punct_map:
                return punct_map[val]

            # Fallback to VkKeyScan for punctuation
            res = ctypes.windll.user32.VkKeyScanW(chr(key_code))
            vk = res & 0xFF
            debug_log(
                f"KeyMap Scan: {key_code} ('{chr(key_code)}') -> Res={hex(res)} -> VK={hex(vk)}"
            )

            if vk == 0xFF:  # Failed
                return None

            return vk

        # Special Qt Codes
        mapping = {
            16777216: 0x1B,  # ESC
            16777217: 0x09,  # TAB
            16777219: 0x08,  # BACK
            16777220: 0x0D,  # ENTER
            16777221: 0x0D,  # NUM ENTER
            16777249: 0x11,  # CTRL
            16777251: 0x12,  # ALT
            16777248: 0x10,  # SHIFT
            16777235: 0x26,  # UP
            16777237: 0x28,  # DOWN
            16777234: 0x25,  # LEFT
            16777236: 0x27,  # RIGHT
            16777223: 0x2E,  # DEL
            16777218: 0x20,  # SPACE (Qt sometimes uses this?) No space is 32
            16777250: 0x5B,  # META/WIN (VK_LWIN)
        }
        return mapping.get(key_code, key_code if key_code < 255 else None)

    def release_all_modifiers(self):
        # Send key up for Ctrl/Alt/Shift
        for vk in [0x10, 0x11, 0x12, 0x5B]:
            self.press_key(vk, False)

    def type_text(self, text):
        """Type text string using SendInput and VkKeyScan"""
        debug_log(f"Type Text: '{text}'")
        user32 = ctypes.windll.user32
        # Define types for safety
        user32.VkKeyScanW.argtypes = [ctypes.c_wchar]
        user32.VkKeyScanW.restype = ctypes.c_short

        for char in text:
            res = user32.VkKeyScanW(char)

            vk = 0
            shift = False
            ctrl = False
            alt = False

            if (res & 0xFFFF) == 0xFFFF:
                # Fallback for Alphanumeric (A-Z, 0-9)
                # This fixes issues where VkKeyScanW fails on some systems
                val = ord(char.upper())
                if (0x41 <= val <= 0x5A) or (0x30 <= val <= 0x39):
                    vk = val
                    shift = char.isupper()
                elif char == " ":
                    vk = 0x20
                else:
                    print(f"[-] VkKeyScanW failed for: {char}")
                    continue
            else:
                vk = res & 0xFF
                shift = (res & 0x0100) != 0
                ctrl = (res & 0x0200) != 0
                alt = (res & 0x0400) != 0

            # Press modifiers
            if shift:
                self.press_key(0x10, True)
            if ctrl:
                self.press_key(0x11, True)
            if alt:
                self.press_key(0x12, True)

            # Press Key
            self.press_key(vk, True)
            self.press_key(vk, False)

            # Release modifiers
            if alt:
                self.press_key(0x12, False)
            if ctrl:
                self.press_key(0x11, False)
            if shift:
                self.press_key(0x10, False)

    def release_all_buttons(self):
        """Release all mouse buttons (safety cleanup)"""
        # 1=Left, 2=Right, 4=Middle. pressed=False
        self.click_mouse(1, False)
        self.click_mouse(2, False)
        self.click_mouse(4, False)
        self.release_all_modifiers()


def parse_mouse_move(payload):
    """Parse mouse move payload: 2 floats (x, y) normalized 0.0-1.0"""
    if len(payload) >= 8:
        x, y = struct.unpack("!ff", payload[:8])
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
        key_code = struct.unpack("!I", payload[:4])[0]
        pressed = payload[4] == 1
        return key_code, pressed
    return None, None


def parse_scroll(payload):
    """Parse scroll payload: dx, dy (2 signed shorts)."""
    if len(payload) < 4:
        return None, None
    dx, dy = struct.unpack("!hh", payload[:4])
    return dx, dy


# ============================================================================
#  DIRECT INPUT (Low-Level Windows Injection)
# ============================================================================

# C Structs for SendInput
PUL = ctypes.POINTER(ctypes.c_ulong)


class KeyBdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]  # ULONG_PTR


class HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort),
    ]


class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]  # ULONG_PTR


class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput), ("mi", MouseInput), ("hi", HardwareInput)]


class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("ii", Input_I)]


# Constants
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_WHEEL = 0x0800
