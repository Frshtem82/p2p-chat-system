<div align="center">

# 🌐 P2P Chat System

**A peer-to-peer chat application with STUN-based discovery, direct TCP messaging, and file transfer.**

![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Docker](https://img.shields.io/badge/Docker-Supported-2496ED.svg)
![Tests](https://img.shields.io/badge/Tests-pytest-orange.svg)

[Features](#-features) • [Architecture](#-architecture) • [Quick Start](#-quick-start) • [Documentation](#-documentation)

</div>

---

## 📖 Overview

A fully-featured **peer-to-peer chat system** built with Python's standard library. Peers register with a central **STUN server** for discovery, then communicate **directly** via TCP — no message relay.

This project demonstrates:
- **HTTP server** implementation (STUN server)
- **TCP socket programming** (peer-to-peer messaging)
- **Multithreading** for concurrent connections
- **File transfer** with SHA256 integrity verification
- **Docker** containerization
- **Event-driven architecture** shared between terminal and GUI clients

---

## ✨ Features

### Core
- 🔍 **STUN Server (HTTP)** — peer registration and discovery
- 🔗 **Direct TCP Chat** — no relay server, real P2P
- ✅ **Accept/Reject** incoming connection requests
- 🧵 **Threaded server** — handles multiple concurrent requests
- 🛡️ **Graceful error handling** — disconnects, duplicates, invalid input

### Bonus
- 💾 **Redis Storage** (optional) — persistent backend with automatic fallback to in-memory
- 📁 **File Transfer** — any file type/size with SHA256 integrity check
- 🐳 **Docker Compose** — one command to run the whole system
- 🖥️ **GUI + TUI** — both terminal and graphical clients share the same core

---

## 🏗️ Architecture

```
┌──────────────┐    HTTP     ┌──────────────┐    HTTP     ┌──────────────┐
│   Peer A     │ ──────────► │  STUN Server │ ◄────────── │   Peer B     │
│  (TUI/GUI)   │ ◄────────── │   (Port 8000)│ ──────────► │  (TUI/GUI)   │
└──────┬───────┘  /register  └──────────────┘  /register  └──────┬───────┘
       │         /peers                                         │
       │         /peerinfo                                      │
       │                                                        │
       │              Direct TCP Connection                     │
       │ ◄────────────────────────────────────────────────────► │
       │        Messages + File Transfer (P2P)                  │
```

**Key idea:** STUN is only used for **discovery**. Once peers know each other's IP:port, they talk **directly**.

### Project Structure

```
NET-Project/
├── shared/                  # 🌟 Code shared between terminal + GUI
│   ├── constants.py         #    Protocol constants
│   ├── protocol.py          #    Message factory + buffer
│   ├── file_transfer.py     #    Hashing, chunking, formatting
│   ├── network_utils.py     #    Socket + HTTP helpers
│   └── peer_core.py         #    PeerNode (the heart)
│
├── stun_server/             # 🔍 Registration + discovery
│   ├── config.py            #    CLI args parsing
│   ├── storage.py           #    Memory / Redis backends
│   ├── handler.py           #    HTTP request handler
│   └── server.py            #    Entry point
│
├── peer/                    # 🔗 Peer nodes
│   ├── peer.py              #    Terminal version (TUI)
│   ├── peer_gui.py          #    GUI entry point
│   └── peer_client.py       #    High-level STUN client
│
├── gui/                     # 🖥️ Tkinter GUI
│   ├── styles.py            #    Colors, fonts, theme
│   ├── login_view.py        #    Login screen
│   ├── peers_panel.py       #    Sidebar
│   ├── chat_panel.py        #    Chat area
│   ├── main_view.py         #    Main layout
│   └── app.py               #    Application controller
│
├── tests/                   # 🧪 pytest suite
├── scripts/                 # 🚀 Launch helpers
├── docker-compose.yml       # 🐳 Full stack
└── README.md
```

---

## 🚀 Quick Start

### Option 1: Run Locally (Recommended for first try)

**Prerequisites:** Python 3.8+

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/p2p-chat.git
cd p2p-chat

# 2. (Optional) Install extras
pip install -r requirements.txt

# 3. Start STUN server (Terminal 1)
python -m stun_server.server --no-redis

# 4. Start Peer 1 (Terminal 2)
python -m peer.peer
# Enter: alice / 9000 / http://localhost:8000

# 5. Start Peer 2 (Terminal 3)
python -m peer.peer
# Enter: bob / 9001 / http://localhost:8000

# 6. In alice's window: menu → 2 → bob
# 7. In bob's window:   menu → 3 → y
# 8. Chat! 🎉
```

### Option 2: GUI Client

```bash
python -m peer.peer_gui
```

### Option 3: Docker (Everything at once)

```bash
docker-compose up --build
```

Then attach to peers:
```bash
docker attach p2p-peer1    # alice
docker attach p2p-peer2    # bob
```

### Option 4: One-shot Script

```bash
# Linux / macOS
./scripts/run_all.sh

# Windows
scripts\run_all.bat
```

---

## 📚 Documentation

### STUN Server API

All responses are JSON. Errors use `{"error": "..."}`.

| Method | Endpoint | Body / Query | Success | Errors |
|--------|----------|--------------|---------|--------|
| `POST` | `/register`   | `{username, ip, port}` | `201` | `400`, `409` |
| `POST` | `/unregister` | `{username}`           | `200` | `400`, `404` |
| `GET`  | `/peers`      | —                      | `200` | — |
| `GET`  | `/peerinfo`   | `?username=alice`      | `200` | `400`, `404` |
| `GET`  | `/health`     | —                      | `200` | — |

### TCP Message Protocol

All messages are **newline-delimited JSON**.

| Type | Direction | Purpose |
|------|-----------|---------|
| `connection_request` | initiator → receiver | ask to chat |
| `connection_response`| receiver → initiator | accept / reject |
| `chat_message`       | both ways            | text message |
| `disconnect`         | both ways            | end chat |
| `file_init`          | sender → receiver    | file metadata |
| `file_chunk`         | sender → receiver    | base64 chunk |
| `file_complete`      | sender → receiver    | hash + verify |

**Example — chat message:**
```json
{"type": "chat_message", "username": "alice", "message": "Hi!", "timestamp": 1700000000}
```

### File Transfer

```
Sender                              Receiver
  │                                    │
  │──── file_init (name, size, hash) ─►│
  │──── file_chunk #0 ───────────────►│
  │──── file_chunk #1 ───────────────►│
  │         ...                        │
  │──── file_complete (hash) ────────►│ → SHA256 verify
```

- Chunk size: **8 KB**
- Encoding: **base64**
- Integrity: **SHA256**
- Save location: `peer/received_files/`
- Duplicate handling: auto-rename with `_1`, `_2`, ...

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Only server tests
pytest tests/test_server.py -v

# Only file transfer tests
pytest tests/test_file_transfer.py -v
```

Tests use **real** servers/peers on random ports — no mocks.

---

## 🛠️ Development

### Requirements

```bash
pip install -r requirements.txt
```

**Core** (STUN + peers): Python 3.8+ stdlib only  
**Optional**: `redis`, `requests`, `pytest`

### Running Tests Continuously

```bash
pytest tests/ -v --tb=short
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| `Username already exists` | Pick a different name, or restart STUN server |
| `Connection refused` to STUN | Make sure STUN server is running and URL is correct |
| `Connection refused` to peer | Peer may be offline, or port blocked by firewall |
| Redis error | Install Redis, or use `--no-redis` |
| GUI doesn't open | Ensure you're on a desktop environment with Tk installed |
| `ModuleNotFoundError` | Run from project root with `python -m ...` |

---

## 🎓 What I Learned

- Building an HTTP server from scratch with `http.server`
- TCP socket programming (stream framing, partial reads)
- Multithreading and thread-safe state management
- Event-driven architecture to share code between TUI and GUI
- SHA256 for file integrity
- Docker containerization and inter-container networking
- Writing tests with `pytest` using real network I/O

---

<div align="center">

**⭐ If you found this useful, consider giving it a star!**

</div>