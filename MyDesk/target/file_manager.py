"""
File Manager - Browse, read, write, delete files
"""
import os
import json
import shutil
from datetime import datetime


class FileManager:
    """Handles file system operations."""
    
    def list_dir(self, path):
        """List directory contents or available drives if path is empty.
        
        Args:
            path: Directory path to list
            
        Returns:
            List of dicts with {name, is_dir, size, modified}
        """
        if not path:
            # List available drives
            import string
            from ctypes import windll
            drives = []
            bitmask = windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if bitmask & 1:
                    drive_name = f"{letter}:\\"
                    drives.append({
                        'name': drive_name,
                        'is_dir': True,
                        'size': 0,
                        'modified': 'N/A'
                    })
                bitmask >>= 1
            return drives

        if not os.path.exists(path):
            return []
        
        if not os.path.isdir(path):
            return []
        
        files = []
        try:
            for name in os.listdir(path):
                try:
                    full_path = os.path.join(path, name)
                    stat = os.stat(full_path)
                    is_dir = os.path.isdir(full_path)
                    
                    files.append({
                        'name': name,
                        'is_dir': is_dir,
                        'size': stat.st_size if not is_dir else 0,
                        'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    })
                except (PermissionError, OSError):
                    continue
        except PermissionError:
            print(f"[-] Permission denied: {path}")
        except Exception as e:
            print(f"[-] List Dir Error: {e}")
        
        # Sort: folders first, then by name
        files.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        return files
    
    def read_file(self, path, chunk_size=64*1024):
        """Read a file in chunks (generator).
        
        Args:
            path: File path to read
            chunk_size: Bytes per chunk
            
        Yields:
            bytes: File chunks
        """
        if not os.path.exists(path) or os.path.isdir(path):
            return
        
        try:
            with open(path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except Exception as e:
            print(f"[-] Read File Error: {e}")
    
    def read_file_full(self, path):
        """Read entire file.
        
        Args:
            path: File path
            
        Returns:
            bytes or None
        """
        try:
            with open(path, 'rb') as f:
                return f.read()
        except Exception as e:
            print(f"[-] Read File Error: {e}")
            return None
    
    def write_file(self, path, data):
        """Write data to file.
        
        Args:
            path: File path
            data: bytes to write
            
        Returns:
            bool: Success
        """
        try:
            # Create parent directories if needed
            parent = os.path.dirname(path)
            if parent and not os.path.exists(parent):
                os.makedirs(parent)
            
            with open(path, 'wb') as f:
                f.write(data)
            return True
        except Exception as e:
            print(f"[-] Write File Error: {e}")
            return False
    
    def delete(self, path):
        """Delete file or directory.
        
        Args:
            path: Path to delete
            
        Returns:
            bool: Success
        """
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            return True
        except Exception as e:
            print(f"[-] Delete Error: {e}")
            return False
    
    def mkdir(self, path):
        """Create directory.
        
        Args:
            path: Directory path
            
        Returns:
            bool: Success
        """
        try:
            os.makedirs(path, exist_ok=True)
            return True
        except Exception as e:
            print(f"[-] Mkdir Error: {e}")
            return False
    
    def to_json(self, files, path=None):
        """Convert file list to JSON bytes."""
        data = {'files': files}
        if path:
            data['path'] = path
        return json.dumps(data).encode('utf-8')
