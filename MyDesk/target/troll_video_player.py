"""
Troll Video Player - Fullscreen video player that can only exit with secret key
"""
import tkinter as tk
import sys
import signal

try:
    import cv2
    from PIL import Image, ImageTk
except ImportError:
    cv2 = None
    Image = None
    ImageTk = None


class TrollVideoPlayer:
    """Fullscreen video player with locked exit."""
    
    def __init__(self, video_path):
        self.video_path = video_path
        self.root = tk.Tk()
        
        # Fullscreen and topmost
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)
        self.root.configure(background='black')
        self.root.configure(cursor='none')
        
        # Disable closing
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        
        # Secret exit: Ctrl+Shift+Alt+`
        self.root.bind('<Control-Shift-Alt-grave>', lambda e: self._on_exit())
        
        # Canvas for video
        self.canvas = tk.Canvas(self.root, bg='black', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Video capture
        self.cap = None
        self.current_image = None
        self.running = True
        
        if cv2:
            self.cap = cv2.VideoCapture(video_path)
        
        # Start playback
        self.play_frame()
        
        # Force focus
        self.root.focus_force()
        self.root.bind('<Unmap>', lambda e: self.root.after(10, self.root.focus_force))
    
    def play_frame(self):
        if not self.running or not self.cap:
            return
        
        ret, frame = self.cap.read()
        
        if not ret:
            # Loop video
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
        
        if ret and frame is not None:
            # Convert BGR to RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Resize to fit screen
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            
            h, w = frame.shape[:2]
            scale = min(screen_w / w, screen_h / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            
            frame = cv2.resize(frame, (new_w, new_h))
            
            # Convert to PhotoImage
            image = Image.fromarray(frame)
            self.current_image = ImageTk.PhotoImage(image)
            
            # Center on canvas
            self.canvas.delete("all")
            x = (screen_w - new_w) // 2
            y = (screen_h - new_h) // 2
            self.canvas.create_image(x, y, anchor=tk.NW, image=self.current_image)
        
        # Schedule next frame (~30fps)
        self.root.after(33, self.play_frame)
    
    def _on_exit(self):
        """Graceful exit."""
        print("[*] Video player exit triggered")
        self.running = False
        if self.cap:
            self.cap.release()
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
    
    def start(self):
        # Signal handlers
        try:
            signal.signal(signal.SIGINT, lambda s, f: self._on_exit())
            signal.signal(signal.SIGTERM, lambda s, f: self._on_exit())
        except Exception:
            pass
        
        self.root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: troll_video_player.py <video_path>")
        sys.exit(1)
    
    if not cv2 or not Image:
        print("[-] cv2 or PIL not available")
        sys.exit(1)
    
    player = TrollVideoPlayer(sys.argv[1])
    player.start()
