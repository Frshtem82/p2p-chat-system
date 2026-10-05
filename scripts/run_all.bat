@echo off
REM Run STUN server + 2 peers in separate cmd windows.
REM Usage: scripts\run_all.bat

setlocal

set "ROOT=%~dp0.."
cd /d "%ROOT%"

echo [+] Starting P2P Chat System from: %CD%

REM STUN Server
start "STUN Server" cmd /k "cd /d "%ROOT%" && python -m stun_server.server --no-redis"
timeout /t 2 /nobreak >nul

REM Peers
start "Peer 1 (alice)" cmd /k "cd /d "%ROOT%" && python -m peer.peer"
start "Peer 2 (bob)"   cmd /k "cd /d "%ROOT%" && python -m peer.peer"

echo [+] All services launched.
echo [!] In each peer window, enter:
echo         alice / 9000 / http://localhost:8000
echo         bob   / 9001 / http://localhost:8000

endlocal