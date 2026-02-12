"""
WebRTC Client for MyDesk Viewer
Handles WebRTC connection to Agent for real-time video streaming.
"""

import asyncio
import json

try:
    from aiortc import (
        RTCPeerConnection,
        RTCSessionDescription,
        RTCConfiguration,
        RTCIceServer,
        RTCIceCandidate,
    )

    AIORTC_AVAILABLE = True
except ImportError:
    AIORTC_AVAILABLE = False
    print("[!] aiortc not installed. WebRTC disabled.")

try:
    from PyQt6.QtCore import QObject, pyqtSignal

    PYQT_AVAILABLE = True
except ImportError:
    # Fallback for non-PyQt environments
    class QObject:
        pass

    def pyqtSignal(*args):
        return None

    PYQT_AVAILABLE = False


class WebRTCClient(QObject if PYQT_AVAILABLE else object):
    """
    WebRTC client for Viewer.

    Signals:
        video_frame_received: Emitted when a video frame is decoded
        connection_state_changed: Emitted when connection state changes
        error_occurred: Emitted on errors
    """

    if PYQT_AVAILABLE:
        video_frame_received = pyqtSignal(object)  # numpy array
        connection_state_changed = pyqtSignal(str)  # state string
        error_occurred = pyqtSignal(str)  # error message

    def __init__(self, send_message_callback):
        """
        Args:
            send_message_callback: async function to send WebSocket messages
                                   signature: async def send(opcode: int, payload: bytes)
        """
        if PYQT_AVAILABLE:
            super().__init__()

        self.send_message = send_message_callback
        self.pc = None
        self.connected = False
        # Stats
        self._last_stats_timestamp = 0
        self._last_stats_bytes = 0
        
        # Queue for candidates arriving before PC is ready
        self._ice_candidates_queue = []
        self._frame_count = 0  # Frame counter for FPS display

    async def start_connection(self):
        """
        Initiate WebRTC connection to Agent.
        Creates offer and sends it via WebSocket signaling.
        """
        if not AIORTC_AVAILABLE:
            raise RuntimeError("aiortc required for WebRTC")

        # Create peer connection with STUN servers
        config = RTCConfiguration(
            iceServers=[
                RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
                RTCIceServer(urls=["stun:stun1.l.google.com:19302"]),
            ]
        )
        self.pc = RTCPeerConnection(configuration=config)
        
        # Drain queued candidates
        while self._ice_candidates_queue:
            candidate_dict = self._ice_candidates_queue.pop(0)
            candidate = RTCIceCandidate(
                candidate=candidate_dict.get("candidate"),
                sdpMid=candidate_dict.get("sdpMid"),
                sdpMLineIndex=candidate_dict.get("sdpMLineIndex"),
            )
            await self.pc.addIceCandidate(candidate)

        # Set up event handlers
        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            state = self.pc.connectionState
            print(f"[Viewer WebRTC] Connection state: {state}")
            self.connected = state == "connected"
            if PYQT_AVAILABLE and self.connection_state_changed:
                self.connection_state_changed.emit(state)

        @self.pc.on("track")
        def on_track(track):
            print(f"[Viewer WebRTC] Received track: {track.kind}")
            if track.kind == "video":
                # Start receiving video frames
                asyncio.create_task(self._receive_video_frames(track))

        @self.pc.on("icecandidate")
        async def on_icecandidate(candidate):
            if candidate:
                # Send ICE candidate to Agent
                ice_data = json.dumps(
                    {
                        "candidate": candidate.candidate,
                        "sdpMid": candidate.sdpMid,
                        "sdpMLineIndex": candidate.sdpMLineIndex,
                    }
                ).encode("utf-8")
                await self.send_message(0x07, ice_data)  # OP_ICE_CANDIDATE

        # Add transceiver to receive video
        self.pc.addTransceiver("video", direction="recvonly")

        # Create offer
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)

        # Hack: Modify SDP to increase bitrate limit to 30 Mbps
        # This forces the remote encoder to target higher quality
        sdp = self.pc.localDescription.sdp
        sdp_lines = sdp.splitlines()
        new_lines = []
        for line in sdp_lines:
            new_lines.append(line)
            if line.startswith("m=video"):
                new_lines.append("b=AS:30000")  # 30 Mbps
                new_lines.append(
                    "b=TIAS:30000000"
                )  # 30 Mbps
                new_lines.append("a=x-google-flag:conference")
                new_lines.append("a=x-google-min-bitrate:10000")
                new_lines.append("a=x-google-start-bitrate:20000")

        offer_with_high_bitrate = "\r\n".join(new_lines) + "\r\n"

        print("[Viewer WebRTC] Sent SDP offer (High Quality: 30Mbps)")

        offer_data = json.dumps(
            {"sdp": offer_with_high_bitrate, "type": self.pc.localDescription.type}
        ).encode("utf-8")

        await self.send_message(0x05, offer_data)  # OP_RTC_OFFER
        print("[Viewer WebRTC] Sent SDP offer")

    async def handle_answer(self, answer_sdp: str, answer_type: str = "answer"):
        """Process SDP answer from Agent"""
        if not self.pc:
            return

        try:
            answer = RTCSessionDescription(sdp=answer_sdp, type=answer_type)
            await self.pc.setRemoteDescription(answer)
            print("[Viewer WebRTC] Set remote description (answer)")
        except Exception as e:
            print(f"[Viewer WebRTC] Answer error: {e}")
            if PYQT_AVAILABLE and self.error_occurred:
                self.error_occurred.emit(str(e))

    async def handle_ice_candidate(self, candidate_dict: dict):
        """Add ICE candidate from Agent"""
        if not self.pc:
            self._ice_candidates_queue.append(candidate_dict)
            return

        try:
            from aiortc import RTCIceCandidate

            candidate = RTCIceCandidate(
                candidate=candidate_dict.get("candidate"),
                sdpMid=candidate_dict.get("sdpMid"),
                sdpMLineIndex=candidate_dict.get("sdpMLineIndex"),
            )
            await self.pc.addIceCandidate(candidate)
        except Exception as e:
            print(f"[Viewer WebRTC] ICE candidate error: {e}")

    async def _receive_video_frames(self, track):
        """Receive and emit video frames from track"""
        try:
            while True:
                frame = await track.recv()

                # Count frames for FPS display
                self._frame_count += 1

                # Convert av.VideoFrame to numpy array
                img = frame.to_ndarray(format="rgb24")

                if PYQT_AVAILABLE and self.video_frame_received:
                    self.video_frame_received.emit(img)

        except Exception as e:
            if "MediaStreamError" not in str(type(e)):
                print(f"[Viewer WebRTC] Video receive error: {e}")

    async def get_bytes_received(self):
        """Get real compressed bytes received from WebRTC stats."""
        if not self.pc:
            return 0
        try:
            stats = await self.pc.getStats()
            total = 0
            for report in stats.values():
                if hasattr(report, 'type') and report.type == 'inbound-rtp':
                    total += getattr(report, 'bytesReceived', 0)
            # Return delta since last call
            delta = total - self._last_stats_bytes
            self._last_stats_bytes = total
            return max(delta, 0)
        except Exception:
            return 0

    async def close(self):
        """Close the WebRTC connection"""
        self.connected = False
        if self.pc:
            await self.pc.close()
            self.pc = None


# Protocol constants (should match protocol.py)
OP_RTC_OFFER = 0x05
OP_RTC_ANSWER = 0x06
OP_ICE_CANDIDATE = 0x07
