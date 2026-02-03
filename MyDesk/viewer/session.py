import sys
import os
import json
from PyQt6.QtWidgets import (QMainWindow, QToolBar, QMessageBox, QWidget, 
                             QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
                             QLabel, QFrame, QToolButton)
from PyQt6.QtGui import QAction, QPixmap
from PyQt6.QtCore import Qt, pyqtSignal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from viewer.widgets import VideoCanvas, KeyLogWidget
from viewer.session_worker import AsyncSessionWorker
from viewer.webcam_window import WebcamWindow
from viewer.audio_player import AudioPlayer
from viewer.settings_dialog import SettingsDialog
from viewer.curtain_dialog import CurtainDialog
from viewer.connection_dialog import ConnectionDialog
from core import protocol

SETTINGS_FILE = "capture_settings.json"

class SessionWindow(QMainWindow):
    def __init__(self, target_url, target_id=None):
        super().__init__()
        self.setWindowTitle(f"MyDesk Session - {target_id or target_url}")
        self.resize(1280, 800)
        
        self.capture_settings = self.load_settings()
        self.curtain_active = False
        self.input_mode = "indirect"  # "direct" or "indirect"
        self.closing = False
        self.mouse_enabled = True
        
        # Mouse Throttling (send every 100ms max = 10 moves/sec)
        self._last_mouse_time = 0
        self._mouse_throttle_ms = 100  # Increased to prevent broker overload
        
        # Main Layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setCentralWidget(main_widget)
        
        # Video Canvas (with curtain overlay)
        self.canvas = VideoCanvas()
        self.canvas.input_signal.connect(self.handle_input)
        
        # Curtain Overlay
        self.curtain_overlay = QLabel(self.canvas)
        self.curtain_overlay.setStyleSheet("background-color: black;")
        self.curtain_overlay.hide()
        self.curtain_overlay.mousePressEvent = lambda e: self.disable_curtain()
        
        main_layout.addWidget(self.canvas, 1)
        
        # Bottom Input Panel
        self.setup_bottom_panel(main_layout)
        
        # KeyLog (separate window now)
        self.keylog_widget = KeyLogWidget()
        self.keylog_widget.setParent(None)  # Detach from main window
        self.keylog_widget.setWindowTitle("Key Log")
        self.keylog_widget.resize(350, 450)
        
        # Webcam Window
        self.webcam_win = WebcamWindow(self)
        self.webcam_win.closed.connect(self.stop_webcam)
        
        # Audio Player
        self.player = AudioPlayer()

        # Toolbar
        self.setup_toolbar()
        
        # Async Worker
        self.worker = AsyncSessionWorker(target_url, target_id)
        self.worker.frame_received.connect(self.canvas.update_frame)
        self.worker.cam_received.connect(self.webcam_win.update_frame)
        self.worker.audio_received.connect(self.player.play_chunk)
        self.worker.log_received.connect(self.keylog_widget.append_log)
        self.worker.connection_lost.connect(self.on_disconnect)
        self.worker.connection_progress.connect(self._on_progress)
        self.worker.connection_ready.connect(self._on_connected)
        
        # Connection Dialog (blocks until connected)
        self.conn_dialog = ConnectionDialog(target_id or target_url, self)
        self.conn_dialog.cancelled.connect(self.close)
        
        # Disable controls until connected
        self._set_controls_enabled(False)
        
        # Start connection
        self.worker.start_async()
        self.conn_dialog.show()
    
    def _on_progress(self, step, hint):
        """Update connection dialog progress"""
        if hasattr(self, 'conn_dialog') and self.conn_dialog.isVisible():
            self.conn_dialog.set_step(step, hint)
    
    def _on_connected(self):
        """Called when handshake complete"""
        if hasattr(self, 'conn_dialog'):
            self.conn_dialog.set_success()
        self._set_controls_enabled(True)
    
    def _set_controls_enabled(self, enabled):
        """Enable/disable all interactive controls"""
        for action in self.toolbar.actions():
            action.setEnabled(enabled)
        self.canvas.setEnabled(enabled)
        if hasattr(self, 'bottom_panel'):
            self.bottom_panel.setEnabled(enabled)

    def setup_toolbar(self):
        self.toolbar = QToolBar("Controls")
        self.toolbar.setStyleSheet("""
            QToolBar { background-color: #2D2D30; spacing: 5px; padding: 5px; }
            QToolButton { color: white; padding: 5px 10px; }
            QToolButton:checked { background-color: #007ACC; }
        """)
        self.addToolBar(self.toolbar)
        
        # Webcam
        self.act_cam = QAction("📷 Webcam", self, checkable=True)
        self.act_cam.triggered.connect(self.toggle_webcam)
        self.toolbar.addAction(self.act_cam)
        
        # Mic
        self.act_mic = QAction("🎙️ Audio", self, checkable=True)
        self.act_mic.triggered.connect(self.toggle_mic)
        self.toolbar.addAction(self.act_mic)
        
        self.toolbar.addSeparator()
        
        # Key Log (dedicated button)
        self.act_keylog = QAction("⌨️ Key Log", self, checkable=True)
        self.act_keylog.triggered.connect(self.toggle_keylog)
        self.toolbar.addAction(self.act_keylog)
        
        # Curtain
        act_curtain = QAction("🔒 Curtain", self)
        act_curtain.triggered.connect(self.show_curtain_dialog)
        self.toolbar.addAction(act_curtain)
        
        self.toolbar.addSeparator()
        
        # Settings
        act_settings = QAction("⚙️ Settings", self)
        act_settings.triggered.connect(self.show_settings_dialog)
        self.toolbar.addAction(act_settings)
        
        # Disconnect
        self.toolbar.addSeparator()
        btn_disconnect = QToolButton()
        btn_disconnect.setText("❌ Disconnect")
        btn_disconnect.setStyleSheet("color: #FF5555; font-weight: bold;")
        btn_disconnect.clicked.connect(self.disconnect_session)
        self.toolbar.addWidget(btn_disconnect)

    def setup_bottom_panel(self, parent_layout):
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame { background-color: #252526; border-top: 1px solid #3E3E42; }
            QLabel { color: #CCCCCC; }
            QPushButton { 
                background-color: #3E3E42; 
                color: white; 
                border-radius: 4px; 
                padding: 8px 15px;
            }
            QPushButton:hover { background-color: #505050; }
            QPushButton:checked { background-color: #007ACC; }
            QTextEdit { 
                background-color: #1E1E1E; 
                color: white; 
                border: 1px solid #3E3E42;
                border-radius: 4px;
            }
        """)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        
        # Controls Row
        controls_row = QHBoxLayout()
        
        # Input Mode Buttons
        mode_label = QLabel("Input:")
        controls_row.addWidget(mode_label)
        
        self.btn_direct = QPushButton("Direct")
        self.btn_direct.setCheckable(True)
        self.btn_direct.setChecked(True)
        self.btn_direct.clicked.connect(lambda: self.set_input_mode("direct"))
        controls_row.addWidget(self.btn_direct)
        
        self.btn_indirect = QPushButton("Buffered")
        self.btn_indirect.setCheckable(True)
        self.btn_indirect.clicked.connect(lambda: self.set_input_mode("indirect"))
        controls_row.addWidget(self.btn_indirect)
        
        controls_row.addSpacing(20)
        
        # Mouse Toggle
        self.btn_mouse = QPushButton("🖱️ Mouse: ON")
        self.btn_mouse.setCheckable(True)
        self.btn_mouse.setChecked(True)
        self.btn_mouse.clicked.connect(self.toggle_mouse)
        controls_row.addWidget(self.btn_mouse)
        
        controls_row.addStretch()
        panel_layout.addLayout(controls_row)
        
        panel_layout.addLayout(controls_row)
        
        # Input Buffer Row (Visible only in Indirect Mode)
        self.buffer_frame = QFrame()
        buffer_layout = QHBoxLayout(self.buffer_frame)
        buffer_layout.setContentsMargins(0, 0, 0, 0)
        
        self.input_buffer = QTextEdit()
        self.input_buffer.setPlaceholderText("Type keys to buffer (e.g. Hello World)...")
        self.input_buffer.setMaximumHeight(60)
        buffer_layout.addWidget(self.input_buffer, 1)
        
        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self.input_buffer.clear)
        buffer_layout.addWidget(btn_clear)
        
        btn_send = QPushButton("Send")
        btn_send.setStyleSheet("background-color: #007ACC;")
        btn_send.clicked.connect(self.send_buffer)
        buffer_layout.addWidget(btn_send)
        
        panel_layout.addWidget(self.buffer_frame)
        
        # Initialize visibility
        self.set_input_mode("direct")
        parent_layout.addWidget(panel)
    
    def set_input_mode(self, mode):
        self.input_mode = mode
        self.btn_direct.setChecked(mode == "direct")
        self.btn_indirect.setChecked(mode == "indirect")
        
        # Dynamic Visibility
        if hasattr(self, 'buffer_frame'):
            self.buffer_frame.setVisible(mode == "indirect")
    
    def toggle_mouse(self):
        self.mouse_enabled = self.btn_mouse.isChecked()
        self.btn_mouse.setText(f"🖱️ Mouse: {'ON' if self.mouse_enabled else 'OFF'}")
    
    def send_buffer(self):
        text = self.input_buffer.toPlainText()
        if text and self.worker.is_connected():
            self.send_command(protocol.OP_KEY_BUFFER, text.encode('utf-8'))
            self.input_buffer.clear()
    
    def handle_input(self, event):
        """Handle input from canvas"""
        if self.curtain_active:
            return
        if not self.worker.is_connected():
            return
        
        event_type = event[0]
        
        if event_type == 'move' and self.mouse_enabled:
            # Throttle mouse moves (max 20/sec)
            import time
            now = time.time() * 1000
            if now - self._last_mouse_time < self._mouse_throttle_ms:
                return
            self._last_mouse_time = now
            
            x, y = event[1], event[2]
            import struct
            payload = struct.pack('!ff', x, y)
            self.send_command(protocol.OP_MOUSE_MOVE, payload)
            
        elif event_type == 'click' and self.mouse_enabled:
            try:
                button_obj, pressed = event[1], event[2]
                # Map Qt MouseButton to int (1=left, 2=right, 4=middle)
                btn_map = {1: 1, 2: 2, 4: 4}  # Qt MouseButton.value values
                btn_value = button_obj.value if hasattr(button_obj, 'value') else 1
                button = btn_map.get(btn_value, 1)
                payload = bytes([button, 1 if pressed else 0])
                self.send_command(protocol.OP_MOUSE_CLICK, payload)
            except Exception as e:
                print(f"[-] Click error: {e}")
            
        elif event_type == 'key' and self.input_mode == "direct":
            key_code, pressed = event[1], event[2]
            payload = struct.pack('!I', key_code) + bytes([1 if pressed else 0])
            self.send_command(protocol.OP_KEY_PRESS, payload)

        elif event_type == 'scroll':
            dx, dy = event[1], event[2]
            import struct
            payload = struct.pack('!bb', dx, dy)
            self.send_command(protocol.OP_SCROLL, payload)
            
    def toggle_keylog(self, checked):
        if checked:
            self.keylog_widget.show()
            self.keylog_widget.raise_()
        else:
            self.keylog_widget.hide()

    def toggle_webcam(self, checked):
        if not self.worker.is_connected():
            self.act_cam.setChecked(False)
            QMessageBox.warning(self, "No Connection", "Not connected to agent.")
            return
        
        if checked:
            self.webcam_win.show()
            self.send_command(protocol.OP_CAM_START)
        else:
            self.webcam_win.hide()
            self.send_command(protocol.OP_CAM_STOP)
            
    def stop_webcam(self):
        self.act_cam.setChecked(False)
        if self.worker.is_connected():
            self.send_command(protocol.OP_CAM_STOP)

    def toggle_mic(self, checked):
        if not self.worker.is_connected():
            self.act_mic.setChecked(not checked)
            QMessageBox.warning(self, "No Connection", "Not connected to agent.")
            return
        
        if checked:
            if self.player.start():
                self.send_command(protocol.OP_MIC_START)
            else:
                self.act_mic.setChecked(False)
        else:
            self.player.stop()
            self.send_command(protocol.OP_MIC_STOP)

    def show_curtain_dialog(self):
        dialog = CurtainDialog(self)
        dialog.curtain_selected.connect(self.activate_curtain)
        dialog.exec()
    
    def activate_curtain(self, curtain_type, data):
        self.curtain_active = True
        self.curtain_overlay.setGeometry(self.canvas.rect())
        
        if curtain_type == "BLACK":
            self.curtain_overlay.setStyleSheet("background-color: black;")
            self.curtain_overlay.setPixmap(QPixmap())
            # Send command to Agent to black out their screen
            self.send_command(protocol.OP_CURTAIN_ON, b"BLACK")
        else:  # IMAGE
            pixmap = QPixmap(data)
            self.curtain_overlay.setPixmap(pixmap.scaled(
                self.canvas.size(), 
                Qt.AspectRatioMode.KeepAspectRatioByExpanding
            ))
            # Send command to Agent (just black for now, can't send image)
            self.send_command(protocol.OP_CURTAIN_ON, b"BLACK")
        
        self.curtain_overlay.show()
        self.curtain_overlay.raise_()
    
    def disable_curtain(self):
        self.curtain_active = False
        self.curtain_overlay.hide()
        # Send command to Agent to restore their screen
        self.send_command(protocol.OP_CURTAIN_OFF)
    
    def show_settings_dialog(self):
        dialog = SettingsDialog(self, self.capture_settings)
        dialog.settings_saved.connect(self.apply_settings)
        dialog.exec()
    
    def apply_settings(self, settings):
        self.capture_settings = settings
        self.save_settings()
        # Send to agent using msgpack (binary, smaller than JSON)
        if self.worker.is_connected():
            try:
                import msgpack
                payload = msgpack.packb(settings)
            except ImportError:
                # Fallback to JSON if msgpack not available
                payload = json.dumps(settings).encode()
            self.send_command(protocol.OP_SETTINGS, payload)
    
    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"method": "MSS", "quality": 50, "scale": 90, "format": "JPEG"}
    
    def save_settings(self):
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(self.capture_settings, f)

    def send_command(self, opcode, payload=b''):
        import asyncio
        from core.network import send_msg
        
        try:
            if self.worker.loop and self.worker.ws:
                asyncio.run_coroutine_threadsafe(
                    send_msg(self.worker.ws, bytes([opcode]) + payload), 
                    self.worker.loop
                )
        except Exception as e:
            print(f"[-] Send command error: {e}")

    def disconnect_session(self):
        """User manually clicked disconnect"""
        self.closing = True
        self.close()

    def on_disconnect(self):
        if self.closing:
            return

        # Close connection dialog if still visible
        if hasattr(self, 'conn_dialog') and self.conn_dialog.isVisible():
            self.conn_dialog.set_error("Connection lost")
            self.conn_dialog.close()
        else:
            # Only show message box if dialog wasn't visible
            QMessageBox.critical(self, "Disconnected", "Connection lost.")
        self.close()
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.curtain_active:
            self.curtain_overlay.setGeometry(self.canvas.rect())
    
    def closeEvent(self, event):
        self.closing = True
        self.worker.stop()
        self.player.stop()
        self.keylog_widget.close()
        super().closeEvent(event)
