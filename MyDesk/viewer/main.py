import sys
import os
import json
import datetime
import requests
import keyring
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QPushButton, QLineEdit, QLabel, QMessageBox, 
                             QFrame, QHBoxLayout, QGridLayout, QScrollArea)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

DEFAULT_BROKER = "ws://localhost:8765"
DEFAULT_REGISTRY_URL = "http://127.0.0.1:5000"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer_config.json")

def normalize_color(color):
    """Convert color to #RRGGBB format for stylesheet manipulation."""
    qc = QColor(color)
    if qc.isValid():
        return qc.name()  # Returns #RRGGBB
    return "#007ACC"  # Fallback

def parse_time(iso_str):
    """Parse ISO timestamp to local readable format."""
    try:
        if not iso_str: return "Never"
        dt = datetime.datetime.fromisoformat(iso_str)
        local = dt.astimezone()
        return local.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(iso_str)

class ModernButton(QPushButton):
    def __init__(self, text, color="#007ACC"):
        super().__init__(text)
        # Normalize color to ensure #RRGGBB format
        base_color = normalize_color(color)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {base_color};
                color: white;
                border-radius: 5px;
                padding: 10px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {base_color}DD;
            }}
            QPushButton:pressed {{
                background-color: {base_color}AA;
            }}
        """)

class AgentCard(QFrame):
    clicked = pyqtSignal(dict) # Emits agent data

    def __init__(self, agent):
        super().__init__()
        self.agent = agent
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("AgentCard")
        
        is_active = agent.get('active', False)
        status_color = "#22c55e" if is_active else "#666666"
        border_color = "#22c55e" if is_active else "#333333"
        bg_color = "#1A1A1A"
        
        self.setStyleSheet(f"""
            QFrame#AgentCard {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            QFrame#AgentCard:hover {{
                background-color: #252525;
                border: 1px solid {status_color};
            }}
            QLabel {{ border: none; background: transparent; }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        
        # Header: Icon + Status
        header = QHBoxLayout()
        icon = QLabel("🖥️")
        icon.setStyleSheet("font-size: 24px;")
        header.addWidget(icon)
        header.addStretch()
        
        status_badge = QLabel("ONLINE" if is_active else "OFFLINE")
        status_badge.setStyleSheet(f"""
            color: white;
            background-color: {status_color};
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: bold;
        """)
        header.addWidget(status_badge)
        layout.addLayout(header)
        
        # Username
        lbl_user = QLabel(agent.get('username', 'Unknown'))
        lbl_user.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        layout.addWidget(lbl_user)
        
        # ID / IP
        lbl_id = QLabel(f"ID: {agent.get('id', '???')}")
        lbl_id.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(lbl_id)
        
        if is_active:
             lbl_last = QLabel("Ready to connect")
             lbl_last.setStyleSheet("color: #22c55e; font-size: 11px;")
        else:
             raw_time = agent.get('last_updated')
             friendly_time = parse_time(raw_time)
             lbl_last = QLabel(f"Last seen: {friendly_time}")
             lbl_last.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(lbl_last)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.agent)

class RegistryWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, url, pwd):
        super().__init__()
        self.url = url
        self.pwd = pwd

    def run(self):
        try:
            # Construct endpoint
            if self.url.endswith("/api"):
                 target_endpoint = f"{self.url}/discover"
            else:
                 target_endpoint = f"{self.url}/api/discover"

            resp = requests.post(target_endpoint, json={"password": self.pwd}, timeout=5)
            
            if resp.status_code == 200:
                self.finished.emit(resp.json())
            elif resp.status_code == 403:
                self.error.emit("Access Denied: Invalid Password")
            else:
                self.error.emit(f"Error: {resp.status_code}")
        except Exception as e:
            self.error.emit(str(e))

