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
    """Parse scroll payload: dx, dy (2 signed bytes)"""
    if len(payload) >= 2:
        dx = struct.unpack('!b', payload[0:1])[0]
        dy = struct.unpack('!b', payload[1:2])[0]
        return dx, dy
    return 0, 0
