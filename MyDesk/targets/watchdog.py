import subprocess
import time
import sys
import os
import signal

def run_agent():
    """Run the Agent and restart it if it crashes/closes."""
    
    # Determine what to run
    if getattr(sys, 'frozen', False):
        # Frozen: Run the Agent executable in the same directory
        base_dir = os.path.dirname(sys.executable)
        agent_exe = os.path.join(base_dir, "MyDeskAgent.exe")
    else:
        # Source: Run python agent_loader.py
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        agent_exe = [sys.executable, os.path.join(base_dir, "agent_loader.py")]

    print(f"[*] Watchdog Started. Monitoring: {agent_exe}")

    while True:
        try:
            # Prepare arguments (pass through arguments like --local)
            args = sys.argv[1:]
            
            # Start Process
            if isinstance(agent_exe, list):
                cmd = agent_exe + args
            else:
                cmd = [agent_exe] + args
                
            print(f"[*] Launching Agent...")
            # Use CREATE_NO_WINDOW if on Windows to hide the agent console if desired
            # But usually we want to see output for now.
            # startupinfo = subprocess.STARTUPINFO()
            # startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            process = subprocess.Popen(cmd) #, startupinfo=startupinfo)
            
            # Wait for it to exit
            process.wait()
            
            print(f"[-] Agent exited with code {process.returncode}. Restarting in 2s...")
            time.sleep(2)
            
        except KeyboardInterrupt:
            print("[*] Watchdog stopped by user.")
            break
        except Exception as e:
            print(f"[-] Watchdog Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_agent()
