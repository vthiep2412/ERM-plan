"""
Process Manager - List and kill processes
"""
import json

try:
    import psutil
except ImportError:
    psutil = None
    print("[!] psutil not installed. Process manager will not work.")


class ProcessManager:
    """Handles process listing and killing."""
    
    def list_processes(self):
        """Get list of running processes.
        
        Returns:
            List of dicts with {pid, name, cpu, mem}
        """
        if not psutil:
            return []
        
        processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
                try:
                    info = proc.info
                    mem_mb = info['memory_info'].rss / (1024 * 1024) if info['memory_info'] else 0
                    processes.append({
                        'pid': info['pid'],
                        'name': info['name'] or 'Unknown',
                        'cpu': info['cpu_percent'] or 0,
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
            pid: Process ID to kill
            
        Returns:
            bool: True if killed successfully
        """
        if not psutil:
            return False
        
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            proc.wait(timeout=3)
            return True
        except psutil.NoSuchProcess:
            print(f"[-] Process {pid} not found")
            return False
        except psutil.AccessDenied:
            print(f"[-] Access denied to kill process {pid}")
            return False
        except psutil.TimeoutExpired:
            # Force kill
            try:
                proc.kill()
                return True
            except Exception:
                return False
        except Exception as e:
            print(f"[-] Kill Process Error: {e}")
            return False
    
    def to_json(self, processes):
        """Convert process list to JSON bytes."""
        return json.dumps(processes).encode('utf-8')
