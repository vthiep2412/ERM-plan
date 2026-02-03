import tkinter as tk
import sys
import time
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
        
        # Center Frame
        self.frame = tk.Frame(self.root, bg='#006dae')
        self.frame.pack(expand=True)
        
        # Text
        self.label = tk.Label(self.frame, 
                              text="Configuring Windows Updates\n1% complete\n\nDon't turn off your computer",
                              font=("Segoe UI", 24), fg="white", bg="#006dae", justify="center")
        self.label.pack(pady=20)
        
        self.progress = 1
        self.update_progress()
        
        # Force focus to prevent alt-tab (best effort)
        self.root.focus_force()
        self.root.bind('<Unmap>', lambda e: self.root.after(10, self.root.focus_force))

    def update_progress(self):
        if self.progress < 100:
            # Random increment speed
            if random.random() > 0.7:
                self.progress += 1
            
            self.label.config(text=f"Configuring Windows Updates\n{self.progress}% complete\n\nDon't turn off your computer")
            
            # Re-schedule
            delay = random.randint(500, 3000)
            self.root.after(delay, self.update_progress)
        else:
            self.label.config(text=f"Configuring Windows Updates\n100% complete\n\nDon't turn off your computer")

    def start(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.root.destroy()

if __name__ == "__main__":
    app = FakeUpdateKiosk()
    app.start()
