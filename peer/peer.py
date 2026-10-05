#!/usr/bin/env python3
"""
P2P Chat System - Terminal (TUI) Client

This is the terminal interface. All P2P logic lives in shared.peer_core.PeerNode.
This file handles:
    - Reading user input
    - Displaying menus and prompts
    - Rendering chat messages, file progress, etc.

Run from project root:
    python -m peer.peer
"""

import sys
import os
import threading
import time
from typing import Optional

# Ensure project root is on sys.path when run as a script
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from shared.peer_core import PeerNode
from shared.constants import (
    DEFAULT_TCP_PORT, DEFAULT_STUN_URL,
    Colors,
)
from shared.file_transfer import FileTransfer


# ─────────────────────────────────────────────────────────────────────────────
# ANSI helpers
# ─────────────────────────────────────────────────────────────────────────────

def c(text: str, color: str) -> str:
    """Wrap text with ANSI color and reset."""
    return f"{color}{text}{Colors.RESET}"


def info(msg: str) -> None:
    print(f"{Colors.CYAN}[*]{Colors.RESET} {msg}")


def success(msg: str) -> None:
    print(f"{Colors.GREEN}[+]{Colors.RESET} {msg}")


def error(msg: str) -> None:
    print(f"{Colors.RED}[-]{Colors.RESET} {msg}")


def warn(msg: str) -> None:
    print(f"{Colors.YELLOW}[!]{Colors.RESET} {msg}")


def banner(title: str) -> None:
    line = "─" * 60
    print(f"\n{line}\n  {title}\n{line}")


# ─────────────────────────────────────────────────────────────────────────────
# Terminal UI
# ─────────────────────────────────────────────────────────────────────────────

