import os
import shutil

# Paths
SOURCE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DEST_DIR = os.path.join(SOURCE_ROOT, "..", "MyDesk_Broker_Deploy")

def main():
    print(f"[*] Exporting Broker to: {DEST_DIR}")
    
    # Validate DEST_DIR to be safe
    # Ensure it's inside the user's project area or explicitly allowed
    safe_base = os.path.abspath(os.path.join(SOURCE_ROOT, ".."))
    if not os.path.abspath(DEST_DIR).startswith(safe_base) or len(DEST_DIR) < 10:
        print(f"[-] Unsafe Export Path: {DEST_DIR}. Aborting.")
        return

    dest_abs = os.path.abspath(DEST_DIR)
    if os.path.basename(dest_abs) != "MyDesk_Broker_Deploy":
        print(f"[-] Safety Abort: Destination folder name must be 'MyDesk_Broker_Deploy', got '{os.path.basename(dest_abs)}'")
        return

    if os.path.exists(DEST_DIR):
        confirm = input(f"[?] Delete existing folder '{DEST_DIR}'? (y/N): ")
        if confirm.lower() != 'y':
            print("[-] Aborted by user.")
            return
        shutil.rmtree(DEST_DIR)
    os.makedirs(DEST_DIR)
    
    # 1. Copy Core
    print("[*] Copying Core library...")
    shutil.copytree(os.path.join(SOURCE_ROOT, "core"), os.path.join(DEST_DIR, "core"))
    
    # 2. Process & Copy Server.py
    print("[*] Processing server.py...")
    with open(os.path.join(SOURCE_ROOT, "broker", "server.py"), "r") as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        # Remove the sys.path hack for parent directory, as we structure it flat now
        if "sys.path.append" in line and ".." in line:
            continue
        new_lines.append(line)
        
    with open(os.path.join(DEST_DIR, "server.py"), "w") as f:
        f.writelines(new_lines)
        
    # 3. Requirements
    print("[*] Creating requirements.txt...")
    with open(os.path.join(DEST_DIR, "requirements.txt"), "w") as f:
        f.write("websockets\n")
        
    # 4. Readme
    with open(os.path.join(DEST_DIR, "README.md"), "w") as f:
        f.write("# MyDesk Broker\n\nDeploy this to Render.com.\n\nStart Command: `python server.py`")

    print(f"\n[+] Done! You can now upload the folder '{DEST_DIR}' to GitHub.")

if __name__ == "__main__":
    main()
