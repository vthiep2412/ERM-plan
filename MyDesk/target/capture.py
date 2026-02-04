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
    
    def __del__(self):
        """Cleanup resources"""
        if self.dxcam_instance is not None:
             try:
                 # Check if it has a release/stop logic (dxcam official has .stop())
                 if hasattr(self.dxcam_instance, 'stop'):
                     self.dxcam_instance.stop()
                 del self.dxcam_instance
             except: pass
             self.dxcam_instance = None
    
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
        
        # Always send keyframe for now (delta frames need debugging)
        # TODO: Re-enable delta frames after fixing decoder
        return self._encode_keyframe(frame_array)
    
    def _capture_raw(self):
        """Capture raw frame as numpy array"""
        # 1. DXCam
        if self.dxcam_instance:
            try:
                img = self.dxcam_instance.grab()
                if img is not None:
                    self._dxcam_fail_count = 0
                    return img
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
        if self.use_mss and mss:
            try:
                with mss.mss() as sct:
                    # Check monitors
                    monitor_idx = 1
                    if len(sct.monitors) <= 1:
                        monitor_idx = 0 # Monitor 0 matches "all monitors" or single
                    
                    sct_img = sct.grab(sct.monitors[monitor_idx])
                    # MSS captures BGRA (4 channels): Blue, Green, Red, Alpha
                    img = np.frombuffer(sct_img.bgra, dtype=np.uint8)
                    # Reshape to (height, width, 4) for BGRA channels
                    img = img.reshape((sct_img.height, sct_img.width, 4))
                    # Convert BGRA to RGB: indices [2,1,0] select R,G,B, dropping Alpha
                    return img[:, :, [2, 1, 0]]
            except Exception as e:
                print(f"[-] MSS Error: {e}")
        
        # 3. Fallback to PIL
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            return np.array(img)
        except Exception as e:
            print(f"[-] PIL Error: {e}")
        
        return None
    
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
