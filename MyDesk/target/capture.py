"""
Fast Delta Frame Capturer for MyDesk
Uses tile-based comparison with optional GPU encoding.
"""
import io
import hashlib
import numpy as np

# Safe Imports
dxcam = None
mss = None
Image = None
cv2 = None

try:
    import dxcam
except ImportError:
    pass

try:
    from PIL import Image
except ImportError:
    pass

try:
    import mss as mss_module
    mss = mss_module
except ImportError:
    pass

try:
    import cv2 as cv2_module
    cv2 = cv2_module
except ImportError:
    pass

# Try JXL plugin
try:
    import pillow_jxl  # noqa: F401
    HAS_JXL = True
except ImportError:
    HAS_JXL = False

# Check for GPU encoding (NVENC via OpenCV)
HAS_GPU = False
if cv2:
    try:
        if cv2.cuda.getCudaEnabledDeviceCount() > 0:
            HAS_GPU = True
            print("[+] GPU Encoding: NVIDIA CUDA Available")
    except Exception:
        pass

# Try ZSTD for faster compression
HAS_ZSTD = False
try:
    import zstd  # noqa: F401
    HAS_ZSTD = True
except ImportError:
    try:
        import zstandard as zstd  # noqa: F401
        HAS_ZSTD = True
    except ImportError:
        pass

TILE_SIZE = 32  # 32x32 pixel tiles

import ctypes
from ctypes import windll, Structure, c_long, byref

class POINT(Structure):
    _fields_ = [("x", c_long), ("y", c_long)]

# Allowed capture formats
ALLOWED_FORMATS = {'JPEG', 'WEBP', 'PNG', 'JXL'}
ALLOWED_METHODS = {'mss', 'dxcam'}

