"""
Alert Looper - Separate file for tweaking alert loop speed.
"""
import time
import threading
import ctypes
import random
import winreg
import os

# TWEAK SPEED HERE (Seconds)
# Set very low (e.g., 0.05 or lower) for intense overlapping effect
SPEED = 0.5

def get_system_sound_path(sound_name="SystemHand"):
    """Get path to a system sound from Registry."""
    try:
        key_path = f"AppEvents\\Schemes\\Apps\\.Default\\{sound_name}\\.Current"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            val, _ = winreg.QueryValueEx(key, "")
            if val and os.path.exists(val):
                return val
    except Exception:
        pass
    # Fallback usually works
    return r"C:\Windows\Media\Windows Background.wav"

def play_sound_overlapped(filepath):
    """Play sound in a way that allows overlap (using MCI)."""
    def _worker():
        # Create unique alias to allow multiple instances
        alias = f"snd_{random.randint(0, 999999)}"
        cmd_open = f'open "{filepath}" type waveaudio alias {alias}'
        cmd_play = f'play {alias} wait'
        cmd_close = f'close {alias}'
        
        try:
            ctypes.windll.winmm.mciSendStringW(cmd_open, None, 0, 0)
            ctypes.windll.winmm.mciSendStringW(cmd_play, None, 0, 0) # Blocks thread until done
        finally:
            ctypes.windll.winmm.mciSendStringW(cmd_close, None, 0, 0)
    
    # Spawn thread to handle playback asynchronously
    threading.Thread(target=_worker, daemon=True).start()

def run_loop(check_active_func):
    """Run the alert loop while check_active_func() returns True."""
    # List of distinct system sounds
    sounds = [
        "SystemHand",       # Critical Stop
        "SystemExclamation",
        "Notification.Reminder",
        "MailBeep",
        "AppGPFault",
        "DeviceConnect",
        "DeviceDisconnect",
        "DeviceFail",
        "MessageNudge"
    ]
    
    print(f"[+] Alert Looper started with {len(sounds)} sounds")
    
    last_sound = None
    
    while check_active_func():
        try:
            # Smart Random: Avoid repeating the same sound
            available_sounds = [s for s in sounds if s != last_sound]
            if not available_sounds: 
                available_sounds = sounds
                
            sound_name = random.choice(available_sounds)
            last_sound = sound_name
            
            sound_path = get_system_sound_path(sound_name)
            if sound_path:
                play_sound_overlapped(sound_path)
            else:
                # Fallback if sound not found
                play_sound_overlapped(r"C:\Windows\Media\Windows Background.wav")
                
        except Exception as e:
            print(f"[-] Alert Error: {e}")
        time.sleep(SPEED)

if __name__ == "__main__":
    run_loop(lambda: True)