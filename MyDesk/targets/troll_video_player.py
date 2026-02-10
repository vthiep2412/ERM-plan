"""
Troll Video Player - Fullscreen video player that can only exit with secret key
"""

import tkinter as tk
import sys
import os
import signal
import traceback

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
        self.valid = False  # Flag to indicate valid capture
        self.frame_delay = 33  # Default: ~30fps

        # Fullscreen and topmost
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(background="black")
        self.root.configure(cursor="none")

        # Disable closing
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

        # Secret exit: Ctrl+Shift+Alt+`
        self.root.bind("<Control-Shift-Alt-grave>", lambda e: self._on_exit())

        # Canvas for video
        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Video capture
        self.cap = None
        self.current_image = None
        self.running = True

        if cv2:
            self.cap = cv2.VideoCapture(video_path)
            # Check if capture opened successfully
            if self.cap.isOpened():
                self.valid = True
                # Get actual FPS from video
                fps = self.cap.get(cv2.CAP_PROP_FPS)
                if fps > 0:
                    self.frame_delay = int(1000 / fps)
                else:
                    self.frame_delay = 33  # Default fallback
                print(
                    f"[+] Video loaded: {video_path} @ {fps:.1f} FPS (delay: {self.frame_delay}ms)"
                )
            else:
                print(f"[-] Failed to open video: {video_path}")
                self.cap.release()
                self.cap = None
                self.valid = False

        # Start playback only if valid
        if self.valid:
            self.play_frame()
        else:
            # Show error message on canvas
            self.canvas.create_text(
                self.root.winfo_screenwidth() // 2,
                self.root.winfo_screenheight() // 2,
                text=f"Failed to load video:\n{video_path}",
                fill="red",
                font=("Arial", 24),
                justify="center",
            )

        self.root.update_idletasks()  # Ensure window is realized for correct dimensions

        # Force focus
        self.root.focus_force()
        self.root.bind("<Unmap>", lambda e: self.root.after(10, self.root.focus_force))

    def play_frame(self):
        if not self.running or not self.cap or not self.valid:
            return

        ret, frame = self.cap.read()

        if not ret:
            # Loop video with retry
            self._read_retries = getattr(self, "_read_retries", 0)
            if self._read_retries > 10:
                print("[-] Video Read Error: Too many retries")
                self.running = False
                return

            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            if not ret:
                self._read_retries += 1
            else:
                self._read_retries = 0

        if ret and frame is not None:
            # Validate frame dimensions before processing
            h, w = frame.shape[:2]
            if w <= 0 or h <= 0:
                print(f"[!] Invalid frame dimensions: {w}x{h}, skipping")
                self.root.after(self.frame_delay, self.play_frame)
                return

            # Convert BGR to RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Resize to fit screen
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()

            # Safe scale calculation with validated w/h
            scale = min(screen_w / w, screen_h / h)
            new_w = int(w * scale)
            new_h = int(h * scale)

            # Ensure new dimensions are valid
            if new_w > 0 and new_h > 0:
                frame = cv2.resize(frame, (new_w, new_h))

                # Convert to PhotoImage
                image = Image.fromarray(frame)
                self.current_image = ImageTk.PhotoImage(image)

                # Center on canvas
                self.canvas.delete("all")
                x = (screen_w - new_w) // 2
                y = (screen_h - new_h) // 2
                self.canvas.create_image(x, y, anchor=tk.NW, image=self.current_image)

        # Schedule next frame using video's actual FPS
        self.root.after(self.frame_delay, self.play_frame)

    def _on_exit(self):
        """Graceful exit."""
        print("[*] Video player exit triggered")
        self.running = False
        if self.cap:
            self.cap.release()
        try:
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            print(f"[-] Video player exit error: {e}")
            traceback.print_exc()

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

    video_path = sys.argv[1]

    # Pre-check video path exists
    if not os.path.exists(video_path):
        print(f"[-] Video file not found: {video_path}")
        sys.exit(1)

    if not os.path.isfile(video_path):
        print(f"[-] Path is not a file: {video_path}")
        sys.exit(1)

    if not cv2 or not Image or not ImageTk:
        print("[-] cv2, PIL, or PIL.ImageTk not available")
        sys.exit(1)

    player = TrollVideoPlayer(video_path)
    player.start()
# alr
