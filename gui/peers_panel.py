"""
Peers panel - left sidebar.

Shows:
- Online peer list (with refresh)
- Connect button
- Pending incoming request (accept/reject)
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, List, Dict, Any

from .styles import Palette, Fonts, Spacing, make_button


class PeersPanel(ttk.Frame):
    """
    Left sidebar showing online peers and pending requests.
    
    Callbacks:
        on_connect(username)  -> user wants to connect to a peer
        on_accept()           -> user accepts pending request
        on_reject()           -> user rejects pending request
        on_refresh()          -> user wants to refresh peer list
    """
    
    def __init__(
        self,
        parent,
        on_connect: Callable[[str], None],
        on_accept: Callable[[], None],
        on_reject: Callable[[], None],
        on_refresh: Callable[[], None],
    ):
        super().__init__(parent, style="Card.TFrame")
        self.on_connect = on_connect
        self.on_accept = on_accept
        self.on_reject = on_reject
        self.on_refresh = on_refresh
        
        self._peers: List[Dict[str, Any]] = []
        self._pending_peer: Optional[str] = None
        
        self._build()
    
    # ─────────────────────────────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────────────────────────────
    
    def _build(self) -> None:
        """Build the sidebar layout."""
        self.configure(width=280)
        self.pack_propagate(False)
        
        # ── Header ───────────────────────────────────────────────────────
        header = ttk.Frame(self, style="Card.TFrame")
        header.pack(fill="x", padx=Spacing.MD, pady=(Spacing.MD, Spacing.SM))
        
        tk.Label(
            header, text="Online Peers",
            bg=Palette.BG_CARD, fg=Palette.FG,
            font=Fonts.HEADING,
        ).pack(side="left")
        
        self.refresh_btn = make_button(
            header, "🔄", command=self.on_refresh,
            style="Secondary.TButton",
        )
        self.refresh_btn.pack(side="right")
        
        # ── Peer list (scrollable) ───────────────────────────────────────
        list_container = ttk.Frame(self, style="Card.TFrame")
        list_container.pack(fill="both", expand=True,
                            padx=Spacing.MD, pady=(0, Spacing.SM))
        
        self.listbox = tk.Listbox(
            list_container,
            font=Fonts.BODY,
            bg=Palette.BG_CARD,
            fg=Palette.FG,
            selectbackground=Palette.PRIMARY_LIGHT,
            selectforeground=Palette.FG,
            highlightthickness=0,
            borderwidth=0,
            activestyle="none",
            exportselection=False,
        )
        scrollbar = ttk.Scrollbar(
            list_container, orient="vertical",
            command=self.listbox.yview,
        )
        self.listbox.configure(yscrollcommand=scrollbar.set)
        
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.listbox.bind("<Double-Button-1>", self._on_double_click)
        
        # ── Connect button ───────────────────────────────────────────────
        self.connect_btn = make_button(
            self, "📞  Connect to Selected",
            command=self._on_connect_clicked,
            style="TButton",
        )
        self.connect_btn.pack(fill="x", padx=Spacing.MD, pady=(0, Spacing.SM))
        
        # ── Separator ────────────────────────────────────────────────────
        ttk.Separator(self, orient="horizontal").pack(
            fill="x", padx=Spacing.MD, pady=Spacing.SM,
        )
        
        # ── Pending requests section ─────────────────────────────────────
        self._build_pending_section()
    
    def _build_pending_section(self) -> None:
        """Build pending request section."""
        container = ttk.Frame(self, style="Card.TFrame")
        container.pack(fill="x", padx=Spacing.MD, pady=(0, Spacing.MD))
        
        tk.Label(
            container, text="Pending Request",
            bg=Palette.BG_CARD, fg=Palette.FG_MUTED,
            font=Fonts.SMALL,
        ).pack(anchor="w")
        
        # Pending frame (styled like a card)
        self.pending_frame = tk.Frame(
            container,
            bg=Palette.BG,
            highlightbackground=Palette.BORDER,
            highlightthickness=1,
            padx=Spacing.SM, pady=Spacing.SM,
        )
        self.pending_frame.pack(fill="x", pady=(Spacing.XS, 0))
        
        self.pending_label = tk.Label(
            self.pending_frame,
            text="No pending requests",
            bg=Palette.BG, fg=Palette.FG_MUTED,
            font=Fonts.SMALL,
            wraplength=220, justify="left",
        )
        self.pending_label.pack(anchor="w")
        
        # Accept/Reject buttons
        buttons = tk.Frame(self.pending_frame, bg=Palette.BG)
        buttons.pack(fill="x", pady=(Spacing.SM, 0))
        
        self.accept_btn = make_button(
            buttons, "✅  Accept", command=self.on_accept,
            style="Success.TButton",
        )
        self.accept_btn.pack(side="left", expand=True, fill="x",
                              padx=(0, Spacing.XS))
        
        self.reject_btn = make_button(
            buttons, "❌  Reject", command=self.on_reject,
            style="Danger.TButton",
        )
        self.reject_btn.pack(side="right", expand=True, fill="x",
                              padx=(Spacing.XS, 0))
        
        # Initially disabled
        self._set_pending_buttons_state("disabled")
    
    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────
    
    def update_peers(self, peers: List[Dict[str, Any]]) -> None:
        """Update the peer list."""
        self._peers = peers
        self.listbox.delete(0, tk.END)
        
        if not peers:
            self.listbox.insert(tk.END, "  (no peers online)")
            self.listbox.itemconfig(0, foreground=Palette.FG_MUTED)
            return
        
        for p in peers:
            username = p.get("username", "?")
            self.listbox.insert(tk.END, f"  👤  {username}")
    
    def set_pending(self, peer: Optional[str]) -> None:
        """Set or clear the pending request."""
        self._pending_peer = peer
        
        if peer:
            self.pending_label.configure(
                text=f"From: {peer}",
                fg=Palette.FG,
            )
            self._set_pending_buttons_state("normal")
        else:
            self.pending_label.configure(
                text="No pending requests",
                fg=Palette.FG_MUTED,
            )
            self._set_pending_buttons_state("disabled")
    
    def set_connected(self, connected: bool) -> None:
        """Enable/disable connect button based on connection state."""
        state = "disabled" if connected else "normal"
        self.connect_btn.configure(state=state)
        self.refresh_btn.configure(state=state)
    
    def set_refreshing(self, refreshing: bool) -> None:
        """Show visual feedback when refreshing."""
        if refreshing:
            self.refresh_btn.configure(text="⏳")
        else:
            self.refresh_btn.configure(text="🔄")
    
    # ─────────────────────────────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────────────────────────────
    
    def _set_pending_buttons_state(self, state: str) -> None:
        self.accept_btn.configure(state=state)
        self.reject_btn.configure(state=state)
    
    def _on_connect_clicked(self) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        
        # First item is placeholder if no peers
        if not self._peers:
            return
        
        index = selection[0]
        if index < len(self._peers):
            peer = self._peers[index]
            self.on_connect(peer.get("username"))
    
    def _on_double_click(self, event) -> None:
        self._on_connect_clicked()