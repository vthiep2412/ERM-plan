# 🧠 Project Memories & Context

**Last Updated:** 2026-02-05 6:47 PM
**Project:** MyDesk (Remote Administration & Support Tool)

## 📌 Status Overview
The project is a functional prototype of a Remote Administration Tool. It uses a **Broker-Agent-Viewer** architecture. The codebase is Python-based, utilizing `asyncio` and `websockets`.

## 🏗️ Architecture Nuances
- **Communication Flow**:
    - Agents register with the Broker using `OP_HELLO`.
    - Viewers lookup Agents using `OP_LOOKUP`.
    - The Broker facilitates a **Bridge** (relay) by default but supports **Direct** connection handoffs if the Agent advertises a public URL (e.g., ngrok).
- **Protocol**: 
    - Defined in `MyDesk/core/protocol.py`.
    - Uses a mix of binary prefixes and text/JSON payloads.
    - Extensive feature set defined: Webcam, Audio, File Manager, Shell, Clipboard, and "Troll" features.

## 🔑 Key Files to Watch
- `MyDesk/broker/server.py`: The heart of the connectivity code. Handling connection state and bridging logic here is critical.
- `MyDesk/core/protocol.py`: The single source of truth for OpCodes. **Do not change OpCodes randomly** as it will break compatibility between Agent/Broker/Viewer.
- `MyDesk/agent_loader.py`: The entry point. It modifies `sys.path` to load the `target` package (which likely contains the actual `agent.py` logic, though `target` folder inspection was not exhaustive in this session).

## 💡 Context for Next Steps
- **Deployment**: `MyDesk_Broker_Deploy` contains deployment scripts, likely for a VPS or cloud instance.
- **Client Identification**: Clients are identified by an ID string sent during `OP_HELLO`.
- **Security**: There is currently **NO** visible authentication or encryption layer beyond standard WSS (if configured) and the opacity of the protocol. This might be a future improvement area.

## 📉 Performance & Bottlenecks (Found 2026-02-05)
- **Cloudflare Tunnel Latency**: Traffic likely hairpins (Agent -> Cloudflare -> Broker -> Viewing Network). Real-time video over TCP-based WebSockets via tunnel suffers from Head-of-Line blocking.
- **Webcam vs Screen Share**:
    - **Screen Share (`capture.py`)**: Highly optimized. Uses **Delta Tiling** (only sends modified 32x32 blocks). Effective for desktop usage.
    - **Webcam (`webcam.py`)**: Inefficient. Sends **Full JPEG** for every frame (MJPEG-style) at 320x240/15fps. No delta compression or H.264 streaming. This explains why it is significantly slower than screen share.

### 🐢 Why is it slower than Discord/Skype?
- **Protocol**: MyDesk uses **TCP (WebSockets)**. TCP waits for every packet to arrive in order. If one packet drops, the video freezes. Discord/Skype use **UDP (WebRTC)** which skips lost packets for real-time speed.
- **Compression**: MyDesk uses Python-based image tiling or MJPEG. Discord/Skype use **Video Codecs** (H.264/VP8) with hardware acceleration, motion vectors, and temporal compression, which are 100x more efficient.

## 📝 Instructions for Updating This File
If you modify the architecture or add new modules:
1. Update **Status Overview**.
2. Add any new **Key Files**.
3. Note any **Protocol Changes** in `Architecture Nuances`.
