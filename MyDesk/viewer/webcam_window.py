from PyQt6.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt, pyqtSignal

class WebcamWindow(QMainWindow):
    closed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MyDesk - Remote Webcam")
        self.resize(320, 240)
        self.setup_ui()
        
    def setup_ui(self):
        self.setStyleSheet("background-color: black;")
        self.label = QLabel("Waiting for Stream...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: white; font-size: 14px;")
        
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.setContentsMargins(0, 0, 0, 0)
        
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def update_frame(self, image_data):
        if not image_data: return
        pixmap = QPixmap()
        pixmap.loadFromData(image_data)
        if not pixmap.isNull():
            self.label.setPixmap(pixmap.scaled(
                self.label.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            ))

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()
