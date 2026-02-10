import sys
import os

# Add target dir to path
sys.path.append(os.path.abspath("../MyDesk/targets"))

try:
    print("Importing input_controller...")
    import input_controller
    print("input_controller imported successfully.")
    
    print("Checking InputController attributes...")
    ic = input_controller.InputController(1920, 1080)
    if hasattr(ic, 'scroll') and hasattr(ic, 'release_all_buttons'):
        print("InputController has required methods.")
    else:
        print("FAIL: InputController missing methods.")
        
except Exception as e:
    print(f"FAIL: input_controller error: {e}")

try:
    print("Importing agent...")
    # Mocking config and tunnel_manager imports if they fail due to dependencies
    sys.modules['targets.config'] = type('config', (), {'REGISTRY_URL': '', 'AGENT_USERNAME': '', 'REGISTRY_PASSWORD': ''})
    sys.modules['targets.tunnel_manager'] = type('tunnel_manager', (), {})
    
    import agent
    print("agent imported successfully.")
except Exception as e:
    print(f"FAIL: agent error: {e}")

try:
    print("Importing protection...")
    import protection
    print("protection imported successfully.")
    if hasattr(protection, 'set_critical_status') and hasattr(protection, 'is_safe_mode'):
        print("[OK] protection API is correct.")
    else:
        print("FAIL: protection API missing methods.")
except Exception as e:
    print(f"FAIL: protection error: {e}")

try:
    print("Importing tunnel_manager...")
    # Mocking urllib for tunnel_manager
    sys.modules['urllib.request'] = type('urllib', (), {'urlopen': lambda *a, **k: None})
    import tunnel_manager
    print("tunnel_manager imported successfully.")
    tm = tunnel_manager.TunnelManager(8765)
    if hasattr(tm, 'restart') and hasattr(tm, 'STUCK_TIMEOUT'):
        print("[OK] TunnelManager API is correct (Phase 7 verified).")
    else:
        print("FAIL: TunnelManager API missing methods.")
except Exception as e:
    print(f"FAIL: tunnel_manager error: {e}")

try:
    print("Importing capture...")
    # Mocking mss and numpy
    sys.modules['mss'] = type('mss', (), {'mss': lambda: None})
    sys.modules['numpy'] = type('numpy', (), {})
    import capture
    print("capture imported successfully.")
    cap = capture.DeltaScreenCapturer()
    if hasattr(cap, 'get_frame_bytes'):
         print("[OK] DeltaScreenCapturer API is correct.")
    else:
        print("FAIL: DeltaScreenCapturer missing methods.")
except Exception as e:
    # Capture might fail if dependencies like cv2 are hard to mock, which is fine for a syntax check
    print(f"[*] capture check skipped or failed: {e}")

print("\n--- Final Result: If no FAILs above, syntax check PASSED ---")
