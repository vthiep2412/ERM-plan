"""
Troll Handler - Fun pranks and visual/audio effects
"""
import subprocess
import os
import tempfile
import threading
import random
import webbrowser
import ctypes
import time

try:
    import winsound
except ImportError:
    winsound = None


class TrollHandler:
    """Handles troll/prank features on Windows."""
    
    def __init__(self):
        self.random_sound_enabled = False
        self.random_sound_thread = None
        self.alert_loop_enabled = False
        self.alert_loop_thread = None
        self.whisper_enabled = False
        self.whisper_thread = None
        self.ghost_cursor_enabled = False
        self.video_process = None
        self.overlay_process = None
    
    # =========================================================================
    # Browser
    # =========================================================================
    
    def open_url(self, url):
        """Open URL in default browser."""
        try:
            webbrowser.open(url)
            return True
        except Exception as e:
            print(f"[-] Open URL Error: {e}")
            return False
    
    # =========================================================================
    # Audio
    # =========================================================================
    
    def play_sound(self, data):
        """Play audio data (saves to temp file then plays)."""
        try:
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                f.write(data)
                temp_path = f.name
            
            # Play async
            if winsound:
                threading.Thread(
                    target=lambda: winsound.PlaySound(temp_path, winsound.SND_FILENAME),
                    daemon=True
                ).start()
            return True
        except Exception as e:
            print(f"[-] Play Sound Error: {e}")
            return False
    
    def start_random_sounds(self, interval_ms=5000):
        """Start playing random system sounds at intervals."""
        self.random_sound_enabled = True
        
        def loop():
            sounds = [
                'SystemAsterisk', 'SystemExclamation', 'SystemHand',
                'SystemQuestion', 'SystemExit'
            ]
            while self.random_sound_enabled:
                if winsound:
                    try:
                        winsound.PlaySound(random.choice(sounds), winsound.SND_ALIAS | winsound.SND_ASYNC)
                    except Exception:
                        pass
                time.sleep(interval_ms / 1000.0 + random.uniform(-1, 1))
        
        self.random_sound_thread = threading.Thread(target=loop, daemon=True)
        self.random_sound_thread.start()
    
    def stop_random_sounds(self):
        self.random_sound_enabled = False
    
    def start_alert_loop(self):
        """Loop Windows error sound."""
        self.alert_loop_enabled = True
        
        def loop():
            while self.alert_loop_enabled:
                if winsound:
                    try:
                        winsound.PlaySound('SystemHand', winsound.SND_ALIAS)
                    except Exception:
                        pass
                time.sleep(0.5)
        
        self.alert_loop_thread = threading.Thread(target=loop, daemon=True)
        self.alert_loop_thread.start()
    
    def stop_alert_loop(self):
        self.alert_loop_enabled = False
    
    def volume_max_sound(self):
        """Set volume to max and play sound."""
        try:
            # Max volume
            subprocess.run(["nircmd", "setsysvolume", "65535"], 
                          capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            # Play sound
            if winsound:
                winsound.PlaySound('SystemExclamation', winsound.SND_ALIAS | winsound.SND_ASYNC)
            return True
        except Exception as e:
            print(f"[-] Volume Max Error: {e}")
            return False
    
    def earrape(self):
        """Play very loud distorted sound."""
        try:
            subprocess.run(["nircmd", "setsysvolume", "65535"],
                          capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            # Rapid beeps
            def beep_loop():
                for _ in range(20):
                    if winsound:
                        winsound.Beep(random.randint(100, 3000), 50)
            
            threading.Thread(target=beep_loop, daemon=True).start()
            return True
        except Exception as e:
            print(f"[-] Earrape Error: {e}")
            return False
    
    def start_whisper(self):
        """Play quiet creepy sounds randomly."""
        self.whisper_enabled = True
        
        def loop():
            while self.whisper_enabled:
                time.sleep(random.randint(10, 30))
                if self.whisper_enabled and winsound:
                    try:
                        # Very quiet beep
                        winsound.Beep(200, 100)
                    except Exception:
                        pass
        
        self.whisper_thread = threading.Thread(target=loop, daemon=True)
        self.whisper_thread.start()
    
    def stop_whisper(self):
        self.whisper_enabled = False
    
    # =========================================================================
    # Visual
    # =========================================================================
    
    def play_video(self, data):
        """Play video fullscreen (saves to temp then launches player)."""
        try:
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
                f.write(data)
                temp_path = f.name
            
            # Launch video player script
            script_dir = os.path.dirname(__file__)
            player_script = os.path.join(script_dir, 'troll_video_player.py')
            
            import sys
            self.video_process = subprocess.Popen(
                [sys.executable, player_script, temp_path],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True
        except Exception as e:
            print(f"[-] Play Video Error: {e}")
            return False
    
    def stop_video(self):
        """Stop video player."""
        if self.video_process:
            try:
                self.video_process.terminate()
                self.video_process = None
            except Exception:
                pass
    
    def start_ghost_cursor(self):
        """Show a fake second cursor."""
        # This would require a separate overlay window
        # For simplicity, we'll skip complex implementation
        self.ghost_cursor_enabled = True
        print("[*] Ghost cursor enabled (placeholder)")
    
    def stop_ghost_cursor(self):
        self.ghost_cursor_enabled = False
    
    def shuffle_desktop_icons(self):
        """Randomly rearrange desktop icons using Shell automation."""
        try:
            ps_script = '''
            $shell = New-Object -ComObject Shell.Application
            $desktop = $shell.NameSpace(0)
            # Trigger desktop refresh to "shuffle" icons
            $desktop.Self.InvokeVerb("Arrange By")
            '''
            subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True
        except Exception as e:
            print(f"[-] Shuffle Icons Error: {e}")
            return False
    
    def set_wallpaper(self, data):
        """Set desktop wallpaper from image data."""
        try:
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
                f.write(data)
                temp_path = f.name
            
            # Set wallpaper using ctypes
            SPI_SETDESKWALLPAPER = 0x0014
            SPIF_UPDATEINIFILE = 0x01
            SPIF_SENDCHANGE = 0x02
            
            ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETDESKWALLPAPER, 0, temp_path,
                SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
            )
            return True
        except Exception as e:
            print(f"[-] Set Wallpaper Error: {e}")
            return False
    
    def show_overlay(self, overlay_type):
        """Show fake crack or hair overlay."""
        try:
            # For now, placeholder - would need overlay images
            print(f"[*] Show overlay: {overlay_type} (placeholder)")
            return True
        except Exception as e:
            print(f"[-] Overlay Error: {e}")
            return False
    
    def stop_overlay(self):
        """Stop overlay."""
        if self.overlay_process:
            try:
                self.overlay_process.terminate()
                self.overlay_process = None
            except Exception:
                pass
    
    # =========================================================================
    # Control
    # =========================================================================
    
    def stop_all(self):
        """Stop all active trolls."""
        self.stop_random_sounds()
        self.stop_alert_loop()
        self.stop_whisper()
        self.stop_ghost_cursor()
        self.stop_video()
        self.stop_overlay()
        
        # Stop any playing sounds
        if winsound:
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
