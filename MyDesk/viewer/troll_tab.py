"""
Troll Tab Widget - Fun pranks and visual/audio effects
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
    QPushButton, QLineEdit, QCheckBox,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import pyqtSignal, Qt

# Maximum video file size for upload (50MB)
MAX_VIDEO_BYTES = 50 * 1024 * 1024


class TrollTab(QWidget):
    """Troll features widget."""
    
    # Browser
    open_url_signal = pyqtSignal(str)
    
    # Audio
    play_sound_signal = pyqtSignal(bytes)  # audio data
    random_sound_signal = pyqtSignal(bool, int)  # enabled, interval_ms
    alert_loop_signal = pyqtSignal(bool)
    volume_max_signal = pyqtSignal()
    earrape_signal = pyqtSignal()
    whisper_signal = pyqtSignal(bool)
    
    # Visual
    play_video_signal = pyqtSignal(bytes)  # video data
    ghost_cursor_signal = pyqtSignal(bool)
    shuffle_icons_signal = pyqtSignal()
    wallpaper_signal = pyqtSignal(bytes)  # image data
    overlay_signal = pyqtSignal(str)  # crack|hair
    
    # Control
    stop_all_signal = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # Browser Section
        browser_group = QGroupBox("🌐 Open URL")
        browser_layout = QHBoxLayout(browser_group)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        self.url_input.returnPressed.connect(self.open_url)
        
        self.open_url_btn = QPushButton("🚀 Open")
        self.open_url_btn.clicked.connect(self.open_url)
        self.open_url_btn.setStyleSheet("background-color: #0e639c; color: white;")
        
        browser_layout.addWidget(self.url_input, 1)
        browser_layout.addWidget(self.open_url_btn)
        
        layout.addWidget(browser_group)
        
        # Audio Section
        audio_group = QGroupBox("🔊 Audio Pranks")
        audio_layout = QVBoxLayout(audio_group)
        
        # Play Sound
        sound_row = QHBoxLayout()
        self.play_sound_btn = QPushButton("🎵 Play Sound")
        self.play_sound_btn.clicked.connect(self.pick_and_send_sound)
        
        self.volume_max_btn = QPushButton("📢 MAX Volume + Sound")
        self.volume_max_btn.clicked.connect(self.volume_max_signal.emit)
        self.volume_max_btn.setStyleSheet("background-color: #d7a426; color: white;")
        
        self.earrape_btn = QPushButton("💥 Earrape")
        self.earrape_btn.clicked.connect(self.earrape_signal.emit)
        self.earrape_btn.setStyleSheet("background-color: #c42b1c; color: white;")
        
        sound_row.addWidget(self.play_sound_btn)
        sound_row.addWidget(self.volume_max_btn)
        sound_row.addWidget(self.earrape_btn)
        audio_layout.addLayout(sound_row)
        
        # Toggles
        toggle_row = QHBoxLayout()
        
        self.random_sound_check = QCheckBox("Random Sounds")
        self.random_sound_check.stateChanged.connect(self.on_random_sound_toggle)
        
        self.alert_loop_check = QCheckBox("Alert Loop")
        self.alert_loop_check.stateChanged.connect(
            lambda s: self.alert_loop_signal.emit(s == Qt.CheckState.Checked.value)
        )
        
        self.whisper_check = QCheckBox("Whisper")
        self.whisper_check.stateChanged.connect(
            lambda s: self.whisper_signal.emit(s == Qt.CheckState.Checked.value)
        )
        
        toggle_row.addWidget(self.random_sound_check)
        toggle_row.addWidget(self.alert_loop_check)
        toggle_row.addWidget(self.whisper_check)
        toggle_row.addStretch()
        
        audio_layout.addLayout(toggle_row)
        layout.addWidget(audio_group)
        
        # Visual Section
        visual_group = QGroupBox("👁️ Visual Pranks")
        visual_layout = QVBoxLayout(visual_group)
        
        # Row 1
        visual_row1 = QHBoxLayout()
        
        self.video_btn = QPushButton("🎬 Play Fullscreen Video")
        self.video_btn.clicked.connect(self.pick_and_send_video)
        
        self.ghost_cursor_check = QCheckBox("👻 Ghost Cursor")
        self.ghost_cursor_check.stateChanged.connect(
            lambda s: self.ghost_cursor_signal.emit(s == Qt.CheckState.Checked.value)
        )
        
        visual_row1.addWidget(self.video_btn)
        visual_row1.addWidget(self.ghost_cursor_check)
        visual_row1.addStretch()
        
        visual_layout.addLayout(visual_row1)
        
        # Row 2
        visual_row2 = QHBoxLayout()
        
        self.shuffle_icons_btn = QPushButton("🔀 Shuffle Desktop Icons")
        self.shuffle_icons_btn.clicked.connect(self.shuffle_icons_signal.emit)
        
        self.wallpaper_btn = QPushButton("🖼️ Change Wallpaper")
        self.wallpaper_btn.clicked.connect(self.pick_and_send_wallpaper)
        
        visual_row2.addWidget(self.shuffle_icons_btn)
        visual_row2.addWidget(self.wallpaper_btn)
        visual_row2.addStretch()
        
        visual_layout.addLayout(visual_row2)
        
        # Row 3 - Overlays
        visual_row3 = QHBoxLayout()
        
        self.crack_btn = QPushButton("💔 Fake Crack")
        self.crack_btn.clicked.connect(lambda: self.overlay_signal.emit("crack"))
        
        self.hair_btn = QPushButton("🦱 Fake Hair")
        self.hair_btn.clicked.connect(lambda: self.overlay_signal.emit("hair"))
        
        visual_row3.addWidget(self.crack_btn)
        visual_row3.addWidget(self.hair_btn)
        visual_row3.addStretch()
        
        visual_layout.addLayout(visual_row3)
        layout.addWidget(visual_group)
        
        # Stop All Button
        self.stop_all_btn = QPushButton("🛑 STOP ALL TROLLS")
        self.stop_all_btn.clicked.connect(self.stop_all)
        self.stop_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #c42b1c;
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #e03e2d;
            }
        """)
        layout.addWidget(self.stop_all_btn)
        
        # Spacer
        layout.addStretch()
    
    def show_error_message(self, msg):
        """Show error message in a dialog."""
        QMessageBox.critical(self, "Error", msg)
    
    def open_url(self):
        url = self.url_input.text().strip()
        if url:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            self.open_url_signal.emit(url)
    
    def on_random_sound_toggle(self, state):
        enabled = state == Qt.CheckState.Checked.value
        interval = 5000  # 5 seconds default
        self.random_sound_signal.emit(enabled, interval)
    
    def pick_and_send_sound(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Audio File", 
            "", "Audio Files (*.mp3 *.wav *.ogg)"
        )
        if file_path:
            try:
                with open(file_path, 'rb') as f:
                    data = f.read()
                self.play_sound_signal.emit(data)
            except Exception as e:
                self.show_error_message(f"Error reading audio file:\n{file_path}\n\n{e}")
    
    def pick_and_send_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File",
            "", "Video Files (*.mp4 *.avi *.mkv *.webm)"
        )
        if file_path:
            try:
                # Check file size before loading
                file_size = os.path.getsize(file_path)
                if file_size > MAX_VIDEO_BYTES:
                    size_mb = file_size / (1024 * 1024)
                    limit_mb = MAX_VIDEO_BYTES / (1024 * 1024)
                    self.show_error_message(
                        f"Video file is too large ({size_mb:.1f} MB).\n\n"
                        f"Maximum allowed size is {limit_mb:.0f} MB."
                    )
                    return
                
                with open(file_path, 'rb') as f:
                    data = f.read()
                self.play_video_signal.emit(data)
            except Exception as e:
                self.show_error_message(f"Error reading video file:\n{file_path}\n\n{e}")
    
    def pick_and_send_wallpaper(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Wallpaper Image",
            "", "Image Files (*.jpg *.jpeg *.png *.bmp)"
        )
        if file_path:
            try:
                with open(file_path, 'rb') as f:
                    data = f.read()
                self.wallpaper_signal.emit(data)
            except Exception as e:
                self.show_error_message(f"Error reading image file:\n{file_path}\n\n{e}")
    
    def stop_all(self):
        """Stop all active trolls and uncheck all toggles."""
        self.random_sound_check.setChecked(False)
        self.alert_loop_check.setChecked(False)
        self.whisper_check.setChecked(False)
        self.ghost_cursor_check.setChecked(False)
        self.stop_all_signal.emit()
