"""
Shell Handler - Execute commands in PowerShell or CMD (Persistent/Interactive)
"""
import subprocess
import threading
import os
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
        self._cwd_buffer = ""  # Buffer for detecting __CWD__ markers

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
                # Returns: "__CWD__C:\Path\nPS C:\Path> "
                hack = 'function prompt { "__CWD__" + $pwd.ProviderPath + "`nPS " + $pwd.ProviderPath + "> " }'
                args = ["powershell", "-NoLogo", "-NoExit", "-Command", hack]
            else:
                # CMD prompt hack: emit CWD marker then path prompt
                # $P = Path, $G = >
                args = ["cmd", "/k", "prompt __CWD__$P$_$P$G"]
            
            # Cross-platform Popen: only use CREATE_NO_WINDOW on Windows
            popen_kwargs = {
                'stdout': subprocess.PIPE,
                'stderr': subprocess.STDOUT,  # Merge stderr into stdout
                'stdin': subprocess.PIPE,
                'text': True,
                'bufsize': 1,  # Line-buffered (text=True requires bufsize >= 1)
            }
            
            # Only add creationflags on Windows
            if os.name == 'nt':
                popen_kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            
            self.process = subprocess.Popen(args, **popen_kwargs)
            
            # Start reader thread (Subject to merged stream)
            t1 = threading.Thread(target=self._read_stream, args=(self.process.stdout, "stdout"), daemon=True)
            self._threads = [t1]
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
                # Use read(1) for instant character streaming (fixes prompt lag)
                char = stream.read(1)
                if not char:
                    # EOF
                    break
                
                # Add to CWD buffer for marker detection
                self._cwd_buffer += char
                
                # Check for complete __CWD__ marker pattern
                if "__CWD__" in self._cwd_buffer:
                    # Look for the complete marker (ends at newline)
                    marker_start = self._cwd_buffer.find("__CWD__")
                    newline_pos = self._cwd_buffer.find("\n", marker_start)
                    
                    if newline_pos != -1:
                        # Extract the path from marker
                        path = self._cwd_buffer[marker_start + 7:newline_pos]
                        
                        # Send text before marker to output
                        text_before = self._cwd_buffer[:marker_start]
                        if text_before and self.on_output:
                            self.on_output(text_before)
                        
                        # Call on_cwd callback with extracted path
                        if callable(self.on_cwd):
                            try:
                                self.on_cwd(path)
                            except Exception:
                                pass
                        
                        # Keep text after the marker line
                        self._cwd_buffer = self._cwd_buffer[newline_pos + 1:]
                        
                        # Also send the normal prompt part to output (skip the __CWD__ line)
                        continue
                
                # Flush buffer if it's getting too long without a marker
                if len(self._cwd_buffer) > 500 and "__CWD__" not in self._cwd_buffer:
                    if self.on_output:
                        self.on_output(self._cwd_buffer)
                    self._cwd_buffer = ""
                elif len(self._cwd_buffer) > 0:
                    # If buffer doesn't start with potential marker, flush immediate
                    # Optimized: Check if buffer matches the START of marker
                    marker_prefix = "__CWD__"[:len(self._cwd_buffer)]
                    if self._cwd_buffer != marker_prefix:
                        # It's not the start of a marker, so it's safe to flush
                        if self.on_output:
                            self.on_output(self._cwd_buffer)
                        self._cwd_buffer = ""
                    
        except (EOFError, BrokenPipeError, OSError) as e:
            # Expected stream closure errors
            print(f"[*] Shell stream closed: {type(e).__name__}")
        except Exception as e:
            # Unexpected errors
            print(f"[-] Shell stream handler error: {e}")
        finally:
            # Flush any remaining buffer
            if self._cwd_buffer and self.on_output:
                self.on_output(self._cwd_buffer)
                self._cwd_buffer = ""
            
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
                # Wait briefly for graceful exit
                try:
                    self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    print("[!] Shell did not terminate, killing...")
                    self.process.kill()
            except Exception as e:
                print(f"[-] Shell stop error: {e}")
            self.process = None
        self.current_shell = None
        self._cwd_buffer = ""
