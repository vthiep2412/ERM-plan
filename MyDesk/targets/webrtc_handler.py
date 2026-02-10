"""
WebRTC Handler for MyDesk Agent
Manages WebRTC peer connections and signaling.
Uses H.264 for optimal performance.
"""
import logging

try:
    from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
    from aiortc.contrib.media import MediaRelay
    from aiortc.codecs import h264
    AIORTC_AVAILABLE = True
    
    # --- PHASE 9: HARDWARE ENCODING OPTIMIZATION ---
    # Auto-detects NVENC (Nvidia), QSV (Intel), or Fallback to CPU
    
    import av
    
    def find_best_codec():
        """
        Detects the best available H.264 encoder.
        Priority: NVENC > QSV > AMF > CPU (libx264)
        Returns: (codec_name, options_dict)
        """
        codecs = av.codecs_available
        
        # 1. NVIDIA NVENC
        if 'h264_nvenc' in codecs:
            print("[+] WebRTC: Found NVIDIA NVENC (Hardware Accelerated)")
            return 'h264_nvenc', {
                'preset': 'p4',       # Medium/Fast (p1=fastest, p7=slowest)
                'tune': 'ull',        # Ultra-Low Latency
                'rc': 'cbr',          # Constant Bitrate for stability
                'zerolatency': '1',
                'delay': '0'
            }
            
        # 2. Intel QSV
        if 'h264_qsv' in codecs:
            print("[+] WebRTC: Found Intel QSV (Hardware Accelerated)")
            return 'h264_qsv', {
                'preset': 'veryfast',
                'look_ahead': '0'
            }
            
        # 3. AMD AMF (Rare on servers, but check)
        if 'h264_amf' in codecs:
             print("[+] WebRTC: Found AMD AMF (Hardware Accelerated)")
             return 'h264_amf', {'usage': 'ultralowlatency'}

        # 4. CPU Fallback (libx264)
        print("[*] WebRTC: CPU Fallback (libx264)")
        return 'libx264', {
            'preset': 'ultrafast',
            'tune': 'zerolatency',
            'profile': 'baseline'
        }

    # Detect once at module load
    BEST_CODEC, BEST_OPTIONS = find_best_codec()

    _orig_h264_encoder_init = h264.H264Encoder.__init__

    def _optimized_h264_init(self, codec):
        _orig_h264_encoder_init(self, codec)
        
        # Force the detected best codec
        self.codec = av.CodecContext.create(BEST_CODEC, "w")
        
        # Apply Optimized Options
        self.codec.options = BEST_OPTIONS.copy()
        
        # Crucial for Real-Time
        self.codec.flags |= 'LOW_DELAY'
        self.codec.flags2 |= 'FAST'
    
    h264.H264Encoder.__init__ = _optimized_h264_init
    print(f"[+] WebRTC: Applied {BEST_CODEC} optimization")
    # -----------------------------------------------

except ImportError:
    AIORTC_AVAILABLE = False
    print("[!] aiortc not installed. WebRTC disabled. Install with: pip install aiortc")

# Configure logging
logging.basicConfig(level=logging.INFO) 
logging.getLogger('aiortc').setLevel(logging.INFO) # Enable aiortc logs
logging.getLogger('aioice').setLevel(logging.WARNING)

# STUN servers for NAT traversal (free public servers)
# CLOUDFLARED USER: Disabling STUN to prevent "Slow Start" (5-10s timeout)
# If direct P2P fails over internet, uncomment these.
ICE_SERVERS = []
# ICE_SERVERS = [
#     RTCIceServer(urls=['stun:stun.l.google.com:19302']),
#     RTCIceServer(urls=['stun:stun1.l.google.com:19302']),
# ] if AIORTC_AVAILABLE else []