class DeltaScreenCapturer:
    def __init__(self, quality=50, scale=0.9, method="mss", format="WEBP"):
        self.quality = quality
        self.scale = scale
        
        # Validate format
        format_upper = format.upper()
        if format_upper not in ALLOWED_FORMATS:
            print(f"[!] Invalid format '{format}'. Allowed: {ALLOWED_FORMATS}. Defaulting to WEBP.")
            format_upper = 'WEBP'
        
        if format_upper == 'JXL' and not HAS_JXL:
            print("[!] JXL requested but pillow_jxl not available. Defaulting to WEBP.")
            format_upper = 'WEBP'
            
        self.format = format_upper
        
        # Validate method
        method_lower = method.lower()
        if method_lower not in ALLOWED_METHODS:
            print(f"[!] Invalid method '{method}'. Allowed: {ALLOWED_METHODS}. Defaulting to mss.")
            method_lower = 'mss'
        self.method = method_lower
        
        self.dxcam_instance = None
        self.dxcam_active = False  # Separate flag for DXCam state
        self._dxcam_fail_count = 0 
        self.use_mss = True  # Default fallback
        
        # Method Selection
        if self.method == "dxcam" and dxcam:
            try:
                # Initialize DXCam
                print("[*] Initializing DXCam...")
                self.dxcam_instance = dxcam.create(output_color="RGB")
                self.dxcam_active = True
                self.use_mss = False
                print("[+] Capture: DXCam Active")
            except Exception as e:
                print(f"[-] DXCam Init Failed: {e}. Falling back to MSS.")
                self.dxcam_active = False
                self.use_mss = True
        
        if self.use_mss:
            if mss:
                print(f"[+] Capture: MSS Delta @ Q{quality}")
            else:
                print("[!] Capture: Pillow Fallback (MSS missing)")

        # Delta state
        self.prev_frame = None
        self.prev_hashes = {}  # tile_pos -> hash
        self.frame_count = 0
        self.keyframe_interval = 60  # Full frame every 60 frames (~2 sec at 30fps)
        
        # GPU encoding
        self.use_gpu = HAS_GPU and cv2 is not None
        
        if self.use_gpu:
            print("[+] Encoding: GPU (NVENC)")
        else:
            print(f"[+] Encoding: CPU ({self.format})")
    
    def release(self):
        """Explicitly release resources"""
        if self.dxcam_instance is not None:
            try:
                # Stop capture loop first
                if hasattr(self.dxcam_instance, 'stop'):
                    self.dxcam_instance.stop()
                 
                # Explicit release if available
                if hasattr(self.dxcam_instance, 'release'):
                    self.dxcam_instance.release()  
                 
                # Note: Setting to None triggers comtypes __del__ which might log
                # "access violation" warnings due to race conditions in comtypes cleanup.
                # This is often benign in this context but noisy.
            except Exception: 
                pass
            finally:
                self.dxcam_instance = None

    def __del__(self):
        """Cleanup resources"""
        self.release()
    
    def get_raw_frame(self):
        """
        Get raw numpy frame for WebRTC (no JPEG encoding).
        Used by webrtc_tracks.py for H.264 encoding via aiortc.
        """
        raw_frame = self._capture_raw()
        if raw_frame is None:
            return None
        
        # Convert to numpy if needed
        if not isinstance(raw_frame, np.ndarray):
            frame_array = np.array(raw_frame)
        else:
            frame_array = raw_frame
        
        # Resize if needed
        if self.scale < 1.0:
            new_h = int(frame_array.shape[0] * self.scale)
            new_w = int(frame_array.shape[1] * self.scale)
            if cv2:
                frame_array = cv2.resize(frame_array, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            else:
                img = Image.fromarray(frame_array)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                frame_array = np.array(img)
        
        return frame_array
    
    def get_frame_bytes(self):
        """Get delta-encoded frame (or full keyframe)"""
        self.frame_count += 1
        
        # Force keyframe periodically (reserved for future delta frame implementation)
        _force_keyframe = (self.frame_count % self.keyframe_interval == 0)
        
        # Capture raw frame
        raw_frame = self._capture_raw()
        if raw_frame is None:
            return None
        
        # Convert to numpy for fast comparison
        if not isinstance(raw_frame, np.ndarray):
            frame_array = np.array(raw_frame)
        else:
            frame_array = raw_frame
        
        # Resize if needed
        if self.scale < 1.0:
            new_h = int(frame_array.shape[0] * self.scale)
            new_w = int(frame_array.shape[1] * self.scale)
            if cv2:
                frame_array = cv2.resize(frame_array, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            else:
                img = Image.fromarray(frame_array)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                frame_array = np.array(img)
        
        # Skip identical frames (fast hash check) - disabled for now, causes issues
        # frame_hash = hashlib.md5(frame_array.tobytes()[:10000]).digest()
        # if hasattr(self, '_last_frame_hash') and self._last_frame_hash == frame_hash:
        #     return None  # Skip - frame unchanged
        # self._last_frame_hash = frame_hash
        
        # Draw remote cursor functionality
        frame_array = self._draw_cursor(frame_array)

        # Always send keyframe for now (delta frames need debugging)
        # TODO: Re-enable delta frames after fixing decoder
        return self._encode_keyframe(frame_array)
    
        return None
    
    def _draw_cursor(self, frame_array):
        """Draw cursor overlay on frame with offset correction and click-reactive colors"""
        try:
            pt = POINT()
            windll.user32.GetCursorPos(byref(pt))
            
            # Adjust global cursor (screen 0,0) to monitor local
            off_x = getattr(self, 'monitor_left', 0)
            off_y = getattr(self, 'monitor_top', 0)
            x = pt.x - off_x
            y = pt.y - off_y
            
            # Simple bounds check
            h, w = frame_array.shape[:2]
            # print(f"Cursor: ({pt.x}, {pt.y}) -> ({x}, {y}) | Off: ({off_x}, {off_y}) | Shape: {w}x{h}") # Debug coordinates
            if 0 <= x < w and 0 <= y < h:
                # Default Color: Red (RGB: 255, 0, 0)
                color = (255, 0, 0)
                
                # Check Mouse Buttons (High Bit set = Pressed)
                # VK_LBUTTON=0x01, VK_RBUTTON=0x02, VK_MBUTTON=0x04
                if windll.user32.GetAsyncKeyState(0x01) & 0x8000:
                    color = (0, 255, 0) # Green (Left)
                elif windll.user32.GetAsyncKeyState(0x02) & 0x8000:
                    color = (0, 0, 255) # Blue (Right)
                elif windll.user32.GetAsyncKeyState(0x04) & 0x8000:
                    color = (255, 255, 0) # Yellow (Middle)

                if cv2:
                    # Ensure array is C-contiguous for OpenCV
                    if not frame_array.flags['C_CONTIGUOUS']:
                        frame_array = np.ascontiguousarray(frame_array)
                    
                    # cv2.circle works in-place
                    # Draw Color Dot
                    cv2.circle(frame_array, (x, y), 5, color, -1) 
                    # Add white outline for contrast (User preferred style)
                    cv2.circle(frame_array, (x, y), 6, (255, 255, 255), 1)
                    # print("Drew Cursor") # Debug
                else:
                    # Manual numpy drawing (less precise, square approx)
                    r = 4
                    y1, y2 = max(0, y-r), min(h, y+r)
                    x1, x2 = max(0, x-r), min(w, x+r)
                    frame_array[y1:y2, x1:x2] = list(color)
        except Exception as e:
            print(f"[-] Cursor Draw Error: {e}") # Debugging
            pass
        return frame_array

    def _capture_raw(self):
        """Capture raw frame as numpy array"""
        img = None
        
        # 1. DXCam
        if self.dxcam_instance:
            try:
                img = self.dxcam_instance.grab()
                if img is not None:
                    self._dxcam_fail_count = 0
                    # DXCam usually captures primary monitor at (0,0)
                    # TODO: If DXCam supports multi-monitor, get its offset
                    self.monitor_left = 0
                    self.monitor_top = 0
            except Exception as e:
                # Disable after failures
                self._dxcam_fail_count += 1
                if self._dxcam_fail_count > 5:
                    print(f"[-] DXCam failed repeatedly ({e}). Disabling.")
                    self.dxcam_instance = None
                    self.dxcam_active = False
                    self.use_mss = True
                else:
                    print(f"[-] DXCam Grab Error: {e}")

        # 2. MSS
        if img is None and self.use_mss and mss:
            try:
                with mss.mss() as sct:
                    # Check monitors
                    monitor_idx = 1
                    if len(sct.monitors) <= 1:
                        monitor_idx = 0 # Monitor 0 matches "all monitors" or single
                    
                    mon = sct.monitors[monitor_idx]
                    self.monitor_left = mon['left']
                    self.monitor_top = mon['top']
                    
                    sct_img = sct.grab(mon)
                    # MSS captures BGRA (4 channels): Blue, Green, Red, Alpha
                    img_bgra = np.frombuffer(sct_img.bgra, dtype=np.uint8)
                    # Reshape to (height, width, 4) for BGRA channels
                    img_bgra = img_bgra.reshape((sct_img.height, sct_img.width, 4))
                    # Convert BGRA to RGB: indices [2,1,0] select R,G,B, dropping Alpha
                    img = img_bgra[:, :, [2, 1, 0]]
            except Exception as e:
                print(f"[-] MSS Error: {e}")
        
        # 3. Fallback to PIL
        if img is None:
            try:
                from PIL import ImageGrab
                # ImageGrab.grab() captures primary or virtual screen
                # usually (0,0) for main
                pil_img = ImageGrab.grab()
                img = np.array(pil_img)
                self.monitor_left = 0
                self.monitor_top = 0
            except Exception as e:
                print(f"[-] PIL Error: {e}")
        
        # Draw Cursor
        if img is not None:
            img = self._draw_cursor(img)
            
        return img
    
    def _encode_keyframe(self, frame_array):
        """Encode full keyframe"""
        self.prev_frame = frame_array.copy()
        self._update_tile_hashes(frame_array)
        
        # Encode with GPU if available
        jpeg_data = self._compress_frame(frame_array)
        
        # Prefix with 'K' for keyframe
        return b'K' + jpeg_data
    
    def _encode_delta(self, frame_array):
        """Encode only changed tiles"""
        h, w = frame_array.shape[:2]
        changed_tiles = []
        
        for y in range(0, h, TILE_SIZE):
            for x in range(0, w, TILE_SIZE):
                tile_key = (x, y)
                tile = frame_array[y:y+TILE_SIZE, x:x+TILE_SIZE]
                
                # Fast hash comparison
                tile_hash = hashlib.md5(tile.tobytes()).digest()
                
                if tile_key not in self.prev_hashes or self.prev_hashes[tile_key] != tile_hash:
                    # Tile changed
                    self.prev_hashes[tile_key] = tile_hash
                    changed_tiles.append((x, y, tile))
        
        # Update previous frame
        self.prev_frame = frame_array.copy()
        
        # If too many tiles changed, send keyframe instead
        total_tiles = (h // TILE_SIZE) * (w // TILE_SIZE)
        if len(changed_tiles) > total_tiles * 0.5:
            return self._encode_keyframe(frame_array)
        
        # If nothing changed, send empty delta
        if not changed_tiles:
            return b'D\x00\x00'  # Delta with 0 tiles
        
        # Encode changed tiles
        # Format: 'D' + num_tiles(2 bytes) + [x(2), y(2), data_len(4), data]...
        import struct
        result = io.BytesIO()
        result.write(b'D')
        result.write(struct.pack('!H', len(changed_tiles)))
        
        for x, y, tile in changed_tiles:
            tile_jpeg = self._compress_tile(tile)
            result.write(struct.pack('!HHI', x, y, len(tile_jpeg)))
            result.write(tile_jpeg)
        
        return result.getvalue()
    
    def _update_tile_hashes(self, frame_array):
        """Update all tile hashes for keyframe"""
        h, w = frame_array.shape[:2]
        self.prev_hashes.clear()
        
        for y in range(0, h, TILE_SIZE):
            for x in range(0, w, TILE_SIZE):
                tile = frame_array[y:y+TILE_SIZE, x:x+TILE_SIZE]
                self.prev_hashes[(x, y)] = hashlib.md5(tile.tobytes()).digest()
    
    def _compress_frame(self, frame_array):
        """Compress full frame"""
        if self.use_gpu and cv2:
            # GPU JPEG encoding
            encode_param = [cv2.IMWRITE_JPEG_QUALITY, self.quality]
            _, buf = cv2.imencode('.jpg', cv2.cvtColor(frame_array, cv2.COLOR_RGB2BGR), encode_param)
            return buf.tobytes()
        else:
            # CPU encoding
            img = Image.fromarray(frame_array)
            with io.BytesIO() as output:
                if self.format == "WEBP":
                    img.save(output, format="WEBP", quality=self.quality, method=4)
                elif self.format == "JXL":
                    img.save(output, format="JXL", quality=self.quality)
                elif self.format == "PNG":
                    img.save(output, format="PNG", optimize=True)
                else:
                    img.save(output, format="JPEG", quality=self.quality, optimize=True)
                return output.getvalue()
    
    def _compress_tile(self, tile_array):
        """Compress single tile - always use fast JPEG"""
        if self.use_gpu and cv2:
            encode_param = [cv2.IMWRITE_JPEG_QUALITY, self.quality]
            _, buf = cv2.imencode('.jpg', cv2.cvtColor(tile_array, cv2.COLOR_RGB2BGR), encode_param)
            return buf.tobytes()
        else:
            img = Image.fromarray(tile_array)
            with io.BytesIO() as output:
                img.save(output, format="JPEG", quality=self.quality)
                return output.getvalue()


# Backwards compatible - use Delta capturer as default
ScreenCapturer = DeltaScreenCapturer
