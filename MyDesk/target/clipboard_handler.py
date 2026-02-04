"""
Clipboard Handler - Get/Set Windows clipboard + History Monitoring
"""
import subprocess
import threading
import time
import json
import os
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
        self.set = self.set_clipboard
        
        # Load history from file if exists
        self._load_history()
    
    def _get_history_path(self):
        """Get path to history JSON file."""
        return os.path.join(os.path.dirname(__file__), "clipboard_history.json")
    
    def _load_history(self):
        """Load history from JSON file."""
        try:
            path = self._get_history_path()
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
                # Trim to max
                if len(self.history) > self.max_history:
                    self.history = self.history[-self.max_history:]
                print(f"[+] Loaded {len(self.history)} clipboard history entries")
        except Exception as e:
            print(f"[-] Load clipboard history error: {e}")
            self.history = []
    
    def _save_history(self):
        """Save history to JSON file."""
        try:
            path = self._get_history_path()
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[-] Save clipboard history error: {e}")
    
    def get_clipboard(self):
        """Get text from clipboard safely."""
        try:
            cmd = "Get-Clipboard"
            output = subprocess.check_output(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                creationflags=subprocess.CREATE_NO_WINDOW
            ).decode('utf-8', errors='ignore').strip()
            return output
        except Exception as e:
            print(f"[-] Get Clipboard Error: {e}")
            return ""
    
    def set_clipboard(self, text):
        """Set clipboard text safely."""
        try:
            safe_text = text.replace("'", "''")
            cmd = f"Set-Clipboard -Value '{safe_text}'"
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=True
            )
            return True
        except Exception as e:
            print(f"[-] Set Clipboard Error: {e}")
            return False
    
    def start_monitoring(self):
        """Start background clipboard monitoring."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
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
                    entry = {
                        "text": current,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Add to history (avoid duplicates of last entry)
                    if not self.history or self.history[-1]["text"] != current:
                        self.history.append(entry)
                        
                        # Trim if over max
                        if len(self.history) > self.max_history:
                            self.history.pop(0)
                        
                        # Save to disk
                        self._save_history()
                        
                        # Notify callback
                        if self.on_change:
                            self.on_change(entry)
                
            except Exception as e:
                print(f"[-] Clipboard monitor error: {e}")
            
            time.sleep(0.5)  # Poll every 500ms
    
    def get_history(self):
        """Get full clipboard history."""
        return self.history
    
    def delete_entry(self, index):
        """Delete entry by index."""
        try:
            if 0 <= index < len(self.history):
                del self.history[index]
                self._save_history()
                return True
        except Exception as e:
            print(f"[-] Delete entry error: {e}")
        return False
    
    def clear_history(self):
        """Clear all history."""
        self.history = []
        self._save_history()
