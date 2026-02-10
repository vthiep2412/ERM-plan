"""
File Manager - Browse, read, write, delete files
"""

import os
import sys
import json
import shutil
from datetime import datetime


class FileManager:
    """Handles file system operations."""

    # Dangerous paths that should never be deleted
    # Use frozen set of normalized paths
    FORBIDDEN_PATHS = frozenset(
        os.path.normcase(os.path.normpath(p))
        for p in [
            "/",
            "C:\\",
            "C:\\Windows",
            "C:\\Windows\\System32",
            "C:\\Program Files",
            "C:\\Program Files (x86)",
            "/usr",
            "/bin",
            "/sbin",
            "/etc",
            "/var",
            "/root",
        ]
    )

    def __init__(self, base_dir=None):
        """Initialize with optional base directory restriction.

        Args:
            base_dir: Optional base directory to restrict all operations to.
                      If None, allows access to entire filesystem (admin mode).
        """
        self.base_dir = os.path.realpath(base_dir) if base_dir else None
        self.safety_mode = True  # Default to ON

    def _is_safe_path(self, path):
        """Check if path is safe (inside base_dir if set).

        Args:
            path: Path to validate

        Returns:
            bool: True if safe, False if potentially malicious
        """
        if not path:
            return True  # Empty path is allowed (returns drives)

        try:
            # Normalize and resolve
            real_path = os.path.realpath(os.path.normpath(path))

            # If base_dir is set, ensure path is under it
            if self.base_dir:
                # Use strict prefix check instead of commonpath (simpler/faster)
                base = os.path.normcase(self.base_dir)
                target = os.path.normcase(real_path)

                # Must be equal or start with base_dir + sep
                if not (target == base or target.startswith(base + os.sep)):
                    print(f"[-] Path traversal blocked: {path}")
                    return False

            return True
        except Exception:
            return False

    def list_dir(self, path):
        """List directory contents or available drives if path is empty.

        Args:
            path: Directory path to list

        Returns:
            List of dicts with {name, is_dir, size, modified}
        """
        # Sanitize path
        if path:
            path = os.path.normpath(path)

            # Validate path safety
            if not self._is_safe_path(path):
                return []

        if not path:
            # If constrained to base_dir, return only that
            if self.base_dir:
                try:
                    stat = os.stat(self.base_dir)
                    return [
                        {
                            "name": os.path.basename(self.base_dir) or self.base_dir,
                            "is_dir": True,
                            "size": 0,
                            "modified": datetime.fromtimestamp(stat.st_mtime).strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                        }
                    ]
                except (OSError, PermissionError):
                    return []
            # List available drives (cross-platform)
            if sys.platform == "win32":
                # Windows: use GetLogicalDrives
                import string
                from ctypes import windll

                drives = []
                bitmask = windll.kernel32.GetLogicalDrives()
                for letter in string.ascii_uppercase:
                    if bitmask & 1:
                        drive_name = f"{letter}:\\"
                        drives.append(
                            {
                                "name": drive_name,
                                "is_dir": True,
                                "size": 0,
                                "modified": "N/A",
                            }
                        )
                    bitmask >>= 1
                return drives
            else:
                # POSIX: list root mounts
                try:
                    # Try psutil if available
                    import psutil

                    drives = []
                    for part in psutil.disk_partitions():
                        drives.append(
                            {
                                "name": part.mountpoint,
                                "is_dir": True,
                                "size": 0,
                                "modified": "N/A",
                            }
                        )
                    return (
                        drives
                        if drives
                        else [
                            {"name": "/", "is_dir": True, "size": 0, "modified": "N/A"}
                        ]
                    )
                except ImportError:
                    # Fallback: just return root
                    return [{"name": "/", "is_dir": True, "size": 0, "modified": "N/A"}]

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

                    files.append(
                        {
                            "name": name,
                            "is_dir": is_dir,
                            "size": stat.st_size if not is_dir else 0,
                            "modified": datetime.fromtimestamp(stat.st_mtime).strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                        }
                    )
                except (PermissionError, OSError):
                    continue
        except PermissionError:
            print(f"[-] Permission denied: {path}")
        except Exception as e:
            print(f"[-] List Dir Error: {e}")

        # Sort: folders first, then by name
        files.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return files

    def read_file(self, path, chunk_size=64 * 1024):
        """Read a file in chunks (generator).

        Args:
            path: File path to read
            chunk_size: Bytes per chunk

        Yields:
            bytes: File chunks
        """
        if not self._is_safe_path(path):
            return

        if not os.path.exists(path) or os.path.isdir(path):
            return

        try:
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except Exception as e:
            print(f"[-] Read File Error: {e}")

    # Alias for compatibility
    def read_file_chunks(self, path, chunk_size=64 * 1024):
        """Alias for read_file."""
        return self.read_file(path, chunk_size)

    def read_file_full(self, path, size_limit=None):
        """Read entire file.

        Args:
            path: File path
            size_limit: Optional maximum file size in bytes. If exceeded, returns None.

        Returns:
            bytes or None
        """
        try:
            # Check file size first if limit specified
            if not self._is_safe_path(path):
                return None

            # Check file size first if limit specified
            if size_limit is not None:
                if not os.path.exists(path):
                    return None
                file_size = os.path.getsize(path)
                if file_size > size_limit:
                    print(f"[-] File too large: {file_size} bytes > {size_limit} limit")
                    return None

            with open(path, "rb") as f:
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
            # Create parent directories if needed (TOCTOU safe)
            if not self._is_safe_path(path):
                return False

            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)

            with open(path, "wb") as f:
                f.write(data)
            return True
        except Exception as e:
            print(f"[-] Write File Error: {e}")
            return False

    def delete(self, path, confirm_recursive=True):
        """Delete file or directory with safety checks.

        Args:
            path: Path to delete
            confirm_recursive: Must be True for directory deletes (safety)

        Returns:
            bool: Success
        """
        try:
            # Validate path
            if not path:
                print("[-] Delete Error: Empty path")
                return False

            # Resolve to real absolute path
            real_path = os.path.realpath(os.path.normpath(path))
            norm_real_path = os.path.normcase(real_path)

            # Check against forbidden paths
            if self.safety_mode:
                if (
                    norm_real_path in self.FORBIDDEN_PATHS
                    or os.path.normcase(real_path.rstrip("/\\")) in self.FORBIDDEN_PATHS
                ):
                    print(f"[-] Delete blocked (Safety Mode): Cannot delete system path: {real_path}")
                    return False

            # Check if path is a root drive
            if sys.platform == "win32":
                if len(real_path) <= 3 and real_path[1:3] in (":\\", ":"):
                    print(f"[-] Delete blocked: Cannot delete drive root: {real_path}")
                    return False
            else:
                if real_path == "/":
                    print("[-] Delete blocked: Cannot delete root")
                    return False

            # Check base_dir restriction
            if not self._is_safe_path(real_path):
                print(
                    f"[-] Delete blocked: Path outside allowed directory: {real_path}"
                )
                return False

            # Perform delete
            if os.path.isdir(real_path):
                if not confirm_recursive:
                    print("[-] Delete Error: Recursive delete not confirmed")
                    return False
                shutil.rmtree(real_path)
            else:
                os.remove(real_path)
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
            # exist_ok=True handles TOCTOU race safely
            if not self._is_safe_path(path):
                return False
            os.makedirs(path, exist_ok=True)
            return True
        except Exception as e:
            print(f"[-] Mkdir Error: {e}")
            return False

    def to_json(self, files, path=None):
        """Convert file list to JSON bytes."""
        data = {"files": files}
        if path:
            data["path"] = path
        return json.dumps(data).encode("utf-8")


# alr
