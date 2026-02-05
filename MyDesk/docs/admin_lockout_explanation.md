**Answer: Yes, correct.**
The Windows command `BlockInput` **only works if the Agent is running as Administrator**.
If the Agent is running as a normal user, clicking "Lock Input" will seemingly do nothing (it fails silently or logs an "Access Denied" error).

**However, regarding your friend getting "Randomly Locked Out":**
If your friend was **NOT** running as Admin and still got locked out, `BlockInput` wasn't the cause. The "Lockout" was likely caused by one of these "Troll" features which **DO WORK** without Admin:

1.  **Ghost Cursor:** It fights for control of the mouse, making it fast impossible to click anything.
2.  **Fake Update / Curtain:** It forces a fullscreen window that grabs focus, preventing Alt-Tab.
3.  **Infinite Alert Loop:** Can spam focus stealing dialogs.

The new **"🚫 Lock Input"** button I added allows you to *intentionally* use the Admin-level block. If you see them locked out again, check if any "Troll" features (Ghost, Curtain) are active in the toolbar and disable them.
