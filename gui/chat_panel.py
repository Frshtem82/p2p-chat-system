"""
Chat panel - right side.

Shows:
- Chat messages (scrolled, tag-styled)
- Message input
- File transfer section (select + send + progress)
"""

import tkinter as tk
from tkinter import ttk, filedialog
from typing import Callable, Optional
import os
import time

from .styles import Palette, Fonts, Spacing, make_button, make_entry
from shared.file_transfer import FileTransfer


class ChatPanel(ttk.Frame):
    """
    Right panel: chat display + input + file transfer.
    
    Callbacks:
        on_send(text)         -> user wants to send a chat message
        on_disconnect()       -> user wants to disconnect
        on_send_file(path)    -> user wants to send a file
    """
    
    def __init__(
        self,
        parent,
        on_send: Callable[[str], None],
        on_disconnect: Callable[[], None],
        on_send_file: Callable[[str], None],
    ):
        super().__init__(parent, style="Card.TFrame")
        self.on_send = on_send
        self.on_disconnect = on_disconnect
        self.on_send_file = on_send_file
        
        self._connected_peer: Optional[str] = None
        self._selected_file: Optional[str] = None
        
        self._build()
    
    # ─────────────────────────────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────────────────────────────
    
    def _build(self) -> None:
        """Build the chat panel."""
        # ── Header ───────────────────────────────────────────────────────
        header = ttk.Frame(self, style="Card.TFrame")
        header.pack(fill="x", padx=Spacing.MD, pady=(Spacing.MD, Spacing.SM))
        
        self.title_label = tk.Label(
            header, text="💬  Select a peer to start chatting",
            bg=Palette.BG_CARD, fg=Palette.FG,
            font=Fonts.HEADING,
        )
        self.title_label.pack(side="left")
        
        self.disconnect_btn = make_button(
            header, "🔌  Disconnect", command=self.on_disconnect,
            style="Secondary.TButton",
        )
        self.disconnect_btn.pack(side="right")
        self.disconnect_btn.configure(state="disabled")
        
        # ── Chat display ─────────────────────────────────────────────────
        chat_frame = ttk.Frame(self, style="Card.TFrame")
        chat_frame.pack(fill="both", expand=True,
                         padx=Spacing.MD, pady=(0, Spacing.SM))
        
        self.chat_display = tk.Text(
            chat_frame,
            wrap="word",
            font=Fonts.CHAT,
            bg=Palette.BG_CARD,
            fg=Palette.FG,
            relief="flat",
            highlightthickness=0,
            borderwidth=0,
            padx=Spacing.SM,
            pady=Spacing.SM,
            state="disabled",
            cursor="arrow",
        )
        scrollbar = ttk.Scrollbar(
            chat_frame, orient="vertical",
            command=self.chat_display.yview,
        )
        self.chat_display.configure(yscrollcommand=scrollbar.set)
        
        self.chat_display.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Configure text tags
        self.chat_display.tag_configure(
            "self_name", foreground=Palette.PRIMARY, font=Fonts.CHAT_BOLD,
        )
        self.chat_display.tag_configure(
            "peer_name", foreground=Palette.SUCCESS, font=Fonts.CHAT_BOLD,
        )
        self.chat_display.tag_configure(
            "timestamp", foreground=Palette.FG_MUTED, font=Fonts.SMALL,
        )
        self.chat_display.tag_configure(
            "system", foreground=Palette.SYSTEM_TEXT,
            font=(Fonts.FAMILY, 10, "italic"),
        )
        self.chat_display.tag_configure(
            "error", foreground=Palette.DANGER,
        )
        self.chat_display.tag_configure(
            "success", foreground=Palette.SUCCESS,
        )
        
        # ── Message input ────────────────────────────────────────────────
        input_frame = ttk.Frame(self, style="Card.TFrame")
        input_frame.pack(fill="x", padx=Spacing.MD, pady=(0, Spacing.SM))
        
        self.message_entry = make_entry(input_frame)
        self.message_entry.pack(side="left", fill="x", expand=True,
                                 padx=(0, Spacing.SM), ipady=Spacing.XS)
        self.message_entry.bind("<Return>", lambda e: self._on_send_clicked())
        self.message_entry.configure(state="disabled")
        
        self.send_btn = make_button(
            input_frame, "📤  Send", command=self._on_send_clicked,
        )
        self.send_btn.pack(side="right")
        self.send_btn.configure(state="disabled")
        
        # ── File transfer section ────────────────────────────────────────
        self._build_file_section()
    
    def _build_file_section(self) -> None:
        """Build the file transfer section."""
        section = tk.Frame(
            self,
            bg=Palette.BG,
            highlightbackground=Palette.BORDER,
            highlightthickness=1,
            padx=Spacing.MD, pady=Spacing.SM,
        )
        section.pack(fill="x", padx=Spacing.MD, pady=(0, Spacing.MD))
        
        # Header
        tk.Label(
            section, text="📁  File Transfer",
            bg=Palette.BG, fg=Palette.FG,
            font=Fonts.BODY_BOLD,
        ).pack(anchor="w")
        
        # Select + Send buttons
        buttons = tk.Frame(section, bg=Palette.BG)
        buttons.pack(fill="x", pady=(Spacing.SM, 0))
        
        self.select_btn = make_button(
            buttons, "📂  Select File", command=self._on_select_file,
            style="Secondary.TButton",
        )
        self.select_btn.pack(side="left")
        self.select_btn.configure(state="disabled")
        
        self.file_label = tk.Label(
            buttons, text="No file selected",
            bg=Palette.BG, fg=Palette.FG_MUTED,
            font=Fonts.SMALL,
            anchor="w",
        )
        self.file_label.pack(side="left", fill="x", expand=True,
                              padx=(Spacing.SM, Spacing.SM))
        
        self.file_send_btn = make_button(
            buttons, "📤  Send", command=self._on_send_file_clicked,
        )
        self.file_send_btn.pack(side="right")
        self.file_send_btn.configure(state="disabled")
        
        # Progress (hidden by default)
        self.progress_frame = tk.Frame(section, bg=Palette.BG)
        
        self.progress_label = tk.Label(
            self.progress_frame, text="",
            bg=Palette.BG, fg=Palette.FG_MUTED,
            font=Fonts.SMALL, anchor="w",
        )
        self.progress_label.pack(fill="x", pady=(Spacing.SM, Spacing.XS))
        
        self.progress_bar = ttk.Progressbar(
            self.progress_frame, mode="determinate",
        )
        self.progress_bar.pack(fill="x")
        
        # Note: progress_frame is packed only when needed
    
    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────
    
    def set_connected_peer(self, peer: Optional[str]) -> None:
        """Set the peer we're connected to (or None if disconnected)."""
        self._connected_peer = peer
        connected = peer is not None
        
        if connected:
            self.title_label.configure(text=f"💬  Chatting with {peer}")
            state = "normal"
        else:
            self.title_label.configure(text="💬  Select a peer to start chatting")
            state = "disabled"
        
        self.disconnect_btn.configure(state=state)
        self.message_entry.configure(state=state)
        self.send_btn.configure(state=state)
        self.select_btn.configure(state=state)
        self._update_file_send_btn()
    
    def add_message(self, sender: str, message: str,
                    is_self: bool = False) -> None:
        """Add a chat message to the display."""
        self.chat_display.configure(state="normal")
        
        timestamp = time.strftime("%H:%M:%S")
        name_tag = "self_name" if is_self else "peer_name"
        name_text = "You" if is_self else sender
        
        self.chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")
        self.chat_display.insert(tk.END, f"{name_text}: ", name_tag)
        self.chat_display.insert(tk.END, f"{message}\n")
        
        self.chat_display.configure(state="disabled")
        self._scroll_to_bottom()
    
    def add_system(self, message: str, tag: str = "system") -> None:
        """Add a system message (info, error, etc.)."""
        self.chat_display.configure(state="normal")
        self.chat_display.insert(tk.END, f"{message}\n", tag)
        self.chat_display.configure(state="disabled")
        self._scroll_to_bottom()
    
    def clear(self) -> None:
        """Clear all messages."""
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.configure(state="disabled")
    
    def show_progress(self, filename: str, direction: str) -> None:
        """Show progress bar for file transfer."""
        verb = "Sending" if direction == "send" else "Receiving"
        self.progress_label.configure(text=f"{verb}: {filename}")
        self.progress_bar["value"] = 0
        self.progress_frame.pack(fill="x")
    
    def update_progress(self, percent: float) -> None:
        """Update progress bar."""
        self.progress_bar["value"] = percent
    
    def hide_progress(self) -> None:
        """Hide progress bar."""
        self.progress_frame.pack_forget()
    
    def reset_file_selection(self) -> None:
        """Reset file selection after send."""
        self._selected_file = None
        self.file_label.configure(text="No file selected",
                                   fg=Palette.FG_MUTED)
        self._update_file_send_btn()
    
    # ─────────────────────────────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────────────────────────────
    
    def _scroll_to_bottom(self) -> None:
        self.chat_display.see(tk.END)
    
    def _on_send_clicked(self) -> None:
        if not self._connected_peer:
            return
        text = self.message_entry.get().strip()
        if not text:
            return
        self.message_entry.delete(0, tk.END)
        self.on_send(text)
    
    def _on_select_file(self) -> None:
        filepath = filedialog.askopenfilename(
            title="Select a file to send",
        )
        if not filepath:
            return
        
        self._selected_file = filepath
        filename = os.path.basename(filepath)
        try:
            size = FileTransfer.get_file_size(filepath)
            size_str = FileTransfer.format_size(size)
            self.file_label.configure(
                text=f"{filename} ({size_str})",
                fg=Palette.FG,
            )
        except OSError as e:
            self.file_label.configure(
                text=f"Error: {e}",
                fg=Palette.DANGER,
            )
            self._selected_file = None
        
        self._update_file_send_btn()
    
    def _on_send_file_clicked(self) -> None:
        if not self._selected_file or not self._connected_peer:
            return
        path = self._selected_file
        self.on_send_file(path)
    
    def _update_file_send_btn(self) -> None:
        enabled = bool(self._selected_file and self._connected_peer)
        self.file_send_btn.configure(state="normal" if enabled else "disabled")