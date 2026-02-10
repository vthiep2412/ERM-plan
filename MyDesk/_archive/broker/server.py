import asyncio
import websockets
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import protocol
from core.network import send_msg, recv_msg

# Registry: {ClientID: WebSocket}
clients = {}
# Direct Addresses: {ClientID: "wss://ngrok-url..."}
direct_routes = {}


async def handle_client(websocket):
    print(f"[+] Client Connected: {websocket.remote_address}")
    client_id = None

    try:
        # Wait for HELLO or LOOKUP
        # We assume the first message is the handshake
        msg = await recv_msg(websocket)
        if not msg:
            return

        opcode = msg[0]
        payload = msg[1:]

        if opcode == protocol.OP_HELLO:
            # === AGENT REGISTER ===
            # Payload: ID + Optional Separator + DirectURL
            # Format: "ID|wss://..."
            decoded = payload.decode("utf-8").split("|")
            client_id = decoded[0]
            direct_url = decoded[1] if len(decoded) > 1 else None

            clients[client_id] = websocket
            if direct_url:
                direct_routes[client_id] = direct_url
                print(f"[*] Agent {client_id} Registered (Direct: {direct_url})")
            else:
                print(f"[*] Agent {client_id} Registered (Bridge Mode)")

            # Keep alive loop
            try:
                await websocket.wait_closed()
            except:
                pass

        elif opcode == protocol.OP_LOOKUP:
            # === VIEWER LOOKUP ===
            target_id = payload.decode("utf-8")
            print(f"[*] Viewer requested {target_id}")

            direct_url = direct_routes.get(target_id)
            target_ws = clients.get(target_id)

            if direct_url:
                # Case A: Direct Route Available
                # Send OP_BRIDGE_OK + "DIRECT|<URL>"
                resp = f"DIRECT|{direct_url}".encode()
                await send_msg(websocket, bytes([protocol.OP_BRIDGE_OK]) + resp)

            elif target_ws:
                # Case B: Bridge Mode
                # Send OP_BRIDGE_OK + "BRIDGE"
                await send_msg(websocket, bytes([protocol.OP_BRIDGE_OK]) + b"BRIDGE")

                # Signal Agent to start streaming TO US (The Broker)
                # Then we pipe it to Viewer.
                try:
                    await send_msg(target_ws, bytes([protocol.OP_CONNECT]))
                except:
                    return

                # BRIDGE LOOP
                # We need to bridge messages between `websocket` (Viewer) and `target_ws` (Agent)
                # Function to copy A->B
                await bridge_sockets(websocket, target_ws)

                # If we get here, the bridge broke.
                # Notify Viewer if they are still connected
                try:
                    await send_msg(
                        websocket, bytes([protocol.OP_ERROR]) + b"Agent Disconnected"
                    )
                except:
                    pass

            else:
                await send_msg(
                    websocket, bytes([protocol.OP_ERROR]) + b"Target Not Found"
                )

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if client_id:
            if client_id in clients:
                del clients[client_id]
            if client_id in direct_routes:
                del direct_routes[client_id]
            print(f"[-] Agent {client_id} Disconnected")


async def bridge_sockets(ws_a, ws_b):
    """
    Bidirectional Async Bridge.
    This is tricky in Python because recv() awaits.
    We create 2 tasks: A->B and B->A.
    """

    async def forward(src, dst):
        try:
            while True:
                msg = await recv_msg(src)
                if msg is None:
                    break
                await send_msg(dst, msg)
        except Exception:
            pass
        finally:
            # If Viewer (src) disconnected, tell Agent (dst) to stop
            try:
                await send_msg(dst, bytes([protocol.OP_DISCONNECT]))
            except:
                pass

    # Run both pipe tasks
    t1 = asyncio.create_task(forward(ws_a, ws_b))
    t2 = asyncio.create_task(forward(ws_b, ws_a))

    # Wait for either to finish (close)
    done, pending = await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    
    # Wait for tasks to finish to allow `finally` blocks to run
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


async def main():
    # Force Unbuffered Output for Render Logs
    sys.stdout.reconfigure(line_buffering=True)

    # Render provides PORT env var usually, or we default to 8765
    port_str = os.environ.get("PORT", "8765")
    try:
        port = int(port_str)
    except ValueError:
        print(f"[-] Invalid PORT '{port_str}', defaulting to 8765")
        port = 8765
    print(f"[*] Broker Listening on 0.0.0.0:{port} (WebSockets)", flush=True)
    async with websockets.serve(handle_client, "0.0.0.0", port):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
