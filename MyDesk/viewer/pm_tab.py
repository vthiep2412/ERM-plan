"""
Process Manager Tab Widget - View and manage remote processes
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QCheckBox, QMessageBox, QLineEdit, QLabel
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer


class NumericTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem subclass that sorts numerically."""
    
    def __init__(self, value, display_text=None):
        """
        Args:
            value: Numeric value for sorting
            display_text: Optional text to display (defaults to str(value))
        """
        super().__init__(display_text if display_text is not None else str(value))
        self._numeric_value = value
    
    def __lt__(self, other):
        """Compare numerically if both items have numeric values."""
        if isinstance(other, NumericTableWidgetItem):
            try:
                return float(self._numeric_value) < float(other._numeric_value)
            except (TypeError, ValueError):
                pass
        # Fallback to string comparison
        return super().__lt__(other)


class PMTab(QWidget):
    """Process Manager widget."""
    
    refresh_signal = pyqtSignal()  # Request process list
    kill_signal = pyqtSignal(int)  # Kill process by PID
    
    def __init__(self, parent=None):
        super().__init__(parent)
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
        self.table.setSortingEnabled(True) # Enable Sorting
        
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
        self.table.setSortingEnabled(False) # Disable sorting during update
        self.last_processes = processes
        self.filter_processes()
        self.table.setSortingEnabled(True) # Re-enable sorting

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
            pid = proc.get('pid', 0)
            name = proc.get('name', '')
            
            # Defensive None handling for cpu/mem
            cpu = proc.get('cpu')
            if cpu is None:
                cpu = 0.0
            
            mem = proc.get('mem')
            if mem is None:
                mem = 0.0
            
            # Use NumericTableWidgetItem for numeric columns
            self.table.setItem(row, 0, NumericTableWidgetItem(pid, str(pid)))
            self.table.setItem(row, 1, QTableWidgetItem(name))
            self.table.setItem(row, 2, NumericTableWidgetItem(cpu, f"{cpu:.1f}"))
            self.table.setItem(row, 3, NumericTableWidgetItem(mem, f"{mem:.1f}"))
    
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
        
        # Safe PID conversion with ValueError handling
        try:
            pid = int(pid_item.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid PID", "Could not parse process ID.")
            return
        
        name = name_item.text() if name_item else "Unknown"
        
        reply = QMessageBox.question(
            self, "Confirm Kill",
            f"Are you sure you want to kill process?\n\nPID: {pid}\nName: {name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.kill_signal.emit(pid)
