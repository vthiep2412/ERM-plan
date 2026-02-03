import cv2
import threading
import io

class WebcamStreamer:
    def __init__(self, dev_index=0, quality=50):
        self.dev_index = dev_index
        self.quality = quality
        self.cap = None
        self.running = False
        self.lock = threading.Lock()

    def start(self):
        with self.lock:
            if self.running:
                return True
            
            try:
                # Try finding a working camera (scan index 0 to 2)
                found = False
                for idx in range(3):
                    try:
                        print(f"[*] Trying Webcam Index {idx}...")
                        # Try DirectShow first
                        self.cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                        if not self.cap.isOpened():
                            # Fallback to default
                            self.cap.release()
                            self.cap = cv2.VideoCapture(idx)
                        
                        if self.cap.isOpened():
                            self.dev_index = idx # Save working index
                            found = True
                            print(f"[+] Webcam found at index {idx}")
                            break
                        else:
                            self.cap.release()
                    except Exception as e:
                        print(f"[-] Webcam Error: {e}")
                        continue
                
                if not found:
                    print("[-] No working webcam found in indices 0-2")
                    return False

                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                self.cap.set(cv2.CAP_PROP_FPS, 15)
                
                # Defensive check: isOpened() should always be true here due to
                # camera discovery loop above, but VideoCapture.set() could theoretically
                # cause side-effects on some drivers. Kept for safety.
                if not self.cap.isOpened():
                    print("[-] Webcam closed unexpectedly after set()")
                    self.cap = None
                    return False
                    
                self.running = True
                print("[+] Webcam Started")
                return True
            except Exception as e:
                print(f"[-] Webcam Error: {e}")
                self.cap = None
                return False

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
