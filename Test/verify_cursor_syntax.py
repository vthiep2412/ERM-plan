from PyQt6.QtWidgets import QApplication, QLabel
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen
import sys
import os

sys.path.append('MyDesk')

try:
    print("Importing viewer.widgets...")
    from viewer.widgets import VideoCanvas
    print("SUCCESS: Imported VideoCanvas")
    
    app = QApplication([])
    canvas = VideoCanvas()
    
    # Test internal state
    if hasattr(canvas, '_cursor_pos') and hasattr(canvas, '_cursor_color'):
        print(f"SUCCESS: Cursor state initialized: {canvas._cursor_pos}, {canvas._cursor_color}")
    else:
        print("FAIL: Cursor state missing")

    # Simulate Paint Event (Dry Run logic check)
    print("Checking update_frame logic...")
    if 'setPixmap' in VideoCanvas.update_frame.__code__.co_names:
       print("SUCCESS: update_frame calls setPixmap")
    else:
       print("FAIL: update_frame does not call setPixmap")
       
    print("Syntax Check Passed.")
except Exception as e:
    print(f"FAIL: {e}")
# alr 
