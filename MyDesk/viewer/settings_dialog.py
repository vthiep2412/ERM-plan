"""
Settings Dialog for MyDesk Viewer
Configure capture method, quality, scale, and format.
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QComboBox, QSlider, QPushButton, QGroupBox)
from PyQt6.QtCore import Qt, pyqtSignal

class SettingsDialog(QDialog):
    settings_saved = pyqtSignal(dict)
    
    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle("Capture Settings")
        self.setMinimumWidth(350)
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; }
            QLabel { color: #CCCCCC; font-size: 13px; }
            QComboBox, QSlider { 
                background-color: #2D2D30; 
                color: white; 
                border: 1px solid #3E3E42; 
                padding: 5px;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #007ACC;
                color: white;
                border-radius: 5px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #005A9E; }
            QGroupBox { 
                color: #CCCCCC; 
                border: 1px solid #3E3E42;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title { padding: 0 5px; }
        """)
        
        self.settings = current_settings or {
            "method": "MSS",
            "quality": 50,
            "scale": 90,
            "format": "JPEG"
        }
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Capture Method
        method_group = QGroupBox("Capture Method")
        method_layout = QVBoxLayout(method_group)
        self.method_combo = QComboBox()
        self.method_combo.addItems(["MSS", "DXCam", "PIL"])
        self.method_combo.setCurrentText(self.settings.get("method", "MSS"))
        method_layout.addWidget(self.method_combo)
        layout.addWidget(method_group)
        
        # Quality Slider
        quality_group = QGroupBox("Quality")
        quality_layout = QVBoxLayout(quality_group)
        self.quality_label = QLabel(f"{self.settings.get('quality', 50)}%")
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(10, 100)
        self.quality_slider.setValue(self.settings.get("quality", 50))
        self.quality_slider.valueChanged.connect(lambda v: self.quality_label.setText(f"{v}%"))
        quality_layout.addWidget(self.quality_slider)
        quality_layout.addWidget(self.quality_label)
        layout.addWidget(quality_group)
        
        # Scale Slider
        scale_group = QGroupBox("Resolution Scale")
        scale_layout = QVBoxLayout(scale_group)
        self.scale_label = QLabel(f"{self.settings.get('scale', 90)}%")
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(50, 100)
        self.scale_slider.setValue(self.settings.get("scale", 90))
        self.scale_slider.valueChanged.connect(lambda v: self.scale_label.setText(f"{v}%"))
        scale_layout.addWidget(self.scale_slider)
        scale_layout.addWidget(self.scale_label)
        layout.addWidget(scale_group)
        
        # Format
        format_group = QGroupBox("Compression Format")
        format_layout = QVBoxLayout(format_group)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["JPEG", "WebP", "JXL"])
        self.format_combo.setCurrentText(self.settings.get("format", "JPEG"))
        format_layout.addWidget(self.format_combo)
        layout.addWidget(format_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("background-color: #3E3E42;")
        btn_cancel.clicked.connect(self.reject)
        
        btn_save = QPushButton("Save")
        btn_save.clicked.connect(self.save_settings)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
    def save_settings(self):
        self.settings = {
            "method": self.method_combo.currentText(),
            "quality": self.quality_slider.value(),
            "scale": self.scale_slider.value(),
            "format": self.format_combo.currentText()
        }
        self.settings_saved.emit(self.settings)
        self.accept()
    
    def get_settings(self):
        return self.settings
# This line was added at the bottom to force re-check. 
