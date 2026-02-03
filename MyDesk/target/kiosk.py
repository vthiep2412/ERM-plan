import tkinter as tk
import random

class FakeUpdateKiosk:
    def __init__(self):
        self.root = tk.Tk()
        # Fullscreen and Topmost
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)
        self.root.configure(background='#006dae') # Standard Windows Update Blue
        self.root.configure(cursor='none') # Hide cursor
        
        # Disable Closing
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        
        # Secret Exit: Ctrl+Shift+Alt+`
        self.root.bind('<Control-Shift-Alt-grave>', lambda e: self.secret_exit())
        
        # Center Frame
        self.frame = tk.Frame(self.root, bg='#006dae')
        self.frame.pack(expand=True)
        
        # Text
        self.label = tk.Label(self.frame, 
                              text="Configuring Windows Updates\n1% complete\n\nDon't turn off your computer",
                              font=("Segoe UI", 24), fg="white", bg="#006dae", justify="center")
        self.label.pack(pady=20)
        
        self.progress = 1
        self.last_progress = 0  # Track last displayed progress
        
        # Total duration: ~3 hours (10800 seconds)
        # With 99 increments, each increment ~= 109 seconds on average
        # Using random delays between 30-180 seconds = avg 105s per tick
        self.update_progress()
        
        # Force focus to prevent alt-tab (best effort)
        self.root.focus_force()
        self.root.bind('<Unmap>', lambda e: self.root.after(10, self.root.focus_force))

    def update_progress(self):
        if self.progress < 100:
            # Random increment (about 30% chance per tick)
            if random.random() > 0.7:
                self.progress += 1
                # Only update label when progress actually changes
                self.label.config(text=f"Configuring Windows Updates\n{self.progress}% complete\n\nDon't turn off your computer")
            
            # Re-schedule with delays to stretch to ~3 hours
            # 99 increments * avg 109s = ~3 hours
            delay = random.randint(30000, 180000)  # 30s-180s in ms
            self.root.after(delay, self.update_progress)
        else:
            # Progress complete - finish up
            self.finish_updates()

    def finish_updates(self):
        """Called when progress reaches 100%"""
        self.label.config(text="Configuring Windows Updates\n100% complete\n\nRestarting...")
        # Auto-close after 3 seconds
        self.root.after(3000, self.root.destroy)

    def secret_exit(self):
        """Secret exit via Ctrl+Shift+Alt+`"""
        print("[*] Secret exit triggered")
        self.root.destroy()

    def start(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.root.destroy()

if __name__ == "__main__":
    app = FakeUpdateKiosk()
    app.start()
