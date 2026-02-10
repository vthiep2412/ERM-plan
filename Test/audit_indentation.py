import os
import re
import sys

def check_indentation(directory):
    print(f"[*] Auditing indentation in: {os.path.abspath(directory)}")
    print("-" * 50)
    
    python_files = []
    for root, dirs, files in os.walk(directory):
        # Skip hidden and non-source directories
        if any(d in root for d in [".git", ".gemini", "node_modules", "dist", "build", "__pycache__"]):
            continue
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
    
    total_issues = 0
    total_files = len(python_files)
    files_with_issues = 0

    for file_path in python_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"[!] Error reading {file_path}: {e}")
            continue
                
        file_issues = []
        for i, line in enumerate(lines, 1):
            # 1. Check for Tabs (Hard Tabs)
            if "\t" in line:
                file_issues.append(f"Line {i}: Contains TABS (expected spaces)")
            
            # 2. Check for Inconsistent indentation (expected multiple of 4 spaces)
            match = re.match(r"^( +)", line)
            if match:
                spaces = len(match.group(1))
                if spaces % 4 != 0:
                    file_issues.append(f"Line {i}: Inconsistent indentation ({spaces} spaces, not a multiple of 4)")
        
        if file_issues:
            files_with_issues += 1
            print(f"[!] {os.path.relpath(file_path, directory)}")
            for issue in file_issues[:5]: 
                print(f"    {issue}")
            if len(file_issues) > 5:
                print(f"    ... and {len(file_issues) - 5} more issues")
            total_issues += len(file_issues)

    print("-" * 50)
    if total_issues == 0:
        print(f"[+] SUCCESS: All {total_files} files follow consistent 4-space indentation!")
    else:
        print(f"[*] Audit complete. Found {total_issues} issues in {files_with_issues}/{total_files} files.")
        print("[TIP] You can fix these automatically by running: python -m black <directory>")

if __name__ == "__main__":
    # Determine the project root (default is parent of this script if it's in Test/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, ".."))
    
    # If a path is provided as argument, use that
    target = sys.argv[1] if len(sys.argv) > 1 else project_root
    
    check_indentation(target)