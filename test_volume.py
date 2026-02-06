import subprocess
import time

def set_mute(mute_status: bool):
    """
    Mutes or Unmutes the system audio using C# reflection via PowerShell.
    True = Mute, False = Unmute.
    """
    # Convert Python boolean to PowerShell boolean syntax
    ps_bool = "$true" if mute_status else "$false"
    
    # The Fixed PowerShell Script (Flush-left to avoid indentation errors)
    ps_script = f'''
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAudioEndpointVolume {{
    // VTable Padding: Matches Windows Core Audio API order
    int f(); int g(); int h(); int i();
    int SetMasterVolumeLevelScalar(float fLevel, Guid pguidEventContext);
    int j();
    int GetMasterVolumeLevelScalar(out float pfLevel);
    int k(); int l(); int m(); int n();
    int SetMute([MarshalAs(UnmanagedType.Bool)] bool bMute, Guid pguidEventContext);
    int GetMute(out bool pbMute);
}}

[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDevice {{
    // Activate is Index 0
    int Activate(ref Guid id, int clsCtx, IntPtr activationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
}}

[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDeviceEnumerator {{
    // FIXED: Added dummy 'f' so GetDefaultAudioEndpoint hits Index 1
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

    # Execute the PowerShell command silently
    try:
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script]
        # Use simple subprocess run
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"[-] Error Muting/Unmuting: {result.stderr.strip()}")
        else:
            state = "MUTED" if mute_status else "UNMUTED"
            print(f"[+] System Audio is now: {state}")
            
    except Exception as e:
        print(f"[-] Execution Failed: {e}")

# --- TEST SECTION ---
if __name__ == "__main__":
    print("[*] Testing Audio Mute Logic...")
    
    # 1. Mute
    set_mute(True)
    
    # 2. Wait so you can verify
    print("[*] Waiting 3 seconds (check your speaker icon)...")
    time.sleep(3)
    
    # 3. Unmute
    set_mute(False)
    
    print("[*] Test Complete.")