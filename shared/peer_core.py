"""
Core PeerNode - shared logic for terminal and GUI peers.

This module contains ALL P2P logic:
- STUN registration
- TCP server (accept connections)
- TCP client (connect to peers)
- Chat messaging
- File transfer
- Connection state management

It exposes an event-based API so both terminal and GUI can use it.
GUI adds a callback system; terminal polls state.
"""

import socket
import threading
import os
import time
from typing import Optional, Dict, Any, Callable, List

from .constants import (
    DEFAULT_STUN_URL, DEFAULT_HOST, MAX_PENDING_CONNECTIONS,
    SOCKET_TIMEOUT, CONNECTION_TIMEOUT, RECV_TIMEOUT,
    HANDSHAKE_BUFFER, RECV_BUFFER,
    CHUNK_SIZE, RECEIVED_FILES_DIR, CHUNK_DELAY,
    MessageType,
)
from .protocol import Message, MessageBuffer, encode_message
from .file_transfer import FileTransfer
from .network_utils import (
    get_local_ip, send_json, recv_until_newline,
    create_server_socket, create_client_socket,
    close_socket, STUNClientHTTP,
)


class PeerEvents:
    """
    Event callback container.
    
    Both terminal and GUI can register callbacks for these events.
    If no callback is registered, the event is silently ignored.
    """
    
    def __init__(self):
        self._callbacks: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
    
    def on(self, event: str, callback: Callable) -> None:
        """Register a callback for an event."""
        with self._lock:
            self._callbacks.setdefault(event, []).append(callback)
    
    def emit(self, event: str, **kwargs) -> None:
        """Fire an event. Calls all registered callbacks."""
        with self._lock:
            callbacks = list(self._callbacks.get(event, []))
        for cb in callbacks:
            try:
                cb(**kwargs)
            except Exception as e:
                print(f"[PeerEvents] Error in callback for '{event}': {e}")


