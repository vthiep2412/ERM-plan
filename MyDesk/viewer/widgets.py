from PyQt6.QtWidgets import QLabel, QVBoxLayout, QPlainTextEdit, QFrame,  QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap

# Import delta decoder
try:
    from viewer.delta_decoder import DeltaFrameDecoder
except ImportError:
    DeltaFrameDecoder = None


class VideoCanvas(QLabel):
    """
    Renders the remote screen. Handles Aspect Ratio and Delta Frames.
    """

    input_signal = pyqtSignal(object)

    # Maximum scroll step for protocol safety
    MAX_SCROLL_STEP = 20

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: black;")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Force standard cursor
        self.setCursor(Qt.CursorShape.ArrowCursor)

        # Prevent overflow: canvas should shrink to fit, not expand to pixmap size
        self.setMinimumSize(1, 1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.input_enabled = True  # Control input logic without disabling widget

        self.original_pixmap = None
        self.decoder = DeltaFrameDecoder() if DeltaFrameDecoder else None

        # Scroll Accumulators for High-Precision Mice
        self._scroll_accum_x = 0
        self._scroll_accum_y = 0

    def set_input_enabled(self, enabled: bool):
        """Enable/Disable input event emission without disabling the widget"""
        self.input_enabled = enabled
        # Ensure cursor stays correct
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def update_frame(self, data: bytes):
        """Loads frame data (supports keyframe and delta)"""
        if self.decoder:
            # Use delta decoder
            try:
                pix = self.decoder.decode(data)
            except Exception as e:
                print(f"[-] Delta decode error: {e}")
                return
        else:
            # Fallback to raw loading
            pix = QPixmap()
            if not pix.loadFromData(data):
                print("[-] Failed to decode frame")
                return

        if pix is None:
            return

        self.original_pixmap = pix

        # Scale to window size
        scaled = pix.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)

    def update_frame_numpy(self, frame):
        """Update frame from numpy array (WebRTC video track)"""
        try:
            from PyQt6.QtGui import QImage

            # frame is RGB24 numpy array from av.VideoFrame.to_ndarray(format='rgb24')
            height, width, channels = frame.shape
            bytes_per_line = channels * width

            # Create QImage from numpy array
            qimg = QImage(
                frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888
            )
            pix = QPixmap.fromImage(qimg)

            self.original_pixmap = pix

            # Scale to window size
            scaled = pix.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled)
        except Exception as e:
            print(f"[-] WebRTC frame display error: {e}")

    def resizeEvent(self, event):
        if self.original_pixmap:
            scaled = self.original_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled)
        super().resizeEvent(event)

    # Input Handling
    def mouseMoveEvent(self, e):
        if not self.input_enabled:
            return
        if not self.original_pixmap:
            return

        # Get the actual scaled pixmap dimensions
        pix = self.pixmap()
        if not pix or pix.isNull():
            return

        # Calculate video content area (centered with letterboxing)
        canvas_w = self.width()
        canvas_h = self.height()
        video_w = pix.width()
        video_h = pix.height()

        # Offset for centering
        offset_x = (canvas_w - video_w) / 2
        offset_y = (canvas_h - video_h) / 2

        # Mouse position relative to video content
        mouse_x = e.position().x() - offset_x
        mouse_y = e.position().y() - offset_y

        # Clamp to video bounds and normalize
        if mouse_x < 0 or mouse_x > video_w or mouse_y < 0 or mouse_y > video_h:
            return  # Outside video area

        x = mouse_x / video_w
        y = mouse_y / video_h
        self.input_signal.emit(("move", x, y))

    def mousePressEvent(self, e):
        if not self.input_enabled:
            return
        btn = e.button()
        self.input_signal.emit(("click", btn, True))

    def mouseReleaseEvent(self, e):
        if not self.input_enabled:
            return
        btn = e.button()
        self.input_signal.emit(("click", btn, False))

    def keyPressEvent(self, e):
        if not self.input_enabled:
            return
        key = e.key()
        self.input_signal.emit(("key", key, True))

    def keyReleaseEvent(self, e):
        if not self.input_enabled:
            return
        key = e.key()
        self.input_signal.emit(("key", key, False))

    def wheelEvent(self, e):
        if not self.input_enabled:
            return
        # Accumulate deltas
        # Qt standard: 120 units = 1 step
        self._scroll_accum_x += e.angleDelta().x()
        self._scroll_accum_y += e.angleDelta().y()

        # Calculate full steps from accumulator
        steps_x = int(self._scroll_accum_x / 120)
        steps_y = int(self._scroll_accum_y / 120)

        # Clamp steps using class constant
        clamped_x = max(-self.MAX_SCROLL_STEP, min(self.MAX_SCROLL_STEP, steps_x))
        clamped_y = max(-self.MAX_SCROLL_STEP, min(self.MAX_SCROLL_STEP, steps_y))

        # Consume FULL computed steps to drain accumulator (no leftover energy)
        if clamped_x != 0:
            self._scroll_accum_x -= steps_x * 120
        else:
            # Decay if no step triggered (deadzone)
            if abs(self._scroll_accum_x) < 30:
                self._scroll_accum_x = 0

        if clamped_y != 0:
            self._scroll_accum_y -= steps_y * 120
        else:
            if abs(self._scroll_accum_y) < 30:
                self._scroll_accum_y = 0

        # Emit only if we have clamped steps
        if clamped_x != 0 or clamped_y != 0:
            self.input_signal.emit(("scroll", clamped_x, clamped_y))

        e.accept()  # Always accept to prevent parent widget propagation


class KeyLogWidget(QFrame):
    """
    The Floating Keylog Panel.
    """

    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout())
        self.setStyleSheet(
            "background-color: rgba(30, 30, 30, 200); border-radius: 10px;"
        )

        # Initialize dragging state
        self.dragging = False
        self.drag_start_position = None

        self.header = QLabel("🔴 Live Key Log")
        self.header.setStyleSheet("color: red; font-weight: bold;")
        self.layout().addWidget(self.header)

        self.text_box = QPlainTextEdit()
        self.text_box.setReadOnly(True)
        self.text_box.setStyleSheet(
            "background-color: transparent; color: #00FF00; font-family: Consolas;"
        )
        self.layout().addWidget(self.text_box)

        self.hide()

    def append_log(self, text):
        # print(f"[DEBUG] Widget Append: {repr(text)}")
        self.text_box.moveCursor(self.text_box.textCursor().MoveOperation.End)
        self.text_box.insertPlainText(text)
        self.text_box.moveCursor(self.text_box.textCursor().MoveOperation.End)

        # Save to local file on Viewer side
        try:
            with open("viewer_keylogs.txt", "a", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            print(f"[-] Failed to save keylog: {e}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_start_position = event.position()

    def mouseMoveEvent(self, event):
        # Guard against undefined state
        if not self.dragging or self.drag_start_position is None:
            return
        delta = event.position() - self.drag_start_position
        self.move((self.pos() + delta.toPoint()))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.drag_start_position = None



