"""
Connection Progress Dialog for MyDesk Viewer
Shows handshake progress and blocks interaction until connected.
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

class ConnectionDialog(QDialog):
    """Modal dialog showing connection progress"""
    
    cancelled = pyqtSignal()
    
    def __init__(self, target_id, parent=None):
        super().__init__(parent)
        self.target_id = target_id
        self.setWindowTitle("Connecting...")
        self.setModal(True)
        self.setFixedSize(400, 200)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; }
            QLabel { color: #CCCCCC; }
            QProgressBar { 
                background-color: #2D2D30;
                border: none;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #007ACC;
                border-radius: 5px;
            }
        """)
        
        self.setup_ui()
        self.current_step = 0
        self.steps = [
            "🔌 Connecting to Broker...",
            "🔍 Looking up Target ID...",
            "🤝 Waiting for Handshake...",
            "✅ Connection Established!"
        ]
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title
        title = QLabel(f"Connecting to: {self.target_id}")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white;")
        layout.addWidget(title)
        
        # Status label
        self.status_label = QLabel("🔌 Initializing...")
        self.status_label.setFont(QFont("Segoe UI", 11))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        layout.addWidget(self.progress)
        
        # Hint label
        self.hint_label = QLabel("Please wait...")
        self.hint_label.setFont(QFont("Segoe UI", 9))
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet("color: #888;")
        layout.addWidget(self.hint_label)
        
        layout.addStretch()
    
    def set_step(self, step_index, hint=""):
        """Update current step (0-3)"""
        self.current_step = step_index
        if 0 <= step_index < len(self.steps):
            self.status_label.setText(self.steps[step_index])
            self.progress.setValue(int((step_index + 1) / len(self.steps) * 100))
        
        if hint:
            self.hint_label.setText(hint)
    
    def set_error(self, message):
        """Show error state"""
        self.status_label.setText(f"❌ {message}")
        self.status_label.setStyleSheet("color: #FF6B6B;")
        self.hint_label.setText("Click anywhere to close")
        self.progress.setStyleSheet("""
            QProgressBar::chunk { background-color: #FF6B6B; }
        """)
    
    def set_success(self):
        """Show success state and auto-close"""
        self.set_step(3)
        self.status_label.setStyleSheet("color: #4CAF50;")
        QTimer.singleShot(500, self.accept)
    
    def mousePressEvent(self, event):
        """Allow closing on click if error"""
        if "❌" in self.status_label.text():
            self.reject()
    
    def closeEvent(self, event):
        """Emit cancelled signal if closed before success"""
        if self.current_step < 3:
            self.cancelled.emit()
        super().closeEvent(event)
# alr 
