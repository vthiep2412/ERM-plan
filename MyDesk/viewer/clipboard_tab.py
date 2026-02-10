"""
Clipboard Tab Widget - View clipboard history and sync with agent
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QLabel,
    QScrollArea,
    QFrame,
    QDialog,
    QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QGuiApplication, QFontDatabase


class ClipboardDetailDialog(QDialog):
    """Dialog to show full clipboard entry text."""

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.text = text
        self.setWindowTitle("Clipboard Entry")
        self.setMinimumSize(500, 300)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Full text display
        self.text_view = QPlainTextEdit()
        self.text_view.setPlainText(self.text)
        self.text_view.setReadOnly(True)
        # Cross-platform monospace font
        mono_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono_font.setPointSize(10)
        self.text_view.setFont(mono_font)
        self.text_view.setStyleSheet("""
            QPlainTextEdit {
                background-color: #2d2d2d;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.text_view, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        copy_btn = QPushButton("📋 Copy")
        copy_btn.clicked.connect(self.copy_text)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #5c5c5c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #6e6e6e;
            }
        """)

        btn_layout.addWidget(copy_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def copy_text(self):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.text)


class ClipboardEntryWidget(QFrame):
    """Single clipboard history entry widget."""

    copy_clicked = pyqtSignal(str)
    delete_clicked = pyqtSignal(int)

    def __init__(self, index, text, timestamp="", max_preview=60, parent=None):
        super().__init__(parent)
        self.index = index
        self.text = text
        self.max_preview = max_preview
        self.setup_ui()

    def setup_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            ClipboardEntryWidget {
                background-color: #2d2d2d;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                margin: 2px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # Text preview (truncated)
        preview = self.text.replace("\n", " ").replace("\r", "")
        is_truncated = len(preview) > self.max_preview
        if is_truncated:
            preview = preview[: self.max_preview] + "..."

        self.text_label = QLabel(preview)
        self.text_label.setStyleSheet("color: #d4d4d4;")
        self.text_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self.text_label, 1)

        # More button (only if truncated)
        if is_truncated:
            more_btn = QPushButton("More")
            more_btn.setFixedWidth(50)
            more_btn.clicked.connect(self.show_full_text)
            more_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a4a4a;
                    color: #d4d4d4;
                    border: none;
                    border-radius: 3px;
                    padding: 4px 8px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #5a5a5a;
                }
            """)
            layout.addWidget(more_btn)

        # Copy button
        copy_btn = QPushButton("📋")
        copy_btn.setFixedWidth(30)
        copy_btn.setToolTip("Copy to clipboard")
        copy_btn.clicked.connect(self.copy_text)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        layout.addWidget(copy_btn)

        # Delete button
        delete_btn = QPushButton("🗑")
        delete_btn.setFixedWidth(30)
        delete_btn.setToolTip("Delete entry")
        delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.index))
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #8b0000;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #a00000;
            }
        """)
        layout.addWidget(delete_btn)

    def copy_text(self):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.text)
        self.copy_clicked.emit(self.text)

    def show_full_text(self):
        dialog = ClipboardDetailDialog(self.text, self)
        dialog.exec()


class ClipboardTab(QWidget):
    """Clipboard history widget."""

    get_clipboard_signal = pyqtSignal()  # Request current clipboard

    get_history_signal = pyqtSignal()  # Request clipboard history
    delete_entry_signal = pyqtSignal(int)  # Delete entry by index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Title and refresh
        title_layout = QHBoxLayout()
        title = QLabel("📋 Clipboard History")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #d4d4d4;")
        title_layout.addWidget(title)

        self.count_label = QLabel("(0 entries)")
        self.count_label.setStyleSheet("color: #888; font-size: 12px;")
        title_layout.addWidget(self.count_label)

        title_layout.addStretch()

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.request_history)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #5c5c5c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #6e6e6e;
            }
        """)
        title_layout.addWidget(refresh_btn)
        layout.addLayout(title_layout)

        # History scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                background-color: #1e1e1e;
            }
        """)

        self.history_container = QWidget()
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setContentsMargins(4, 4, 4, 4)
        self.history_layout.setSpacing(4)
        self.history_layout.addStretch()  # Push items to top

        scroll.setWidget(self.history_container)
        layout.addWidget(scroll, 1)

        # Manual clipboard actions
        action_layout = QHBoxLayout()

        self.get_btn = QPushButton("📥 Get Current")
        self.get_btn.clicked.connect(self.get_clipboard_signal.emit)
        self.get_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)

        action_layout.addWidget(self.get_btn)
        action_layout.addStretch()
        layout.addLayout(action_layout)

    def request_history(self):
        """Request clipboard history from agent."""
        self.get_history_signal.emit()

    def update_history(self, history_list):
        """Update with full history list from agent."""
        self.history = history_list
        self.rebuild_history_ui()

    def add_entry(self, entry):
        """Add new real-time clipboard entry and update local clipboard."""
        # Update local clipboard (Viewer side)
        text = entry.get("text", "")
        if text:
            # Prevent loop? Agent->Viewer (Here) -> Viewer (System) -> Viewer Monitor (None) -> Agent
            # Viewer doesn't have a monitor, so this is safe.
            try:
                QGuiApplication.clipboard().setText(text)
            except Exception as e:
                print(f"[-] Viewer Clipboard Set Error: {e}")

        # Add to end of history (displayed newest first via reversal)
        self.history.append(entry)
        self.rebuild_history_ui()

    def rebuild_history_ui(self):
        """Rebuild the history list UI."""
        # Clear existing widgets
        while self.history_layout.count() > 1:  # Keep the stretch
            item = self.history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add entries (newest first = reversed order)
        for i, entry in enumerate(reversed(self.history)):
            text = entry.get("text", "") if isinstance(entry, dict) else str(entry)
            # Use original index (from end of list)
            original_index = len(self.history) - 1 - i

            widget = ClipboardEntryWidget(original_index, text)
            widget.delete_clicked.connect(self.on_delete_entry)
            self.history_layout.insertWidget(i, widget)

        self.count_label.setText(f"({len(self.history)} entries)")

    def on_delete_entry(self, index):
        """Handle delete button click."""
        self.delete_entry_signal.emit(index)

    def update_content(self, content):
        """Update with current clipboard content (legacy compatibility)."""
        # Handle both string (legacy) and dict (new)
        text = content.get("text", "") if isinstance(content, dict) else str(content)

        # Just add to history display
        if text and (not self.history or self.history[-1].get("text") != text):
            self.history.append({"text": text, "timestamp": ""})
            self.rebuild_history_ui()


# alr
