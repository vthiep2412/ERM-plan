import cv2
import threading

class WebcamStreamer:
    def __init__(self, dev_index=0, quality=50):
        self.dev_index = dev_index
        self.quality = quality
        self.cap = None
        self.running = False
        self.lock = threading.Lock()

    def start(self):
        # Quick check with lock
        with self.lock:
            if self.running:
                return True
        
        # Camera discovery WITHOUT holding lock (allows stop() to be called)
        temp_cap = None
        found_idx = None
        
        for idx in range(3):
            try:
                print(f"[*] Trying Webcam Index {idx}...")
                # Try DirectShow first
                temp_cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                if not temp_cap.isOpened():
                    # Fallback to default
                    temp_cap.release()
                    temp_cap = cv2.VideoCapture(idx)
                
                if temp_cap.isOpened():
                    found_idx = idx
                    print(f"[+] Webcam found at index {idx}")
                    break
                else:
                    temp_cap.release()
                    temp_cap = None
            except Exception as e:
                print(f"[-] Webcam Error: {e}")
                if temp_cap is not None:
                    try:
                        temp_cap.release()
                    except Exception as release_err:
                        print(f"[-] Webcam Release Error: {release_err}")
                temp_cap = None
                continue
        
        if not temp_cap or found_idx is None:
            print("[-] No working webcam found in indices 0-2")
            return False
        
        # Configure camera
        try:
            temp_cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
            temp_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
            temp_cap.set(cv2.CAP_PROP_FPS, 15)
            
            if not temp_cap.isOpened():
                print("[-] Webcam closed unexpectedly after set()")
                temp_cap.release()
                return False
        except Exception as e:
            print(f"[-] Webcam Config Error: {e}")
            try:
                temp_cap.release()
            except Exception:
                pass
            return False
        
        # Acquire lock to set state
        with self.lock:
            # Check if stop() was called while we were discovering
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
            
            self.cap = temp_cap
            self.dev_index = found_idx
            self.running = True
            print("[+] Webcam Started")
            return True

    def stop(self):
        with self.lock:
            self.running = False
            if self.cap:
                try:
                    self.cap.release()
                except Exception as e:
                    print(f"[-] Webcam Release Error: {e}")
                self.cap = None

    def get_frame_bytes(self):
        with self.lock:
            if not self.running or not self.cap:
                return None
            try:
                ret, frame = self.cap.read()
            except Exception as e:
                print(f"[-] Webcam Read Error: {e}")
                return None
            
        if not ret or frame is None:
            return None

        # Encode to JPEG
        ret, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality])
        if ret:
            return jpeg.tobytes()
        return None
