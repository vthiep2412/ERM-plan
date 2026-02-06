import subprocess
import os
import time
import requests
import threading
import re

CLOUDFLARED_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
CLOUDFLARED_BIN = "cloudflared.exe"

class TunnelManager:
    def __init__(self, port):
        self.port = port
        self.process = None
        self.public_url = None
        self.running = False
        
    def _download_binary(self):
        # 1. Check current directory
        if os.path.exists(CLOUDFLARED_BIN):
            self.cloudflared_path = CLOUDFLARED_BIN
            return True
            
        # 2. Check globally installed (PATH)
        import shutil
        import tempfile
        path_bin = shutil.which("cloudflared")
        if path_bin:
            print(f"[*] Found cloudflared in PATH: {path_bin}")
            self.cloudflared_path = path_bin
            return True
            
        # 3. Check Temp Directory
        temp_dir = tempfile.gettempdir()
        temp_bin = os.path.join(temp_dir, CLOUDFLARED_BIN)
        if os.path.exists(temp_bin):
             print(f"[*] Found cloudflared in TEMP: {temp_bin}")
             self.cloudflared_path = temp_bin
             return True
        
        # 4. Try Download to CWD, then Fallback to TEMP
        print("[*] Downloading cloudflared...")
        
        # Helper to download to a specific path
        def download_to(path):
            try:
                print(f"[*] Attempting download to: {path}")
                r = requests.get(CLOUDFLARED_URL, stream=True, timeout=15)
                r.raise_for_status()
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
            except Exception as e:
                print(f"[-] Download to {path} failed: {e}")
                return False

        # Try CWD first
        if download_to(CLOUDFLARED_BIN):
            print("[+] Downloaded to CWD")
            self.cloudflared_path = CLOUDFLARED_BIN
            return True
            
        # If CWD failed, Try TEMP
        print("[!] CWD Write Failed. Trying Temp Folder...")
        if download_to(temp_bin):
            print(f"[+] Downloaded to TEMP: {temp_bin}")
            self.cloudflared_path = temp_bin
            return True
            
        return False

    def start(self):
        if not self._download_binary():
            return None

        # Use the path resolved by _download_binary
        cmd = [self.cloudflared_path, "tunnel", "--url", f"http://localhost:{self.port}"]
        
        # Prevent console window popping up
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,  # Discard stdout to prevent buffer deadlock
            stderr=subprocess.PIPE,     # We only need stderr for the URL
            stdin=subprocess.DEVNULL,
            startupinfo=startupinfo,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        self.running = True
        
        # Start thread to parse output for URL
        t = threading.Thread(target=self._parse_output)
        t.daemon = True
        t.start()
        
        # Wait for URL up to 45s
        for _ in range(45):
            if self.public_url:
                return self.public_url
            time.sleep(1)
            
        return None

    def _parse_output(self):
        # Cloudflared prints the URL to stderr usually
        while self.running and self.process:
            line = self.process.stderr.readline()
            if not line:
                break
            
            # Look for *.trycloudflare.com
            # Example: https://fitting-random-word.trycloudflare.com
            match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
            if match:
                self.public_url = match.group(0)
                print(f"[+] Tunnel URL Found: {self.public_url}")
                
    def stop(self):
        self.running = False
        if self.process:
            self.process.terminate()
            self.process = None
# alr 
