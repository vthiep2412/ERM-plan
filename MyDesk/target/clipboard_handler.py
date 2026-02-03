"""
Clipboard Handler - Get and set Windows clipboard (Robust PowerShell version)
"""
import subprocess
import base64

class ClipboardHandler:
    """Handles Windows clipboard operations using PowerShell (Crash-safe)."""
    
    def __init__(self):
        # Aliases for compatibility
        self.get = self.get_clipboard
        self.set = self.set_clipboard
    
    def get_clipboard(self):
        """Get text from clipboard safely."""
        try:
            # Use PowerShell to get clipboard text
            cmd = "Get-Clipboard"
            # -NoProfile -ExecutionPolicy Bypass to avoid profile lag/restrictions
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
            # Use PowerShell to set clipboard text
            # Escape single quotes for PowerShell string
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
