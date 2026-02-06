import sys
import os

# Add target dir to path
sys.path.append(os.path.abspath("MyDesk/targets"))

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
    sys.modules['target.config'] = type('config', (), {'REGISTRY_URL': '', 'AGENT_USERNAME': '', 'REGISTRY_PASSWORD': ''})
    sys.modules['target.tunnel_manager'] = type('tunnel_manager', (), {})
    
    import agent
    print("agent imported successfully.")
except Exception as e:
    print(f"FAIL: agent error: {e}")
# alr 
