**Buffer Mode Lockout Explanation**
You mentioned being in "Buffer Mode". This is the likely culprit.

When you send text via Buffer Mode, the Agent's `pynput` library types it out character-by-character on the Target machine.
**If `pynput` hangs or gets flooded:**
1.  **Pynput Internal Lock:** The keyboard controller might be waiting for a key press to "complete" before processing physical keystrokes, effectively freezing the keyboard for the local user.
2.  **Focus Stealing:** If the "Typed" text triggers shortcuts (like opening menus), it can steal focus.

**Why Non-Admin?**
`pynput` works fine without admin, so a bug in its typing loop can absolutely freeze the input queue of the user's session.

**Next Step:**
I am checking the `type_text` function. If it lacks a delay or error handling, a long string could choke the input system. I will add safety checks to it.
