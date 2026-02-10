import os
import re


def check_indentation(directory):
    print(f"[*] Auditing indentation in: {directory}")
    print("-" * 50)

    python_files = []
    for root, dirs, files in os.walk(directory):
        if "node_modules" in root or ".git" in root or ".gemini" in root:
            continue
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))

    total_issues = 0
    for file_path in python_files:
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                lines = f.readlines()
            except UnicodeDecodeError:
                continue

        file_issues = []
        for i, line in enumerate(lines, 1):
            # Check for tabs
            if "\t" in line:
                file_issues.append(f"Line {i}: Contains TABS")

            # Check for trailing whitespace
            if line.rstrip("\n") != line.rstrip():
                # file_issues.append(f"Line {i}: Trailing whitespace")
                pass  # Ignore trailing whitespace for now to focus on indentation

            # Check indentation level (should be multiple of 4 spaces)
            match = re.match(r"^( +)", line)
            if match:
                spaces = len(match.group(1))
                if spaces % 4 != 0:
                    file_issues.append(
                        f"Line {i}: Inconsistent indentation ({spaces} spaces, not a multiple of 4)"
                    )

        if file_issues:
            print(f"[!] {os.path.relpath(file_path, directory)}")
            for issue in file_issues[:5]:  # Show first 5 issues per file
                print(f"    {issue}")
            if len(file_issues) > 5:
                print(f"    ... and {len(file_issues) - 5} more issues")
            total_issues += len(file_issues)

    print("-" * 50)
    if total_issues == 0:
        print("[+] SUCCESS: All files follow consistent 4-space indentation!")
    else:
        print(f"[*] Total indentation issues found: {total_issues}")
        print(
            "[TIP] You can fix these automatically by running: pip install black && black MyDesk"
        )


if __name__ == "__main__":
    check_indentation("MyDesk")
