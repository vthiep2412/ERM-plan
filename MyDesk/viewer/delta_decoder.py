"""
Delta Frame Decoder for MyDesk Viewer
Reconstructs frames from delta updates.
"""

import struct
from PyQt6.QtGui import QImage, QPixmap, QPainter

import time

TILE_SIZE = 32
MAX_LAG_MS = 100  # If behind by more than 100ms, drop to keyframe


class DeltaFrameDecoder:
    def __init__(self):
        self.current_frame = None  # QPixmap
        self.frame_size = None  # (width, height)
        self._last_decode_time = 0
        self._frames_behind = 0

    def decode(self, data):
        """
        Decode frame data.
        Returns QPixmap of the current frame state.

        Format:
        - 'K' + jpeg_data = Keyframe
        - 'D' + num_tiles(2 bytes) + [x(2), y(2), data_len(4), data]... = Delta
        """
        if not data or len(data) < 1:
            return self.current_frame

        # Lag detection
        now = time.time() * 1000
        if self._last_decode_time > 0:
            elapsed = now - self._last_decode_time
            if elapsed > MAX_LAG_MS:
                self._frames_behind += 1
            else:
                self._frames_behind = max(0, self._frames_behind - 1)
        self._last_decode_time = now

        frame_type = chr(data[0])
        payload = data[1:]

        if frame_type == "K":
            # Keyframe - always decode
            self._frames_behind = 0  # Reset lag counter
            return self._decode_keyframe(payload)
        elif frame_type == "D":
            # Skip delta if lagging (wait for next keyframe)
            if self._frames_behind > 3:
                return self.current_frame  # Skip this delta
            return self._decode_delta(payload)
        else:
            # Legacy format - raw JPEG
            return self._decode_keyframe(data)

    def _decode_keyframe(self, jpeg_data):
        """Decode full keyframe"""
        img = QImage()
        if img.loadFromData(jpeg_data):
            self.current_frame = QPixmap.fromImage(img)
            self.frame_size = (self.current_frame.width(), self.current_frame.height())
        return self.current_frame

    def _decode_delta(self, data):
        """Decode delta frame with changed tiles"""
        if len(data) < 2:
            return self.current_frame

        num_tiles = struct.unpack("!H", data[:2])[0]

        if num_tiles == 0:
            # No changes
            return self.current_frame

        if self.current_frame is None:
            # No base frame yet, can't apply delta
            return None

        # Create mutable copy
        result = QPixmap(self.current_frame)
        painter = QPainter(result)

        offset = 2
        for _ in range(num_tiles):
            if offset + 8 > len(data):
                break

            x, y, data_len = struct.unpack("!HHI", data[offset : offset + 8])
            offset += 8

            if offset + data_len > len(data):
                break

            tile_data = data[offset : offset + data_len]
            offset += data_len

            # Decode tile
            tile_img = QImage()
            if tile_img.loadFromData(tile_data):
                painter.drawImage(x, y, tile_img)

        painter.end()
        self.current_frame = result
        return self.current_frame

    def reset(self):
        """Reset decoder state"""
        self.current_frame = None
        self.frame_size = None



