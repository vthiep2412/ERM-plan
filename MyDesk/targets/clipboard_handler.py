"""
Clipboard Handler - Get Windows clipboard + History Monitoring
"""

import threading
import time
import ctypes

from datetime import datetime


class ClipboardHandler:
    """Handles Windows clipboard operations with history monitoring."""

    def __init__(self, on_change=None, max_history=100):
        """
        Args:
            on_change: callback(entry_dict) when clipboard changes
            max_history: max number of entries to store
        """
        self.on_change = on_change
        self.max_history = max_history
        self.history = []  # [{text: str, timestamp: str}, ...]
        self.last_content = ""
        self._monitoring = False
        self._monitor_thread = None

        # Aliases for compatibility
        self.get = self.get_clipboard

        # Lock for thread safety
        self._lock = threading.Lock()

    def get_clipboard(self):
        """Get text from clipboard using the most reliable available method."""

        # Method 1: Try pyperclip (most reliable, handles all edge cases)
        try:
            import pyperclip

            return pyperclip.paste() or ""
        except ImportError:
            pass
        except Exception:
            pass

        # Method 2: PowerShell with short timeout (reliable but slower)
        try:
            import subprocess

            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                capture_output=True,
                text=True,
                timeout=2,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass

        # Method 3: Native Windows API (fast but can be tricky)
        try:
            return self._get_clipboard_ctypes()
        except Exception:
            pass

        return ""

    def _get_clipboard_ctypes(self):
        """Get clipboard using ctypes Windows API."""
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        CF_UNICODETEXT = 13

        # Set up function signatures
        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.restype = ctypes.c_bool
        user32.CloseClipboard.restype = ctypes.c_bool
        user32.GetClipboardData.argtypes = [ctypes.c_uint]
        user32.GetClipboardData.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]

        if not user32.OpenClipboard(None):
            return ""

        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return ""

            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                return ""

            try:
                return ctypes.wstring_at(ptr) or ""
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()

    def start_monitoring(self):
        if self._monitoring:
            return  eady monitoring
        """Start background clipboard monitoring."""
        with self._lock:
            if self._monitoring:
                return

            self._monitoring = True
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop, daemon=True
            )
            self._monitor_thread.start()
        print("[+] Clipboard monitoring started")

    def stop_monitoring(self):
        """Stop clipboard monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
        print("[!] Clipboard monitoring stopped")

    def _monitor_loop(self):
        """Monitor clipboard for changes."""
        # Initialize with current content
        self.last_content = self.get_clipboard()

        while self._monitoring:
            try:
                current = self.get_clipboard()

                # Check if changed and not empty
                if current and current != self.last_content:
                    self.last_content = current

                    # Create entry
                    entry = {"text": current, "timestamp": datetime.now().isoformat()}

                    # Store in history (with lock for thread safety)
                    with self._lock:
                        self.history.append(entry)
                        # Trim if over max
                        if len(self.history) > self.max_history:
                            self.history = self.history[-self.max_history :]

                    # Notify callback (Real-time sync)
                    if self.on_change:
                        try:
                            self.on_change(entry)
                        except Exception as cb_err:
                            print(f"[-] Clipboard Callback Error: {cb_err}")

            except Exception as e:
                print(f"[-] Clipboard monitor error: {e}")

            time.sleep(1.0)  # Verify check interval (1s is enough)

    def get_history(self):
        """Return clipboard history list."""
        with self._lock:
            return list(self.history)

    def delete_entry(self, index):
        """Delete a clipboard history entry by index."""
        with self._lock:
            if 0 <= index < len(self.history):
                del self.history[index]
                return True
        return False

    async def get_windows_history(self):
        """Get full Windows Clipboard History (Win+V) using WinRT API.

        Returns list of dicts: [{"text": str, "timestamp": str}, ...]
        Falls back to internal history if WinRT unavailable or fails.
        """
        try:
            from winrt.windows.applicationmodel.datatransfer import (
                Clipboard,
                ClipboardHistoryItemsResultStatus,
            )

            result = await Clipboard.get_history_items_async()
            items = []

            if result.status == ClipboardHistoryItemsResultStatus.SUCCESS:
                for item in result.items:
                    try:
                        # Get text from DataPackageView
                        data_view = item.content
                        if data_view.contains("Text"):
                            text = await data_view.get_text_async()
                            items.append(
                                {
                                    "text": text,
                                    "timestamp": (
                                        str(item.timestamp)
                                        if hasattr(item, "timestamp")
                                        else ""
                                    ),
                                }
                            )
                    except Exception:
                        continue
            return items

        except ImportError:
            pass  # winrt not installed
        except Exception as e:
            print(f"[-] Windows Clipboard History Error: {e}")

        # Fallback to internal history
        return self.get_history()
