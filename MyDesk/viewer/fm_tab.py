"""
File Manager Tab Widget - Browse, download, upload, delete files
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QLineEdit, QFileDialog, QMessageBox, QMenu, QComboBox, QInputDialog
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QAction
import os
import ntpath  # For remote Windows path operations

# Maximum file size for upload (100MB default)
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


class FMTab(QWidget):
    """File Manager widget."""
    
    list_signal = pyqtSignal(str)  # Request directory listing
    download_signal = pyqtSignal(str)  # Download file
    upload_signal = pyqtSignal(str, bytes)  # Upload file (remote_path, data)
    delete_signal = pyqtSignal(str)  # Delete file/folder
    mkdir_signal = pyqtSignal(str)  # Create directory
    
    def __init__(self):
        super().__init__()
        self.current_path = "C:\\"
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Path bar
        path_bar = QHBoxLayout()
        
        self.up_btn = QPushButton("⬆️")
        self.up_btn.setFixedWidth(40)
        self.up_btn.clicked.connect(self.go_up)
        
        self.path_input = QLineEdit(self.current_path)
        self.path_input.returnPressed.connect(self.navigate_to_path)
        self.path_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        
        self.go_btn = QPushButton("Go")
        self.go_btn.clicked.connect(self.navigate_to_path)
        
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedWidth(40)
        self.refresh_btn.clicked.connect(self.refresh)
        
        # Drive Selector
        self.drives_combo = QComboBox()
        self.drives_combo.setFixedWidth(60)
        self.drives_combo.currentIndexChanged.connect(self.on_drive_change)
        
        path_bar.addWidget(self.drives_combo)
        path_bar.addWidget(self.up_btn)
        path_bar.addWidget(self.path_input, 1)
        path_bar.addWidget(self.go_btn)
        path_bar.addWidget(self.refresh_btn)
        
        layout.addLayout(path_bar)
        
        # Action buttons
        action_bar = QHBoxLayout()
        
        self.upload_btn = QPushButton("📤 Upload")
        self.upload_btn.clicked.connect(self.upload_file)
        
        self.new_folder_btn = QPushButton("📁 New Folder")
        self.new_folder_btn.clicked.connect(self.create_folder)
        
        action_bar.addWidget(self.upload_btn)
        action_bar.addWidget(self.new_folder_btn)
        action_bar.addStretch()
        
        layout.addLayout(action_bar)
        
        # File table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Size", "Modified"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self.on_double_click)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        # Column sizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 150)
        
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
            QComboBox {
                background-color: #2d2d2d;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                padding: 4px;
            }
        """)
        
        layout.addWidget(self.table, 1)

    def on_drive_change(self, index):
        drive = self.drives_combo.currentText()
        if drive and drive != self.current_path:
            # Just navigate to the drive root
            self.current_path = drive
            self.path_input.setText(drive)
            self.list_signal.emit(drive)
    
    def navigate_to_path(self):
        path = self.path_input.text().strip()
        if path:
            self.current_path = path
            self.list_signal.emit(path)
    
    def go_up(self):
        # Use ntpath for Windows remote paths
        remote_path = ntpath
        
        # Handle Windows root
        if len(self.current_path) <= 3 and ":" in self.current_path:
            # At drive root (e.g. C:\), go to drive list
            self.current_path = ""
            self.path_input.setText("")
            self.list_signal.emit("")
            return

        # Strip trailing separator consistently
        stripped = self.current_path.rstrip("\\/")
        parent = remote_path.dirname(stripped)
        
        if parent:
            self.current_path = parent
            self.path_input.setText(parent)
            self.list_signal.emit(parent)
        elif self.current_path and self.current_path != ".":
             # Last resort, go to drive list
             self.current_path = ""
             self.path_input.setText("")
             self.list_signal.emit("")
    
    def refresh(self):
        self.list_signal.emit(self.current_path)
    
    def on_double_click(self, index):
        row = index.row()
        type_item = self.table.item(row, 1)
        name_item = self.table.item(row, 0)
        
        if type_item and name_item:
            if type_item.text() == "📁 Folder":
                # Navigate into folder - use ntpath for Windows remotes
                # Handle drive entries at root (empty current_path)
                if not self.current_path or self.current_path == "":
                    # At root, name is the full drive path like "C:\"
                    new_path = name_item.text()
                else:
                    new_path = ntpath.join(self.current_path, name_item.text())
                self.current_path = new_path
                self.path_input.setText(new_path)
                self.list_signal.emit(new_path)
    
    def show_context_menu(self, pos):
        menu = QMenu(self)
        
        download_action = QAction("📥 Download", self)
        download_action.triggered.connect(self.download_selected)
        
        delete_action = QAction("🗑️ Delete", self)
        delete_action.triggered.connect(self.delete_selected)
        
        menu.addAction(download_action)
        menu.addAction(delete_action)
        
        menu.exec(self.table.mapToGlobal(pos))
    
    def download_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        
        row = selected[0].row()
        name_item = self.table.item(row, 0)
        type_item = self.table.item(row, 1)
        if name_item:
            # Use ntpath for Windows remote paths
            file_path = ntpath.join(self.current_path, name_item.text())
            # Check if it's a folder
            is_dir = type_item and type_item.text() == "📁 Folder"
            if is_dir:
                QMessageBox.information(
                    self, "Download", 
                    "Folder download not yet supported.\nPlease download individual files."
                )
                return
            self.download_signal.emit(file_path)
    
    def delete_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        
        row = selected[0].row()
        name_item = self.table.item(row, 0)
        if name_item:
            # Use ntpath for Windows remote paths
            file_path = ntpath.join(self.current_path, name_item.text())
            
            reply = QMessageBox.question(
                self, "Confirm Delete",
                f"Are you sure you want to delete?\n\n{file_path}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.delete_signal.emit(file_path)
    
    def upload_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Upload")
        if file_path:
            try:
                # Check file size before loading into memory
                file_size = os.path.getsize(file_path)
                if file_size > MAX_UPLOAD_BYTES:
                    size_mb = file_size / (1024 * 1024)
                    limit_mb = MAX_UPLOAD_BYTES / (1024 * 1024)
                    QMessageBox.warning(
                        self, "Upload Limit Exceeded",
                        f"File is {size_mb:.1f} MB which exceeds the {limit_mb:.0f} MB hard limit.\n"
                        "Preventing upload to avoid memory exhaustion.",
                        QMessageBox.StandardButton.Ok
                    )
                    return
                
                with open(file_path, 'rb') as f:
                    data = f.read()
                # Use ntpath for Windows remote path construction
                remote_path = ntpath.join(self.current_path, os.path.basename(file_path))
                self.upload_signal.emit(remote_path, data)
            except Exception as e:
                QMessageBox.critical(self, "Upload Error", f"Failed to read file: {e}")
    
    def create_folder(self):
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            # Use ntpath for Windows remote path construction
            folder_path = ntpath.join(self.current_path, name)
            self.mkdir_signal.emit(folder_path)
    
    def update_data(self, files, path=None):
        """Update table with file list.
        
        Args:
            files: List of dicts with {name, is_dir, size, modified}
            path: Optional path that was listed
        """
        if path:
            self.current_path = path
            self.path_input.setText(path)
        
        # Populate drives if we are at root listing (path is empty)
        if not path:
            self.drives_combo.blockSignals(True)
            self.drives_combo.clear()
            for file in files:
                name = file.get('name', '')
                if ":" in name and len(name) <= 3:  # Simple drive check
                    self.drives_combo.addItem(name)
            self.drives_combo.blockSignals(False)

        self.table.setRowCount(len(files))
        
        for row, file in enumerate(files):
            name = file.get('name', '')
            is_dir = file.get('is_dir', False)
            size = file.get('size', 0)
            modified = file.get('modified', '')
            
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem("📁 Folder" if is_dir else "📄 File"))
            self.table.setItem(row, 2, QTableWidgetItem(self.format_size(size) if not is_dir else ""))
            self.table.setItem(row, 3, QTableWidgetItem(modified))
    
    def format_size(self, size):
        """Format bytes to human readable."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
# This line was added at the bottom to force re-check. 
