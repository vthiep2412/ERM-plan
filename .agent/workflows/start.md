---
description: # 🤖 Instructions for the Next Agent
---

Hello! You are picking up the **MyDesk** project. This is a Remote Administration Tool (RAT) / Remote Support application.

## 🚨 IMMEDIATE ACTIONS
1. **Read `memories.md`**: This file contains the high-level context, architectural decisions, and current status. **Do this first.**
2. **Read `README.md`**: This gives you the usage instructions and component overview.
3. **Check `task.md`** (if available/persisted) or start a new one based on the user's request.

## 📂 Key Codebase Areas
- **Protocol**: `MyDesk/core/protocol.py` - *The dictionary of the app.*
- **Broker**: `MyDesk/broker/server.py` - *The switchboard.*
- **Agent**: `MyDesk/agent_loader.py` - *The client.*

## ✍️ Updating Memories
Your goal is not just to code, but to maintain the continuity of intelligence.
- If you **add a feature**, update `memories.md` to reflect the new capability.
- If you **refactor code**, note the structural changes in `memories.md`.
- If you **encounter a bug** that you can't fix immediately, log it in `memories.md` under a "Known Issues" section.

**Go forth and code efficiently!**
