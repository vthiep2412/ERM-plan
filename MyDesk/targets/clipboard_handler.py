"""
Clipboard Handler - Get/Set Windows clipboard + History Monitoring
"""
import subprocess
import threading
import time

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
        
        # Runtime history (transient)
        self.history = []
    

    
    
    def get_clipboard(self):
        """Get text from clipboard safely."""
        try:
            cmd = "Get-Clipboard"
            output = subprocess.check_output(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5
            ).decode('utf-8', errors='ignore').strip()
            return output
        except Exception as e:
            print(f"[-] Get Clipboard Error: {e}")
            return "" 

    def set_clipboard(self, text):
        """Set clipboard text safely using Pipeline execution to prevent injection."""
        try:
            # Use pipeline input to avoid command line injection
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", 
                   "-Command", "Set-Clipboard -Value ([Console]::In.ReadToEnd())"]
            
            subprocess.run(
                cmd,
                input=text.encode('utf-8'), 
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=True,
                timeout=5
            )
            # Update last content to prevent echo loop
            self.last_content = text
            return True
        except Exception as e:
            print(f"[-] Set Clipboard Error: {e}")
            return False
    
    def start_monitoring(self):
        """Start background clipboard monitoring."""
        with self._lock:
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
                    
                    # Notify callback (Real-time sync)
                    if self.on_change:
                        try:
                            self.on_change(entry)
                        except Exception as cb_err:
                            print(f"[-] Clipboard Callback Error: {cb_err}")
                
            except Exception as e:
                print(f"[-] Clipboard monitor error: {e}")
            
            time.sleep(1.0)  # Verify check interval (1s is enough)

# alr 
