"""
Device Settings Handler - Control WiFi, volume, brightness, time, power
"""
import subprocess
import ctypes
import json
import platform
from datetime import datetime

try:
    import psutil
except ImportError:
    psutil = None


class DeviceSettings:
    """Handles device settings control on Windows."""
    
    def __init__(self):
        pass
    
    # =========================================================================
    # Network
    # =========================================================================
    
    def set_wifi(self, enabled):
        """Enable or disable WiFi adapter."""
        action = "enable" if enabled else "disable"
        try:
            # Try common WiFi interface names
            for name in ["Wi-Fi", "WiFi", "Wireless Network Connection"]:
                result = subprocess.run(
                    ["netsh", "interface", "set", "interface", name, action],
                    capture_output=True, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode == 0:
                    print(f"[+] WiFi {action}d")
                    return True
            print("[-] WiFi interface not found")
            return False
        except Exception as e:
            print(f"[-] WiFi Error: {e}")
            return False
    
    def set_ethernet(self, enabled):
        """Enable or disable Ethernet adapter."""
        action = "enable" if enabled else "disable"
        try:
            for name in ["Ethernet", "Local Area Connection"]:
                result = subprocess.run(
                    ["netsh", "interface", "set", "interface", name, action],
                    capture_output=True, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode == 0:
                    print(f"[+] Ethernet {action}d")
                    return True
            print("[-] Ethernet interface not found")
            return False
        except Exception as e:
            print(f"[-] Ethernet Error: {e}")
            return False
    
    # =========================================================================
    # Audio
    # =========================================================================
    
    def set_volume(self, level):
        """Set system volume (0-100).
        
        Uses nircmd if available, otherwise attempts PowerShell.
        """
        level = max(0, min(100, level))
        try:
            # Method 1: nircmd (if installed)
            result = subprocess.run(
                ["nircmd", "setsysvolume", str(int(level * 655.35))],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                return True
        except FileNotFoundError:
            pass
        
        # Method 2: PowerShell with AudioDeviceCmdlets or direct COM
        try:
            ps_script = f'''
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAudioEndpointVolume {{
    // Needs 4 dummies to skip: Register, Unregister, GetChannelCount, SetMasterVolumeLevel
    int f(); int g(); int h(); int i();
    int SetMasterVolumeLevelScalar(float fLevel, Guid pguidEventContext);
}}

[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDevice {{
    // Activate is the very 1st method. No dummies needed.
    int Activate(ref Guid id, int clsCtx, IntPtr activationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
}}

[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDeviceEnumerator {{
    // Needs 1 dummy to skip: EnumAudioEndpoints
    int f();
    int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppDevice);
}}

[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
public class MMDeviceEnumeratorComObject {{ }}

public class Audio {{
    public static void SetVolume(float v) {{
        var enumerator = new MMDeviceEnumeratorComObject() as IMMDeviceEnumerator;
        IMMDevice dev = null;
        // 0 = eRender, 1 = eConsole
        enumerator.GetDefaultAudioEndpoint(0, 1, out dev);
        
        var iid = new Guid("5CDF2C82-841E-4546-9722-0CF74078229A");
        object volObj;
        dev.Activate(ref iid, 23, IntPtr.Zero, out volObj);
        
        var vol = volObj as IAudioEndpointVolume;
        vol.SetMasterVolumeLevelScalar(v, Guid.Empty);
    }}
}}
"@
[Audio]::SetVolume([float]({level / 100.0}))
'''
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                return True
            else:
                print(f"[-] Volume PowerShell Error: {result.stderr.decode() if result.stderr else 'Unknown error'}")
                return False
        except Exception as e:
            print(f"[-] Volume Error: {e}")
            return False
    
    def set_mute(self, muted):
        """Mute or unmute system audio."""
        # Method 1: Try nircmd
        try:
            action = "1" if muted else "0"
            result = subprocess.run(
                ["nircmd", "mutesysvolume", action],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                return True
        except FileNotFoundError:
            pass
        
        # Method 2: PowerShell fallback
        try:
            # Convert Python bool to PowerShell boolean string
            ps_bool = "$true" if mute_val else "$false"

            ps_script = f'''
            Add-Type -TypeDefinition @"
            using System;
            using System.Runtime.InteropServices;

            [Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
            public interface IAudioEndpointVolume {{
                // VTable Padding: These match the Windows header file order
                int f(); int g(); int h(); int i();
                int SetMasterVolumeLevelScalar(float fLevel, Guid pguidEventContext);
                int j();
                int GetMasterVolumeLevelScalar(out float pfLevel);
                int k(); int l(); int m(); int n();
                
                // SetMute is correctly placed at Index 11 (after 4 dummies k,l,m,n)
                int SetMute([MarshalAs(UnmanagedType.Bool)] bool bMute, Guid pguidEventContext);
                int GetMute(out bool pbMute);
            }}

            [Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
            public interface IMMDevice {{
                // Activate is Index 0. No dummies needed.
                int Activate(ref Guid id, int clsCtx, IntPtr activationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
            }}

            [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
            public interface IMMDeviceEnumerator {{
                // FIXED: Added dummy 'f' so GetDefaultAudioEndpoint hits the right Index (1)
                int f();
                int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppDevice);
            }}

            [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
            public class MMDeviceEnumeratorComObject {{ }}

            public class Audio {{
                public static void SetMute(bool mute) {{
                    var enumerator = new MMDeviceEnumeratorComObject() as IMMDeviceEnumerator;
                    IMMDevice dev = null;
                    enumerator.GetDefaultAudioEndpoint(0, 1, out dev);
                    
                    var iid = new Guid("5CDF2C82-841E-4546-9722-0CF74078229A");
                    object volObj;
                    dev.Activate(ref iid, 23, IntPtr.Zero, out volObj);
                    
                    var vol = volObj as IAudioEndpointVolume;
                    vol.SetMute(mute, Guid.Empty);
                }}
            }}
            "@
            [Audio]::SetMute({ps_bool})
            '''
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                return True
            else:
                print(f"[-] Mute PowerShell Error: {result.stderr.decode() if result.stderr else 'Unknown error'}")
                return False
        except Exception as e:
            print(f"[-] Mute Error: {e}")
            return False
    
    # =========================================================================
    # Display
    # =========================================================================
    
    def set_brightness(self, level):
        """Set screen brightness (0-100)."""
        level = max(0, min(100, level))
        try:
            # Use WMI via PowerShell
            ps_cmd = f'(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})'
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode != 0:
                print(f"[-] Brightness PowerShell Error: {result.stderr.decode() if result.stderr else 'Unknown'}")
                return False
            return True
        except Exception as e:
            print(f"[-] Brightness Error: {e}")
            return False
    
    # =========================================================================
    # Date & Time
    # =========================================================================
    
    def set_time(self, iso_datetime):
        """Set system time from ISO8601 string using PowerShell (locale-independent)."""
        try:
            dt = datetime.fromisoformat(iso_datetime.replace('Z', '+00:00'))
            
            # Normalize to local timezone
            if dt.tzinfo:
                dt = dt.astimezone()

            # Use PowerShell Set-Date which is locale-independent
            ps_script = f"Set-Date -Date '{dt.strftime('%Y-%m-%d %H:%M:%S')}'"
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                return True
            else:
                print(f"[-] Set Time Error: {result.stderr.decode() if result.stderr else 'Unknown error'}")
                return False
        except Exception as e:
            print(f"[-] Set Time Error: {e}")
            return False
    
    def sync_time(self):
        """Sync time with NTP server."""
        try:
            result = subprocess.run(
                ["w32tm", "/resync", "/nowait"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode != 0:
                # Try starting Windows Time service
                print(f"[!] Time sync failed (code {result.returncode}), attempting to start w32time...")
                start_result = subprocess.run(
                    ["sc", "start", "w32time"],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if start_result.returncode != 0:
                    print(f"[-] Failed to start w32time: {start_result.stderr.decode() if start_result.stderr else 'Unknown'}")
                    return False
                
                # Retry loop (wait for service)
                import time
                for _ in range(3):
                    time.sleep(2)
                    result = subprocess.run(
                        ["w32tm", "/resync", "/nowait"],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    if result.returncode == 0:
                        return True
                
                return False
            return True
        except Exception as e:
            print(f"[-] Sync Time Error: {e}")
            return False
    
    # =========================================================================
    # Power
    # =========================================================================
    
    def power_action(self, action):
        """Execute power action.
        
        Args:
            action: sleep|restart|shutdown|lock|logoff
        """
        try:
            if action == "sleep":
                # Requires SetSuspendState
                ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
            elif action == "restart":
                subprocess.run(["shutdown", "/r", "/t", "0"], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            elif action == "shutdown":
                subprocess.run(["shutdown", "/s", "/t", "0"], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            elif action == "lock":
                ctypes.windll.user32.LockWorkStation()
            elif action == "logoff":
                subprocess.run(["shutdown", "/l"], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                print(f"[-] Unknown power action: {action}")
                return False
            return True
        except Exception as e:
            print(f"[-] Power Action Error: {e}")
            return False
    
    # =========================================================================
    # System Info
    # =========================================================================
    
    def get_sysinfo(self):
        """Get system information.
        
        Returns:
            dict with os, cpu, ram, disk, battery, wifi_available, uptime
        """
        info = {}
        
        # OS
        info['os'] = f"{platform.system()} {platform.release()} ({platform.version()})"
        
        # CPU
        # Try to get detailed CPU name via PowerShell (WMIC is deprecated)
        try:
            cpu_name = subprocess.check_output(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "(Get-CimInstance Win32_Processor).Name"], 
                creationflags=subprocess.CREATE_NO_WINDOW
            ).decode().strip()
        except Exception:
            # Silent fallback to platform.processor()
            cpu_name = platform.processor()
            
        info['cpu'] = cpu_name
        if psutil:
            # interval=0.1 avoids blocking too long but gives instant reading (better than 0.0)
            info['cpu'] += f" ({psutil.cpu_percent(interval=0.1)}%)"
        
        # RAM
        if psutil:
            mem = psutil.virtual_memory()
            info['ram'] = f"{mem.used / (1024**3):.1f} GB / {mem.total / (1024**3):.1f} GB ({mem.percent}%)"
        
        # Disk
        if psutil:
            disk = psutil.disk_usage('/')
            info['disk'] = f"{disk.used / (1024**3):.1f} GB / {disk.total / (1024**3):.1f} GB ({disk.percent}%)"
        
        # Battery
        if psutil:
            battery = psutil.sensors_battery()
            if battery:
                status = "Charging" if battery.power_plugged else "Discharging"
                info['battery'] = f"{battery.percent}% ({status})"
            else:
                info['battery'] = "No battery"
        
        # Uptime
        if psutil:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            hours, remainder = divmod(int(uptime.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            info['uptime'] = f"{hours}h {minutes}m {seconds}s"
        
        # WiFi available
        info['wifi_available'] = self._check_wifi_available()
        
        return info
    
    def _check_wifi_available(self):
        """Check if WiFi adapter exists."""
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return "State" in result.stdout
        except Exception:
            return False
    
    def to_json(self, info):
        """Convert sysinfo to JSON bytes."""
        return json.dumps(info).encode('utf-8')
# This line was added at the bottom to force re-check. 
