import sys
import os
sys.path.append('MyDesk')
from MyDesk.targets.file_manager import FileManager

fm = FileManager()
print(f"Base dir: {fm.base_dir}")
print(f"List drives: {fm.list_dir('')}")
print(f"Is safe '/': {fm._is_safe_path('/')}")
