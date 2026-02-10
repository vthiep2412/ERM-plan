import threading
import tkinter as tk


class PrivacyCurtain:
    def __init__(self):
        self.root = None
        self.active = False
        self._thread = None

    def _show_curtain(self):
        # print("[DEBUG] Privacy thread started")
        try:
            self.root = tk.Tk()
            # print("[DEBUG] Tk created")
            self.root.attributes("-fullscreen", True)
            self.root.attributes("-topmost", True)
            self.root.configure(background="black")
            self.root.config(cursor="none")

            label = tk.Label(
                self.root,
                text="Remote Administration in Progress",
                font=("Arial", 24),
                fg="white",
                bg="black",
            )
            label.pack(expand=True)

            # Initial state: Hidden logic is handled by the loop below
            # We start with the window created.

            # Exclusion Logic
            try:
                from ctypes import windll

                hwnd = self.root.winfo_id()
                # Try setting on root and parent
                hwnds = [hwnd]
                try:
                    parent = windll.user32.GetParent(hwnd)
                    if parent:
                        hwnds.append(parent)
                except:
                    pass

                for h in hwnds:
                    try:
                        windll.user32.SetWindowDisplayAffinity(
                            h, 0x00000011
                        )  # WDA_EXCLUDEFROMCAPTURE
                    except:
                        pass
            except:
                pass

            import time

            while True:
                # Check for thread exit request (optional, but good for cleanup)
                if not getattr(self, "_thread_running", True):
                    break

                try:
                    if self.active:
                        # Ensure Visible
                        if self.root.state() != "normal":
                            self.root.deiconify()
                            self.root.attributes("-fullscreen", True)
                            self.root.attributes("-topmost", True)

                        self.root.lift()
                        self.root.attributes("-topmost", True)
                        self.root.update()
                    else:
                        # Ensure Hidden
                        if self.root.state() != "withdrawn":
                            self.root.withdraw()
                        self.root.update()

                    time.sleep(0.1)  # Sleep to save CPU
                except Exception:
                    break

            self.root.destroy()
        except Exception as e:
            print(f"[-] Privacy Thread Crash: {e}")

    def enable(self):
        self.active = True
        self._thread = threading.Thread(target=self._show_curtain, daemon=True)
        self._thread.start()
        print("[+] Privacy Curtain Enabled")

    def disable(self):
        if not self.active:
            return
        self.active = False
        # The thread loop will see this flag, exit, and destroy the window
        if self._thread:
            self._thread.join(timeout=1.0)
        print("[-] Privacy Curtain Disabled")


# alr
