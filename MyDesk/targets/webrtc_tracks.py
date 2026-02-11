"""
WebRTC Media Tracks for MyDesk Agent
Custom VideoStreamTrack implementations for screen capture and webcam.
"""

import asyncio
import time
import fractions

try:
    from aiortc import VideoStreamTrack
    import av

    AIORTC_AVAILABLE = True
except ImportError:
    AIORTC_AVAILABLE = False

    # Dummy class for when aiortc isn't available
    class VideoStreamTrack:
        pass


import numpy as np


class ScreenShareTrack(VideoStreamTrack):
    """
    Video track that captures screen content.
    Uses existing DeltaScreenCapturer but outputs av.VideoFrame for WebRTC.

    H.264 encoding is handled automatically by aiortc.
    """

    kind = "video"

    def __init__(self, capturer, resource_manager=None):
        super().__init__()
        self._capturer = capturer # Can be a direct object or an object with a .capturer attr
        self.resource_manager = resource_manager

        # Frame timing
        self._start_time = None
        self._frame_count = 0
        self._target_fps = 30

    @property
    def capturer(self):
        # Support dynamic reference if we passed the Agent itself
        if hasattr(self._capturer, "capturer"):
            # Ensure the inner capturer is valid (not None)
            inner = getattr(self._capturer, "capturer", None)
            if inner is not None:
                return inner
        return self._capturer

    async def recv(self):
        """
        Called by aiortc to get the next video frame.
        Returns av.VideoFrame for H.264 encoding.
        """
        # ... (lines 60-90 unchanged) ...

        # Capture frame immediately to reduce input-to-display latency
        try:
            raw_frame = self._capture_frame()
            if raw_frame is None:
                # Return a blank frame if capture fails
                if not hasattr(self, "_black_frame") or self._black_frame is None:
                    self._black_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
                raw_frame = self._black_frame
            else:
                # Store size for fallback
                if not hasattr(self, "_last_size") or self._last_size != raw_frame.shape[:2]:
                    self._last_size = raw_frame.shape[:2]
                    self._black_frame = np.zeros((self._last_size[0], self._last_size[1], 3), dtype=np.uint8)

        except Exception as e:
            print(f"[ScreenTrack] Capture error: {e}")
            if hasattr(self, "_black_frame") and self._black_frame is not None:
                raw_frame = self._black_frame
            else:
                # Use last known size or default
                if hasattr(self, "_last_size") and self._last_size:
                    h, w = self._last_size
                else:
                    h, w = 720, 1280
                raw_frame = np.zeros((h, w, 3), dtype=np.uint8)

        # Timing: wait until the frame interval is actually reached
        target_time = self._start_time + (self._frame_count * frame_duration)
        now = time.time()
        if target_time > now:
            await asyncio.sleep(target_time - now)

        self._frame_count += 1

        # Convert numpy array to av.VideoFrame
        try:
            video_frame = av.VideoFrame.from_ndarray(raw_frame, format="rgb24")
            video_frame.pts = self._frame_count
            video_frame.time_base = fractions.Fraction(1, self._target_fps)
            return video_frame
        except Exception as e:
            print(f"[ScreenTrack] av.VideoFrame error: {e}")
            # Final fallback
            if hasattr(self, "_last_size") and self._last_size:
                h, w = self._last_size
            else:
                h, w = 720, 1280
            black = np.zeros((h, w, 3), dtype=np.uint8)
            video_frame = av.VideoFrame.from_ndarray(black, format="rgb24")
            video_frame.pts = self._frame_count
            video_frame.time_base = fractions.Fraction(1, self._target_fps)
            return video_frame

    def _capture_frame(self) -> np.ndarray:
        """Get raw numpy frame from capturer"""
        # Check if capturer has get_raw_frame method (we'll add this)
        if hasattr(self.capturer, "get_raw_frame"):
            return self.capturer.get_raw_frame()

        # Fallback: use _capture_raw directly
        if hasattr(self.capturer, "_capture_raw"):
            return self.capturer._capture_raw()

        return None


class WebcamTrack(VideoStreamTrack):
    """
    Video track that captures webcam content.
    Uses existing WebcamStreamer but outputs av.VideoFrame for WebRTC.
    """

    kind = "video"

    def __init__(self, webcam_streamer, resource_manager=None):
        super().__init__()
        self.webcam = webcam_streamer
        self.resource_manager = resource_manager

        # Frame timing
        self._start_time = None
        self._frame_count = 0
        self._target_fps = 15  # Webcam typically 15 FPS

    async def recv(self):
        """Get next webcam frame"""
        if self._start_time is None:
            self._start_time = time.time()

        # Frame timing
        frame_duration = 1.0 / self._target_fps
        target_time = self._start_time + (self._frame_count * frame_duration)
        now = time.time()
        if target_time > now:
            await asyncio.sleep(target_time - now)

        self._frame_count += 1

        # Capture from webcam
        try:
            raw_frame = self._capture_frame()
            if raw_frame is None:
                raw_frame = np.zeros((240, 320, 3), dtype=np.uint8)
        except Exception as e:
            print(f"[WebcamTrack] Capture error: {e}")
            raw_frame = np.zeros((240, 320, 3), dtype=np.uint8)

        # Convert to av.VideoFrame
        video_frame = av.VideoFrame.from_ndarray(
            raw_frame, format="bgr24"
        )  # cv2 uses BGR
        video_frame.pts = self._frame_count
        video_frame.time_base = fractions.Fraction(1, self._target_fps)

        return video_frame

    def _capture_frame(self) -> np.ndarray:
        """Get raw numpy frame from webcam"""
        if not self.webcam or not self.webcam.running:
            return None

        if hasattr(self.webcam, "cap") and self.webcam.cap:
            ret, frame = self.webcam.cap.read()
            if ret:
                return frame
        return None


# Factory functions
def create_screen_track(capturer, resource_manager=None):
    """Create a screen sharing video track"""
    if not AIORTC_AVAILABLE:
        raise RuntimeError("aiortc required for WebRTC tracks")
    return ScreenShareTrack(capturer, resource_manager)


def create_webcam_track(webcam_streamer, resource_manager=None):
    """Create a webcam video track"""
    if not AIORTC_AVAILABLE:
        raise RuntimeError("aiortc required for WebRTC tracks")
    return WebcamTrack(webcam_streamer, resource_manager)
