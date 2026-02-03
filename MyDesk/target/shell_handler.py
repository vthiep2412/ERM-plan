"""
Shell Handler - Execute commands in PowerShell or CMD (Persistent/Interactive)
"""
import subprocess
import threading
import time
import queue

import psutil

class ShellHandler:
    """Handles persistent remote shell sessions."""
    
    def __init__(self, on_output=None, on_exit=None, on_cwd=None):
        """
        Args:
            on_output: callback(text) for stdout/stderr
            on_exit: callback(code) when process exits
            on_cwd: callback(path) when directory changes
        """
        self.on_output = on_output
        self.on_exit = on_exit
        self.on_cwd = on_cwd
        self.process = None
        self.current_shell = None
        self.running = False
        self._threads = []

    def get_cwd(self):
        """Get current working directory of the shell process."""
        if not self.process or not self.running:
            return ""
        try:
            p = psutil.Process(self.process.pid)
            return p.cwd()
        except Exception:
            return ""

    def start_shell(self, shell_type="ps"):
        """Start a new persistent shell process."""
        self.stop()  # Stop any existing shell
        
        self.current_shell = shell_type
        self.running = True
        
        try:
            if shell_type == "ps":
                # FIX: Inject prompt hack to emit CWD events for instant updates
                # We print a special marker that the reader thread will intercept
                hack = "function prompt { Write-Host \"`n__CWD__$pwd\"; 'PS> ' }"
                args = ["powershell", "-NoLogo", "-NoExit", "-Command", hack]
            else:
                # CMD prompt hack: emit CWD marker
                args = ["cmd", "/k", "prompt __CWD__$P$_$G"]
            
            self.process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=0, # Unbuffered
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # Start reader threads
            t1 = threading.Thread(target=self._read_stream, args=(self.process.stdout, "stdout"), daemon=True)
            t2 = threading.Thread(target=self._read_stream, args=(self.process.stderr, "stderr"), daemon=True)
            self._threads = [t1, t2]
            for t in self._threads:
                t.start()
                
            print(f"[+] Started persistent shell: {shell_type}")
            
        except Exception as e:
            if self.on_output:
                self.on_output(f"Error starting shell: {e}\n")
            self.running = False

    def write_input(self, cmd):
        """Write command to shell stdin."""
        if not self.process or not self.running:
             # Auto-start if not running (defaulting to ps/cmd based on what might be reasonable or just failing)
             # But better to let agent handle start. Here we just error or start default.
             return

        try:
            if cmd:
                self.process.stdin.write(cmd + "\n")
                self.process.stdin.flush()
        except Exception as e:
            if self.on_output:
                self.on_output(f"Write Error: {e}\n")

    def _read_stream(self, stream, name):
        """Read stdout/stderr in background thread."""
        try:
            while self.running and self.process:
                # Revert to readline() as requested (read(1) caused issues)
                line = stream.readline()
                if not line:
                    break
                
                clean_line = line.rstrip('\r\n')
                
                # Check for CWD marker
                if "__CWD__" in clean_line:
                    try:
                        new_cwd = clean_line.split("__CWD__")[1].strip()
                        if self.on_cwd:
                            self.on_cwd(new_cwd)
                        continue # Don't show marker in output
                    except Exception:
                        pass

                if self.on_output:
                    self.on_output(clean_line)
                    
        except Exception as e:
            pass # Stream closed
        finally:
            if self.process and self.process.poll() is not None and self.running:
                # Process exited unexpectedly
                self.running = False
                if self.on_exit:
                    self.on_exit(self.process.returncode)

    def stop(self):
        """Stop current process."""
        self.running = False
        if self.process:
            try:
                self.process.terminate()
            except:
                pass
            self.process = None
        self.current_shell = None
