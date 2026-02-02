import os
import sys
import time
import subprocess
import ctypes

# Ensure uiautomation is installed
try:
    import uiautomation as auto
except ImportError:
    print("Installing uiautomation library...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "uiautomation"])
    import uiautomation as auto

def disable_tamper_protection():
    print("[-] Initializing Revolution Agent...")
    print("[-] Target: Windows Security > Tamper Protection")

    # 1. Launch Windows Security
    print("[-] Opening Security Dashboard...")
    os.system("start windowsdefender://threat")
    
    # 2. Attach to Window
    print("[-] Searching for window...")
    window = auto.WindowControl(searchDepth=1, Name="Windows Security")
    if not window.Exists(maxSearchSeconds=10):
        print("[!] ERROR: Windows Security window not found.")
        return

    window.SetFocus()
    time.sleep(1)

    # 3. Find "Manage settings"
    print("[-] Locating 'Manage settings'...")
    manage_settings_link = window.HyperlinkControl(Name="Manage settings", searchDepth=10)
    
    if not manage_settings_link.Exists(maxSearchSeconds=2):
        manage_settings_link = window.Control(Name="Manage settings", searchDepth=12)

    if manage_settings_link.Exists():
        print("[-] Found 'Manage settings'. Clicking...")
        try:
            manage_settings_link.Invoke()
        except:
            manage_settings_link.Click()
    else:
        print("[!] ERROR: Could not find 'Manage settings' link.")
        return

    # Dynamic Wait for new page (Wait for 'Real-time protection' or 'Tamper Protection' to appear)
    print("[-] Waiting for settings page to load...")
    # We look for the "Real-time protection" toggle or text which is usually first
    if not window.Control(Name="Real-time protection", searchDepth=15).Exists(maxSearchSeconds=10):
        print("[!] Warning: Settings page load timed out or layout changed.")
    else:
        print("[-] Page loaded.")

    # 4. Find "Tamper Protection" Toggle
    print("[-] searching for Tamper Protection toggle...")
    
    # Strategy 1: CheckBox with Name (Standard)
    tp_toggle = window.CheckBoxControl(Name="Tamper Protection", searchDepth=15)
    
    # Strategy 2: Button with Name (Some versions)
    if not tp_toggle.Exists(maxSearchSeconds=1):
         tp_toggle = window.ButtonControl(Name="Tamper Protection", searchDepth=15)

    # Strategy 3: Find Text "Tamper Protection" and look for the Switch in the same group
    if not tp_toggle.Exists(maxSearchSeconds=1):
        print("[-] Direct name match failed. Searching by Label...")
        tp_label = window.TextControl(Name="Tamper Protection", searchDepth=15)
        if tp_label.Exists():
            parent = tp_label.GetParent()
            tp_toggle = parent.CheckBoxControl()
            if not tp_toggle.Exists():
                tp_toggle = parent.ButtonControl()
    
    if tp_toggle.Exists():
        print(f"[-] Found Toggle element: {tp_toggle.Name}")
        
        # Check State
        current_state = -1
        try:
             # Try Toggle Pattern
             current_state = tp_toggle.GetTogglePattern().ToggleState
        except:
             pass
        
        # If state is unknown (-1) or On (1), we try to disable it.
        # For ButtonControl without TogglePattern, we just Click.
        
        if current_state == 1 or current_state == -1:
            print(f"[-] Tamper Protection appears ON/Unknown (State={current_state}). Clicking...")
            try:
                if hasattr(tp_toggle, 'Toggle'):
                     tp_toggle.Toggle()
                else:
                     tp_toggle.Click()
            except Exception as e:
                print(f"[-] Toggle/Click failed: {e}. Trying Invoke...")
                try:
                    tp_toggle.Invoke()
                except:
                    print("[-] Invoke failed. Trying blind click...")
                    tp_toggle.Click()

            print("[-] Toggle action sent.")
            print("[!] ACTION REQUIRED: If UAC prompts, please click YES.")
        else:
            print("[-] Tamper Protection is ALREADY OFF (State=0).")
    else:
        print("[!] Critical: Could not isolate Tamper Protection switch.")
        
    print("[-] Operation Complete. Closing...")
    time.sleep(2)
    window.GetWindowPattern().Close()

if __name__ == "__main__":
    try:
        if not ctypes.windll.shell32.IsUserAnAdmin():
            print("[!] Warning: Script may need Admin privileges to toggle settings.")
    except:
        pass
    disable_tamper_protection()