class ClientManager(QMainWindow):
    MODE_BROKER = "broker"
    MODE_DIRECT = "direct"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MyDesk - Connection Manager")
        self.resize(900, 700) # Wider for grid
        
        self.config = self.load_config()
        self.setup_ui()
        
        # Load registry password from Keyring
        try:
            saved_pwd = keyring.get_password("MyDesk", "registry")
            if saved_pwd:
                self.pwd_input.setText(saved_pwd)
                # Auto-fetch if pwd is there
                QTimer.singleShot(500, self.refresh_registry_list)
        except Exception as e:
            print(f"[-] Keyring Load Error: {e}")
            
        self.session = None
        self.worker = None
        
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[!] Failed to load config, using defaults: {e}")
        return {"broker_url": DEFAULT_BROKER}

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"[-] Failed to save config: {e}")
            import traceback
            traceback.print_exc()

    def setup_ui(self):
        # Dark Palette
        self.setStyleSheet("""
            QMainWindow { background-color: #000000; }
            QLabel { color: #CCCCCC; font-size: 14px; }
            QLineEdit, QComboBox, QListWidget { 
                background-color: #111111; 
                color: white; 
                border: 1px solid #333333; 
                padding: 8px; 
                border-radius: 6px;
            }
            QLineEdit:focus { border: 1px solid #0070f3; }
            QScrollArea { border: none; background: transparent; }
            QScrollBar:horizontal, QScrollBar:vertical { border: none; background: #000; margin: 0; }
            QScrollBar::handle:horizontal, QScrollBar::handle:vertical { background: #333; min-width: 20px; border-radius: 5px; }
            QScrollBar::add-line, QScrollBar::sub-line { border: none; background: none; }
        """)

        cw = QWidget()
        self.setCentralWidget(cw)
        main_layout = QVBoxLayout(cw)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        # Header
        header_layout = QHBoxLayout()
        logo = QLabel("MyDesk Viewer")
        logo.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        header_layout.addWidget(logo)
        header_layout.addStretch()
        
        # Registry Password Input
        self.pwd_input = QLineEdit()
        self.pwd_input.setPlaceholderText("Registry Master Password")
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setFixedWidth(200)
        self.pwd_input.editingFinished.connect(self.save_registry_pwd)
        header_layout.addWidget(self.pwd_input)
        
        main_layout.addLayout(header_layout)
        
        # Controls Bar
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Discovered Agents"))
        controls.addStretch()
        
        btn_refresh = ModernButton("Refresh List", "#111111")
        btn_refresh.setStyleSheet("""
            QPushButton { background-color: #111111; border: 1px solid #333; color: white; padding: 6px 15px; border-radius: 6px; }
            QPushButton:hover { background-color: #222; }
        """)
        btn_refresh.clicked.connect(self.refresh_registry_list)
        controls.addWidget(btn_refresh)
        
        main_layout.addLayout(controls)
        
        # Agent Grid Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        
        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll.setWidget(self.grid_container)
        main_layout.addWidget(self.scroll)
        
        # Footer / Manual Connect
        footer = QFrame()
        footer.setStyleSheet("background-color: #111; border-radius: 8px; border: 1px solid #222;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(15, 10, 15, 10)
        
        footer_layout.addWidget(QLabel("Direct Connect:"))
        
        self.manual_url_input = QLineEdit()
        self.manual_url_input.setPlaceholderText("wss://...")
        footer_layout.addWidget(self.manual_url_input)
        
        btn_manual = ModernButton("Connect", "#0070f3")
        btn_manual.clicked.connect(self.manual_connect)
        footer_layout.addWidget(btn_manual)
        
        main_layout.addWidget(footer)
        
        # Status Bar
        self.status_bar = QLabel("Ready")
        self.status_bar.setStyleSheet("color: #666; font-size: 12px;")
        self.status_bar.setWordWrap(True) # Fix: Prevent long errors from expanding window width
        main_layout.addWidget(self.status_bar)

    def save_registry_pwd(self):
        text = self.pwd_input.text()
        try:
            keyring.set_password("MyDesk", "registry", text)
            # Remove from config if it exists there to clean up
            if "registry_password" in self.config:
                del self.config["registry_password"]
                self.save_config()
        except Exception as e:
            print(f"[-] Keyring Save Error: {e}")

    def refresh_registry_list(self):
        pwd = self.pwd_input.text()
        registry_url = self.config.get("registry_url", DEFAULT_REGISTRY_URL)
        
        self.status_bar.setText("Fetching registry...")
        
        # Disable button? (Optional, but good UX)
        
        self.worker = RegistryWorker(registry_url, pwd)
        self.worker.finished.connect(self.on_refresh_success)
        self.worker.error.connect(self.on_refresh_error)
        self.worker.start()

    def on_refresh_success(self, agents):
        # Clear Grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
                
        self.populate_grid(agents)
        self.status_bar.setText(f"Found {len(agents)} agents")

    def on_refresh_error(self, err_msg):
        self.status_bar.setText(err_msg)
        if "Access Denied" in err_msg:
             QMessageBox.warning(self, "Auth Error", err_msg)
        else:
             print(f"[-] Registry Error: {err_msg}")

    def populate_grid(self, agents):
        # Sort by active status
        agents.sort(key=lambda x: x.get('active', False), reverse=True)
        
        columns = 3
        for i, agent in enumerate(agents):
            row = i // columns
            col = i % columns
            
            card = AgentCard(agent)
            card.clicked.connect(self.connect_to_agent)
            self.grid_layout.addWidget(card, row, col)

    def connect_to_agent(self, agent):
        url = agent.get('url')
        if not url:
            QMessageBox.warning(self, "Error", "Agent has no URL")
            return
        self.launch_session(url)

    def manual_connect(self):
        url = self.manual_url_input.text().strip()
        if not url: return
        self.launch_session(url)

    def launch_session(self, url):
        # Auto-convert https -> wss, http -> ws
        if url.startswith("https://"):
            url = url.replace("https://", "wss://", 1)
        elif url.startswith("http://"):
            url = url.replace("http://", "ws://", 1)
            
        # Strip trailing slash if present (e.g. wss://.../)
        url = url.rstrip("/")

        # Validate URL scheme (wss or ws)
        if not (url.startswith("ws://") or url.startswith("wss://")):
            QMessageBox.warning(self, "Error", "Invalid URL protocol. Use wss:// or https://")
            return

        # Show status
        self.status_bar.setText(f"Connecting to {url}...")
        QApplication.processEvents() # Update UI before blocking import/connect

        from viewer.session import SessionWindow # Lazy Load
        print(f"[*] Connecting to {url}")
        
        # Cleanup old session if exists
        if self.session:
            try:
                self.session.close()
            except: pass
            
        self.session = SessionWindow(url, target_id=None)
        self.session.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ClientManager()
    window.show()
    sys.exit(app.exec())

