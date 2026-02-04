# MyDesk Testing Checklist

## 🔌 Connection
- [x] Direct WS connection (`ws://localhost:8765`)
- [x] Cloudflare tunnel connection (`wss://...trycloudflare.com`)
- [x] Broker connection (if using)
- [x] Reconnection after disconnect

## 🖥️ Screen Streaming
- [x] Stream starts on connect
- [ ] Quality adjustment works
- [ ] No freezing / smooth FPS
- [ ] Window resize works

## 🖱️ Input Controls
- [ ] Mouse move (accurate positioning)
- [ ] Left click / Right click
- [ ] Mouse drag
- [ ] Scroll (vertical + horizontal)
- [ ] Keyboard letters (A-Z)
- [ ] Special keys (Shift, Ctrl, Alt, Tab, Enter, Backspace)
- [ ] Arrow keys (Up, Down, Left, Right)
- [ ] Space key works
- [ ] Block Input toggle works

## 📷 Webcam
- [ ] Toggle on → agent starts camera
- [ ] Webcam window shows frames
- [ ] Toggle off → agent stops camera
- [ ] Error message if no camera found
- [ ] Toggle unchecks on error

## 🎙️ Microphone
- [ ] Toggle on → agent starts mic
- [ ] Audio heard in viewer
- [ ] Toggle off → agent stops mic
- [ ] Error message if no mic found
- [ ] Toggle unchecks on error
- [ ] Mic restart recovery works

## 🔒 Privacy Curtain
- [ ] Black screen curtain
- [ ] Fake Update curtain (kiosk)
- [ ] Custom image curtain
- [ ] Curtain off → restores screen
- [ ] Kiosk exit: `Ctrl+Shift+Alt+\`` (only works in kiosk mode, backtick is needed)

## ⌨️ Keylogger
- [ ] Toggle shows log window
- [ ] Keys appear in log
- [ ] Toggle hides log

## 📜 History
- [ ] New connection added to history
- [ ] Same URL+ID updates timestamp (no duplicate)
- [ ] History entries are clickable
- [ ] Delete history entry works

## ⚙️ Settings Persistence
- [ ] Config saved to `viewer_config.json`
- [ ] Broker URL saved
- [ ] History saved

## 🔄 Error Handling
- [ ] Agent crash → viewer shows disconnect
- [ ] Invalid URL → error message
- [ ] Device error → warning (no disconnect)
- [ ] Large File Upload (>100MB) → Blocked with warning

## ⚙️ Device Controls
- [ ] WiFi/Ethernet toggle
- [ ] Volume/Mute/Brightness
- [ ] Power Actions (Sleep/Lock) - Use with caution!

---

## 🧪 Test Commands

```powershell
# Start Agent
python MyDesk/target/agent.py

# Start Viewer
python MyDesk/viewer/main.py

# Test Kiosk Standalone
python MyDesk/target/kiosk.py
```
