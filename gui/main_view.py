"""
Main view - shown after successful login.

Layout:
    ┌─────────────────────────────────────────────┐
    │  Header: 👤 username • port • status        │
    ├──────────────┬──────────────────────────────┤
    │              │                              │
    │  PeersPanel  │       ChatPanel              │
    │              │                              │
    └──────────────┴──────────────────────────────┘
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, List, Dict, Any

from .styles import Palette, Fonts, Spacing, make_button
from .peers_panel import PeersPanel
from .chat_panel import ChatPanel


class MainView(ttk.Frame):
    """
    Main view: header + sidebar + chat area.
    
    This class is a pure layout container. It delegates actions
    to callbacks provided by the app.
    """
    
    def __init__(
        self,
        parent,
        username: str,
        port: int,
        on_logout: Callable[[], None],
        on_refresh: Callable[[], None],
        on_connect: Callable[[str], None],
        on_accept: Callable[[], None],
        on_reject: Callable[[], None],
        on_send: Callable[[str], None],
        on_disconnect: Callable[[], None],
        on_send_file: Callable[[str], None],
    ):
        super().__init__(parent)
        self.username = username
        self.port = port
        
        self._build_header(on_logout)
        
        # ── Body: sidebar + chat ─────────────────────────────────────────
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True,
                   padx=Spacing.MD, pady=(0, Spacing.MD))
        
        # Sidebar
        self.peers_panel = PeersPanel(
            body,
            on_connect=on_connect,
            on_accept=on_accept,
            on_reject=on_reject,
            on_refresh=on_refresh,
        )
        self.peers_panel.pack(side="left", fill="y",
                               padx=(0, Spacing.MD))
        
        # Chat
        self.chat_panel = ChatPanel(
            body,
            on_send=on_send,
            on_disconnect=on_disconnect,
            on_send_file=on_send_file,
        )
        self.chat_panel.pack(side="right", fill="both", expand=True)
    
    # ─────────────────────────────────────────────────────────────────────
    # Header
    # ─────────────────────────────────────────────────────────────────────
    
    def _build_header(self, on_logout: Callable[[], None]) -> None:
        header = tk.Frame(self, bg=Palette.BG_DARK, padx=Spacing.LG, pady=Spacing.MD)
        header.pack(fill="x")
        
        # Left: user info
        left = tk.Frame(header, bg=Palette.BG_DARK)
        left.pack(side="left")
        
        tk.Label(
            left, text=f"👤  {self.username}",
            bg=Palette.BG_DARK, fg=Palette.FG_LIGHT,
            font=Fonts.HEADING,
        ).pack(side="left")
        
        tk.Label(
            left, text=f"   •   Port {self.port}",
            bg=Palette.BG_DARK, fg=Palette.FG_MUTED,
            font=Fonts.SMALL,
        ).pack(side="left", padx=(Spacing.SM, 0))
        
        self.status_label = tk.Label(
            left, text="   •   🟢 Online",
            bg=Palette.BG_DARK, fg=Palette.SUCCESS,
            font=Fonts.SMALL,
        )
        self.status_label.pack(side="left", padx=(Spacing.SM, 0))
        
        # Right: logout
        logout_btn = tk.Button(
            header, text="🚪  Logout",
            command=on_logout,
            bg=Palette.BG_DARK, fg=Palette.FG_LIGHT,
            activebackground=Palette.DANGER,
            activeforeground=Palette.FG_LIGHT,
            font=Fonts.SMALL,
            relief="flat", bd=0,
            padx=Spacing.MD, pady=Spacing.XS,
            cursor="hand2",
        )
        logout_btn.pack(side="right")
    
    # ─────────────────────────────────────────────────────────────────────
    # Public API (delegate to sub-views)
    # ─────────────────────────────────────────────────────────────────────
    
    def update_peers(self, peers: List[Dict[str, Any]]) -> None:
        self.peers_panel.update_peers(peers)
        self.peers_panel.set_refreshing(False)
    
    def set_refreshing(self, refreshing: bool) -> None:
        self.peers_panel.set_refreshing(refreshing)
    
    def set_pending(self, peer: Optional[str]) -> None:
        self.peers_panel.set_pending(peer)
    
    def set_connected(self, peer: Optional[str]) -> None:
        connected = peer is not None
        self.peers_panel.set_connected(connected)
        self.chat_panel.set_connected_peer(peer)
        
        if connected:
            self.status_label.configure(
                text=f"   •   🟡 Chatting with {peer}",
                fg=Palette.WARNING,
            )
        else:
            self.status_label.configure(
                text="   •   🟢 Online",
                fg=Palette.SUCCESS,
            )
    
    def add_message(self, sender: str, message: str, is_self: bool = False) -> None:
        self.chat_panel.add_message(sender, message, is_self)
    
    def add_system(self, message: str, tag: str = "system") -> None:
        self.chat_panel.add_system(message, tag)
    
    def clear_chat(self) -> None:
        self.chat_panel.clear()
    
    def show_file_progress(self, filename: str, direction: str) -> None:
        self.chat_panel.show_progress(filename, direction)
    
    def update_file_progress(self, percent: float) -> None:
        self.chat_panel.update_progress(percent)
    
    def hide_file_progress(self) -> None:
        self.chat_panel.hide_progress()
    
    def reset_file_selection(self) -> None:
        self.chat_panel.reset_file_selection()