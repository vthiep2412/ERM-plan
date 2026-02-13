# 🧠 Project Memories & Context

**Last Updated:** 2026-02-13 11:00 AM
**Project:** MyDesk (Remote Administration Tool)

## 📌 Status Overview
MyDesk is a mature Remote Administration Tool (RAT, not Trojan) prototype using a **Registry-Agent-Viewer** architecture. It has transitioned from simple TCP streaming to high-performance **WebRTC** (Project Supersonic UDP) with hardware acceleration.

## 🏗️ Architecture Nuances
- **Discovery (Registry)**:
    - Agents register with a global registry (`mydesk-registry.vercel.app`) via a heartbeat loop.
    - Uses Firebase for data persistence.
    - Heartbeat includes fallback to `curl` if standard Python SSL libraries fail in restricted environments.
- **Communication Flow**:
    - **Control Channel**: WebSockets (WSS/WS) through Cloudflare Tunnels (using `cloudflared.exe`).
    - **Media Channel**: WebRTC (using `aiortc`). Direct P2P if possible, or via signaling relay.
- **Protocol (`MyDesk/core/protocol.py`)**:
    - **WebRTC Signaling**: SDP Offer (0x05), Answer (0x06), ICE Candidates (0x07).
    - **Feature Rich**: Detailed handlers for File Manager (0x78-0x7F), Process Manager (0x74-0x76), Clipboard (0x80-0x87), and Device Settings (0x88-0x91).
- **Ghost Mode**:
    - Agent uses an `output_buffer` (deque, max 5000 items) to store shell output, keylogs, and clipboard entries during disconnection.
    - Data is automatically replayed to the viewer upon reconnection.

## 🏗️ Component Breakdown
### `MyDesk/targets/` (The Agent)
- `agent.py`: High-concurrency async orchestrator. Manages heartbeat, tunneling, and message routing.
- `webrtc_handler.py`: **Hardware-accelerated** video streaming. Priority: `NVENC` (Nvidia) > `QSV` (Intel) > `AMF` (AMD) > CPU (`libx264`).
- `protection.py`: Implements process persistence via Windows ACLs to prevent termination.
- `tunnel_manager.py`: Automated `cloudflared` lifecycle management.
- `troll_handler.py`: Prank suite utilizing MCI for overlapping, non-blocking audio effects.

### `MyDesk/viewer/` (The Controller)
- `main.py`: PyQt6-based dashboard.
- `session.py`: Manages the lifecycle of a remote viewing session.
- `webrtc_client.py`: Client-side WebRTC logic for receiving high-speed video.

## 🔑 Key Files to Watch
- `MyDesk/targets/agent.py`: Core logic for the agent's behavior and persistence.
- `MyDesk/core/protocol.py`: Single source of truth for all communication OpCodes.
- `MyDesk/scripts/build_hydra.bat`: Main build script for compiling the agent.

## 🧪 Testing & Building

### Syntax Verification
```bash
# From project root (ERM-plan/)
.\\MyDesk\\scripts\\integration_test.bat
```
- Validates all core and target modules can be imported
- Runs deep logic checks (ScreenShareTrack, InputController, Protocol constants)
- Expected result: `ALL SAFE CHECKS PASSED`

### Build Agent (Hydra Build)
```bash
# From project root (ERM-plan/)
cd MyDesk
scripts\build_hydra.bat
```
- Builds 3 executables: `MyDeskAgent.exe`, `MyDeskAudio.exe`, `MyDeskSetup.exe`
- Output: `MyDesk/dist/MyDeskSetup.exe`
- Set `USE_CONSOLE=true` in the bat file for debug builds (shows console window)
- **Rebuild required** when changing anything in `targets/`, `core/`, or shared modules

### Running the Viewer (no build needed)
```bash
# From project root (ERM-plan/)
python MyDesk/viewer/main.py
```
- Viewer runs directly from source (PyQt6), no compilation needed

## 🔧 Engineering Notes
- **WebRTC Optimization**: We've forced `LOW_DELAY` and `zerolatency` presets in the H.264 encoder to achieve sub-100ms latency.
- **Port Liberation**: The agent includes a "Port Liberator" that kills processes occupying its required ports on startup.
- **Security**: Current focus is on connectivity and features. No end-to-end encryption (E2EE) is implemented yet; relies on WSS/WebRTC security.

## ⚠️ Known Limitations
- **Tunnel Overhead**: Latency is mostly introduced by the Cloudflare Tunnel hairpin (~50-150ms).
- **Admin Rights**: Many features (UAC bypass, ACL protection, InputBlock mode) require the agent to run as SYSTEM or Administrator.
- **Upload Size Limit**: `fm_tab.py` has `MAX_UPLOAD_BYTES = 100 MB` hard cap in the UI.

## 📋 Recent Changes (2026-02-12)
- **Refined Shutdown Protection**: The `WatcherService` implements a Tri-Layer Shutdown System.
    - **Confirmed Fix**: The `SetConsoleCtrlHandler` fallback (Layer 3) successfully caught `CTRL_SHUTDOWN_EVENT` (6) in Session 0 when standard SCM handlers failed. This was critical for parsing the shutdown signal and preventing BSOD.
- **Watchdog Reliability**: Implemented retry logic for `WTSQueryUserToken` (Error 1008) in `watcher.py`.
    - **Parameters**: 10 Retries, 2s wait (Total 20s window).
    - **Fixes**: Agent failing to restart during session transitions (Sleep/Wake/Lock).
- **Agent Path Validation**: Implemented strict `base_dir` containment, `os.path.realpath` resolution, and Windows drive checks in `Agent.py` for all file operations.
- **Atomic Buffer**: Secured the Agent's `output_buffer` with locks and implemented an atomic swap to prevent race conditions during message flushing.
- **Chunked File Transfer**: Files >5MB use 256KB chunks with `QProgressDialog` (both upload and download).
  - New OpCode: `OP_FM_DOWNLOAD_INFO = 0x7F`.
  - Agent supports chunked upload receiver via `OP_FM_CHUNK`.
- **Connection Speed Indicator**: Toolbar shows real-time bandwidth (green) or "Connection Lost" (red).

## 📝 Instructions for Updating This File
1. Update **Last Updated** timestamp.
2. Note any new **OpCodes** or **Protocol Changes**.
3. Document any new **Hardware Support** or **Security Layers**.
4. Add significant features to **Recent Changes** with date.
