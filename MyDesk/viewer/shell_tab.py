"""
Shell Tab Widget - Remote command execution (PowerShell/CMD)
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, 
    QLineEdit, QPushButton, QComboBox, QLabel
)
from PyQt6.QtCore import pyqtSignal, pyqtSlot, Qt
from PyQt6.QtGui import QFont, QTextCursor


class ShellTab(QWidget):
    """Remote shell widget with PS/CMD toggle."""
    
    command_signal = pyqtSignal(str, str)  # (shell_type, command)
    
    def __init__(self):
        super().__init__()
        print("[*] ShellTab Loaded (V10 - History)")
        self.setup_ui()
        self.stdout_buffer = ""
        
        # Command history (last 30 commands)
        self.command_history = []
        self.history_index = -1
        self.max_history = 30
    
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
        # Install event filter for arrow key history navigation
        self.input.installEventFilter(self)
        
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
        
        # Add to command history
        if cmd and (not self.command_history or self.command_history[-1] != cmd):
            self.command_history.append(cmd)
            if len(self.command_history) > self.max_history:
                self.command_history.pop(0)
        self.history_index = len(self.command_history)  # Reset to end
        
        # Emit signal to send command to agent
        self.command_signal.emit(shell_type, cmd)
        
        # Clear input
        self.input.clear()
    
    def eventFilter(self, obj, event):
        """Handle arrow keys for command history navigation."""
        if obj == self.input and event.type() == event.Type.KeyPress:
            key = event.key()
            
            if key == Qt.Key.Key_Up:
                # Navigate to older command
                if self.command_history and self.history_index > 0:
                    self.history_index -= 1
                    self.input.setText(self.command_history[self.history_index])
                return True
            
            elif key == Qt.Key.Key_Down:
                # Navigate to newer command
                if self.command_history:
                    if self.history_index < len(self.command_history) - 1:
                        self.history_index += 1
                        self.input.setText(self.command_history[self.history_index])
                    else:
                        # Past end of history - clear input
                        self.history_index = len(self.command_history)
                        self.input.clear()
                return True
        
        return super().eventFilter(obj, event)
    
    @pyqtSlot(str)
    def append_output(self, text):
        """Append output from agent with CWD parsing - V10 with prompt display."""
        # Add incoming text to buffer
        self.stdout_buffer += text
        
        # Process complete lines (lines ending with \n)
        while '\n' in self.stdout_buffer:
            # Split at first newline
            idx = self.stdout_buffer.index('\n')
            line = self.stdout_buffer[:idx]
            self.stdout_buffer = self.stdout_buffer[idx + 1:]
            
            # Check for __CWD__ marker in this line
            if '__CWD__' in line:
                # Extract path from marker
                marker_pos = line.find('__CWD__')
                path = line[marker_pos + 7:].strip()  # 7 = len('__CWD__')
                
                if path:
                    self.update_cwd(path)
                
                # Get any text BEFORE the marker (keep it)
                before = line[:marker_pos].rstrip()
                if before:
                    self._append_text(before + '\n')
                # Don't display the __CWD__ line itself
            else:
                # Normal line - display it
                self._append_text(line + '\n')
        
        # Handle remaining buffer (partial line like prompt "PS C:\path> ")
        # Only flush if it can't be a __CWD__ marker
        if self.stdout_buffer:
            # Check if buffer could be start of __CWD__ marker
            could_be_marker = False
            marker = "__CWD__"
            
            # If buffer contains full marker, wait for newline
            if marker in self.stdout_buffer:
                could_be_marker = True
            # If buffer ends with start of marker, wait for more data
            elif any(marker.startswith(self.stdout_buffer[-i:]) for i in range(1, min(len(marker), len(self.stdout_buffer)) + 1)):
                could_be_marker = True
            
            if not could_be_marker:
                # Safe to display (it's the prompt or other partial output)
                self._append_text(self.stdout_buffer)
                self.stdout_buffer = ""
    
    def _append_text(self, text):
        """Helper to append text to output widget."""
        if text:
            self.output.moveCursor(QTextCursor.MoveOperation.End)
            self.output.insertPlainText(text)
            sb = self.output.verticalScrollBar()
            sb.setValue(sb.maximum())
    
    def show_exit_code(self, code):
        """Show exit code."""
        self.output.appendPlainText(f"\n[Exit Code: {code}]\n")
    
    def clear_output(self):
        self.output.clear()
        self.stdout_buffer = ""# This line was added at the bottom to force re-check. 
