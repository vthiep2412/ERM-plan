import time
try:
    import pyaudio
except ImportError:
    pyaudio = None

class AudioStreamer:
    def __init__(self):
        self.pa = pyaudio.PyAudio() if pyaudio else None
        self.stream = None
        self.running = False
        self.FORMAT = pyaudio.paInt16 if pyaudio else 8
        self.CHANNELS = 1
        self.RATE = 16000 # 16kHz is enough for voice, saves bandwidth
        self.CHUNK = 1024
        self._restart_attempts = 0
        self._last_restart_time = 0

    def start(self):
        if not self.pa or self.running: return False
        try:
            self.stream = self.pa.open(format=self.FORMAT,
                                       channels=self.CHANNELS,
                                       rate=self.RATE,
                                       input=True,
                                       frames_per_buffer=self.CHUNK)
            self.running = True
            print("[+] Mic Started")
            return True
        except Exception as e:
            print(f"[-] Mic Error: {e}")
            return False

    def stop(self):
        self.running = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        # Do not terminate PyAudio instance, keep it for restart
        
    def close(self):
        """Cleanup PyAudio (Only call on exit)"""
        if self.pa:
            self.pa.terminate()
            self.pa = None

    def get_chunk(self):
        if not self.running or not self.stream: return None
        try:
            # Non-blocking read? PyAudio read is blocking by default.
            # We use exception_on_overflow=False to avoid crashes.
            data = self.stream.read(self.CHUNK, exception_on_overflow=False)
            self._restart_attempts = 0  # Reset on success
            return data
        except Exception as e:
            print(f"[-] Mic Read Error: {e}")
            
            # Restart Backoff Logic
            now = time.time()
            cooldown_seconds = 1.0
            max_attempts = 5
            
            # Check cooldown
            if now - self._last_restart_time < cooldown_seconds:
                return None  # Still in cooldown
            
            # Check max attempts
            if self._restart_attempts >= max_attempts:
                print(f"[-] Mic Max Restart Attempts ({max_attempts}) Reached. Giving up.")
                self.stop()
                return None
            
            # Try restart
            self._restart_attempts += 1
            self._last_restart_time = now
            try:
                self.stop()
                if self.start():
                    print(f"[*] Mic Restart Attempt {self._restart_attempts} succeeded.")
                else:
                    print(f"[-] Mic Restart Attempt {self._restart_attempts} failed.")
            except Exception as restart_err: 
                print(f"[-] Mic Restart Error: {restart_err}")
            return None