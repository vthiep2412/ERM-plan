import subprocess
import os
import time
import requests
import threading
import re

CLOUDFLARED_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
CLOUDFLARED_BIN = "cloudflared.exe"

class TunnelManager:
    def __init__(self, port, on_url_change=None):
        self.port = port
        self.process = None
        self.public_url = None
        self.running = False
        self.on_url_change = on_url_change  # Callback when URL changes (for registry update)
        
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
            tmp_path = path + ".tmp"
            try:
                print(f"[*] Attempting download to: {path}")
                r = requests.get(CLOUDFLARED_URL, stream=True, timeout=15)
                r.raise_for_status()
                with open(tmp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                    f.flush()
                    os.fsync(f.fileno())
                
                # Atomic move
                os.replace(tmp_path, path)
                
                return True
            except Exception as e:
                print(f"[-] Download to {path} failed: {e}")
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except:
                        pass
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

        # Start watchdog to monitor and restart if it dies
        self.start_watchdog()
        
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
                new_url = match.group(0)
                print(f"[+] Tunnel URL Found: {new_url}")
                
                # Only trigger callback if URL actually changed
                if new_url != self.public_url:
                    self.public_url = new_url
                    
                    # Notify agent to update registry
                    if self.on_url_change:
                        try:
                            self.on_url_change(new_url)
                        except Exception as e:
                            print(f"[-] URL change callback error: {e}")

    def _watchdog(self):
        """Monitor cloudflared and restart if it dies."""
        while self.running:
            time.sleep(2)  # Faster response
            
            if self.process and self.process.poll() is not None:
                # Process died
                print("[!] Cloudflared tunnel died, restarting...")
                self._restart_tunnel()
    
    def _restart_tunnel(self):
        """Restart the tunnel (internal, no download check)."""
        try:
            # Use the path resolved by _download_binary
            cmd = [self.cloudflared_path, "tunnel", "--url", f"http://localhost:{self.port}"]
            
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                startupinfo=startupinfo,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Restart URL parser
            t = threading.Thread(target=self._parse_output)
            t.daemon = True
            t.start()
            
            print("[+] Cloudflared tunnel restarted")
        except Exception as e:
            print(f"[-] Tunnel restart failed: {e}")

    def start_watchdog(self):
        """Start the watchdog thread (call after start())."""
        wt = threading.Thread(target=self._watchdog)
        wt.daemon = True
        wt.start()
        print("[+] Tunnel watchdog started")
                
    def stop(self):
        self.running = False
        if self.process:
            self.process.terminate()
            self.process = None

