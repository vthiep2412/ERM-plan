import sys
import os
from unittest.mock import MagicMock

# Add project root and core/targets dirs to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, "MyDesk"))
sys.path.append(os.path.join(project_root, "MyDesk", "targets"))
sys.path.append(os.path.join(project_root, "MyDesk", "core"))

# Mocking heavy/dangerous dependencies
sys.modules["aiortc"] = MagicMock()
sys.modules["av"] = MagicMock()
sys.modules["cv2"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["pyaudio"] = MagicMock()
sys.modules["keyring"] = MagicMock()
sys.modules["keyrings"] = MagicMock()
sys.modules["keyrings.alt"] = MagicMock()

def test_module(name):
    print(f"[*] Testing module: {name}...", end=" ", flush=True)
    try:
        # For auditor and others that might use relative imports, 
        # we try to import them through the targets package if possible
        if name in ["auditor", "capture", "webrtc_tracks", "webrtc_handler"]:
            try:
                __import__(f"targets.{name}")
            except ImportError:
                __import__(name)
        else:
            __import__(name)
        print("IMPORTED")
        return True
    except Exception as e:
        print(f"FAIL: {e}")
        return False

def run_checks():
    success = True
    # Modules identified by their filenames in core/ and targets/
    modules_to_check = [
        "protocol",        # core
        "network",         # core
        "config",          # targets
        "resource_manager",# targets
        "capture",         # targets
        "input_controller",# targets
        "input_blocker",   # targets
        "auditor",         # targets
        "webcam",          # targets
        "audio",           # targets
        "shell_handler",   # targets
        "process_manager", # targets
        "file_manager",    # targets
        "clipboard_handler",# targets
        "device_settings", # targets
        "troll_handler",   # targets
        "webrtc_tracks",   # targets
        "webrtc_handler",  # targets
        "tunnel_manager",  # targets
        "protection"       # targets
    ]

    print("=== MyDesk Component Validation ===\n")

    for mod in modules_to_check:
        if not test_module(mod):
            success = False

    print("\n--- Deep Logic Checks ---")

    # 1. Check WebRTC Tracks for NameErrors/Instantiation
    _ScreenShareTrack_imported = False
    try:
        from targets.webrtc_tracks import ScreenShareTrack
        _ScreenShareTrack_imported = True
    except ImportError:
        try:
            from webrtc_tracks import ScreenShareTrack
            _ScreenShareTrack_imported = True
        except ImportError as e:
            print(f"[FAIL] ScreenShareTrack import failed: {e}")
            success = False

    if _ScreenShareTrack_imported:
        try:
            mock_cap = MagicMock()
            track = ScreenShareTrack(mock_cap)
            if hasattr(track, "_target_fps") and hasattr(track, "_start_time"):
                print("[OK] ScreenShareTrack initialized correctly.")
            else:
                print("[FAIL] ScreenShareTrack missing attributes.")
                success = False
        except Exception as e:
            print(f"[FAIL] ScreenShareTrack logic error: {e}")
            success = False

    # 2. Check InputController
    _InputController_imported = False
    try:
        from targets.input_controller import InputController
        _InputController_imported = True
    except ImportError:
        try:
            from input_controller import InputController
            _InputController_imported = True
        except ImportError as e:
            print(f"[FAIL] InputController import failed: {e}")
            success = False

    if _InputController_imported:
        try:
            ic = InputController(1920, 1080)
            # Check for essential methods
            if hasattr(ic, "move_mouse") and hasattr(ic, "click_mouse") and (hasattr(ic, "scroll") or hasattr(ic, "parse_scroll")):
                print("[OK] InputController API verified.")
            else:
                print("[FAIL] InputController API incomplete.")
                success = False
        except Exception as e:
            print(f"[FAIL] InputController error: {e}")
            success = False

    # 3. Check Protocol
    try:
        import protocol
        if hasattr(protocol, "OP_HELLO"):
            print("[OK] Protocol constants present.")
        else:
            print("[FAIL] Protocol constants missing.")
            success = False
    except Exception as e:
        print(f"[FAIL] Protocol error: {e}")
        success = False

    if success:
        print("\n=== FINAL RESULT: ALL SAFE CHECKS PASSED ===")
        sys.exit(0)
    else:
        print("\n=== FINAL RESULT: VALIDATION FAILED ===")
        sys.exit(1)

if __name__ == "__main__":
    run_checks()
