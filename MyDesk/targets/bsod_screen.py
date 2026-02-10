"""
BSOD Screen - Fake Blue Screen of Death for curtain mode
"""

import tkinter as tk
import signal


class BSODScreen:
    """Fake Blue Screen of Death."""

    def __init__(self):
        self.root = tk.Tk()

        # Fullscreen and topmost
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(background="#0078D7")  # Windows 10 BSOD blue
        self.root.configure(cursor="none")

        # Disable closing
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

        # Secret exit: Ctrl+Shift+Alt+`
        self.root.bind("<Control-Shift-Alt-grave>", lambda e: self._on_exit())

        # Main frame
        frame = tk.Frame(self.root, bg="#0078D7")
        frame.place(relx=0.5, rely=0.4, anchor="center")

        # Sad face
        sad_face = tk.Label(
            frame, text=":(", font=("Segoe UI", 120), fg="white", bg="#0078D7"
        )
        sad_face.pack()

        # Main text
        main_text = tk.Label(
            frame,
            text="Your PC ran into a problem and needs to restart.\nWe're just collecting some error info, and then we'll\nrestart for you.",
            font=("Segoe UI", 20),
            fg="white",
            bg="#0078D7",
            justify="left",
        )
        main_text.pack(pady=(40, 30))

        # Progress
        self.progress = 0
        self.progress_label = tk.Label(
            frame, text="0% complete", font=("Segoe UI", 16), fg="white", bg="#0078D7"
        )
        self.progress_label.pack()

        # QR code placeholder
        qr_frame = tk.Frame(frame, bg="white", width=100, height=100)
        qr_frame.pack(pady=(40, 10))
        qr_frame.pack_propagate(False)

        qr_text = tk.Label(
            qr_frame, text="QR", font=("Consolas", 30), fg="black", bg="white"
        )
        qr_text.place(relx=0.5, rely=0.5, anchor="center")

        # Error info
        error_text = tk.Label(
            frame,
            text="For more information about this issue and possible fixes, visit\nhttps://www.windows.com/stopcode\n\nIf you call a support person, give them this info:\nStop code: CRITICAL_PROCESS_DIED",
            font=("Segoe UI", 12),
            fg="white",
            bg="#0078D7",
            justify="left",
        )
        error_text.pack(pady=(20, 0))

        # Start progress animation
        self.update_progress()

        # Force focus
        self.root.focus_force()
        self.root.bind("<Unmap>", lambda e: self.root.after(10, self.root.focus_force))

    def update_progress(self):
        if self.progress < 100:
            self.progress += 1
            self.progress_label.config(text=f"{self.progress}% complete")
            # Slow progress to make it realistic
            delay = 500 if self.progress < 30 else 1000 if self.progress < 70 else 2000
            self._after_id = self.root.after(delay, self.update_progress)

    def _on_exit(self):
        """Graceful exit."""
        print("[*] BSOD exit triggered")
        try:
            if hasattr(self, "_after_id"):
                self.root.after_cancel(self._after_id)
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
    bsod = BSODScreen()
    bsod.start()
# alr
