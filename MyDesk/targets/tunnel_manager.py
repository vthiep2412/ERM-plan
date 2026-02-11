import subprocess
import os
import time
import threading
import re
import shutil
import tempfile
import urllib.request
import urllib.error
import ssl

CLOUDFLARED_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
CLOUDFLARED_BIN = "cloudflared.exe"

class TunnelManager:
    def __init__(self, port, on_url_change=None):
        self.port = port
        self.process = None
        self.public_url = None
        self.running = False
        self.on_url_change = (
            on_url_change  # Callback when URL changes (for registry update)
        )
        self.start_time = 0
        self.STUCK_TIMEOUT = 300  # 5 minutes
        self.cloudflared_path = None

    def _download_binary(self):
        """Ensures cloudflared.exe exists, downloading if necessary."""
        # 1. Check current directory
        if os.path.exists(CLOUDFLARED_BIN):
            self.cloudflared_path = os.path.abspath(CLOUDFLARED_BIN)
            return True

        # 2. Check globally installed (PATH)
        path_bin = shutil.which("cloudflared")
        if path_bin:
            self.cloudflared_path = path_bin
            return True

        # 3. Check Temp Directory
        temp_dir = tempfile.gettempdir()
        temp_bin = os.path.join(temp_dir, CLOUDFLARED_BIN)
        if os.path.exists(temp_bin):
            self.cloudflared_path = temp_bin
            return True

        # 4. Try Download to CWD, then Fallback to TEMP
        print(
            f"[*] Binary Resurrection: cloudflared.exe is missing from {CLOUDFLARED_BIN}, PATH, and TEMP. Downloading..."
        )

        def download_to(path):
            tmp_path = path + ".tmp"
            try:
                print(f"[*] Attempting download to: {path}")

                # Standard urllib (Uses Windows System Certs)
                with urllib.request.urlopen(CLOUDFLARED_URL, timeout=60) as response:
                    with open(tmp_path, "wb") as f:
                        f.write(response.read())

                # Atomic move
                os.replace(tmp_path, path)
                print(f"[+] Download Success: {path}")
                return True
            except Exception as e:
                print(f"[-] Download to {path} failed: {e}")
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                return False

        # Try CWD first
        if download_to(CLOUDFLARED_BIN):
            self.cloudflared_path = os.path.abspath(CLOUDFLARED_BIN)
            return True

        # If CWD failed, Try TEMP
        if download_to(temp_bin):
            self.cloudflared_path = temp_bin
            return True

        return False

    def start(self):
        if not self._download_binary():
            return None

        # Use the path resolved by _download_binary
        self.start_time = time.time()
        self.public_url = None
        cmd = [
            self.cloudflared_path,
            "tunnel",
            "--url",
            f"http://localhost:{self.port}",
        ]

        # Prevent console window popping up
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        print(f"[*] Tunnel Subprocess: Executing {cmd}")
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                startupinfo=startupinfo,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            print(f"[-] Tunnel Subprocess Error: Failed to launch: {e}")
            return None

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
            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
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
        """Immortal Watchdog: Monitor, Resurrect Binary, and Restart Tunnel."""
        fail_count = 0
        MAX_RETRIES = 60

        while self.running:
            try:
                time.sleep(5)
                if not self.running:
                    break

                if not self.process or self.process.poll() is not None:
                    # Tunnel is down!
                    if fail_count >= MAX_RETRIES:
                        print(
                            f"[-] Immortal Watchdog: MAX_RETRIES ({MAX_RETRIES}) exceeded. Giving up."
                        )
                        self.running = False
                        break

                    print(
                        f"[!] Immortal Watchdog: Tunnel is down (Fail Count: {fail_count})"
                    )

                    # 1. Binary Resurrection: Check if file was deleted
                    if not os.path.exists(self.cloudflared_path):
                        print(
                            "[!] Binary Resurrection: cloudflared.exe was deleted! Recovering..."
                        )
                        if not self._download_binary():
                            print("[-] Binary Resurrection: FAILED. Retrying in 30s...")
                            time.sleep(30)
                            fail_count += 1
                            continue

                    # 2. Restart
                    self._restart_tunnel()
                    fail_count += 1

                    # Exponential backoff for repeated failures (up to 5 mins)
                    # wait_time = 5, 10, 20, 40, 80, 160, 300...
                    wait_time = min(300, 5 * (2 ** min(fail_count - 1, 6)))
                    if fail_count > 1:
                        print(f"[*] Backing off for {wait_time}s...")
                        time.sleep(wait_time)
                else:
                    # Reset failure count if it stayed up (has a URL)
                    if self.public_url:
                        fail_count = 0

                    # 3. Stuck Detection: Process is alive but no URL after 5 mins
                    if (
                        not self.public_url
                        and (time.time() - self.start_time) > self.STUCK_TIMEOUT
                    ):
                        print(
                            f"[!] Immortal Watchdog: Tunnel is STUCK (No URL for {self.STUCK_TIMEOUT}s). Force restarting..."
                        )
                        self._restart_tunnel()
                        fail_count += 1
            except Exception as e:
                print(f"[-] Watchdog Exception: {e}")
                time.sleep(10)

    def _restart_tunnel(self):
        """Restart the tunnel (internal, no download check)."""
        try:
            self.start_time = time.time()
            self.public_url = None
            # Use the path resolved by _download_binary
            cmd = [
                self.cloudflared_path,
                "tunnel",
                "--url",
                f"http://localhost:{self.port}",
            ]

            startupinfo = None
            if os.name == "nt":
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
                universal_newlines=True,
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

    def restart(self):
        """Public method to manually trigger a restart of the tunnel."""
        # Force kill current process if alive
        if self.process:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            except:
                pass
        self._restart_tunnel()

    def stop(self):
        self.running = False
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
