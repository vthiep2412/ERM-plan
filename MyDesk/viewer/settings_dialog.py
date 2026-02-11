"""
Settings Dialog for MyDesk Viewer
Configure capture method, quality, scale, and format.
"""

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QSlider,
    QPushButton,
    QGroupBox,
    QCheckBox,
    QMessageBox,
)
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
            "quality": 70,
            "scale": 100,
            "fps": 30,
            "format": "JPEG",
            "safety_mode": True,
        }

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Capture Method
        method_group = QGroupBox("Capture Method")
        method_layout = QVBoxLayout(method_group)
        self.method_combo = QComboBox()
        self.method_combo.addItems(["MSS"])
        self.method_combo.setCurrentText(self.settings.get("method", "MSS"))
        method_layout.addWidget(self.method_combo)
        layout.addWidget(method_group)

        # FPS Slider
        fps_group = QGroupBox("Target FPS (WebRTC)")
        fps_layout = QVBoxLayout(fps_group)
        self.fps_label = QLabel(f"{self.settings.get('fps', 30)} FPS")
        self.fps_slider = QSlider(Qt.Orientation.Horizontal)
        self.fps_slider.setRange(1, 60)
        self.fps_slider.setValue(self.settings.get("fps", 30))
        self.fps_slider.valueChanged.connect(
            lambda v: self.fps_label.setText(f"{v} FPS")
        )
        fps_layout.addWidget(self.fps_slider)
        fps_layout.addWidget(self.fps_label)
        layout.addWidget(fps_group)

        # Quality Slider
        quality_group = QGroupBox("Quality / Bitrate")
        quality_layout = QVBoxLayout(quality_group)
        self.quality_label = QLabel(f"{self.settings.get('quality', 70)}%")
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(10, 100)
        self.quality_slider.setValue(self.settings.get("quality", 70))
        self.quality_slider.valueChanged.connect(
            lambda v: self.quality_label.setText(f"{v}%")
        )
        quality_layout.addWidget(self.quality_slider)
        quality_layout.addWidget(self.quality_label)
        layout.addWidget(quality_group)

        # Scale Slider
        scale_group = QGroupBox("Resolution Scale")
        scale_layout = QVBoxLayout(scale_group)
        self.scale_label = QLabel(f"{self.settings.get('scale', 100)}%")
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(25, 100)
        self.scale_slider.setValue(self.settings.get("scale", 100))
        self.scale_slider.valueChanged.connect(
            lambda v: self.scale_label.setText(f"{v}%")
        )
        scale_layout.addWidget(self.scale_slider)
        scale_layout.addWidget(self.scale_label)
        layout.addWidget(scale_group)

        # Format
        format_group = QGroupBox("Compression Format (Legacy)")
        format_layout = QVBoxLayout(format_group)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["JPEG", "WebP"])
        self.format_combo.setCurrentText(self.settings.get("format", "JPEG"))
        format_layout.addWidget(self.format_combo)
        layout.addWidget(format_group)

        # Safety Mode
        safety_group = QGroupBox("Security")
        safety_layout = QVBoxLayout(safety_group)
        self.safety_check = QCheckBox("Safety Mode (Protect System Files)")
        is_safe = self.settings.get("safety_mode", True)
        self.safety_check.setChecked(is_safe)
        self.safety_check.setStyleSheet(f"color: {'#22c55e' if is_safe else '#CCCCCC'};")
        self.safety_check.clicked.connect(self.on_safety_toggle)
        safety_layout.addWidget(self.safety_check)
        
        lbl_hint = QLabel("Prevents deletion of critical folders (Windows, Program Files, etc.)")
        lbl_hint.setWordWrap(True)
        lbl_hint.setStyleSheet("color: #888; font-size: 10px; margin-top: 5px;")
        safety_layout.addWidget(lbl_hint)
        layout.addWidget(safety_group)

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
            "fps": self.fps_slider.value(),
            "quality": self.quality_slider.value(),
            "scale": self.scale_slider.value(),
            "format": self.format_combo.currentText(),
            "safety_mode": self.safety_check.isChecked(),
        }
        self.settings_saved.emit(self.settings)
        self.accept()

    def on_safety_toggle(self, checked):
        """Double confirmation for disabling safety mode"""
        if not checked:
            # First warning
            reply1 = QMessageBox.warning(
                self,
                "Security Warning",
                "Disabling Safety Mode will allow the viewer to DELETE critical system folders and drives.\n\n"
                "This could PERMANENTLY DAMAGE the target operating system.\n\n"
                "Are you sure you want to proceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply1 == QMessageBox.StandardButton.Yes:
                # Second warning
                reply2 = QMessageBox.critical(
                    self,
                    "CRITICAL CONFIRMATION",
                    "THIS IS DANGEROUS.\n\n"
                    "By clicking YES, you confirm that you take full responsibility for any "
                    "instability or data loss caused by unauthorized file system operations.\n\n"
                    "STILL PROCEED?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )

                if reply2 == QMessageBox.StandardButton.Yes:
                    self.safety_check.setStyleSheet("color: #FF5555;")
                    return

            # Revert check if any "No" or dialog closed
            self.safety_check.setChecked(True)
        else:
            self.safety_check.setStyleSheet("color: #22c55e;")

    def get_settings(self):
        return self.settings
