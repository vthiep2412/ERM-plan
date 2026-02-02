import os
import sys
import time
import ctypes
import uiautomation as auto

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def disable_tamper_protection():
    # Force Console Output Flush
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    
    # Detect OS for Tab Calibration
    # Windows 11 >= 22000
    build = sys.getwindowsversion().build
    is_win11 = build >= 22000
    
    if is_win11:
        print(f"[-] OS Detected: Windows 11 (Build {build})")
        # User calibrated these for Win 11
        TABS_TO_SETTINGS = 4
        TABS_TO_TOGGLE = 7
    else:
        print(f"[-] OS Detected: Windows 10 (Build {build})")
        # Derived from Win 10 Screenshots
        TABS_TO_SETTINGS = 4
        TABS_TO_TOGGLE = 4

    # 1. Open Windows Security (Triple-Launch Strategy)
    print("[-] Launching Windows Security...")
    
    # Try 1: Standard URI
    os.system("start windowsdefender://threat")
    time.sleep(1)
    
    # Try 2: Protocol Handler
    try:
        if not auto.WindowControl(searchDepth=1, Name="Windows Security").Exists(maxSearchSeconds=1):
             print("[-] Retrying with 'windowsdefender:' protocol...")
             os.system("start windowsdefender:")
             
        # Try 3: Settings App Redirect
        if not auto.WindowControl(searchDepth=1, Name="Windows Security").Exists(maxSearchSeconds=1):
             print("[-] Retrying with 'ms-settings:'...")
             os.system("start ms-settings:windowsdefender")
    except:
        pass

    
    # DYNAMIC WAIT LOGIC
    print("[-] Waiting for page to fully load...")
    try:
        # Use UIA to wait until "Manage settings" actually exists (Page Loaded)
        win = auto.WindowControl(searchDepth=1, Name="Windows Security")
        if not win.Exists(maxSearchSeconds=1):
            win = auto.WindowControl(searchDepth=1, Name="Windows Defender Security Center")
            
        if win.Exists(maxSearchSeconds=10):
            # Wait for content
            link = win.HyperlinkControl(Name="Manage settings", searchDepth=12)
            if not link.Exists(maxSearchSeconds=15):
                 link = win.Control(Name="Manage settings", searchDepth=15)
                 link.Exists(maxSearchSeconds=5) 
            print("Page loaded!")
        else:
            print("Window did not appear in time. Proceeding anyway...")
            time.sleep(3)
    except Exception as e:
        print(f"Wait failed ({e}). Falling back to sleep.")
        time.sleep(5)
    
    # 2. Navigate to "Manage settings"
    # Ensure window is in focus using UIA
    print("[-] Focusing Window...")
    try:
        win.SetFocus()
    except:
        print("[-] Focus failed, continuing anyway...")
        
    time.sleep(0.5) 

    print(f"Navigating to Settings ({TABS_TO_SETTINGS} Tabs)...")
    
    # BATCH SEND KEYS (Faster than loop)
    # interval=0.01 is fast but distinct
    auto.SendKeys('{Tab}' * TABS_TO_SETTINGS, interval=0.01, waitTime=0.1)
    
    auto.SendKeys('{Enter}', waitTime=0.5) 
    
    # 3. Toggle "Tamper Protection"
    print(f"Navigating to Tamper Switch ({TABS_TO_TOGGLE} Tabs)...")
    
    # BATCH SEND KEYS
    auto.SendKeys('{Tab}' * TABS_TO_TOGGLE, interval=0.01, waitTime=0.1)
        
    print("Toggling Switch...")
    auto.SendKeys('{Space}', waitTime=0.5)
    
    # 4. Close GUI
    print("Closing...")
    auto.SendKeys('{Alt}{F4}')
    
    print("[-] Done.")

if __name__ == "__main__":
    print("hi")
    disable_tamper_protection()
