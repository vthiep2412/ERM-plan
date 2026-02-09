import sys

try:
    from pipreqs import pipreqs
except ImportError:
    print("Error: pipreqs module not found.")
    sys.exit(1)

# Target directory
target_dir = r"C:\Users\vthie\.vscode\ERM-plan\MyDesk"

# Arguments for pipreqs
# We need to mimic sys.argv
# pipreqs uses docopt, so it parses sys.argv
sys.argv = ["pipreqs", target_dir, "--encoding", "utf-8", "--force"]

print(f"Running pipreqs on {target_dir}...")
try:
    pipreqs.main()
    print("pipreqs finished successfully.")
except SystemExit as e:
    # pipreqs calls sys.exit()
    print(f"pipreqs exited with code {e.code}")
except Exception as e:
    print(f"An error occurred: {e}")
# alr 
