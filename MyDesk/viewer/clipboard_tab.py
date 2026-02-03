"""
Clipboard Tab Widget - View and sync clipboard between viewer and agent
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, 
    QPushButton, QLabel
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont, QGuiApplication


class ClipboardTab(QWidget):
    """Clipboard sync widget."""
    
    get_clipboard_signal = pyqtSignal()  # Request remote clipboard
    set_clipboard_signal = pyqtSignal(str)  # Set remote clipboard
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Title
        title = QLabel("📋 Remote Clipboard")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #d4d4d4;")
        layout.addWidget(title)
        
        # Remote clipboard content
        self.remote_text = QPlainTextEdit()
        self.remote_text.setFont(QFont("Consolas", 10))
        self.remote_text.setPlaceholderText("Remote clipboard content will appear here...")
        self.remote_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #2d2d2d;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.remote_text, 1)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.get_btn = QPushButton("📥 Get Remote Clipboard")
        self.get_btn.clicked.connect(self.get_remote_clipboard)
        self.get_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        
        self.set_btn = QPushButton("📤 Send to Remote")
        self.set_btn.clicked.connect(self.set_remote_clipboard)
        self.set_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d7d46;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #38a55a;
            }
        """)
        
        self.copy_local_btn = QPushButton("📋 Copy to Local")
        self.copy_local_btn.clicked.connect(self.copy_to_local)
        self.copy_local_btn.setStyleSheet("""
            QPushButton {
                background-color: #5c5c5c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #6e6e6e;
            }
        """)
        
        self.paste_local_btn = QPushButton("📌 Paste from Local")
        self.paste_local_btn.clicked.connect(self.paste_from_local)
        self.paste_local_btn.setStyleSheet("""
            QPushButton {
                background-color: #5c5c5c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #6e6e6e;
            }
        """)
        
        btn_layout.addWidget(self.get_btn)
        btn_layout.addWidget(self.set_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.copy_local_btn)
        btn_layout.addWidget(self.paste_local_btn)
        
        layout.addLayout(btn_layout)
    
    def get_remote_clipboard(self):
        """Request remote clipboard content."""
        self.get_clipboard_signal.emit()
    
    def set_remote_clipboard(self):
        """Send text box content to remote clipboard."""
        text = self.remote_text.toPlainText()
        if text:
            self.set_clipboard_signal.emit(text)
    
    def copy_to_local(self):
        """Copy remote clipboard content to local clipboard."""
        text = self.remote_text.toPlainText()
        if text:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(text)
    
    def paste_from_local(self):
        """Paste local clipboard content to text area."""
        clipboard = QGuiApplication.clipboard()
        text = clipboard.text()
        if text:
            self.remote_text.setPlainText(text)
    
    def update_content(self, text):
        """Update with remote clipboard content."""
        self.remote_text.setPlainText(text)