class WebRTCHandler:
    """
    Handles WebRTC peer connections for real-time media streaming.
    
    Flow:
    1. Viewer sends SDP Offer via WebSocket (OP_RTC_OFFER)
    2. Agent processes offer, adds media tracks
    3. Agent sends SDP Answer back (OP_RTC_ANSWER)
    4. ICE candidates exchanged (OP_ICE_CANDIDATE)
    5. P2P connection established - media flows directly!
    """
    
    def __init__(self, on_track_callback=None):
        if not AIORTC_AVAILABLE:
            raise RuntimeError("aiortc is required for WebRTC support")
        
        self.pc = None
        self.relay = MediaRelay()
        self.on_track_callback = on_track_callback
        
        # Track state
        self.screen_track = None
        self.webcam_track = None
        self.audio_track = None
        
        # Connection state
        self.connected = False
        self.ice_candidates = []
        
        # Initialize PC immediately
        self._init_pc()
        
    def _init_pc(self):
        """Create a new RTCPeerConnection"""
        config = RTCConfiguration(iceServers=ICE_SERVERS)
        self.pc = RTCPeerConnection(configuration=config)
        
        # Set up event handlers
        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            if self.pc is None:
                return
            state = self.pc.connectionState
            print(f"[WebRTC] Connection state: {state}")
            if state == "connected":
                self.connected = True
            elif state in ("failed", "closed", "disconnected"):
                self.connected = False
                
        @self.pc.on("icecandidate")
        async def on_icecandidate(candidate):
            if candidate:
                self.ice_candidates.append({
                    'candidate': candidate.candidate,
                    'sdpMid': candidate.sdpMid,
                    'sdpMLineIndex': candidate.sdpMLineIndex
                })

    async def create_connection(self):
        """Deprecated: PC is initialized in __init__"""
        if self.pc is None:
            self._init_pc()
        return self.pc
    
    async def set_remote_description(self, offer_sdp: str, offer_type: str = "offer"):
        """
        Step 1: Set remote description from offer.
        Do this BEFORE adding tracks.
        """
        if self.pc is None:
            self._init_pc()
            
        offer = RTCSessionDescription(sdp=offer_sdp, type=offer_type)
        await self.pc.setRemoteDescription(offer)
        
    async def create_answer(self) -> dict:
        """
        Step 2: Create and set local description (answer).
        Do this AFTER adding tracks.
        """
        if self.pc is None:
            raise RuntimeError("PeerConnection not initialized")
            
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        
        # Hack: Modify SDP to increase bitrate limit
        sdp = self.pc.localDescription.sdp
        sdp_lines = sdp.splitlines()
        new_lines = []
        for line in sdp_lines:
            new_lines.append(line)
            if line.startswith("m=video"):
                new_lines.append("b=AS:10000")
                new_lines.append("b=TIAS:10000000")
                new_lines.append("a=x-google-flag:conference")
                new_lines.append("a=x-google-min-bitrate:5000")
                new_lines.append("a=x-google-start-bitrate:8000")
        
        high_quality_sdp = "\r\n".join(new_lines) + "\r\n"
        
        return {
            'sdp': high_quality_sdp,
            'type': self.pc.localDescription.type
        }

    async def handle_offer(self, offer_sdp: str, offer_type: str = "offer") -> dict:
        """DEPRECATED: Use set_remote_description -> add_track -> create_answer"""
        await self.set_remote_description(offer_sdp, offer_type)
        return await self.create_answer()
    
    async def add_ice_candidate(self, candidate_dict: dict):
        """Add an ICE candidate received from the viewer"""
        if self.pc is None:
            return
            
        try:
            from aiortc import RTCIceCandidate
            candidate = RTCIceCandidate(
                candidate=candidate_dict.get('candidate'),
                sdpMid=candidate_dict.get('sdpMid'),
                sdpMLineIndex=candidate_dict.get('sdpMLineIndex')
            )
            await self.pc.addIceCandidate(candidate)
        except Exception as e:
            print(f"[WebRTC] Failed to add ICE candidate: {e}")
    
    def add_video_track(self, track):
        """Add a video track (screen share or webcam) to the connection"""
        if self.pc is None:
            return
        
        # Revert to addTrack (maxBitrate not supported in this aiortc ver)
        # Relying on SDP modification (b=AS:10000) instead
        self.pc.addTrack(track)
        
    def add_audio_track(self, track):
        """Add an audio track to the connection"""
        if self.pc is None:
            return
        
        relayed_track = self.relay.subscribe(track)
        self.pc.addTrack(relayed_track)
    
    def get_pending_ice_candidates(self) -> list:
        """Get and clear pending ICE candidates"""
        candidates = self.ice_candidates.copy()
        self.ice_candidates.clear()
        return candidates
    
    async def close(self):
        """Close the peer connection"""
        self.connected = False
        if self.pc:
            await self.pc.close()
            self.pc = None


# Factory function
def create_webrtc_handler(on_track_callback=None) -> WebRTCHandler:
    """Create a new WebRTC handler instance"""
    if not AIORTC_AVAILABLE:
        raise RuntimeError("aiortc not available")
    return WebRTCHandler(on_track_callback)
