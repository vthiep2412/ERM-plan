# MyDesk - Remote Administration & Support Tool

MyDesk is a Python-based Remote Administration Tool (RAT) / Remote Desktop application designed for support and administration. It uses a centralized **Broker** to relay messages between **Agents** (targets) and **Viewers** (controllers), supporting both bridged and direct P2P (where applicable) connections.

## 📂 Project Structure

- **MyDesk/**: Main application source code.
    - **agent_loader.py**: Entry point for the Agent application.
    - **core/**: Shared core functionality.
        - **protocol.py**: Defines the binary protocol, OpCodes, and constants for communication.
        - **network.py**: Networking utilities (send/recv).
    - **broker/**: The intermediary server.
        - **server.py**: Asyncio WebSocket server that handles registry, lookups, and bridging.
    - **build/** & **dist/**: PyInstaller compilation artifacts.
- **MyDesk_Broker_Deploy/**: Scripts and configs for deploying the Broker.

## 🚀 Key Components

### 1. The Broker (`MyDesk/broker/server.py`)
A WebSocket server that acts as a registry and relay.
- **Registry**: Tracks connected Agents by ID.
- **Bridging**: Relays traffic between Viewer and Agent if a direct connection isn't possible.
- **Direct Routes**: Supports handoff to direct WebSocket URLs (e.g., via ngrok) if available.

### 2. The Agent (`MyDesk/agent_loader.py`)
The client application running on the target machine.
- Connects to the Broker via WebSocket.
- Executes commands received from the Viewer.
- Capabilities include:
    - **Webcam & Audio Streaming**
    - **Screen Sharing** (IMG_FRAME)
    - **Remote Shell** access
    - **File Manager** (Upload/Download/List)
    - **System Control** (Power, Volume, Brightness)
    - **"Troll" Features** (Ghost cursor, fake BSOD, etc. - *Use responsibly*)

### 3. The Protocol (`MyDesk/core/protocol.py`)
A custom binary/text hybrid protocol over WebSockets.
- **Handshake**: `OP_HELLO` (Agent -> Broker), `OP_LOOKUP` (Viewer -> Broker).
- **Session**: `OP_BRIDGE_OK`, `OP_CONNECT`.
- **Features**: Distinct OpCodes for different subsystems (e.g., `0x40` for Webcam, `0x70` for Shell).

## 🛠️ Setup & Building

### Prerequisites
- Python 3.10+
- `websockets`, `pyinstaller`

### Running the Broker
```bash
python MyDesk/broker/server.py
```
*Defaults to port 8765.*

### Running the Agent
```bash
python MyDesk/agent_loader.py
```

### Building the Agent (EXE)
Use PyInstaller with the provided spec files:
```bash
pyinstaller MyDesk/MyDeskAgent.spec
```

## ⚠️ Disclaimer
This software is intended for educational purposes and authorized remote administration only. **You must obtain explicit written consent from the system owner before deploying this tool.** Unauthorized access to computer systems may violate laws including the Computer Fraud and Abuse Act (CFAA) and similar statutes worldwide. Users assume all legal responsibility for their use of this software. Misuse of this software for malicious purposes is strictly prohibited.