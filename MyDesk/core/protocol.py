"""
MyDesk Protocol Definitions
defines OpCodes and Constants for the network communication.
"""

# Connection / Broker Protocol
OP_HELLO        = 1  # Agent -> Broker (Register ID)
OP_LOOKUP       = 2  # Viewer -> Broker (Request Connection to ID)
OP_CONNECT      = 3  # Broker -> Agent (Incoming Connection)
OP_BRIDGE_OK    = 4  # Broker -> Viewer (Connection Established)
# WEBCAM
OP_CAM_START = 0x40
OP_CAM_STOP = 0x41
OP_CAM_FRAME = 0x42

# AUDIO
OP_MIC_START = 0x50
OP_MIC_STOP = 0x51
OP_AUDIO_CHUNK = 0x52

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
OP_SHELL_CMD    = 31 # command string
OP_SHELL_OUT    = 32 # output string
OP_KEY_LOG      = 33 # text log stream

# Settings Constants
SETTING_BLOCK_INPUT = 1
SETTING_PRIVACY     = 2
SETTING_QUALITY     = 3
SETTING_AUDIO       = 4

# Privacy Curtain
OP_CURTAIN_ON  = 0x60  # Payload: "BLACK" or image path
OP_CURTAIN_OFF = 0x61

# Buffered Input
OP_KEY_BUFFER  = 0x62  # Payload: buffered keystrokes

# Remote Settings
OP_SETTINGS    = 0x63  # Payload: JSON settings

# System
OP_ERROR        = 0xF0 # 240
OP_DISCONNECT   = 0xF1 # 241
