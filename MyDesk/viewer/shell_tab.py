"""
Shell Tab Widget - Remote command execution (PowerShell/CMD)
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, 
    QLineEdit, QPushButton, QComboBox, QLabel
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont


class ShellTab(QWidget):
    """Remote shell widget with PS/CMD toggle."""
    
    command_signal = pyqtSignal(str, str)  # (shell_type, command)
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Shell type selector
        top_bar = QHBoxLayout()
        
        shell_label = QLabel("Shell:")
        self.shell_combo = QComboBox()
        self.shell_combo.addItems(["PowerShell", "CMD"])
        self.shell_combo.setFixedWidth(120)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_output)
        
        # CWD Label (Top Bar)
        self.cwd_label = QLabel("DIR: ...")
        self.cwd_label.setStyleSheet("color: #888; padding-left: 10px; font-family: Consolas;")
        
        top_bar.addWidget(shell_label)
        top_bar.addWidget(self.shell_combo)
        top_bar.addWidget(self.cwd_label) # Add to top bar
        top_bar.addStretch()
        top_bar.addWidget(self.clear_btn)
        
        layout.addLayout(top_bar)
        
        # Output area
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Consolas", 10))
        self.output.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.output, 1)
        
        # Input area
        input_layout = QHBoxLayout()
        
        self.prompt_label = QLabel("PS>")
        self.prompt_label.setStyleSheet("color: #569cd6; font-weight: bold;")
        
        self.input = QLineEdit()
        self.input.setFont(QFont("Consolas", 10))
        self.input.setPlaceholderText("Enter command...")
        self.input.returnPressed.connect(self.send_command)
        self.input.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_command)
        self.send_btn.setStyleSheet("""
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
        
        input_layout.addWidget(self.prompt_label)
        input_layout.addWidget(self.input, 1)
        input_layout.addWidget(self.send_btn)
        
        layout.addLayout(input_layout)
        


        # Update prompt on shell change
        self.shell_combo.currentTextChanged.connect(self.update_prompt)
    
    def update_prompt(self, shell_type):
        if shell_type == "PowerShell":
            self.prompt_label.setText("PS>")
            self.prompt_label.setStyleSheet("color: #569cd6; font-weight: bold;")
        else:
            self.prompt_label.setText("CMD>")
            self.prompt_label.setStyleSheet("color: #ce9178; font-weight: bold;")
    
    def update_cwd(self, path):
        """Update current working directory label."""
        self.cwd_label.setText(f"DIR: {path}")

    def send_command(self):
        cmd = self.input.text().strip()
        if not cmd:
            return
        
        shell_type = "ps" if self.shell_combo.currentText() == "PowerShell" else "cmd"
        
        # Display command in output (REMOVED: let shell echo it to prevent duplication)
        # prompt = "PS>" if shell_type == "ps" else "CMD>"
        # self.output.appendPlainText(f"{prompt} {cmd}")
        
        # Emit signal
        self.command_signal.emit(shell_type, cmd)
        
        # Clear input
        self.input.clear()
    
    def append_output(self, text):
        """Append output from agent."""
        self.output.appendPlainText(text)
        # Auto-scroll to bottom
        scrollbar = self.output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def show_exit_code(self, code):
        """Show exit code."""
        self.output.appendPlainText(f"\n[Exit Code: {code}]\n")
    
    def clear_output(self):
        self.output.clear()
