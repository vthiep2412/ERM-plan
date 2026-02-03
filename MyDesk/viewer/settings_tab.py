"""
Settings Tab Widget - Control device settings (WiFi, volume, time, power)
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QSlider,
    QPushButton, QLabel, QCheckBox, QDateTimeEdit,
    QMessageBox
)
from PyQt6.QtCore import pyqtSignal, Qt, QDateTime


class SettingsTab(QWidget):
    """Device settings control widget."""
    
    # Network signals
    set_wifi_signal = pyqtSignal(bool)
    set_ethernet_signal = pyqtSignal(bool)
    
    # Audio signals
    set_volume_signal = pyqtSignal(int)
    set_mute_signal = pyqtSignal(bool)
    
    # Display signals
    set_brightness_signal = pyqtSignal(int)
    
    # Time signals
    set_time_signal = pyqtSignal(str)  # ISO8601
    sync_time_signal = pyqtSignal()
    
    # Power signals
    power_action_signal = pyqtSignal(str)  # sleep|restart|shutdown|lock|logoff
    
    # System info
    get_sysinfo_signal = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.wifi_available = True
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # Network Section - Removed by request
        # network_group = QGroupBox("🌐 Network")
        # network_layout = QHBoxLayout(network_group)
        # 
        # self.wifi_check = QCheckBox("WiFi")
        # self.wifi_check.stateChanged.connect(lambda s: self.set_wifi_signal.emit(s == Qt.CheckState.Checked.value))
        # 
        # self.ethernet_check = QCheckBox("Ethernet")
        # self.ethernet_check.stateChanged.connect(lambda s: self.set_ethernet_signal.emit(s == Qt.CheckState.Checked.value))
        # 
        # network_layout.addWidget(self.wifi_check)
        # network_layout.addWidget(self.ethernet_check)
        # network_layout.addStretch()
        # 
        # layout.addWidget(network_group)
        
        # Audio Section
        audio_group = QGroupBox("🔊 Audio")
        audio_layout = QVBoxLayout(audio_group)
        
        volume_row = QHBoxLayout()
        volume_label = QLabel("Volume:")
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.valueChanged.connect(self.on_volume_change)
        self.volume_value = QLabel("50%")
        self.volume_value.setFixedWidth(40)
        
        self.mute_check = QCheckBox("Mute")
        self.mute_check.stateChanged.connect(lambda s: self.set_mute_signal.emit(s == Qt.CheckState.Checked.value))
        
        volume_row.addWidget(volume_label)
        volume_row.addWidget(self.volume_slider, 1)
        volume_row.addWidget(self.volume_value)
        volume_row.addWidget(self.mute_check)
        
        audio_layout.addLayout(volume_row)
        layout.addWidget(audio_group)
        
        # Display Section
        display_group = QGroupBox("🖥️ Display")
        display_layout = QHBoxLayout(display_group)
        
        brightness_label = QLabel("Brightness:")
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(0, 100)
        self.brightness_slider.setValue(100)
        self.brightness_slider.valueChanged.connect(self.on_brightness_change)
        self.brightness_value = QLabel("100%")
        self.brightness_value.setFixedWidth(40)
        
        display_layout.addWidget(brightness_label)
        display_layout.addWidget(self.brightness_slider, 1)
        display_layout.addWidget(self.brightness_value)
        
        layout.addWidget(display_group)
        
        # Date & Time Section
        time_group = QGroupBox("🕐 Date & Time")
        time_layout = QVBoxLayout(time_group)
        
        time_row1 = QHBoxLayout()
        self.datetime_edit = QDateTimeEdit(QDateTime.currentDateTime())
        self.datetime_edit.setCalendarPopup(True)
        self.datetime_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        
        self.set_time_btn = QPushButton("Set Time")
        self.set_time_btn.clicked.connect(self.on_set_time)
        
        self.sync_time_btn = QPushButton("🔄 Sync to Correct Time")
        self.sync_time_btn.clicked.connect(self.sync_time_signal.emit)
        self.sync_time_btn.setStyleSheet("background-color: #0e639c; color: white;")
        
        time_row1.addWidget(self.datetime_edit)
        time_row1.addWidget(self.set_time_btn)
        time_row1.addWidget(self.sync_time_btn)
        
        time_layout.addLayout(time_row1)
        layout.addWidget(time_group)
        
        # Power Section
        power_group = QGroupBox("⚡ Power")
        power_layout = QHBoxLayout(power_group)
        
        self.sleep_btn = QPushButton("💤 Sleep")
        self.sleep_btn.clicked.connect(lambda: self.confirm_power_action("sleep"))
        
        self.restart_btn = QPushButton("🔄 Restart")
        self.restart_btn.clicked.connect(lambda: self.confirm_power_action("restart"))
        self.restart_btn.setStyleSheet("background-color: #d7a426; color: white;")
        
        self.shutdown_btn = QPushButton("⏻ Shutdown")
        self.shutdown_btn.clicked.connect(lambda: self.confirm_power_action("shutdown"))
        self.shutdown_btn.setStyleSheet("background-color: #c42b1c; color: white;")
        
        self.lock_btn = QPushButton("🔒 Lock")
        self.lock_btn.clicked.connect(lambda: self.power_action_signal.emit("lock"))
        
        self.logoff_btn = QPushButton("🚪 Log Off")
        self.logoff_btn.clicked.connect(lambda: self.confirm_power_action("logoff"))
        
        power_layout.addWidget(self.sleep_btn)
        power_layout.addWidget(self.lock_btn)
        power_layout.addWidget(self.logoff_btn)
        power_layout.addStretch()
        power_layout.addWidget(self.restart_btn)
        power_layout.addWidget(self.shutdown_btn)
        
        layout.addWidget(power_group)
        
        # System Info Section
        sysinfo_group = QGroupBox("📊 System Info")
        sysinfo_layout = QVBoxLayout(sysinfo_group)
        
        self.sysinfo_label = QLabel("Click Refresh to load system info...")
        self.sysinfo_label.setWordWrap(True)
        self.sysinfo_label.setStyleSheet("color: #888;")
        
        self.refresh_sysinfo_btn = QPushButton("🔄 Refresh")
        self.refresh_sysinfo_btn.clicked.connect(self.get_sysinfo_signal.emit)
        
        sysinfo_layout.addWidget(self.sysinfo_label)
        sysinfo_layout.addWidget(self.refresh_sysinfo_btn)
        
        layout.addWidget(sysinfo_group)
        
        # Spacer
        layout.addStretch()
    
    def on_volume_change(self, value):
        self.volume_value.setText(f"{value}%")
        self.set_volume_signal.emit(value)
    
    def on_brightness_change(self, value):
        self.brightness_value.setText(f"{value}%")
        self.set_brightness_signal.emit(value)
    
    def on_set_time(self):
        dt = self.datetime_edit.dateTime()
        iso_str = dt.toString(Qt.DateFormat.ISODate)
        self.set_time_signal.emit(iso_str)
    
    def confirm_power_action(self, action):
        action_names = {
            "sleep": "put the computer to sleep",
            "restart": "restart the computer",
            "shutdown": "shut down the computer",
            "logoff": "log off the current user"
        }
        
        reply = QMessageBox.question(
            self, "Confirm Action",
            f"Are you sure you want to {action_names.get(action, action)}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.power_action_signal.emit(action)
    
    def update_sysinfo(self, info):
        """Update system info display.
        
        Args:
            info: dict with {os, cpu, ram, disk, battery, wifi_available}
        """
        lines = []
        if 'os' in info:
            lines.append(f"<b>OS:</b> {info['os']}")
        if 'cpu' in info:
            lines.append(f"<b>CPU:</b> {info['cpu']}")
        if 'ram' in info:
            lines.append(f"<b>RAM:</b> {info['ram']}")
        if 'disk' in info:
            lines.append(f"<b>Disk:</b> {info['disk']}")
        if 'battery' in info:
            lines.append(f"<b>Battery:</b> {info['battery']}")
        if 'uptime' in info:
            lines.append(f"<b>Uptime:</b> {info['uptime']}")
        
        self.sysinfo_label.setText("<br>".join(lines))
        
        
        # Update WiFi availability (Removed UI)
        # if 'wifi_available' in info:
        #     self.wifi_available = info['wifi_available']
        #     # self.wifi_check.setEnabled(self.wifi_available)
