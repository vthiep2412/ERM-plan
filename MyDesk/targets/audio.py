import time

try:
    import pyaudiowpatch as pyaudio
except ImportError:
    try:
        import pyaudio
    except ImportError:
        pyaudio = None


class AudioStreamer:
    def __init__(self, loopback=False):
        self.pa = pyaudio.PyAudio() if pyaudio else None
        self.stream = None
        self.running = False
        self.loopback = loopback

        self.FORMAT = pyaudio.paInt16 if pyaudio else 8
        self.CHANNELS = 2 if loopback else 1  # Stereo for system, Mono for mic
        self.RATE = 48000 if loopback else 16000  # Higher quality for system
        self.CHUNK = 1024
        self._restart_attempts = 0
        self._last_restart_time = 0

    def _get_loopback_device(self):
        """Find the default WASAPI loopback device."""
        if not self.pa or not hasattr(self.pa, "get_host_api_info_by_type"):
            return None

        try:
            # Find WASAPI Host API
            wasapi_info = None
            for i in range(self.pa.get_host_api_count()):
                api = self.pa.get_host_api_info_by_index(i)
                if hasattr(pyaudio, "paWASAPI") and api["type"] == pyaudio.paWASAPI:
                    wasapi_info = api
                    break

            if not wasapi_info:
                print("[-] WASAPI not found.")
                return None

            # Get default output device for that API
            default_speakers = self.pa.get_device_info_by_index(
                wasapi_info["defaultOutputDevice"]
            )

            if not default_speakers["isLoopbackDevice"]:
                # If default isn't loopback, try to find the loopback version of it
                # pyaudiowpatch exposes loopback devices as separate inputs
                for i in range(self.pa.get_device_count()):
                    dev = self.pa.get_device_info_by_index(i)
                    if (
                        dev["hostApi"] == wasapi_info["index"]
                        and dev["isLoopbackDevice"]
                    ):
                        # Found a loopback device, let's hope it's the default one
                        # Ideally we match names or IDs but this is usually sufficient
                        return dev

            return None
        except Exception as e:
            print(f"[-] Loopback Discovery Error: {e}")
            return None

    def start(self, reset_restart_counter=True):
        if not self.pa or self.running:
            return False

        if reset_restart_counter:
            self._restart_attempts = 0
            self._last_restart_time = 0

        try:
            device_index = None

            if self.loopback:
                dev = self._get_loopback_device()
                if not dev:
                    print("[-] No Loopback Device Found.")
                    return False
                print(f"[+] Found Loopback Device: {dev['name']}")
                device_index = dev["index"]
                self.CHANNELS = 2
                self.RATE = int(
                    dev["defaultSampleRate"]
                )  # Match hardware rate usually 48k

            self.stream = self.pa.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.CHUNK,
            )
            self.running = True
            print(f"[+] Audio Stream Started (Loopback={self.loopback})")
            return True
        except Exception as e:
            print(f"[-] Audio Start Error (Loopback={self.loopback}): {e}")
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

    def close(self):
        if self.pa:
            self.pa.terminate()
            self.pa = None

    def get_chunk(self):
        if not self.running or not self.stream:
            return None
        try:
            data = self.stream.read(self.CHUNK, exception_on_overflow=False)
            self._restart_attempts = 0
            return data
        except Exception as e:
            now = time.time()
            # Simple cooldown logic
            if now - self._last_restart_time > 1.0:
                print(f"[-] Audio Read Error: {e} - Restarting...")
                self._last_restart_time = now
                self.stop()
                self.start(reset_restart_counter=False)
            return None
