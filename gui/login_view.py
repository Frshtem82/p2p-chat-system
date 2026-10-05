"""
Login view for the GUI.

Collects username, TCP port, and STUN server URL.
Then calls the callback with the validated configuration.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional

from .styles import (
    Palette, Fonts, Spacing, Sizes,
    make_button, make_entry,
)


class LoginView(ttk.Frame):
    """
    Login screen.
    
    Usage:
        view = LoginView(parent, on_connect=callback)
        view.pack(fill='both', expand=True)
        
        def callback(username, port, stun_url):
            # Called when user clicks "Connect"
            ...
    """
    
    def __init__(self, parent, on_connect: Callable[[str, int, str], None]):
        super().__init__(parent)
        self.on_connect = on_connect
        
        # Form variables
        self.username_var = tk.StringVar()
        self.port_var = tk.StringVar(value="9090")
        self.stun_var = tk.StringVar(value="http://localhost:8000")
        
        # Status message
        self.status_var = tk.StringVar()
        self._status_color = Palette.FG_MUTED
        
        self._build()
    
    # ─────────────────────────────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────────────────────────────
    
    def _build(self) -> None:
        """Build the login screen layout."""
        # Centered wrapper
        wrapper = ttk.Frame(self)
        wrapper.place(relx=0.5, rely=0.5, anchor="center")
        
        # ── Header ───────────────────────────────────────────────────────
        header = ttk.Frame(wrapper)
        header.pack(pady=(0, Spacing.XXL))
        
        ttk.Label(
            header, text="🌐  P2P Chat System",
            style="Title.TLabel",
        ).pack()
        
        ttk.Label(
            header,
            text="Computer Networks Project — TCP & HTTP P2P",
            style="Subtitle.TLabel",
        ).pack(pady=(Spacing.SM, 0))
        
        # ── Card with form ───────────────────────────────────────────────
        card = tk.Frame(
            wrapper,
            bg=Palette.BG_CARD,
            highlightbackground=Palette.BORDER,
            highlightthickness=1,
            padx=Spacing.XXL,
            pady=Spacing.XL,
        )
        card.pack(fill="x")
        
        # Card title
        tk.Label(
            card, text="Configuration",
            bg=Palette.BG_CARD, fg=Palette.FG,
            font=Fonts.HEADING,
        ).grid(row=0, column=0, columnspan=2,
               sticky="w", pady=(0, Spacing.LG))
        
        # Username
        self._add_field(
            card, row=1,
            label="Username",
            variable=self.username_var,
            hint="Pick a unique name",
        )
        
        # Port
        self._add_field(
            card, row=2,
            label="TCP Port",
            variable=self.port_var,
            hint="1024-65535",
        )
        
        # STUN URL
        self._add_field(
            card, row=3,
            label="STUN Server",
            variable=self.stun_var,
            hint="e.g. http://localhost:8000",
        )
        
        # ── Connect button ───────────────────────────────────────────────
        self.connect_btn = make_button(
            wrapper, text="🔗  Connect to Network",
            command=self._on_submit, style="TButton",
        )
        self.connect_btn.pack(fill="x", pady=(Spacing.XL, 0), ipady=Spacing.SM)
        
        # ── Status ───────────────────────────────────────────────────────
        self.status_label = tk.Label(
            wrapper, textvariable=self.status_var,
            bg=Palette.BG, fg=Palette.FG_MUTED,
            font=Fonts.SMALL,
        )
        self.status_label.pack(pady=(Spacing.MD, 0))
        
        # Focus + keybindings
        self.after(100, lambda: self._get_entry(0).focus_set())
        self.bind_all("<Return>", lambda e: self._on_submit())
    
    def _add_field(self, parent, row: int, label: str,
                   variable: tk.StringVar, hint: str = "") -> None:
        """Add a labeled entry field to the card."""
        # Label
        tk.Label(
            parent, text=label,
            bg=Palette.BG_CARD, fg=Palette.FG,
            font=Fonts.BODY_BOLD, anchor="w",
        ).grid(row=row * 2, column=0, columnspan=2,
               sticky="w", pady=(Spacing.MD, Spacing.XS))
        
        # Entry
        entry = make_entry(parent, textvariable=variable)
        entry.grid(row=row * 2 + 1, column=0, columnspan=2,
                   sticky="ew", ipady=Spacing.XS)
        
        # Hint
        if hint:
            tk.Label(
                parent, text=hint,
                bg=Palette.BG_CARD, fg=Palette.FG_MUTED,
                font=Fonts.SMALL, anchor="w",
            ).grid(row=row * 2 + 1, column=2,
                   sticky="w", padx=(Spacing.SM, 0))
        
        # Store entry for focus management
        if not hasattr(self, "_entries"):
            self._entries = []
        self._entries.append(entry)
        
        # Configure grid weights
        parent.grid_columnconfigure(1, weight=1)
    
    def _get_entry(self, index: int) -> ttk.Entry:
        """Get nth entry widget."""
        return self._entries[index]
    
    # ─────────────────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────────────────
    
    def _on_submit(self) -> None:
        """Validate inputs and call on_connect callback."""
        username = self.username_var.get().strip()
        port_str = self.port_var.get().strip()
        stun_url = self.stun_var.get().strip()
        
        # ── Validate username ────────────────────────────────────────────
        if not username:
            self._show_error("Username is required")
            self._get_entry(0).focus_set()
            return
        
        if len(username) > 32:
            self._show_error("Username must be 32 characters or less")
            return
        
        # Basic sanity: no whitespace inside
        if any(c.isspace() for c in username):
            self._show_error("Username cannot contain spaces")
            return
        
        # ── Validate port ────────────────────────────────────────────────
        if not port_str.isdigit():
            self._show_error("Port must be a number")
            self._get_entry(1).focus_set()
            return
        
        port = int(port_str)
        if not (1024 <= port <= 65535):
            self._show_error("Port must be between 1024 and 65535")
            self._get_entry(1).focus_set()
            return
        
        # ── Validate STUN URL ────────────────────────────────────────────
        if not stun_url:
            self._show_error("STUN server URL is required")
            return
        
        if not stun_url.startswith(("http://", "https://")):
            stun_url = "http://" + stun_url
            self.stun_var.set(stun_url)
        
        # ── Done ─────────────────────────────────────────────────────────
        self._show_info("Connecting...")
        self.connect_btn.configure(state="disabled")
        self.on_connect(username, port, stun_url)
    
    # ─────────────────────────────────────────────────────────────────────
    # Status helpers
    # ─────────────────────────────────────────────────────────────────────
    
    def _show_error(self, message: str) -> None:
        """Show an error message in the status label."""
        self.status_var.set("❌  " + message)
        self.status_label.configure(fg=Palette.DANGER)
    
    def _show_info(self, message: str) -> None:
        """Show an info message."""
        self.status_var.set("ℹ️  " + message)
        self.status_label.configure(fg=Palette.PRIMARY)
    
    def show_error(self, message: str) -> None:
        """Public method for the app to display errors."""
        self._show_error(message)
        self.connect_btn.configure(state="normal")
    
    def show_info(self, message: str) -> None:
        """Public method for the app to display info."""
        self._show_info(message)