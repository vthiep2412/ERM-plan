"""
Privacy Curtain Dialog for MyDesk Viewer
Allows user to obscure the remote screen with black or custom image.
"""
import os
import shutil
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QListWidget, QListWidgetItem,
                             QFileDialog)
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt, pyqtSignal, QSize

# Store images in user's app data
CURTAIN_DIR = os.path.join(os.path.expanduser("~"), ".mydesk", "curtains")

class CurtainDialog(QDialog):
    curtain_selected = pyqtSignal(str, object) # type ("BLACK", "IMAGE", "FAKE_UPDATE", "PRIVACY"), data (None or path)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Privacy Curtain")
        self.setMinimumSize(400, 350)
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; }
            QLabel { color: #CCCCCC; font-size: 13px; }
            QPushButton {
                background-color: #3E3E42;
                color: white;
                border-radius: 5px;
                padding: 10px 15px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #505050; }
            QPushButton#blackBtn { background-color: #2D2D30; border: 2px solid #666; }
            QPushButton#blackBtn:hover { border-color: #007ACC; }
            QPushButton#fakeBtn { 
                background-color: #006dae; 
                font-weight: bold; 
            }
            QPushButton#fakeBtn:hover { background-color: #0088dd; }
            QListWidget { 
                background-color: #2D2D30; 
                border: 1px solid #3E3E42;
                border-radius: 5px;
            }
            QListWidget::item { padding: 5px; }
            QListWidget::item:selected { background-color: #007ACC; }
        """)
        
        os.makedirs(CURTAIN_DIR, exist_ok=True)
        self.setup_ui()
        self.load_saved_images()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Black Screen Option
        black_btn = QPushButton("⬛ Black Screen")
        black_btn.setObjectName("blackBtn")
        black_btn.setMinimumHeight(40)
        black_btn.clicked.connect(lambda: self.select_curtain("BLACK", None))
        layout.addWidget(black_btn)

        # Privacy Mode Option (Text)
        priv_btn = QPushButton("🔒 Privacy Mode (Text)")
        priv_btn.setObjectName("blackBtn") # Reuse style
        priv_btn.setMinimumHeight(40)
        priv_btn.clicked.connect(lambda: self.select_curtain("PRIVACY", None))
        layout.addWidget(priv_btn)

        # Fake Update Option
        fake_btn = QPushButton("🔄 Fake Update Screen")
        fake_btn.setObjectName("fakeBtn")
        fake_btn.setMinimumHeight(40)
        fake_btn.clicked.connect(lambda: self.select_curtain("FAKE_UPDATE", None))
        layout.addWidget(fake_btn)
        
        # Divider
        divider = QLabel("─── OR select a custom image ───")
        divider.setAlignment(Qt.AlignmentFlag.AlignCenter)
        divider.setStyleSheet("color: #666;")
        layout.addWidget(divider)
        
        # Saved Images List
        self.image_list = QListWidget()
        self.image_list.setIconSize(QSize(80, 60))
        self.image_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.image_list.setSpacing(10)
        self.image_list.itemDoubleClicked.connect(self.use_saved_image)
        layout.addWidget(self.image_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        upload_btn = QPushButton("📁 Upload New Image")
        upload_btn.clicked.connect(self.upload_image)
        btn_layout.addWidget(upload_btn)
        
        delete_btn = QPushButton("🗑️ Delete Selected")
        delete_btn.setStyleSheet("background-color: #8B0000;")
        delete_btn.clicked.connect(self.delete_selected)
        btn_layout.addWidget(delete_btn)
        
        layout.addLayout(btn_layout)
        
    def load_saved_images(self):
        self.image_list.clear()
        if not os.path.exists(CURTAIN_DIR):
            return
            
        for filename in os.listdir(CURTAIN_DIR):
            filepath = os.path.join(CURTAIN_DIR, filename)
            if os.path.isfile(filepath) and filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                icon = QIcon(QPixmap(filepath).scaled(80, 60, Qt.AspectRatioMode.KeepAspectRatio))
                item = QListWidgetItem(icon, filename)
                item.setData(Qt.ItemDataRole.UserRole, filepath)
                self.image_list.addItem(item)
    
    def upload_image(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Curtain Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if filepath:
            # Copy to curtain dir
            filename = os.path.basename(filepath)
            dest = os.path.join(CURTAIN_DIR, filename)
            shutil.copy(filepath, dest)
            self.load_saved_images()
    
    def delete_selected(self):
        item = self.image_list.currentItem()
        if item:
            filepath = item.data(Qt.ItemDataRole.UserRole)
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
            self.load_saved_images()
    
    def use_saved_image(self, item):
        filepath = item.data(Qt.ItemDataRole.UserRole)
        if filepath:
            self.select_curtain("IMAGE", filepath)
    
    def select_curtain(self, curtain_type, data):
        self.curtain_selected.emit(curtain_type, data)
        self.accept()
# alr 
