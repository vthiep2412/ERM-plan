import sys
import os
import json
import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QPushButton, QLineEdit, QLabel, QMessageBox, QComboBox, QFrame, 
                             QListWidget, QListWidgetItem, QAbstractItemView)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

DEFAULT_BROKER = "ws://localhost:8765"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer_config.json")

def normalize_color(color):
    """Convert color to #RRGGBB format for stylesheet manipulation."""
    qc = QColor(color)
    if qc.isValid():
        return qc.name()  # Returns #RRGGBB
    return "#007ACC"  # Fallback

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

class ClientManager(QMainWindow):
    MODE_BROKER = "broker"
    MODE_DIRECT = "direct"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MyDesk - Connection Manager")
        self.resize(500, 750)
        
        self.config = self.load_config()
        self.setup_ui()
        
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[!] Failed to load config, using defaults: {e}")
        return {"broker_url": DEFAULT_BROKER, "history": []}

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"[-] Failed to save config: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Config Error", f"Failed to save settings to {CONFIG_FILE}\n{e}")

    def setup_ui(self):
        # Dark Palette
        self.setStyleSheet("""
            QMainWindow { background-color: #1E1E1E; }
            QLabel { color: #CCCCCC; font-size: 14px; }
            QLineEdit, QComboBox, QListWidget { 
                background-color: #2D2D30; 
                color: white; 
                border: 1px solid #3E3E42; 
                padding: 8px; 
                border-radius: 4px;
            }
            QFrame { border: none; }
            QListWidget::item { padding: 10px; }
            QListWidget::item:selected { background-color: #007ACC; }
        """)

        cw = QWidget()
        self.setCentralWidget(cw)
        main_layout = QVBoxLayout(cw)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        # Header
        header = QLabel("MyDesk")
        header.setStyleSheet("font-size: 32px; font-weight: bold; color: #007ACC;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header)
        
        # Connection Box
        box = QFrame()
        box.setStyleSheet("background-color: #252526; border-radius: 10px;")
        box_layout = QVBoxLayout(box)
        box_layout.setSpacing(15)
        box_layout.setContentsMargins(20, 20, 20, 20)
        
        # Mode Selection
        box_layout.addWidget(QLabel("Connection Mode"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Broker (Render/Local)", self.MODE_BROKER)
        self.mode_combo.addItem("Direct WebSocket", self.MODE_DIRECT)
        self.mode_combo.currentIndexChanged.connect(lambda: self.on_mode_change(self.mode_combo.currentData()))
        box_layout.addWidget(self.mode_combo)
        
        # Alias (Name)
        box_layout.addWidget(QLabel("Computer Name (Alias)"))
        self.alias_input = QLineEdit()
        self.alias_input.setPlaceholderText("e.g. My Laptop")
        box_layout.addWidget(self.alias_input)

        # URL Input
        self.lbl_url = QLabel("Server URL")
        box_layout.addWidget(self.lbl_url)
        self.url_input = QLineEdit(self.config.get("broker_url", DEFAULT_BROKER))
        self.url_input.setPlaceholderText("wss://...")
        box_layout.addWidget(self.url_input)
        
        # ID Input
        self.lbl_id = QLabel("Target Agent ID")
        box_layout.addWidget(self.lbl_id)
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("Enter Agent ID...")
        box_layout.addWidget(self.id_input)
        
        # Connect Button
        self.btn_connect = ModernButton("Connect", "#28A745") # Green
        self.btn_connect.clicked.connect(self.start_connection)
        box_layout.addWidget(self.btn_connect)
        
        main_layout.addWidget(box)
        
        # History Section
        main_layout.addWidget(QLabel("Recent Connections"))
        self.history_list = QListWidget()
        self.history_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.history_list.itemDoubleClicked.connect(self.load_history_item)
        main_layout.addWidget(self.history_list)
        
        self.refresh_history()
        self.on_mode_change(self.mode_combo.currentData()) # Init state
        
        # Footer
        footer = QLabel("v3.2.0 | Secure Remote Access")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #666666; font-size: 12px;")
        main_layout.addWidget(footer)

    def on_mode_change(self, mode_key):
        is_broker = (mode_key == self.MODE_BROKER)
        # Broker: Hide URL, Show ID
        # Direct: Show URL, Hide ID
        
        self.lbl_url.setVisible(not is_broker)
        self.url_input.setVisible(not is_broker)
        
        self.lbl_id.setVisible(is_broker)
        self.id_input.setVisible(is_broker)

    def refresh_history(self):
        self.history_list.clear()
        for item in reversed(self.config.get("history", [])):
            if isinstance(item, dict):
                # Safe access with defaults
                alias = item.get('alias', 'Unknown')
                mode_key = item.get('mode', self.MODE_BROKER)
                item_id = str(item.get('id') or '')
                target_url = item.get('url', '')
                
                # Check for legacy "Broker" strings or new "broker" key
                is_broker = (mode_key == self.MODE_BROKER) or (isinstance(mode_key, str) and "Broker" in mode_key)

                if is_broker:
                    label = f"[{alias}] ID: {item_id}"
                else:
                    label = f"[{alias}] Direct: {target_url}"
                
                list_item = QListWidgetItem(label)
                list_item.setData(Qt.ItemDataRole.UserRole, item)
                self.history_list.addItem(list_item)

    def load_history_item(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data and isinstance(data, dict):
            mode_key = data.get('mode', self.MODE_BROKER)
            
            # Legacy conversion
            if isinstance(mode_key, str) and "Broker" in mode_key and mode_key != self.MODE_BROKER:
                mode_key = self.MODE_BROKER
            elif isinstance(mode_key, str) and "Direct" in mode_key and mode_key != self.MODE_DIRECT:
                mode_key = self.MODE_DIRECT

            # Find data
            index = self.mode_combo.findData(mode_key)            
            if index >= 0:
                self.mode_combo.setCurrentIndex(index)
            else:
                self.mode_combo.setCurrentIndex(0) # Default
            
            self.alias_input.setText(data.get('alias', ''))
            self.id_input.setText(str(data.get('id') or ''))
            self.url_input.setText(data.get('url', self.config.get("broker_url", DEFAULT_BROKER)))

    def start_connection(self):
        url = self.url_input.text().strip()
        agent_id = self.id_input.text().strip()
        alias = self.alias_input.text().strip() or "Unnamed"
        mode_key = self.mode_combo.currentData()
        
        is_broker = (mode_key == self.MODE_BROKER)

        # Default URL for Broker if hidden
        if is_broker and not url:
            url = self.config.get("broker_url", DEFAULT_BROKER)
        
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a Server URL.")
            return

        # Validate URL scheme
        if not (url.startswith("ws://") or url.startswith("wss://")):
            QMessageBox.warning(self, "Error", "URL must start with ws:// or wss://")
            return

        # Broker Validation
        if is_broker and not agent_id:
            QMessageBox.warning(self, "Error", "Please enter an Agent ID for Broker Mode.")
            return

        # Determine connection type
        from viewer.session import SessionWindow # Lazy Load
        
        if not is_broker:
            # Direct Mode
            print(f"[*] Starting Direct Connection to {url}")
            # Ensure ID is empty in history for direct mode
            self.update_history(mode_key, alias, url, "") 
            self.session = SessionWindow(url, target_id=None)
        else:
            # Broker Mode
            print(f"[*] Starting Broker Connection to {url} (Target: {agent_id})")
            self.update_history(mode_key, alias, url, agent_id)
            self.session = SessionWindow(url, target_id=agent_id)
            
        self.session.show()
        # self.hide()

    def update_history(self, mode, alias, url, target_id):
        history = self.config.get("history", [])
        
        # Deduplicate history: Remove entry with same URL + ID to move it to top.
        # This way reconnecting to the same target updates its position and timestamp.
        history = [h for h in history if not (h.get('url') == url and (h.get('id') or "") == (target_id or ""))]
        
        new_entry = {
            "mode": mode,
            "alias": alias,
            "url": url,
            "id": target_id,
            "last_seen": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        
        history.append(new_entry)
        
        # Limit to 10
        if len(history) > 10:
            history.pop(0)
            
        self.config["history"] = history
        self.refresh_history()
        self.save_config()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ClientManager()
    window.show()
    sys.exit(app.exec())
# This line was added at the bottom to force re-check. 
