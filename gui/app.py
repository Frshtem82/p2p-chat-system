"""
Main GUI application.

Orchestrates:
- Login view <-> Main view switching
- PeerNode lifecycle (start, shutdown)
- Event handling from PeerNode (rendered via MainView)
- Thread-safe UI updates (all events go through root.after)
"""

import tkinter as tk
from tkinter import messagebox
import threading
import queue
from typing import Optional, Dict, Any, List

from .styles import apply_theme, Palette, Sizes
from .login_view import LoginView
from .main_view import MainView
from shared.peer_core import PeerNode
from shared.constants import DEFAULT_STUN_URL


class P2PChatApp:
    """
    Main application controller.
    
    Manages:
        - The root Tk window
        - The current view (login / main)
        - The PeerNode instance
        - Thread-safe event dispatch
    """
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("P2P Chat System")
        self.root.geometry(f"{Sizes.WINDOW_DEF_W}x{Sizes.WINDOW_DEF_H}")
        self.root.minsize(Sizes.WINDOW_MIN_W, Sizes.WINDOW_MIN_H)
        
        # Apply theme
        apply_theme(self.root)
        
        # State
        self.peer: Optional[PeerNode] = None
        self.current_view = None
        self._refresh_timer_id: Optional[str] = None
        self._closing = False
        
        # Thread-safe event queue (PeerNode -> UI)
        self._event_queue: "queue.Queue[tuple]" = queue.Queue()
        self._poll_events()
        
        # Window close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Show login
        self.show_login()
    
    # ─────────────────────────────────────────────────────────────────────
    # View Management
    # ─────────────────────────────────────────────────────────────────────
    
    def _clear_view(self) -> None:
        """Destroy the current view."""
        if self.current_view is not None:
            self.current_view.destroy()
            self.current_view = None
    
    def show_login(self) -> None:
        """Show the login screen."""
        self._stop_refresh_timer()
        self._clear_view()
        
        self.current_view = LoginView(
            self.root,
            on_connect=self._on_login_submit,
        )
        self.current_view.pack(fill="both", expand=True)
    
    def show_main(self, username: str, port: int) -> None:
        """Show the main screen."""
        self._clear_view()
        
        self.current_view = MainView(
            self.root,
            username=username,
            port=port,
            on_logout=self._on_logout,
            on_refresh=self._on_refresh_peers,
            on_connect=self._on_connect_to_peer,
            on_accept=self._on_accept_pending,
            on_reject=self._on_reject_pending,
            on_send=self._on_send_message,
            on_disconnect=self._on_disconnect,
            on_send_file=self._on_send_file,
        )
        self.current_view.pack(fill="both", expand=True)
        
        # Initial peer list + auto-refresh
        self._on_refresh_peers()
        self._start_refresh_timer()
    
    # ─────────────────────────────────────────────────────────────────────
    # Login Handling
    # ─────────────────────────────────────────────────────────────────────
    
    def _on_login_submit(self, username: str, port: int, stun_url: str) -> None:
        """Called when user clicks 'Connect' in LoginView."""
        # Create the peer
        try:
            self.peer = PeerNode(username, port, stun_url)
        except Exception as e:
            self._login_error(f"Failed to create peer: {e}")
            return
        
        # Register event handlers
        self._register_peer_events()
        
        # Start peer in background thread (so UI doesn't freeze)
        threading.Thread(
            target=self._start_peer_bg,
            args=(username, port),
            daemon=True,
        ).start()
    
    def _start_peer_bg(self, username: str, port: int) -> None:
        """Start PeerNode in a background thread."""
        success = self.peer.start()
        if success:
            # Switch to main view on the UI thread
            self.root.after(0, lambda: self.show_main(username, port))
        else:
            # Already emitted 'register_failed' — nothing to do here
            pass
    
    def _login_error(self, message: str) -> None:
        """Show error on login screen."""
        if isinstance(self.current_view, LoginView):
            self.current_view.show_error(message)
    
    # ─────────────────────────────────────────────────────────────────────
    # PeerNode Event Handlers
    # ─────────────────────────────────────────────────────────────────────
    
    def _register_peer_events(self) -> None:
        """
        Register handlers for PeerNode events.
        
        All handlers push events into a thread-safe queue, which is
        drained by the UI thread in _poll_events().
        """
        if not self.peer:
            return
        
        e = self.peer.events
        e.on("registered",          lambda **kw: self._enqueue("registered", kw))
        e.on("register_failed",     lambda **kw: self._enqueue("register_failed", kw))
        e.on("peer_connected",      lambda **kw: self._enqueue("peer_connected", kw))
        e.on("peer_disconnected",   lambda **kw: self._enqueue("peer_disconnected", kw))
        e.on("chat_message",        lambda **kw: self._enqueue("chat_message", kw))
        e.on("connection_request",  lambda **kw: self._enqueue("connection_request", kw))
        e.on("file_incoming",       lambda **kw: self._enqueue("file_incoming", kw))
        e.on("file_progress",       lambda **kw: self._enqueue("file_progress", kw))
        e.on("file_complete",       lambda **kw: self._enqueue("file_complete", kw))
        e.on("error",               lambda **kw: self._enqueue("error", kw))
    
    def _enqueue(self, event: str, data: Dict[str, Any]) -> None:
        """Called from PeerNode's threads. Puts event into queue."""
        self._event_queue.put((event, data))
    
    def _poll_events(self) -> None:
        """
        Called from the UI thread every 50ms.
        Drains the event queue and dispatches to handlers.
        """
        if self._closing:
            return
        
        try:
            while True:
                event, data = self._event_queue.get_nowait()
                self._dispatch_event(event, data)
        except queue.Empty:
            pass
        
        self.root.after(50, self._poll_events)
    
    def _dispatch_event(self, event: str, data: Dict[str, Any]) -> None:
        """Dispatch one event on the UI thread."""
        handler = getattr(self, f"_handle_{event}", None)
        if handler is None:
            return
        try:
            handler(**data)
        except Exception as e:
            print(f"[App] Error handling '{event}': {e}")
    
    # ─────────────────────────────────────────────────────────────────────
    # Individual Event Handlers (all run on UI thread)
    # ─────────────────────────────────────────────────────────────────────
    
    def _handle_registered(self, username: str, ip: str, port: int) -> None:
        # Login succeeded — MainView will show soon
        pass
    
    def _handle_register_failed(self, reason: str) -> None:
        self._login_error(f"Registration failed: {reason}")
        if self.peer:
            self.peer.shutdown()
            self.peer = None
    
    def _handle_peer_connected(self, peer: str) -> None:
        if isinstance(self.current_view, MainView):
            self.current_view.set_connected(peer)
            self.current_view.add_system(
                f"✅ Connected to '{peer}'", tag="success"
            )
    
    def _handle_peer_disconnected(self, peer: Optional[str], reason: str) -> None:
        if isinstance(self.current_view, MainView):
            self.current_view.set_connected(None)
            self.current_view.hide_file_progress()
            self.current_view.reset_file_selection()
            if peer:
                self.current_view.add_system(
                    f"⚠️ Disconnected from '{peer}' ({reason})"
                )
    
    def _handle_chat_message(self, sender: str, message: str,
                             timestamp: float) -> None:
        if isinstance(self.current_view, MainView):
            self.current_view.add_message(sender, message, is_self=False)
    
    def _handle_connection_request(self, from_peer: str) -> None:
        if isinstance(self.current_view, MainView):
            self.current_view.set_pending(from_peer)
            self.current_view.add_system(
                f"📨 Incoming request from '{from_peer}'"
            )
    
    def _handle_file_incoming(self, sender: str, filename: str,
                              filesize: int, save_path: str) -> None:
        if isinstance(self.current_view, MainView):
            from shared.file_transfer import FileTransfer
            size_str = FileTransfer.format_size(filesize)
            self.current_view.add_system(
                f"📥 Receiving '{filename}' ({size_str}) from {sender}"
            )
            self.current_view.show_file_progress(filename, "recv")
    
    def _handle_file_progress(self, direction: str, filename: str,
                              progress: float, sent: int, total: int) -> None:
        if isinstance(self.current_view, MainView):
            self.current_view.update_file_progress(progress)
    
    def _handle_file_complete(self, filename: str, success: bool,
                              path: str, hash_match: bool,
                              direction: str) -> None:
        if not isinstance(self.current_view, MainView):
            return
        
        self.current_view.hide_file_progress()
        
        if direction == "send":
            if success:
                self.current_view.add_system(
                    f"✅ File '{filename}' sent", tag="success"
                )
            else:
                self.current_view.add_system(
                    f"❌ Failed to send '{filename}'", tag="error"
                )
            self.current_view.reset_file_selection()
        else:
            if hash_match:
                self.current_view.add_system(
                    f"✅ Received '{filename}' — integrity OK", tag="success"
                )
                self.current_view.add_system(f"   Saved to: {path}")
            else:
                self.current_view.add_system(
                    f"⚠️ Received '{filename}' — INTEGRITY FAILED", tag="error"
                )
    
    def _handle_error(self, message: str) -> None:
        if isinstance(self.current_view, MainView):
            self.current_view.add_system(f"❌ {message}", tag="error")
        elif isinstance(self.current_view, LoginView):
            self.current_view.show_error(message)
    
    # ─────────────────────────────────────────────────────────────────────
    # User Actions (from MainView)
    # ─────────────────────────────────────────────────────────────────────
    
    def _on_logout(self) -> None:
        """User clicked Logout."""
        if not messagebox.askyesno(
            "Logout",
            "Are you sure you want to logout?",
        ):
            return
        
        self._stop_refresh_timer()
        
        # Shutdown peer (in background, since it might block briefly)
        if self.peer:
            peer = self.peer
            self.peer = None
            threading.Thread(target=peer.shutdown, daemon=True).start()
        
        self.show_login()
    
    def _on_refresh_peers(self) -> None:
        """User clicked Refresh (or auto-timer fired)."""
        if not self.peer:
            return
        
        if isinstance(self.current_view, MainView):
            self.current_view.set_refreshing(True)
        
        threading.Thread(
            target=self._refresh_peers_bg,
            daemon=True,
        ).start()
    
    def _refresh_peers_bg(self) -> None:
        """Fetch peer list in background."""
        try:
            peers = self.peer.list_peers() if self.peer else []
            self.root.after(0, self._apply_peers, peers)
        except Exception as e:
            print(f"[App] Refresh error: {e}")
            self.root.after(0, self._apply_peers, [])
    
    def _apply_peers(self, peers: List[Dict[str, Any]]) -> None:
        """Apply peer list on UI thread."""
        if isinstance(self.current_view, MainView):
            self.current_view.update_peers(peers)
    
    def _on_connect_to_peer(self, username: str) -> None:
        """User wants to connect to a peer."""
        if not self.peer or not username:
            return
        
        if self.peer.is_chatting:
            messagebox.showinfo("Busy", "You are already in a chat.")
            return
        
        if isinstance(self.current_view, MainView):
            self.current_view.add_system(f"📞 Connecting to '{username}'...")
        
        threading.Thread(
            target=self._connect_to_peer_bg,
            args=(username,),
            daemon=True,
        ).start()
    
    def _connect_to_peer_bg(self, username: str) -> None:
        """Connect in background. PeerNode will emit peer_connected on success."""
        if self.peer:
            self.peer.connect_to_peer(username)
    
    def _on_accept_pending(self) -> None:
        """User accepts pending connection."""
        if not self.peer:
            return
        if self.peer.accept_pending():
            # peer_connected event will be emitted automatically
            if isinstance(self.current_view, MainView):
                self.current_view.set_pending(None)
    
    def _on_reject_pending(self) -> None:
        """User rejects pending connection."""
        if not self.peer:
            return
        self.peer.reject_pending()
        if isinstance(self.current_view, MainView):
            self.current_view.set_pending(None)
            self.current_view.add_system("❌ Rejected incoming request")
    
    def _on_send_message(self, text: str) -> None:
        """User sent a chat message."""
        if not self.peer or not text:
            return
        
        if self.peer.send_chat(text):
            if isinstance(self.current_view, MainView):
                self.current_view.add_message(
                    self.peer.username, text, is_self=True
                )
        else:
            if isinstance(self.current_view, MainView):
                self.current_view.add_system(
                    "❌ Failed to send message", tag="error"
                )
    
    def _on_disconnect(self) -> None:
        """User clicked Disconnect."""
        if not self.peer:
            return
        if not self.peer.is_chatting:
            return
        
        if not messagebox.askyesno("Disconnect", "End the current chat?"):
            return
        
        # peer_disconnected event will fire and update UI
        self.peer.disconnect()
    
    def _on_send_file(self, filepath: str) -> None:
        """User wants to send a file."""
        if not self.peer or not self.peer.is_chatting:
            return
        
        if isinstance(self.current_view, MainView):
            import os
            self.current_view.show_file_progress(
                os.path.basename(filepath), "send"
            )
        
        threading.Thread(
            target=self._send_file_bg,
            args=(filepath,),
            daemon=True,
        ).start()
    
    def _send_file_bg(self, filepath: str) -> None:
        """Send file in background. Progress is streamed via events."""
        if self.peer:
            self.peer.send_file(filepath)
    
    # ─────────────────────────────────────────────────────────────────────
    # Refresh Timer
    # ─────────────────────────────────────────────────────────────────────
    
    def _start_refresh_timer(self) -> None:
        """Auto-refresh peer list every 10 seconds."""
        self._stop_refresh_timer()
        self._refresh_timer_id = self.root.after(10000, self._auto_refresh)
    
    def _stop_refresh_timer(self) -> None:
        if self._refresh_timer_id is not None:
            try:
                self.root.after_cancel(self._refresh_timer_id)
            except Exception:
                pass
            self._refresh_timer_id = None
    
    def _auto_refresh(self) -> None:
        """Timer callback."""
        if self._closing:
            return
        if isinstance(self.current_view, MainView) and not self.peer.is_chatting:
            self._on_refresh_peers()
        self._refresh_timer_id = self.root.after(10000, self._auto_refresh)
    
    # ─────────────────────────────────────────────────────────────────────
    # Shutdown
    # ─────────────────────────────────────────────────────────────────────
    
    def on_closing(self) -> None:
        """Handle window close."""
        if self._closing:
            return
        
        if self.peer and self.peer.is_chatting:
            if not messagebox.askyesno(
                "Quit",
                "You are in an active chat. Quit anyway?",
            ):
                return
        
        self._closing = True
        self._stop_refresh_timer()
        
        # Shutdown peer (best-effort, non-blocking)
        if self.peer:
            peer = self.peer
            self.peer = None
            try:
                threading.Thread(target=peer.shutdown, daemon=True).start()
            except Exception:
                pass
        
        # Destroy window
        try:
            self.root.destroy()
        except Exception:
            pass


def run_gui() -> None:
    """Entry point for the GUI."""
    root = tk.Tk()
    app = P2PChatApp(root)
    root.mainloop()