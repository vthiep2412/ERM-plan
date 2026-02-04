import tkinter as tk
import random
import signal

class FakeUpdateKiosk:
    def __init__(self):
        self.root = tk.Tk()
        self._shutdown_requested = False  # Flag for signal-based shutdown
        
        # Fullscreen and Topmost
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)
        self.root.configure(background='#006dae') # Standard Windows Update Blue
        self.root.configure(cursor='none') # Hide cursor
        
        # Disable Closing via window manager
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        
        # Secret Exit: Ctrl+Shift+Alt+`
        self.root.bind('<Control-Shift-Alt-grave>', lambda e: self._on_exit())
        # Fallback exits
        self.root.bind('<Control-q>', lambda e: self._on_exit())
        self.root.bind('<Escape>', lambda e: self._on_exit())
        
        # Center Frame
        self.frame = tk.Frame(self.root, bg='#006dae')
        self.frame.pack(expand=True)
        
        # Text
        self.label = tk.Label(self.frame, 
                              text="Configuring Windows Updates\n1% complete\n\nDon't turn off your computer",
                              font=("Segoe UI", 24), fg="white", bg="#006dae", justify="center")
        self.label.pack(pady=20)
        
        self.progress = 1        
        # Total duration: ~3 hours (10800 seconds)
        # With 99 increments, each increment ~= 109 seconds on average
        # Using random delays between 30-180 seconds = avg 105s per tick
        self.update_progress()
        
        # Force focus to prevent alt-tab (best effort)
        self.root.focus_force()
        self.root.bind('<Unmap>', lambda e: self.root.after(10, self.root.focus_force))

    def update_progress(self):
        if self.progress < 100:
            # Target duration logic: spread 100 increments over ~3-9 hours
            # Avg duration = 6 hours = 21600 seconds
            # Avg per tick = 216 sec (if linear), but we randomize
            
            # Chance to increment
            if random.random() > 0.6: 
                self.progress += 1
                self.label.config(text=f"Configuring Windows Updates\n{self.progress}% complete\n\nDon't turn off your computer")
            
            # Random delay 1-5 minutes
            delay = random.randint(60000, 300000) 
            self.root.after(delay, self.update_progress)
        else:
            # Progress complete - finish up
            self.finish_updates()

    def finish_updates(self):
        """Called when progress reaches 100%"""
        self.label.config(text="Configuring Windows Updates\n100% complete\n\nRestarting...")
        # Auto-restart cycle
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
            pass  # Signal handling may not work on all platforms
        
        # Start polling for shutdown flag
        self.root.after(500, self._check_shutdown)
        
        self.root.mainloop()

if __name__ == "__main__":
    app = FakeUpdateKiosk()
    app.start()

