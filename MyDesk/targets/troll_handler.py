"""
Troll Handler - Fun pranks and visual/audio effects
"""
import subprocess
import os
import sys
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
        self.ghost_cursor_thread = None
        self.overlay_enabled = False
        self.overlay_thread = None
        self.video_process = None
        self._temp_video_path = None  # Track temp video file for cleanup
        self._wallpaper_temps = []  # Track temp wallpaper files for cleanup
    
    # =========================================================================
    # Browser
    # =========================================================================
    
    def open_url(self, url):
        """Open URL in default browser.
        
        Only opens http/https URLs for security.
        """
        try:
            # Validate URL scheme
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                print(f"[-] Invalid URL scheme: {parsed.scheme}. Only http/https allowed.")
                return False
            if not parsed.netloc:
                print("[-] Invalid URL: missing host")
                return False
            
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
        if not winsound:
            return False
            
        try:
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                f.write(data)
                temp_path = f.name
            
            def _play_and_cleanup(path):
                """Play sound then clean up temp file."""
                try:
                    if winsound:
                        winsound.PlaySound(path, winsound.SND_FILENAME)
                finally:
                    try:
                        os.remove(path)
                    except Exception:
                        pass  # Ignore cleanup errors
            
            # Play async with cleanup
            threading.Thread(target=_play_and_cleanup, args=(temp_path,), daemon=True).start()
            return True
        except Exception as e:
            print(f"[-] Play Sound Error: {e}")
            return False
    
    def start_random_sounds(self, interval_ms=5000):
        """Start playing random system sounds at intervals."""
        # Guard against duplicate threads
        if self.random_sound_enabled:
            return
        if self.random_sound_thread and self.random_sound_thread.is_alive():
            return
        
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
                # Ensure sleep duration is non-negative
                sleep_duration = max(0, interval_ms / 1000.0 + random.uniform(-1, 1))
                time.sleep(sleep_duration)
        
        self.random_sound_thread = threading.Thread(target=loop, daemon=True)
        self.random_sound_thread.start()
    
    def stop_random_sounds(self):
        self.random_sound_enabled = False
    
    def start_alert_loop(self):
        """Loop Windows error sound."""
        if self.alert_loop_enabled or (self.alert_loop_thread and self.alert_loop_thread.is_alive()):
            return

        self.alert_loop_enabled = True
        
        def loop():
            while self.alert_loop_enabled:
                if winsound:
                    try:
                        winsound.PlaySound('SystemHand', winsound.SND_ALIAS)
                    except Exception:
                        pass
                time.sleep(0.1)
        
        self.alert_loop_thread = threading.Thread(target=loop, daemon=True)
        self.alert_loop_thread.start()
    
    def stop_alert_loop(self):
        self.alert_loop_enabled = False
        if self.alert_loop_thread:
            self.alert_loop_thread = None
    
    def _check_nircmd(self):
        """Check if nircmd is available in PATH."""
        import shutil
        return shutil.which("nircmd") is not None
    
    def volume_max_sound(self):
        """Set volume to max and play sound.
        
        Requires: nircmd in PATH
        """
        if not self._check_nircmd():
            print("[-] nircmd not found in PATH. Cannot set volume.")
            return False
        
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
        """Play very loud distorted sound.
        
        Requires: nircmd in PATH
        """
        if not self._check_nircmd():
            print("[-] nircmd not found in PATH. Cannot set volume.")
            return False
        
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
        if self.whisper_enabled or (self.whisper_thread and self.whisper_thread.is_alive()):
            return

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
        if self.whisper_thread:
            self.whisper_thread = None
    
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
            
            # Store for cleanup
            self._temp_video_path = temp_path
            
            # Launch video player script
            script_dir = os.path.dirname(__file__)
            player_script = os.path.join(script_dir, 'troll_video_player.py')
            
            self.video_process = subprocess.Popen(
                [sys.executable, player_script, temp_path],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True
        except Exception as e:
            print(f"[-] Play Video Error: {e}")
            return False
    
    def stop_video(self):
        """Stop video player and clean up temp file."""
        if self.video_process:
            try:
                self.video_process.terminate()
                self.video_process = None
            except Exception:
                pass
        
        # Clean up temp video file
        if self._temp_video_path:
            try:
                os.remove(self._temp_video_path)
            except Exception:
                pass  # File may be locked or already deleted
            self._temp_video_path = None
    
    def start_ghost_cursor(self):
        """Show a fake second cursor (actually just erratic mouse movement)."""
        # Guard against duplicate threads
        if self.ghost_cursor_enabled:
            return
        if self.ghost_cursor_thread and self.ghost_cursor_thread.is_alive():
            return
        
        self.ghost_cursor_enabled = True
        
        def loop():
            user32 = ctypes.windll.user32
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            while self.ghost_cursor_enabled:
                # Random jumps
                if random.random() < 0.3:
                    x = random.randint(0, w - 1)
                    y = random.randint(0, h - 1)
                    # Clamp to display bounds
                    x = max(0, min(x, w - 1))
                    y = max(0, min(y, h - 1))
                    user32.SetCursorPos(x, y)
                # Jitter
                else:
                    pt = ctypes.wintypes.POINT()
                    user32.GetCursorPos(ctypes.byref(pt))
                    dx = random.randint(-50, 50)
                    dy = random.randint(-50, 50)
                    new_x = pt.x + dx
                    new_y = pt.y + dy
                    # Clamp to display bounds
                    new_x = max(0, min(new_x, w - 1))
                    new_y = max(0, min(new_y, h - 1))
                    user32.SetCursorPos(new_x, new_y)
                
                time.sleep(random.uniform(0.05, 0.2))
        
        self.ghost_cursor_thread = threading.Thread(target=loop, daemon=True)
        self.ghost_cursor_thread.start()
    
    def stop_ghost_cursor(self):
        self.ghost_cursor_enabled = False
    
    def shuffle_desktop_icons(self):
        """Trigger desktop arrange/refresh via Shell automation effectively shuffling icons."""
        try:
            ps_script = '''
            $shell = New-Object -ComObject Shell.Application
            $desktop = $shell.NameSpace(0)
            # Trigger desktop refresh to "shuffle" icons
            $desktop.Self.InvokeVerb("Arrange By")
            '''
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
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
            # Clean up previous temp wallpaper files
            for old_path in self._wallpaper_temps[:]:
                try:
                    if os.path.exists(old_path):
                        os.remove(old_path)
                    self._wallpaper_temps.remove(old_path)
                except Exception:
                    pass  # Ignore if file is locked
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
                f.write(data)
                temp_path = f.name
            
            # Track for future cleanup
            self._wallpaper_temps.append(temp_path)
            
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
    
    def show_overlay(self, overlay_type="xor"):
        """Show GDI artifacts on screen.
        
        Args:
            overlay_type: "xor", "invert", "clear", or "random"
        """
        self.overlay_enabled = True
        
        # Determine raster operation based on overlay_type
        raster_ops = {
            "xor": 0x005A0049,      # PATINVERT (XOR)
            "invert": 0x00660046,   # DSTINVERT
            "clear": None,          # Will use InvalidateRect
            "random": None          # Will randomize each frame
        }
        
        # Guard against duplicates
        if self.overlay_thread and self.overlay_thread.is_alive():
             return

        def loop():
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            hdc = getattr(user32, 'GetDC', lambda x: 0)(0)
            if not hdc: return

            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            
            try:
                while self.overlay_enabled:
                    x = random.randint(0, w)
                    y = random.randint(0, h)
                    width = random.randint(10, 300)
                    height = random.randint(10, 300)
                    
                    if overlay_type == "clear":
                        user32.InvalidateRect(0, 0, True)
                    elif overlay_type == "random":
                        # Randomize raster operation each frame
                        rop = random.choice([0x005A0049, 0x00660046, 0x00550009])
                        gdi32.PatBlt(hdc, x, y, width, height, rop)
                    else:
                        # Use specified raster operation
                        rop = raster_ops.get(overlay_type, 0x005A0049)
                        gdi32.PatBlt(hdc, x, y, width, height, rop)
                    
                    time.sleep(0.1)
                    
                    # Occasionally clear to prevent total unusability
                    if random.random() < 0.05:
                        user32.InvalidateRect(0, 0, True)
            finally:
                # Cleanup GDI resources
                try:
                    user32.ReleaseDC(0, hdc)
                    user32.InvalidateRect(0, 0, True)
                except: pass

        self.overlay_thread = threading.Thread(target=loop, daemon=True)
        self.overlay_thread.start()
    
    def stop_overlay(self):
        """Stop overlay."""
        self.overlay_enabled = False
    
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
        
        # Clean up temp wallpaper files
        for path in self._wallpaper_temps[:]:
            try:
                if os.path.exists(path):
                    os.remove(path)
                self._wallpaper_temps.remove(path)
            except Exception:
                pass  # Ignore errors
        
        # Stop any playing sounds
        if winsound:
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
# alr 
