
import re

def test_parsing():
    """Tests for shell output regex parsing."""
    
    # Simulate the prompt function output
    # hack = 'function prompt { "__CWD__" + $pwd.ProviderPath + "`nPS " + $pwd.ProviderPath + "> " }'
    
    path = r"C:\Users\vthie\.vscode\ERM-plan\mydesk\targets"
    # Case 1: Standard output (Simulated)
    # PowerShell `n is LF (\n)
    simulated_output = f"__CWD__{path}\nPS {path}> "
    
    stdout_buffer = ""
    stdout_buffer += simulated_output
    
    cwd_pattern = re.compile(r'__CWD__(.*?)(\r\n|\r|\n)')
    
    # Test Case 1: Standard output parsing
    match = cwd_pattern.search(stdout_buffer)
    assert match is not None, "No match found for CWD pattern"
    
    extracted = match.group(1).strip()
    assert extracted == path, f"Path mismatch. Expected '{path}', got '{extracted}'"
    
    start, end = match.span()
    remaining = stdout_buffer[:start] + stdout_buffer[end:]
    expected_remaining = f"PS {path}> "
    assert remaining == expected_remaining, f"Remaining mismatch. Expected '{expected_remaining}', got '{remaining}'"
    
    # Test Case 2: Split buffer (no newline yet)
    stdout_buffer = f"__CWD__{path}"  # No newline yet
    
    match = cwd_pattern.search(stdout_buffer)
    assert match is None, "Should not match partial buffer without newline"
    
    # Simulate flushing logic
    marker_idx = stdout_buffer.find("__CWD__")
    assert marker_idx != -1, "Marker not found in buffer"
    stdout_buffer = stdout_buffer[marker_idx:]
    
    # Add newline
    stdout_buffer += "\nPS >"
    match = cwd_pattern.search(stdout_buffer)
    assert match is not None, "Match not found after newline arrived"


if __name__ == "__main__":
    test_parsing()
    print("All tests passed!")
