"""
Process Manager - List and kill processes
"""
import json
import time

try:
    import psutil
except ImportError:
    psutil = None
    print("[!] psutil not installed. Process manager will not work.")


class ProcessManager:
    """Handles process listing and killing."""
    
    def list_processes(self):
        """Get list of running processes.
        
        Uses two-pass CPU measurement for accurate readings.
        
        Returns:
            List of dicts with {pid, name, cpu, mem}
        """
        if not psutil:
            return []
        
        processes = []
        try:
            # Two-pass measurement for accurate CPU readings
            # First pass: initialize CPU sampling
            procs = []
            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    proc.cpu_percent(None)  # Initialize sampling
                    procs.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Short sleep to allow CPU sampling
            time.sleep(0.1)
            
            # Second pass: collect actual readings
            for proc in procs:
                try:
                    info = proc.as_dict(['pid', 'name', 'memory_info'])
                    cpu = proc.cpu_percent(None)  # Now get real reading
                    mem_mb = info['memory_info'].rss / (1024 * 1024) if info.get('memory_info') else 0
                    
                    processes.append({
                        'pid': info['pid'],
                        'name': info.get('name') or 'Unknown',
                        'cpu': cpu if cpu is not None else 0,
                        'mem': round(mem_mb, 1)
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"[-] Process List Error: {e}")
        
        # Sort by memory usage (descending)
        processes.sort(key=lambda x: x['mem'], reverse=True)
        return processes
    
    def kill_process(self, pid):
        """Kill a process by PID.
        
        Args:
            pid: Process ID to kill (must be int)
            
        Returns:
            bool: True if killed successfully
        """
        if not psutil:
            return False
        
        # Validate pid is an integer
        if pid is None:
            print("[-] Kill Process Error: PID is None")
            return False
        
        if not isinstance(pid, int):
            # Try to coerce numeric string to int
            try:
                pid = int(pid)
            except (ValueError, TypeError) as e:
                print(f"[-] Kill Process Error: Invalid PID type - {e}")
                return False
        
        try:
            proc = psutil.Process(pid)
            proc.kill() # Use kill() generally for immediate effect
            proc.wait(timeout=5)
            return True
        except psutil.NoSuchProcess:
            print(f"[-] Process {pid} not found")
            return False
        except psutil.AccessDenied:
            print(f"[-] Access denied to kill process {pid}")
            return False
        except (psutil.TimeoutExpired, Exception) as e:
            print(f"[-] Kill Process Error: {e}")
            return False
    
    def to_json(self, processes):
        """Convert process list to JSON bytes."""
        return json.dumps(processes).encode('utf-8')
