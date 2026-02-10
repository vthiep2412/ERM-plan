import threading

try:
    import pyaudio
except ImportError:
    pyaudio = None


class AudioPlayer:
    def __init__(self):
        self.pa = pyaudio.PyAudio() if pyaudio else None
        self.stream = None
        self.FORMAT = pyaudio.paInt16 if pyaudio else 8
        self.CHANNELS = 1
        self.RATE = 16000
        self.running = False
        self._lock = threading.Lock()  # Thread safety

    def start(self):
        with self._lock:
            # Check if already running with an active stream
            if self.running and self.stream:
                return True  # No-op, already started

            # Close existing stream if orphaned
            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
                self.running = False

            # Re-init PyAudio if needed
            if not self.pa and pyaudio:
                try:
                    self.pa = pyaudio.PyAudio()
                except Exception as e:
                    print(f"[-] PyAudio Re-Init Failed: {e}")
                    return False

            if not self.pa:
                return False

            try:
                self.stream = self.pa.open(
                    format=self.FORMAT,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    output=True,
                )
                self.running = True
                return True
            except Exception as e:
                print(f"Audio Player Error: {e}")
                return False

    def stop(self):
        """Stop playback but keep PyAudio open for reuse."""
        with self._lock:
            self._stop_stream()

    def _stop_stream(self):
        """Stop and close stream (call within lock)"""
        self.running = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                print(f"[-] Audio Stream Close Error: {e}")
            finally:
                self.stream = None

    def _close_pa(self):
        """Cleanup PyAudio instance (call within lock)"""
        if self.pa:
            try:
                self.pa.terminate()
            except Exception as e:
                print(f"[-] PyAudio Terminate Error: {e}")
            finally:
                self.pa = None

    def close(self):
        """Public cleanup method - ensures stream is stopped first"""
        with self._lock:
            self._stop_stream()
            self._close_pa()

    def play_chunk(self, data):
        with self._lock:
            if self.running and self.stream:
                try:
                    self.stream.write(data)
                except Exception as e:
                    print(f"[-] Audio Stream Write Error: {e}")  # alr
