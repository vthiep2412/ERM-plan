# Network utilities for WebSocket communication

async def send_msg(ws, data: bytes):
    """
    Sends a message via WebSocket.
    With WebSockets, we don't strictly need length-prefixing as messages are framed,
    but we keep it for protocol consistency if we ever switch back.
    Actually, WS handles framing. Passing raw bytes is fine.
    """
    if ws is None:
        return  # Silently ignore if disconnected
    try:
        await ws.send(data)
    except Exception as e:
        raise ConnectionError(f"WS Send failed: {e}")

from typing import Optional
import websockets

async def recv_msg(ws) -> Optional[bytes]:
    """
    Receives a message via WebSocket.
    Returns None on disconnect.
    """
    try:
        data = await ws.recv()
        # Ensure it's bytes
        if isinstance(data, str):
            data = data.encode('utf-8')
        return data
    except websockets.exceptions.ConnectionClosed:
        return None
    except Exception as e:
        # Check for close or other errors
        print(f"[-] WS Recv Error: {e}")
        return None
