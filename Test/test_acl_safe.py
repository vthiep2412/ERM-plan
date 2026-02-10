import sys
import os
import time
import ctypes

is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0

# Add target dir to path to import protection (Script-relative)
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
targets_dir = os.path.join(base_dir, "MyDesk", "targets")
sys.path.append(targets_dir)

if not is_admin:
    print("[-] ERROR: This script must be run as Administrator!")
    sys.exit(1)

try:
    from protection import protect_process
    print("========================================")
    print("   ACL PROTECTION SAFETY TESTER")
    print("========================================")
    print(f"[*] Current PID: {os.getpid()}")
    
    if protect_process():
        print("[+] SUCCESS: ACL Protection Applied.")
        print("[!] TRY TO KILL ME NOW!")
        print("    1. Open Task Manager -> End Task")
        print(f"    2. Try: taskkill /F /PID {os.getpid()}")
        print("\n[*] This script will stay alive for 1 minutes.")
        print("[*] (Note: Since 'Critical Status' is OFF, your PC is safe if this fails)")
        
        for i in range(60, 0, -1):
            sys.stdout.write(f"\rTime remaining: {i}s   ")
            sys.stdout.flush()
            time.sleep(1)
            
    else:
        print("[-] FAILED: Could not apply protection.")
        print("[TIP] Try running the terminal as Administrator!")
        
except Exception as e:
    print(f"[-] ERROR: {e}")

print("\n\nTest Finished.")
