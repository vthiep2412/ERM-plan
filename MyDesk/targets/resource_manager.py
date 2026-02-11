"""
Resource Manager - Stealth Mode for MyDesk Agent
Minimizes CPU/memory usage when not actively streaming.
"""

import time
import threading


class ResourceManager:
    """
    Intelligent resource throttling for invisible idle mode.

    When no viewer is connected or screen is static:
    - Reduces capture rate to near-zero
    - Minimizes CPU usage (< 1%)
    """

    def __init__(self):
        self.viewer_connected = False
        self.stream_enabled = False
        self.screen_static = True
        self.last_activity = time.time()
        self._lock = threading.Lock()

        # User settings
        self.user_target_fps = 30
        self.user_quality = 70

        # Frame skip tracking
        self._last_frame_hash = None
        self._static_frame_count = 0

    def set_user_settings(self, fps: int = None, quality: int = None):
        """Update user-defined limits"""
        with self._lock:
            if fps is not None:
                self.user_target_fps = max(1, min(60, fps))
            if quality is not None:
                self.user_quality = max(1, min(100, quality))

    def set_viewer_connected(self, connected: bool):
        """Called when viewer connects/disconnects"""
        with self._lock:
            self.viewer_connected = connected
            if connected:
                self.last_activity = time.time()

    def set_stream_enabled(self, enabled: bool):
        """Called when stream starts/stops"""
        with self._lock:
            self.stream_enabled = enabled

    def mark_screen_changed(self):
        """Called when screen content changes"""
        with self._lock:
            self.screen_static = False
            self._static_frame_count = 0
            self.last_activity = time.time()

    def mark_screen_static(self):
        """Called when screen hasn't changed"""
        with self._lock:
            self._static_frame_count += 1
            if self._static_frame_count > 10:
                self.screen_static = True

    def should_capture(self) -> bool:
        """Returns True if we should capture a frame"""
        with self._lock:
            # Don't capture if no one is watching
            if not self.viewer_connected:
                return False
            if not self.stream_enabled:
                return False
            return True

    def get_target_fps(self) -> int:
        """
        Returns optimal FPS based on current state.

        - Idle (no viewer): 0 FPS
        - Static screen: 5 FPS (just in case something changes)
        - Active: User target FPS (default 30)
        """
        with self._lock:
            if not self.viewer_connected:
                return 0
            if self.screen_static:
                return min(5, self.user_target_fps)
            return self.user_target_fps

    def get_frame_delay(self) -> float:
        """Returns delay between frames in seconds"""
        fps = self.get_target_fps()
        if fps <= 0:
            return 1.0  # Check once per second when idle
        return 1.0 / fps

    def get_adaptive_quality(self, base_quality: int = None) -> int:
        """
        Returns quality based on current state.

        - Static screen: Lower quality OK (less bandwidth)
        - Active: Full quality
        """
        with self._lock:
            target = base_quality if base_quality is not None else self.user_quality
            if self.screen_static:
                return max(30, target - 20)  # Lower quality for static
            return target


# Global instance
_resource_manager = None


def get_resource_manager() -> ResourceManager:
    """Get global ResourceManager instance"""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager
