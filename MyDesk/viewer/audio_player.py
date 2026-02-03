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

    def start(self):
        if not self.pa and pyaudio:
            try:
                self.pa = pyaudio.PyAudio()
            except Exception as e:
                print(f"[-] PyAudio Re-Init Failed: {e}")
                return False

        if not self.pa:
            return False
        try:
            self.stream = self.pa.open(format=self.FORMAT,
                                       channels=self.CHANNELS,
                                       rate=self.RATE,
                                       output=True)
            self.running = True
            return True
        except Exception as e:
            print(f"Audio Player Error: {e}")
            return False

    def stop(self):
        self.running = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                print(f"[-] Audio Stream Close Error: {e}")
            finally:
                self.stream = None
        self.close()
    
    def close(self):
        """Cleanup PyAudio instance"""
        if self.pa:
            try:
                self.pa.terminate()
            except Exception as e:
                print(f"[-] PyAudio Terminate Error: {e}")
            finally:
                self.pa = None

    def play_chunk(self, data):
        if self.running and self.stream:
            try:
                self.stream.write(data)
            except Exception:
                pass