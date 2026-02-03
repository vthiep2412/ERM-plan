from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QPlainTextEdit, QFrame
from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from PyQt6.QtGui import QPixmap, QImage

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

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: black;")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        self.original_pixmap = None
        self.decoder = DeltaFrameDecoder() if DeltaFrameDecoder else None

    def update_frame(self, data: bytes):
        """Loads frame data (supports keyframe and delta)"""
        if self.decoder:
            # Use delta decoder
            pix = self.decoder.decode(data)
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
        scaled = pix.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.setPixmap(scaled)

    def resizeEvent(self, event):
        if self.original_pixmap:
            scaled = self.original_pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(scaled)
        super().resizeEvent(event)

    # Input Handling
    def mouseMoveEvent(self, e):
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
        self.input_signal.emit(('move', x, y))

    def mousePressEvent(self, e):
        btn = e.button()
        self.input_signal.emit(('click', btn, True))

    def mouseReleaseEvent(self, e):
        btn = e.button()
        self.input_signal.emit(('click', btn, False))

    def keyPressEvent(self, e):
        key = e.key()
        self.input_signal.emit(('key', key, True))

    def keyReleaseEvent(self, e):
        key = e.key()
        self.input_signal.emit(('key', key, False))

    def wheelEvent(self, e):
        # Read both axes (X and Y)
        delta_x = e.angleDelta().x()
        delta_y = e.angleDelta().y()
        
        # Compute step counts by dividing by standard 120 provided by Qt
        # Use rounding for better precision with high-res mice
        steps_x = round(delta_x / 120)
        steps_y = round(delta_y / 120)
        
        # Clamp values to avoid overflow or extreme jumps
        MAX_STEP = 20
        steps_x = max(-MAX_STEP, min(MAX_STEP, steps_x))
        steps_y = max(-MAX_STEP, min(MAX_STEP, steps_y))
        
        # Emit if there is any movement
        if steps_x != 0 or steps_y != 0:
            self.input_signal.emit(('scroll', steps_x, steps_y))


class KeyLogWidget(QFrame):
    """
    The Floating Keylog Panel.
    """
    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout())
        self.setStyleSheet("background-color: rgba(30, 30, 30, 200); border-radius: 10px;")
        
        # Initialize dragging state
        self.dragging = False
        self.drag_start_position = None
        
        self.header = QLabel("🔴 Live Key Log")
        self.header.setStyleSheet("color: red; font-weight: bold;")
        self.layout().addWidget(self.header)
        
        self.text_box = QPlainTextEdit()
        self.text_box.setReadOnly(True)
        self.text_box.setStyleSheet("background-color: transparent; color: #00FF00; font-family: Consolas;")
        self.layout().addWidget(self.text_box)
        
        self.hide()

    def append_log(self, text):
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