class TerminalUI:
    """
    Terminal user interface for a P2P peer.
    
    Subscribes to PeerNode events and renders them in the terminal.
    Provides an interactive menu loop.
    """
    
    def __init__(self, peer: PeerNode):
        self.peer = peer
        self._shutdown = False
        self._prompt_lock = threading.Lock()
        self._input_active = False
        self._register_events()
    
    # ─────────────────────────────────────────────────────────────────────
    # Event Handlers
    # ─────────────────────────────────────────────────────────────────────
    
    def _register_events(self) -> None:
        """Subscribe to PeerNode events."""
        e = self.peer.events
        e.on("registered", self._on_registered)
        e.on("register_failed", self._on_register_failed)
        e.on("peer_connected", self._on_peer_connected)
        e.on("peer_disconnected", self._on_peer_disconnected)
        e.on("chat_message", self._on_chat_message)
        e.on("connection_request", self._on_connection_request)
        e.on("file_incoming", self._on_file_incoming)
        e.on("file_progress", self._on_file_progress)
        e.on("file_complete", self._on_file_complete)
        e.on("error", self._on_error)
    
    def _on_registered(self, username, ip, port, **_):
        success(f"Registered as '{username}' ({ip}:{port})")
    
    def _on_register_failed(self, reason, **_):
        error(f"Registration failed: {reason}")
    
    def _on_peer_connected(self, peer, **_):
        print()
        success(f"Connected to '{peer}'! You can start chatting.")
        self._print_chat_help()
    
    def _on_peer_disconnected(self, peer, reason, **_):
        print()
        warn(f"Disconnected from '{peer}' ({reason})")
    
    def _on_chat_message(self, sender, message, timestamp, **_):
        ts = time.strftime("%H:%M:%S", time.localtime(timestamp))
        # Use a newline prefix so it doesn't mix with any active prompt
        print(f"\n  {c(f'[{ts}]', Colors.GRAY)} "
              f"{c(f'{sender}:', Colors.GREEN)} {message}")
        if self.peer.is_chatting:
            print(f"  {c('You:', Colors.BLUE)} ", end="", flush=True)
    
    def _on_connection_request(self, from_peer, **_):
        print()
        warn(f"Incoming connection request from '{from_peer}'")
        info("Use menu option 3 to accept or reject.")
    
    def _on_file_incoming(self, sender, filename, filesize, save_path, **_):
        print()
        info(f"Incoming file from '{sender}': {filename} "
             f"({FileTransfer.format_size(filesize)})")
        info(f"Saving to: {save_path}")
    
    def _on_file_progress(self, direction, filename, progress, sent, total, **_):
        arrow = ">" if direction == "send" else "<"
        verb = "Sending" if direction == "send" else "Receiving"
        bar = self._progress_bar(progress)
        sys.stdout.write(
            f"\r  [{arrow}] {verb}: {bar} {progress:5.1f}% "
            f"({FileTransfer.format_size(sent)}/{FileTransfer.format_size(total)})"
        )
        sys.stdout.flush()
    
    def _on_file_complete(self, filename, success, path, hash_match,
                          direction, **_):
        print()  # finish the progress line
        if direction == "send":
            if success:
                success(f"File '{filename}' sent successfully")
            else:
                error(f"Failed to send '{filename}'")
        else:
            if hash_match:
                success(f"File '{filename}' received successfully")
                success(f"Integrity check PASSED (SHA256 match)")
                success(f"Saved to: {path}")
            else:
                error(f"File '{filename}' received but integrity FAILED")
                error(f"Saved to: {path}")
    
    def _on_error(self, message, **_):
        print()
        error(message)
    
    @staticmethod
    def _progress_bar(percent: float, width: int = 20) -> str:
        """Render a simple ASCII progress bar."""
        filled = int(width * percent / 100)
        return "[" + "█" * filled + "░" * (width - filled) + "]"
    
    # ─────────────────────────────────────────────────────────────────────
    # Menus
    # ─────────────────────────────────────────────────────────────────────
    
    def run(self) -> None:
        """Main entry point: register, then show menu loop."""
        banner(f"P2P Chat System — {self.peer.username}")
        print(f"  TCP Port:     {self.peer.tcp_port}")
        print(f"  Local IP:     {self.peer.tcp_ip}")
        print(f"  STUN Server:  {self.peer.stun_url}")
        
        # Register + start server
        info("Starting peer...")
        if not self.peer.start():
            error("Failed to start peer. Exiting.")
            return
        
        # Main loop
        try:
            self._main_menu_loop()
        except KeyboardInterrupt:
            print()
            info("Interrupted.")
        finally:
            self.shutdown()
    
    def _main_menu_loop(self) -> None:
        """Show menu until user exits."""
        while not self._shutdown:
            if self.peer.is_chatting:
                self._chat_loop()
            else:
                self._show_main_menu()
    
    def _show_main_menu(self) -> None:
        """Show main menu and handle choice."""
        banner("Main Menu")
        print("  1. List online peers")
        print("  2. Connect to a peer")
        print("  3. Accept/Reject pending request")
        print("  4. Exit")
        print("─" * 60)
        
        try:
            choice = input("  Select option: ").strip()
        except (EOFError, KeyboardInterrupt):
            self._shutdown = True
            return
        
        if choice == "1":
            self._list_peers()
        elif choice == "2":
            self._connect_menu()
        elif choice == "3":
            self._pending_menu()
        elif choice == "4":
            self._shutdown = True
        else:
            error("Invalid option")
    
    # ─────────────────────────────────────────────────────────────────────
    # Menu Actions
    # ─────────────────────────────────────────────────────────────────────
    
    def _list_peers(self) -> None:
        info("Fetching peer list...")
        peers = self.peer.list_peers()
        if not peers:
            warn("No other peers online.")
            return
        print(f"\n  Online peers ({len(peers)}):")
        for i, p in enumerate(peers, 1):
            print(f"    {i}. {p['username']}  "
                  f"{c(f'({p.get(chr(105)+chr(112), '?')}:{p.get(chr(112)+chr(111)+chr(114)+chr(116), '?')})', Colors.GRAY)}")
    
    def _connect_menu(self) -> None:
        try:
            target = input("  Enter username to connect: ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not target:
            return
        
        info(f"Connecting to '{target}'...")
        if self.peer.connect_to_peer(target):
            self._chat_loop()
    
    def _pending_menu(self) -> None:
        if not self.peer.has_pending_request():
            warn("No pending connection requests.")
            return
        
        peer_name = self.peer.get_pending_peer()
        print()
        warn(f"Pending request from '{peer_name}'")
        try:
            decision = input("  Accept? (y/n): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return
        
        if decision == "y":
            if self.peer.accept_pending():
                self._chat_loop()
            else:
                error("Failed to accept request")
        else:
            self.peer.reject_pending()
            info("Rejected.")
    
    # ─────────────────────────────────────────────────────────────────────
    # Chat Loop
    # ─────────────────────────────────────────────────────────────────────
    
    def _chat_loop(self) -> None:
        """Interactive loop while connected to a peer."""
        if not self.peer.is_chatting:
            return
        
        print()
        banner(f"Chat with '{self.peer.connected_peer}'")
        self._print_chat_help()
        print()
        
        while self.peer.is_chatting and not self._shutdown:
            try:
                text = input(f"  {c('You:', Colors.BLUE)} ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            
            if not text:
                continue
            
            if text == "/quit":
                info("Ending chat...")
                self.peer.disconnect()
                break
            elif text == "/sendfile":
                self._send_file_prompt()
            elif text == "/help":
                self._print_chat_help()
            elif text.startswith("/"):
                warn(f"Unknown command: {text}. Try /help")
            else:
                self.peer.send_chat(text)
    
    def _print_chat_help(self) -> None:
        print("  Commands:")
        print(f"    {c('/quit', Colors.YELLOW)}      - End chat")
        print(f"    {c('/sendfile', Colors.YELLOW)}  - Send a file")
        print(f"    {c('/help', Colors.YELLOW)}      - Show this help")
    
    def _send_file_prompt(self) -> None:
        try:
            filepath = input("  File path: ").strip().strip('"').strip("'")
        except (EOFError, KeyboardInterrupt):
            return
        
        if not filepath:
            return
        
        # Let the core validate + send
        self.peer.send_file(filepath)
    
    # ─────────────────────────────────────────────────────────────────────
    # Shutdown
    # ─────────────────────────────────────────────────────────────────────
    
    def shutdown(self) -> None:
        info("Shutting down...")
        self.peer.shutdown()
        success("Goodbye!")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def prompt_configuration() -> tuple:
    """Ask the user for username, port, and STUN URL."""
    print()
    banner("P2P Chat System — Configuration")
    
    # Username
    while True:
        username = input("  Username: ").strip()
        if username:
            break
        error("Username cannot be empty.")
    
    # Port
    while True:
        port_str = input(f"  TCP port (default {DEFAULT_TCP_PORT}): ").strip()
        if not port_str:
            port = DEFAULT_TCP_PORT
            break
        try:
            port = int(port_str)
            if 1 <= port <= 65535:
                break
            error("Port must be between 1 and 65535.")
        except ValueError:
            error("Port must be a number.")
    
    # STUN URL
    stun_url = input(f"  STUN server (default {DEFAULT_STUN_URL}): ").strip()
    if not stun_url:
        stun_url = DEFAULT_STUN_URL
    if not stun_url.startswith(("http://", "https://")):
        stun_url = "http://" + stun_url
    
    return username, port, stun_url


def main() -> int:
    try:
        username, port, stun_url = prompt_configuration()
    except (EOFError, KeyboardInterrupt):
        print()
        return 130
    
    peer = PeerNode(username, port, stun_url)
    ui = TerminalUI(peer)
    ui.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())