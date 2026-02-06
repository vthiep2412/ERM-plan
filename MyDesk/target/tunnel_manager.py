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
        if os.path.exists(CLOUDFLARED_BIN):
            return True
        
        print("[*] Downloading cloudflared...")
        try:
            r = requests.get(CLOUDFLARED_URL, stream=True)
            with open(CLOUDFLARED_BIN, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            print("[+] Download complete")
            return True
        except Exception as e:
            print(f"[-] Download failed: {e}")
            return False

    def start(self):
        if not self._download_binary():
            return None

        cmd = [CLOUDFLARED_BIN, "tunnel", "--url", f"http://localhost:{self.port}"]
        
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
