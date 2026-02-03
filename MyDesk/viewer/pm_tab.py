"""
Process Manager Tab Widget - View and manage remote processes
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QCheckBox, QMessageBox, QLineEdit, QLabel
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer


class PMTab(QWidget):
    """Process Manager widget."""
    
    refresh_signal = pyqtSignal()  # Request process list
    kill_signal = pyqtSignal(int)  # Kill process by PID
    
    def __init__(self):
        super().__init__()
        self.last_processes = []
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self.request_refresh)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Top bar
        top_bar = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.request_refresh)
        
        self.kill_btn = QPushButton("❌ Kill Process")
        self.kill_btn.clicked.connect(self.kill_selected)
        self.kill_btn.setStyleSheet("background-color: #c42b1c; color: white;")
        
        self.auto_refresh = QCheckBox("Auto-refresh (5s)")
        self.auto_refresh.stateChanged.connect(self.toggle_auto_refresh)

        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search PID or Name...")
        self.search_input.textChanged.connect(self.filter_processes)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 4px;
                background-color: #252526;
                color: #d4d4d4;
            }
        """)
        
        top_bar.addWidget(self.refresh_btn)
        top_bar.addWidget(self.kill_btn)
        top_bar.addSpacing(10)
        top_bar.addWidget(QLabel("Search:"))
        top_bar.addWidget(self.search_input)
        top_bar.addStretch()
        top_bar.addWidget(self.auto_refresh)
        
        layout.addLayout(top_bar)
        
        # Process table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["PID", "Name", "CPU %", "Memory (MB)"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        
        # Column sizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 100)
        
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #2d2d2d;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                gridline-color: #3c3c3c;
            }
            QTableWidget::item:selected {
                background-color: #094771;
            }
            QHeaderView::section {
                background-color: #1e1e1e;
                color: #d4d4d4;
                padding: 4px;
                border: 1px solid #3c3c3c;
            }
        """)
        
        layout.addWidget(self.table, 1)
    
    def request_refresh(self):
        """Request process list from agent."""
        self.refresh_signal.emit()
    
    def toggle_auto_refresh(self, state):
        if state == Qt.CheckState.Checked.value:
            self.auto_refresh_timer.start(5000)  # 5 seconds
        else:
            self.auto_refresh_timer.stop()
    
    def update_data(self, processes):
        """Update table with process list.
        
        Args:
            processes: List of dicts with {pid, name, cpu, mem}
        """
        self.last_processes = processes
        self.filter_processes()

    def filter_processes(self):
        """Filter and display processes based on search text."""
        search_text = self.search_input.text().lower()
        
        filtered = []
        for proc in self.last_processes:
            pid = str(proc.get('pid', ''))
            name = proc.get('name', '').lower()
            if search_text in pid or search_text in name:
                filtered.append(proc)
        
        self.table.setRowCount(len(filtered))
        
        for row, proc in enumerate(filtered):
            self.table.setItem(row, 0, QTableWidgetItem(str(proc.get('pid', ''))))
            self.table.setItem(row, 1, QTableWidgetItem(proc.get('name', '')))
            self.table.setItem(row, 2, QTableWidgetItem(f"{proc.get('cpu', 0):.1f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{proc.get('mem', 0):.1f}"))
    
    def kill_selected(self):
        """Kill selected process."""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a process to kill.")
            return
        
        row = selected[0].row()
        pid_item = self.table.item(row, 0)
        name_item = self.table.item(row, 1)
        
        if not pid_item:
            return
        
        pid = int(pid_item.text())
        name = name_item.text() if name_item else "Unknown"
        
        reply = QMessageBox.question(
            self, "Confirm Kill",
            f"Are you sure you want to kill process?\n\nPID: {pid}\nName: {name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.kill_signal.emit(pid)