class PeerNode:
    """
    Core P2P peer node.
    
    Handles registration, TCP server/client, chat, and file transfer.
    Emits events that UI layers can subscribe to.
    
    Events emitted:
        - 'registered'      -> username, ip, port
        - 'register_failed' -> reason
        - 'peer_connected'  -> peer
        - 'peer_disconnected' -> peer, reason
        - 'chat_message'    -> sender, message, timestamp
        - 'connection_request' -> from_peer
        - 'file_incoming'   -> sender, filename, filesize
        - 'file_progress'   -> direction ('send'/'recv'), progress, filename, sent, total
        - 'file_complete'   -> filename, success, path, hash_match
        - 'error'           -> message
    """
    
    def __init__(self,
                 username: str,
                 tcp_port: int,
                 stun_url: str = DEFAULT_STUN_URL,
                 received_dir: str = RECEIVED_FILES_DIR):
        self.username = username
        self.tcp_port = tcp_port
        self.tcp_ip = get_local_ip()
        self.stun_url = stun_url
        self.received_dir = received_dir
        
        # Ensure received dir exists
        os.makedirs(self.received_dir, exist_ok=True)
        
        # STUN client
        self.stun = STUNClientHTTP(stun_url)
        
        # Server state
        self.server_socket: Optional[socket.socket] = None
        self.server_running = False
        self.server_thread: Optional[threading.Thread] = None
        
        # Connection state
        self.connection_socket: Optional[socket.socket] = None
        self.connected_peer: Optional[str] = None
        self.is_chatting = False
        self.receive_thread: Optional[threading.Thread] = None
        self.message_buffer = MessageBuffer()
        
        # Pending incoming connection
        self.pending_request: Optional[str] = None
        self.pending_socket: Optional[socket.socket] = None
        self._pending_lock = threading.Lock()
        
        # File transfer state
        self.file_transfer_active = False
        self.incoming_file: Optional[Dict[str, Any]] = None
        self._file_lock = threading.Lock()
        
        # Events
        self.events = PeerEvents()
        
        # Shutdown flag
        self._shutdown = False
    
    # ─────────────────────────────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────────────────────────────
    
    def start(self) -> bool:
        """
        Start the peer: register with STUN and start TCP server.
        
        Returns:
            True if both succeeded, False otherwise.
        """
        if not self.register():
            self.events.emit("register_failed", reason="STUN registration failed")
            return False
        
        if not self.start_server():
            self.events.emit("error", message="Failed to start TCP server")
            return False
        
        return True
    
    def shutdown(self) -> None:
        """Stop everything: disconnect, stop server, unregister from STUN."""
        self._shutdown = True
        
        # Disconnect from peer
        self.disconnect(silent=True)
        
        # Stop server
        self.server_running = False
        close_socket(self.server_socket)
        self.server_socket = None
        
        # Unregister from STUN (best effort)
        try:
            self.stun.unregister(self.username)
        except Exception:
            pass
    
    # ─────────────────────────────────────────────────────────────────────
    # STUN Registration
    # ─────────────────────────────────────────────────────────────────────
    
    def register(self) -> bool:
        """Register with STUN server. Returns True on success."""
        status, response = self.stun.register(
            self.username, self.tcp_ip, self.tcp_port
        )
        
        if status == 201:
            self.events.emit("registered",
                             username=self.username,
                             ip=self.tcp_ip,
                             port=self.tcp_port)
            return True
        
        reason = "Unknown error"
        if response:
            reason = response.get("message") or response.get("error") or reason
        self.events.emit("register_failed", reason=reason)
        return False
    
    def list_peers(self) -> List[Dict[str, Any]]:
        """Get list of other online peers (excluding self)."""
        status, response = self.stun.get_peers()
        if status != 200 or not response:
            return []
        peers = response.get("peers", [])
        return [p for p in peers if p.get("username") != self.username]
    
    def get_peer_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Get connection info for a specific peer."""
        status, response = self.stun.get_peer_info(username)
        if status == 200 and response:
            return response
        return None
    
    # ─────────────────────────────────────────────────────────────────────
    # TCP Server
    # ─────────────────────────────────────────────────────────────────────
    
    def start_server(self) -> bool:
        """Start the TCP server in a background thread."""
        self.server_socket = create_server_socket(
            self.tcp_port, DEFAULT_HOST, MAX_PENDING_CONNECTIONS
        )
        if not self.server_socket:
            return False
        
        self.server_socket.settimeout(SOCKET_TIMEOUT)
        self.server_running = True
        
        self.server_thread = threading.Thread(
            target=self._accept_loop,
            daemon=True,
            name=f"PeerServer-{self.username}",
        )
        self.server_thread.start()
        return True
    
    def _accept_loop(self) -> None:
        """Background loop: accept incoming TCP connections."""
        while self.server_running and not self._shutdown:
            try:
                client_socket, _ = self.server_socket.accept()
                threading.Thread(
                    target=self._handle_incoming,
                    args=(client_socket,),
                    daemon=True,
                ).start()
            except socket.timeout:
                continue
            except (OSError, AttributeError):
                break
    
    def _handle_incoming(self, client_socket: socket.socket) -> None:
        """Handle one incoming connection."""
        client_socket.settimeout(RECV_TIMEOUT)
        buffer = MessageBuffer()
        
        # Read handshake
        msg = recv_until_newline(client_socket, buffer, timeout=RECV_TIMEOUT)
        if not msg:
            close_socket(client_socket)
            return
        
        if msg.get("type") != MessageType.CONNECTION_REQUEST:
            close_socket(client_socket)
            return
        
        from_peer = msg.get("username", "Unknown")
        
        # If already chatting, auto-reject
        if self.is_chatting:
            send_json(client_socket, Message.connection_response(
                accepted=False,
                username=self.username,
                reason="User is busy in another chat",
            ))
            close_socket(client_socket)
            self.events.emit("error",
                             message=f"Auto-rejected '{from_peer}' (busy)")
            return
        
        # If a pending request already exists, reject the new one
        with self._pending_lock:
            if self.pending_socket is not None:
                send_json(client_socket, Message.connection_response(
                    accepted=False,
                    username=self.username,
                    reason="Another request pending",
                ))
                close_socket(client_socket)
                return
            
            self.pending_socket = client_socket
            self.pending_request = from_peer
        
        client_socket.settimeout(None)
        self.events.emit("connection_request", from_peer=from_peer)
    
    # ─────────────────────────────────────────────────────────────────────
    # Pending Connection Management
    # ─────────────────────────────────────────────────────────────────────
    
    def has_pending_request(self) -> bool:
        """Check if there's a pending incoming connection request."""
        with self._pending_lock:
            return self.pending_socket is not None
    
    def get_pending_peer(self) -> Optional[str]:
        """Get the username of the pending requester."""
        with self._pending_lock:
            return self.pending_request
    
    def accept_pending(self) -> bool:
        """Accept the pending connection request."""
        with self._pending_lock:
            if not self.pending_socket:
                return False
            sock = self.pending_socket
            peer = self.pending_request
            self.pending_socket = None
            self.pending_request = None
        
        send_json(sock, Message.connection_response(
            accepted=True, username=self.username
        ))
        
        self._set_active_connection(sock, peer)
        return True
    
    def reject_pending(self, reason: str = "Rejected by user") -> bool:
        """Reject the pending connection request."""
        with self._pending_lock:
            if not self.pending_socket:
                return False
            sock = self.pending_socket
            peer = self.pending_request
            self.pending_socket = None
            self.pending_request = None
        
        send_json(sock, Message.connection_response(
            accepted=False, username=self.username, reason=reason
        ))
        close_socket(sock)
        return True
    
    # ─────────────────────────────────────────────────────────────────────
    # Outgoing Connection
    # ─────────────────────────────────────────────────────────────────────
    
    def connect_to_peer(self, target_username: str) -> bool:
        """
        Initiate connection to another peer.
        
        Returns:
            True if connection established, False otherwise.
        """
        if self.is_chatting:
            self.events.emit("error", message="Already in a chat")
            return False
        
        peer_info = self.get_peer_info(target_username)
        if not peer_info:
            self.events.emit("error",
                             message=f"Peer '{target_username}' not found")
            return False
        
        target_ip = peer_info.get("ip")
        target_port = int(peer_info.get("port", 0))
        
        if not target_ip or not target_port:
            self.events.emit("error", message="Invalid peer info")
            return False
        
        sock = create_client_socket(timeout=CONNECTION_TIMEOUT)
        try:
            sock.connect((target_ip, target_port))
        except socket.timeout:
            self.events.emit("error",
                             message=f"Connection to '{target_username}' timed out")
            close_socket(sock)
            return False
        except ConnectionRefusedError:
            self.events.emit("error",
                             message=f"'{target_username}' refused connection")
            close_socket(sock)
            return False
        except Exception as e:
            self.events.emit("error", message=f"Connection failed: {e}")
            close_socket(sock)
            return False
        
        # Send connection request
        send_json(sock, Message.connection_request(
            self.username, self.tcp_ip, self.tcp_port
        ))
        
        # Wait for response
        buffer = MessageBuffer()
        response = recv_until_newline(sock, buffer, timeout=RECV_TIMEOUT)
        
        if not response or response.get("type") != MessageType.CONNECTION_RESPONSE:
            self.events.emit("error", message="Invalid response from peer")
            close_socket(sock)
            return False
        
        if not response.get("accepted"):
            reason = response.get("reason", "No reason given")
            self.events.emit("error",
                             message=f"Connection rejected: {reason}")
            close_socket(sock)
            return False
        
        self._set_active_connection(sock, target_username)
        return True
    
    def _set_active_connection(self, sock: socket.socket,
                               peer: str) -> None:
        """Mark a socket as the active chat connection."""
        sock.settimeout(None)
        self.connection_socket = sock
        self.connected_peer = peer
        self.is_chatting = True
        self.message_buffer.clear()
        
        self.receive_thread = threading.Thread(
            target=self._receive_loop,
            daemon=True,
            name=f"PeerRecv-{peer}",
        )
        self.receive_thread.start()
        
        self.events.emit("peer_connected", peer=peer)
    
    # ─────────────────────────────────────────────────────────────────────
    # Message Receive Loop
    # ─────────────────────────────────────────────────────────────────────
    
    def _receive_loop(self) -> None:
        """Background loop: receive messages from connected peer."""
        while self.is_chatting and self.connection_socket:
            try:
                self.connection_socket.settimeout(SOCKET_TIMEOUT)
                try:
                    data = self.connection_socket.recv(RECV_BUFFER)
                except socket.timeout:
                    continue
                except OSError:
                    break
                
                if not data:
                    self._on_peer_disconnect(reason="Peer disconnected")
                    return
                
                self.message_buffer.add_data(data)
                for msg in self.message_buffer.extract_messages():
                    self._process_message(msg)
            
            except Exception as e:
                if self.is_chatting:
                    self._on_peer_disconnect(reason=f"Error: {e}")
                return
    
    def _process_message(self, msg: Dict[str, Any]) -> None:
        """Route an incoming message to its handler."""
        msg_type = msg.get("type")
        
        if msg_type == MessageType.CHAT_MESSAGE:
            self.events.emit(
                "chat_message",
                sender=msg.get("username", "?"),
                message=msg.get("message", ""),
                timestamp=msg.get("timestamp", time.time()),
            )
        
        elif msg_type == MessageType.DISCONNECT:
            self._on_peer_disconnect(reason="Peer ended the chat")
        
        elif msg_type == MessageType.FILE_INIT:
            self._handle_file_init(msg)
        
        elif msg_type == MessageType.FILE_CHUNK:
            self._handle_file_chunk(msg)
        
        elif msg_type == MessageType.FILE_COMPLETE:
            self._handle_file_complete(msg)
        
        elif msg_type == MessageType.KEEP_ALIVE:
            pass
    
    # ─────────────────────────────────────────────────────────────────────
    # Chat
    # ─────────────────────────────────────────────────────────────────────
    
    def send_chat(self, text: str) -> bool:
        """Send a chat message to the connected peer."""
        if not self.connection_socket or not self.is_chatting:
            return False
        return send_json(
            self.connection_socket,
            Message.chat_message(self.username, text),
        )
    
    def disconnect(self, silent: bool = False) -> None:
        """Disconnect from the current peer."""
        if self.connection_socket and self.is_chatting:
            try:
                send_json(
                    self.connection_socket,
                    Message.disconnect(self.username),
                )
            except Exception:
                pass
        self._on_peer_disconnect(reason="You disconnected",
                                 notify_self=not silent)
    
    def _on_peer_disconnect(self, reason: str = "Disconnected",
                            notify_self: bool = True) -> None:
        """Clean up after disconnect and emit event."""
        if not self.is_chatting and not self.connection_socket:
            return
        
        peer = self.connected_peer
        self.is_chatting = False
        self.connected_peer = None
        
        close_socket(self.connection_socket)
        self.connection_socket = None
        self.message_buffer.clear()
        
        # Cancel any file transfer
        with self._file_lock:
            if self.incoming_file:
                try:
                    self.incoming_file["file_handle"].close()
                except Exception:
                    pass
            self.incoming_file = None
            self.file_transfer_active = False
        
        if notify_self:
            self.events.emit("peer_disconnected", peer=peer, reason=reason)
    
    # ─────────────────────────────────────────────────────────────────────
    # File Transfer - Send
    # ─────────────────────────────────────────────────────────────────────
    
    def send_file(self, filepath: str) -> bool:
        """
        Send a file to the connected peer.
        
        Returns:
            True if the transfer completed successfully.
        """
        if not self.connection_socket or not self.is_chatting:
            self.events.emit("error", message="Not connected to any peer")
            return False
        
        with self._file_lock:
            if self.file_transfer_active:
                self.events.emit("error",
                                 message="A file transfer is already in progress")
                return False
            self.file_transfer_active = True
        
        try:
            return self._do_send_file(filepath)
        finally:
            with self._file_lock:
                self.file_transfer_active = False
    
    def _do_send_file(self, filepath: str) -> bool:
        """Internal file send logic."""
        valid, err = FileTransfer.validate_file(filepath)
        if not valid:
            self.events.emit("error", message=err)
            return False
        
        filename = os.path.basename(filepath)
        filesize = FileTransfer.get_file_size(filepath)
        filehash = FileTransfer.calculate_hash(filepath)
        
        # Send file_init
        if not send_json(self.connection_socket, Message.file_init(
            filename, filesize, filehash, self.username
        )):
            self.events.emit("error", message="Failed to send file_init")
            return False
        
        # Send chunks
        sent = 0
        total_chunks = 0
        for index, chunk in FileTransfer.iter_chunks(filepath):
            encoded = FileTransfer.encode_chunk(chunk)
            if not send_json(self.connection_socket,
                             Message.file_chunk(index, encoded)):
                self.events.emit("error",
                                 message="Connection lost during transfer")
                return False
            
            sent += len(chunk)
            total_chunks = index + 1
            
            if filesize > 0:
                progress = (sent / filesize) * 100
                self.events.emit(
                    "file_progress",
                    direction="send",
                    filename=filename,
                    progress=progress,
                    sent=sent,
                    total=filesize,
                )
            
            time.sleep(CHUNK_DELAY)
        
        # Send completion
        send_json(self.connection_socket, Message.file_complete(
            filename, total_chunks, filehash
        ))
        
        self.events.emit(
            "file_complete",
            filename=filename,
            success=True,
            path=filepath,
            hash_match=True,
            direction="send",
        )
        return True
    
    # ─────────────────────────────────────────────────────────────────────
    # File Transfer - Receive
    # ─────────────────────────────────────────────────────────────────────
    
    def _handle_file_init(self, msg: Dict[str, Any]) -> None:
        """Handle incoming file metadata."""
        filename = msg.get("filename", "unknown")
        filesize = int(msg.get("filesize", 0))
        filehash = msg.get("filehash", "")
        sender = msg.get("sender", "?")
        
        save_path = FileTransfer.get_unique_path(self.received_dir, filename)
        
        try:
            fh = open(save_path, "wb")
        except OSError as e:
            self.events.emit("error", message=f"Cannot open file: {e}")
            return
        
        with self._file_lock:
            self.incoming_file = {
                "filename": filename,
                "save_path": save_path,
                "filesize": filesize,
                "filehash": filehash,
                "sender": sender,
                "received_bytes": 0,
                "file_handle": fh,
                "total_chunks": 0,
            }
            self.file_transfer_active = True
        
        self.events.emit(
            "file_incoming",
            sender=sender,
            filename=filename,
            filesize=filesize,
            save_path=save_path,
        )
    
    def _handle_file_chunk(self, msg: Dict[str, Any]) -> None:
        """Handle an incoming file chunk."""
        with self._file_lock:
            if not self.incoming_file:
                return
            try:
                data = FileTransfer.decode_chunk(msg.get("data", ""))
                self.incoming_file["file_handle"].write(data)
                self.incoming_file["received_bytes"] += len(data)
                self.incoming_file["total_chunks"] += 1
                
                received = self.incoming_file["received_bytes"]
                total = self.incoming_file["filesize"]
                filename = self.incoming_file["filename"]
            except Exception as e:
                self.events.emit("error",
                                 message=f"File chunk error: {e}")
                return
        
        if total > 0:
            progress = (received / total) * 100
            self.events.emit(
                "file_progress",
                direction="recv",
                filename=filename,
                progress=progress,
                sent=received,
                total=total,
            )
    
    def _handle_file_complete(self, msg: Dict[str, Any]) -> None:
        """Handle file completion and verify integrity."""
        with self._file_lock:
            if not self.incoming_file:
                return
            try:
                self.incoming_file["file_handle"].close()
            except Exception:
                pass
            
            save_path = self.incoming_file["save_path"]
            expected = self.incoming_file["filehash"]
            filename = self.incoming_file["filename"]
            self.incoming_file = None
            self.file_transfer_active = False
        
        actual = FileTransfer.calculate_hash(save_path)
        hash_match = (actual == expected)
        
        self.events.emit(
            "file_complete",
            filename=filename,
            success=hash_match,
            path=save_path,
            hash_match=hash_match,
            direction="recv",
        )