"""
P2P Chat System - Complete GUI with TCP + File Transfer
Full implementation according to project requirements
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import socket
import json
import os
import hashlib
import base64
import time
import queue
from datetime import datetime
import requests
from urllib.parse import urljoin

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

PROTOCOL_VERSION = "1.0"
CHUNK_SIZE = 8192  # 8KB chunks for file transfer

# Message types for JSON protocol
MSG_TYPES = {
    'CONNECTION_REQUEST': 'connection_request',
    'CONNECTION_RESPONSE': 'connection_response',
    'CHAT_MESSAGE': 'chat_message',
    'FILE_INIT': 'file_init',
    'FILE_CHUNK': 'file_chunk',
    'FILE_COMPLETE': 'file_complete',
    'DISCONNECT': 'disconnect',
    'KEEP_ALIVE': 'keep_alive'
}

# ─────────────────────────────────────────────────────────────────────────────
# File Transfer Protocol
# ─────────────────────────────────────────────────────────────────────────────

class FileTransfer:
    """Handles file transfer operations between peers."""
    
    @staticmethod
    def calculate_hash(filepath):
        """Calculate SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(CHUNK_SIZE):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    @staticmethod
    def format_size(size_bytes):
        """Format bytes to human readable string."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"
    
    @staticmethod
    def split_file(filepath, chunk_size=CHUNK_SIZE):
        """Split file into chunks for transmission."""
        chunks = []
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                chunks.append(chunk)
        return chunks

# ─────────────────────────────────────────────────────────────────────────────
# Message Buffer
# ─────────────────────────────────────────────────────────────────────────────

class MessageBuffer:
    """Thread-safe message buffer for TCP communication."""
    
    def __init__(self):
        self.buffer = ""
        self.lock = threading.Lock()
    
    def add_data(self, data):
        """Add received data to buffer."""
        with self.lock:
            self.buffer += data
    
    def extract_messages(self):
        """Extract complete JSON messages from buffer."""
        with self.lock:
            messages = []
            while '\n' in self.buffer:
                line, self.buffer = self.buffer.split('\n', 1)
                line = line.strip()
                if line:
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            return messages

# ─────────────────────────────────────────────────────────────────────────────
# STUN Client
# ─────────────────────────────────────────────────────────────────────────────

class STUNClient:
    """Client for interacting with STUN server."""
    
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
    
    def register(self, username, ip, port):
        """Register peer with STUN server."""
        try:
            url = urljoin(self.base_url, '/register')
            response = requests.post(
                url,
                json={'username': username, 'ip': ip, 'port': port},
                timeout=5
            )
            return response.status_code in (200, 201, 202)
        except Exception:
            return False
    
    def get_peers(self):
        """Get list of all peers from STUN server."""
        try:
            url = urljoin(self.base_url, '/peers')
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('peers', [])
            return []
        except Exception:
            return []
    
    def get_peer_info(self, username):
        """Get specific peer information."""
        try:
            url = urljoin(self.base_url, '/peerinfo')
            response = requests.get(
                url,
                params={'username': username},
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None
    
    def unregister(self, username):
        """Unregister peer from STUN server."""
        try:
            url = urljoin(self.base_url, '/unregister')
            response = requests.post(
                url,
                json={'username': username},
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False

# ─────────────────────────────────────────────────────────────────────────────
# Main Application Class
# ─────────────────────────────────────────────────────────────────────────────

class P2PChatGUI:
    """Complete P2P Chat GUI Application."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("🌐 P2P Chat System - Computer Networks Project")
        self.root.geometry("1000x750")
        self.root.minsize(900, 650)
        
        # Configure style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Network configuration
        self.username = None
        self.local_ip = self.get_local_ip()
        self.tcp_port = None
        self.stun_url = "http://localhost:8000"
        self.stun_client = None
        
        # Server state
        self.server_socket = None
        self.server_running = False
        self.server_thread = None
        
        # Connection state
        self.connection_socket = None
        self.connected_peer = None
        self.is_chatting = False
        self.receive_thread = None
        self.message_buffer = MessageBuffer()
        
        # Pending connection
        self.pending_request = None
        self.pending_socket = None
        self.pending_lock = threading.Lock()
        
        # File transfer
        self.selected_file_path = None
        self.receiving_file = None
        self.sending_file = False
        
        # Message queue for thread-safe UI updates
        self.message_queue = queue.Queue()
        
        # Create directories
        self.received_dir = "received_files"
        if not os.path.exists(self.received_dir):
            os.makedirs(self.received_dir)
        
        # Start UI
        self.build_login_screen()
        self.process_message_queue()
    
    # ─────────────────────────────────────────────────────────────────────────
    # UI Building Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def clear_window(self):
        """Clear all widgets from window."""
        for widget in self.root.winfo_children():
            widget.destroy()
    
    def build_login_screen(self):
        """Build login/registration screen."""
        self.clear_window()
        
        # Main container
        main_frame = ttk.Frame(self.root, padding="30")
        main_frame.pack(expand=True, fill='both')
        
        # Title
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(pady=(0, 30))
        
        ttk.Label(
            title_frame,
            text="🌐 P2P Chat System",
            font=('Segoe UI', 32, 'bold')
        ).pack()
        
        ttk.Label(
            title_frame,
            text="Computer Networks Final Project - TCP & HTTP with P2P",
            font=('Segoe UI', 11),
            foreground='gray'
        ).pack(pady=(5, 0))
        
        # Form
        form_frame = ttk.LabelFrame(
            main_frame,
            text=" Network Configuration ",
            padding="25"
        )
        form_frame.pack(fill='x', padx=60)
        
        # Username
        row = 0
        ttk.Label(form_frame, text="Username:", font=('Segoe UI', 11)).grid(
            row=row, column=0, sticky='w', pady=10
        )
        self.username_entry = ttk.Entry(form_frame, width=35, font=('Segoe UI', 11))
        self.username_entry.grid(row=row, column=1, pady=10, padx=(15, 0))
        self.username_entry.focus()
        
        # Port
        row += 1
        ttk.Label(form_frame, text="TCP Port:", font=('Segoe UI', 11)).grid(
            row=row, column=0, sticky='w', pady=10
        )
        self.port_entry = ttk.Entry(form_frame, width=35, font=('Segoe UI', 11))
        self.port_entry.insert(0, "9090")
        self.port_entry.grid(row=row, column=1, pady=10, padx=(15, 0))
        
        # STUN Server
        row += 1
        ttk.Label(form_frame, text="STUN Server:", font=('Segoe UI', 11)).grid(
            row=row, column=0, sticky='w', pady=10
        )
        self.stun_entry = ttk.Entry(form_frame, width=35, font=('Segoe UI', 11))
        self.stun_entry.insert(0, self.stun_url)
        self.stun_entry.grid(row=row, column=1, pady=10, padx=(15, 0))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=30)
        
        ttk.Button(
            button_frame,
            text="🔗 Connect to Network",
            command=self.connect_to_network,
            width=25
        ).pack()
        
        # Status
        self.login_status = ttk.Label(
            main_frame,
            text="",
            font=('Segoe UI', 10)
        )
        self.login_status.pack(pady=(10, 0))
        
        # Bind Enter key
        self.root.bind('<Return>', lambda e: self.connect_to_network())
    
    def build_main_screen(self):
        """Build main application screen after login."""
        self.clear_window()
        self.root.unbind('<Return>')
        
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(expand=True, fill='both')
        
        # Header
        header_frame = ttk.Frame(main_container, padding="10")
        header_frame.pack(fill='x')
        
        # User info
        user_info = ttk.Frame(header_frame)
        user_info.pack(side='left')
        
        ttk.Label(
            user_info,
            text=f"👤 {self.username}",
            font=('Segoe UI', 14, 'bold')
        ).pack(side='left')
        
        ttk.Label(
            user_info,
            text=f" • Port: {self.tcp_port}",
            font=('Segoe UI', 10),
            foreground='gray'
        ).pack(side='left', padx=(10, 0))
        
        self.connection_status = ttk.Label(
            user_info,
            text=" • 🟢 Online",
            font=('Segoe UI', 10),
            foreground='green'
        )
        self.connection_status.pack(side='left', padx=(5, 0))
        
        # Logout button
        ttk.Button(
            header_frame,
            text="🚪 Logout",
            command=self.logout,
            width=12
        ).pack(side='right')
        
        ttk.Separator(main_container, orient='horizontal').pack(fill='x')
        
        # Content area
        content_frame = ttk.Frame(main_container)
        content_frame.pack(expand=True, fill='both', padx=10, pady=10)
        
        # Left panel - Peer list
        left_panel = ttk.Frame(content_frame, width=300)
        left_panel.pack(side='left', fill='y', padx=(0, 10))
        left_panel.pack_propagate(False)
        
        # Peer list header
        peers_header = ttk.Frame(left_panel)
        peers_header.pack(fill='x', pady=(0, 10))
        
        ttk.Label(
            peers_header,
            text="📋 Online Peers",
            font=('Segoe UI', 12, 'bold')
        ).pack(side='left')
        
        ttk.Button(
            peers_header,
            text="🔄 Refresh",
            command=self.refresh_peer_list,
            width=8
        ).pack(side='right')
        
        # Peer list
        list_frame = ttk.Frame(left_panel)
        list_frame.pack(expand=True, fill='both')
        
        self.peer_listbox = tk.Listbox(
            list_frame,
            font=('Segoe UI', 11),
            selectmode='single'
        )
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical')
        self.peer_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.peer_listbox.yview)
        
        self.peer_listbox.pack(side='left', expand=True, fill='both')
        scrollbar.pack(side='right', fill='y')
        self.peer_listbox.bind('<Double-1>', self.on_peer_double_click)
        
        # Connect button
        ttk.Button(
            left_panel,
            text="📞 Connect to Selected Peer",
            command=self.connect_to_selected_peer
        ).pack(fill='x', pady=(10, 0))
        
        # Pending requests section
        ttk.Separator(left_panel, orient='horizontal').pack(fill='x', pady=15)
        
        self.pending_frame = ttk.LabelFrame(
            left_panel,
            text=" 📨 Pending Requests ",
            padding="10"
        )
        self.pending_frame.pack(fill='x')
        
        self.pending_label = ttk.Label(
            self.pending_frame,
            text="No pending requests",
            font=('Segoe UI', 10),
            foreground='gray'
        )
        self.pending_label.pack()
        
        self.pending_buttons = ttk.Frame(self.pending_frame)
        self.pending_buttons.pack(fill='x', pady=(8, 0))
        
        self.accept_btn = ttk.Button(
            self.pending_buttons,
            text="✅ Accept",
            command=self.accept_pending_request,
            state='disabled'
        )
        self.accept_btn.pack(side='left', expand=True, padx=(0, 3))
        
        self.reject_btn = ttk.Button(
            self.pending_buttons,
            text="❌ Reject",
            command=self.reject_pending_request,
            state='disabled'
        )
        self.reject_btn.pack(side='right', expand=True, padx=(3, 0))
        
        # Right panel - Chat area
        right_panel = ttk.Frame(content_frame)
        right_panel.pack(side='right', expand=True, fill='both')
        
        # Chat header
        chat_header = ttk.Frame(right_panel)
        chat_header.pack(fill='x', pady=(0, 10))
        
        self.chat_title = ttk.Label(
            chat_header,
            text="💬 Select a peer to start chatting",
            font=('Segoe UI', 12, 'bold')
        )
        self.chat_title.pack(side='left')
        
        self.disconnect_btn = ttk.Button(
            chat_header,
            text="🔌 Disconnect",
            command=self.disconnect_from_peer,
            state='disabled'
        )
        self.disconnect_btn.pack(side='right')
        
        # Chat display
        chat_display_frame = ttk.Frame(right_panel)
        chat_display_frame.pack(expand=True, fill='both')
        
        self.chat_display = scrolledtext.ScrolledText(
            chat_display_frame,
            wrap=tk.WORD,
            font=('Segoe UI', 10),
            state='disabled',
            height=20
        )
        self.chat_display.pack(expand=True, fill='both')
        
        # Configure text tags
        self.chat_display.tag_config('self', foreground='#0066cc', font=('Segoe UI', 10, 'bold'))
        self.chat_display.tag_config('peer', foreground='#009933', font=('Segoe UI', 10, 'bold'))
        self.chat_display.tag_config('system', foreground='#666666', font=('Segoe UI', 9, 'italic'))
        self.chat_display.tag_config('error', foreground='#cc0000')
        
        # Message input
        input_frame = ttk.Frame(right_panel)
        input_frame.pack(fill='x', pady=(10, 0))
        
        self.message_entry = ttk.Entry(input_frame, font=('Segoe UI', 11))
        self.message_entry.pack(side='left', expand=True, fill='x', padx=(0, 10))
        self.message_entry.bind('<Return>', self.send_chat_message)
        self.message_entry.config(state='disabled')
        
        self.send_btn = ttk.Button(
            input_frame,
            text="📤 Send",
            command=self.send_chat_message,
            state='disabled'
        )
        self.send_btn.pack(side='right')
        
        # File transfer section
        file_frame = ttk.LabelFrame(
            right_panel,
            text=" 📁 File Transfer (Bonus) ",
            padding="10"
        )
        file_frame.pack(fill='x', pady=(15, 0))
        
        file_buttons = ttk.Frame(file_frame)
        file_buttons.pack(fill='x')
        
        self.select_file_btn = ttk.Button(
            file_buttons,
            text="📂 Select File",
            command=self.select_file,
            state='disabled'
        )
        self.select_file_btn.pack(side='left', padx=(0, 10))
        
        self.file_label = ttk.Label(
            file_buttons,
            text="No file selected",
            font=('Segoe UI', 9),
            foreground='gray'
        )
        self.file_label.pack(side='left', expand=True, fill='x')
        
        self.send_file_btn = ttk.Button(
            file_buttons,
            text="📤 Send File",
            command=self.send_file,
            state='disabled'
        )
        self.send_file_btn.pack(side='right')
        
        # Progress bar (hidden by default)
        self.progress_frame = ttk.Frame(file_frame)
        self.progress_label = ttk.Label(self.progress_frame, text="", font=('Segoe UI', 9))
        self.progress_label.pack(fill='x')
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='determinate')
        self.progress_bar.pack(fill='x', pady=(5, 0))
        self.progress_frame.pack_forget()
        
        # Initial refresh
        self.refresh_peer_list()
        self.start_peer_refresh_timer()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Network Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_local_ip(self):
        """Get local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def connect_to_network(self):
        """Connect to P2P network."""
        username = self.username_entry.get().strip()
        port_str = self.port_entry.get().strip()
        stun_url = self.stun_entry.get().strip()
        
        # Validation
        if not username:
            self.show_login_error("Username is required")
            return
        
        if not port_str.isdigit():
            self.show_login_error("Port must be a number")
            return
        
        port = int(port_str)
        if port < 1024 or port > 65535:
            self.show_login_error("Port must be between 1024-65535")
            return
        
        if not stun_url.startswith(('http://', 'https://')):
            stun_url = f"http://{stun_url}"
        
        self.show_login_status("Connecting to network...", 'blue')
        
        # Store configuration
        self.username = username
        self.tcp_port = port
        self.stun_url = stun_url
        self.stun_client = STUNClient(stun_url)
        
        # Start TCP server
        if not self.start_tcp_server():
            self.show_login_error("Failed to start TCP server")
            return
        
        # Register with STUN server
        if not self.stun_client.register(username, self.local_ip, port):
            self.show_login_error("Failed to register with STUN server")
            self.stop_tcp_server()
            return
        
        # Success
        self.build_main_screen()
    
    def start_tcp_server(self):
        """Start TCP server for incoming connections."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.tcp_port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)
            
            self.server_running = True
            self.server_thread = threading.Thread(
                target=self.accept_connections,
                daemon=True
            )
            self.server_thread.start()
            
            print(f"TCP Server started on port {self.tcp_port}")
            return True
            
        except Exception as e:
            print(f"Failed to start TCP server: {e}")
            return False
    
    def stop_tcp_server(self):
        """Stop TCP server."""
        self.server_running = False
        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None
    
    def accept_connections(self):
        """Accept incoming TCP connections."""
        while self.server_running:
            try:
                client_socket, address = self.server_socket.accept()
                threading.Thread(
                    target=self.handle_incoming_connection,
                    args=(client_socket, address),
                    daemon=True
                ).start()
            except socket.timeout:
                continue
            except:
                break
    
    def handle_incoming_connection(self, client_socket, address):
        """Handle incoming connection request."""
        try:
            client_socket.settimeout(5.0)
            data = client_socket.recv(4096).decode('utf-8')
            
            for line in data.split('\n'):
                if not line.strip():
                    continue
                
                try:
                    message = json.loads(line)
                    if message.get('type') == MSG_TYPES['CONNECTION_REQUEST']:
                        from_user = message.get('from')
                        
                        with self.pending_lock:
                            # Check if we're already chatting
                            if self.is_chatting:
                                self.send_response(client_socket, False, "Already in a chat")
                                return
                            
                            # Store as pending request
                            self.pending_socket = client_socket
                            self.pending_request = from_user
                            
                            # Show in UI
                            self.message_queue.put(('pending', {'from': from_user}))
                        return
                        
                except json.JSONDecodeError:
                    continue
            
            client_socket.close()
            
        except Exception as e:
            print(f"Error handling incoming connection: {e}")
            try:
                client_socket.close()
            except:
                pass
    
    def send_response(self, socket, accepted, reason=""):
        """Send connection response."""
        response = {
            'type': MSG_TYPES['CONNECTION_RESPONSE'],
            'accepted': accepted,
            'reason': reason
        }
        try:
            socket.send((json.dumps(response) + '\n').encode('utf-8'))
        except:
            pass
    
    # ─────────────────────────────────────────────────────────────────────────
    # Peer Management
    # ─────────────────────────────────────────────────────────────────────────
    
    def refresh_peer_list(self):
        """Refresh list of online peers."""
        threading.Thread(target=self.do_refresh_peer_list, daemon=True).start()
    
    def do_refresh_peer_list(self):
        """Fetch peers from STUN server."""
        try:
            peers = self.stun_client.get_peers()
            online_peers = [p['username'] for p in peers if p['username'] != self.username]
            
            self.root.after(0, self.update_peer_list, online_peers)
            
        except Exception as e:
            print(f"Error refreshing peer list: {e}")
    
    def update_peer_list(self, peers):
        """Update peer listbox."""
        self.peer_listbox.delete(0, tk.END)
        for peer in peers:
            self.peer_listbox.insert(tk.END, f"👤 {peer}")
    
    def start_peer_refresh_timer(self):
        """Start periodic peer refresh."""
        def refresh():
            if hasattr(self, 'username') and self.username:
                self.refresh_peer_list()
                self.root.after(10000, refresh)  # Every 10 seconds
        
        self.root.after(5000, refresh)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Peer Connection
    # ─────────────────────────────────────────────────────────────────────────
    
    def on_peer_double_click(self, event):
        """Handle double-click on peer."""
        self.connect_to_selected_peer()
    
    def connect_to_selected_peer(self):
        """Connect to selected peer."""
        selection = self.peer_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a peer first")
            return
        
        if self.is_chatting:
            messagebox.showwarning("Warning", "You are already in a chat")
            return
        
        peer_text = self.peer_listbox.get(selection[0])
        peer_username = peer_text.replace("👤 ", "").strip()
        
        threading.Thread(
            target=self.initiate_peer_connection,
            args=(peer_username,),
            daemon=True
        ).start()
    
    def initiate_peer_connection(self, peer_username):
        """Initiate connection to peer."""
        try:
            # Get peer info from STUN
            peer_info = self.stun_client.get_peer_info(peer_username)
            if not peer_info:
                self.message_queue.put(('error', {'message': f"Could not find {peer_username}"}))
                return
            
            # Connect via TCP
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)
            sock.connect((peer_info['ip'], peer_info['port']))
            
            # Send connection request
            request = {
                'type': MSG_TYPES['CONNECTION_REQUEST'],
                'from': self.username,
                'timestamp': time.time()
            }
            sock.send((json.dumps(request) + '\n').encode('utf-8'))
            
            # Wait for response
            sock.settimeout(15.0)
            response_data = sock.recv(4096).decode('utf-8')
            
            for line in response_data.split('\n'):
                if not line.strip():
                    continue
                
                try:
                    response = json.loads(line)
                    if response.get('type') == MSG_TYPES['CONNECTION_RESPONSE']:
                        if response.get('accepted'):
                            # Connection established
                            self.connection_socket = sock
                            self.connected_peer = peer_username
                            self.is_chatting = True
                            
                            self.message_queue.put(('connected', {'peer': peer_username}))
                            self.start_receive_thread()
                            return
                        else:
                            reason = response.get('reason', 'Unknown reason')
                            self.message_queue.put(('error', {'message': f"Rejected: {reason}"}))
                            sock.close()
                            return
                except json.JSONDecodeError:
                    continue
            
            sock.close()
            self.message_queue.put(('error', {'message': "Invalid response from peer"}))
            
        except socket.timeout:
            self.message_queue.put(('error', {'message': "Connection timeout"}))
        except Exception as e:
            self.message_queue.put(('error', {'message': f"Connection failed: {str(e)}"}))
    
    def start_receive_thread(self):
        """Start thread to receive messages."""
        self.receive_thread = threading.Thread(
            target=self.receive_messages,
            daemon=True
        )
        self.receive_thread.start()
    
    def receive_messages(self):
        """Receive messages from connected peer."""
        while self.is_chatting and self.connection_socket:
            try:
                self.connection_socket.settimeout(1.0)
                data = self.connection_socket.recv(65536)
                
                if not data:
                    self.message_queue.put(('disconnected', {}))
                    break
                
                self.message_buffer.add_data(data.decode('utf-8'))
                messages = self.message_buffer.extract_messages()
                
                for message in messages:
                    self.handle_received_message(message)
                    
            except socket.timeout:
                continue
            except:
                self.message_queue.put(('disconnected', {}))
                break
    
    def handle_received_message(self, message):
        """Handle received message based on type."""
        msg_type = message.get('type')
        
        if msg_type == MSG_TYPES['CHAT_MESSAGE']:
            self.message_queue.put(('chat', {
                'sender': message.get('from'),
                'message': message.get('message')
            }))
        
        elif msg_type == MSG_TYPES['FILE_INIT']:
            self.message_queue.put(('file_init', message))
        
        elif msg_type == MSG_TYPES['FILE_CHUNK']:
            self.message_queue.put(('file_chunk', message))
        
        elif msg_type == MSG_TYPES['FILE_COMPLETE']:
            self.message_queue.put(('file_complete', message))
        
        elif msg_type == MSG_TYPES['DISCONNECT']:
            self.message_queue.put(('disconnected', {}))
        
        elif msg_type == MSG_TYPES['KEEP_ALIVE']:
            pass  # Ignore keep-alive messages
    
    # ─────────────────────────────────────────────────────────────────────────
    # Chat Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def send_chat_message(self, event=None):
        """Send chat message."""
        if not self.is_chatting:
            return
        
        message = self.message_entry.get().strip()
        if not message:
            return
        
        try:
            chat_message = {
                'type': MSG_TYPES['CHAT_MESSAGE'],
                'from': self.username,
                'message': message,
                'timestamp': time.time()
            }
            
            self.connection_socket.send((json.dumps(chat_message) + '\n').encode('utf-8'))
            self.add_chat_message(message, 'self')
            self.message_entry.delete(0, tk.END)
            
        except:
            self.disconnect_from_peer()
    
    def add_chat_message(self, message, sender_type='system'):
        """Add message to chat display."""
        self.chat_display.config(state='normal')
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if sender_type == 'self':
            self.chat_display.insert(tk.END, f"[{timestamp}] You: ", 'self')
            self.chat_display.insert(tk.END, f"{message}\n")
        elif sender_type == 'peer':
            self.chat_display.insert(tk.END, f"[{timestamp}] {self.connected_peer}: ", 'peer')
            self.chat_display.insert(tk.END, f"{message}\n")
        else:
            self.chat_display.insert(tk.END, f"[{timestamp}] {message}\n", sender_type)
        
        self.chat_display.config(state='disabled')
        self.chat_display.see(tk.END)
    
    def disconnect_from_peer(self):
        """Disconnect from current peer."""
        if self.connection_socket:
            try:
                disconnect_msg = {
                    'type': MSG_TYPES['DISCONNECT'],
                    'from': self.username
                }
                self.connection_socket.send((json.dumps(disconnect_msg) + '\n').encode('utf-8'))
            except:
                pass
            
            try:
                self.connection_socket.close()
            except:
                pass
            
            self.connection_socket = None
        
        self.is_chatting = False
        self.connected_peer = None
        
        # Update UI
        self.chat_title.config(text="💬 Select a peer to start chatting")
        self.disconnect_btn.config(state='disabled')
        self.message_entry.config(state='disabled')
        self.send_btn.config(state='disabled')
        self.select_file_btn.config(state='disabled')
        self.send_file_btn.config(state='disabled')
        
        self.add_chat_message("Disconnected from peer", 'system')
    
    # ─────────────────────────────────────────────────────────────────────────
    # File Transfer Methods (Bonus)
    # ─────────────────────────────────────────────────────────────────────────
    
    def select_file(self):
        """Select file for transfer."""
        filepath = filedialog.askopenfilename(
            title="Select File to Send"
        )
        
        if filepath:
            self.selected_file_path = filepath
            filename = os.path.basename(filepath)
            size = os.path.getsize(filepath)
            size_str = FileTransfer.format_size(size)
            
            self.file_label.config(
                text=f"{filename} ({size_str})",
                foreground='black'
            )
            self.send_file_btn.config(state='normal')
    
    def send_file(self):
        """Send selected file."""
        if not self.selected_file_path or not self.is_chatting:
            return
        
        threading.Thread(
            target=self.do_send_file,
            args=(self.selected_file_path,),
            daemon=True
        ).start()
    
    def do_send_file(self, filepath):
        """Send file in chunks."""
        try:
            filename = os.path.basename(filepath)
            filesize = os.path.getsize(filepath)
            file_hash = FileTransfer.calculate_hash(filepath)
            
            # Send file initialization
            init_msg = {
                'type': MSG_TYPES['FILE_INIT'],
                'filename': filename,
                'filesize': filesize,
                'hash': file_hash,
                'chunk_size': CHUNK_SIZE
            }
            
            self.connection_socket.send((json.dumps(init_msg) + '\n').encode('utf-8'))
            
            # Show progress
            self.message_queue.put(('file_progress', {
                'action': 'send',
                'filename': filename,
                'total': filesize
            }))
            
            # Send chunks
            sent = 0
            with open(filepath, 'rb') as f:
                while chunk := f.read(CHUNK_SIZE):
                    chunk_b64 = base64.b64encode(chunk).decode('utf-8')
                    
                    chunk_msg = {
                        'type': MSG_TYPES['FILE_CHUNK'],
                        'data': chunk_b64,
                        'index': sent // CHUNK_SIZE
                    }
                    
                    self.connection_socket.send((json.dumps(chunk_msg) + '\n').encode('utf-8'))
                    sent += len(chunk)
                    
                    # Update progress
                    progress = (sent / filesize) * 100
                    self.message_queue.put(('file_update', {'progress': progress}))
                    
                    time.sleep(0.001)  # Small delay
            
            # Send completion
            complete_msg = {
                'type': MSG_TYPES['FILE_COMPLETE'],
                'hash': file_hash
            }
            
            self.connection_socket.send((json.dumps(complete_msg) + '\n').encode('utf-8'))
            
            self.message_queue.put(('file_complete', {'success': True}))
            
        except Exception as e:
            self.message_queue.put(('error', {'message': f"File send failed: {str(e)}"}))
        finally:
            self.selected_file_path = None
            self.root.after(0, lambda: self.file_label.config(
                text="No file selected",
                foreground='gray'
            ))
            self.root.after(0, lambda: self.send_file_btn.config(state='disabled'))
    
    # ─────────────────────────────────────────────────────────────────────────
    # Pending Request Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def accept_pending_request(self):
        """Accept pending connection request."""
        with self.pending_lock:
            if not self.pending_socket:
                return
            
            try:
                # Send acceptance
                self.send_response(self.pending_socket, True)
                
                # Set as active connection
                self.connection_socket = self.pending_socket
                self.connected_peer = self.pending_request
                self.is_chatting = True
                
                # Update UI
                self.message_queue.put(('connected', {'peer': self.pending_request}))
                
                # Start receive thread
                self.start_receive_thread()
                
            except:
                pass
            finally:
                self.clear_pending_request()
    
    def reject_pending_request(self):
        """Reject pending connection request."""
        with self.pending_lock:
            if not self.pending_socket:
                return
            
            try:
                self.send_response(self.pending_socket, False, "Rejected by user")
            except:
                pass
            
            try:
                self.pending_socket.close()
            except:
                pass
            
            self.clear_pending_request()
    
    def clear_pending_request(self):
        """Clear pending request state."""
        self.pending_socket = None
        self.pending_request = None
        self.pending_label.config(text="No pending requests")
        self.accept_btn.config(state='disabled')
        self.reject_btn.config(state='disabled')
    
    # ─────────────────────────────────────────────────────────────────────────
    # Message Queue Processing
    # ─────────────────────────────────────────────────────────────────────────
    
    def process_message_queue(self):
        """Process messages from queue."""
        try:
            while True:
                try:
                    msg_type, data = self.message_queue.get_nowait()
                    self.handle_queued_message(msg_type, data)
                except queue.Empty:
                    break
        except:
            pass
        
        self.root.after(100, self.process_message_queue)
    
    def handle_queued_message(self, msg_type, data):
        """Handle message from queue."""
        if msg_type == 'chat':
            self.add_chat_message(data['message'], 'peer')
        
        elif msg_type == 'error':
            self.add_chat_message(data['message'], 'error')
        
        elif msg_type == 'connected':
            peer = data['peer']
            self.connected_peer = peer
            self.chat_title.config(text=f"💬 Chatting with {peer}")
            self.disconnect_btn.config(state='normal')
            self.message_entry.config(state='normal')
            self.send_btn.config(state='normal')
            self.select_file_btn.config(state='normal')
            self.add_chat_message(f"Connected to {peer}", 'system')
            self.clear_pending_request()
        
        elif msg_type == 'disconnected':
            self.disconnect_from_peer()
        
        elif msg_type == 'pending':
            from_user = data['from']
            self.pending_label.config(text=f"From: {from_user}")
            self.accept_btn.config(state='normal')
            self.reject_btn.config(state='normal')
        
        elif msg_type == 'file_progress':
            self.progress_frame.pack(fill='x', pady=(10, 0))
            self.progress_label.config(
                text=f"{data['action'].title()}ing: {data['filename']}"
            )
            self.progress_bar['value'] = 0
        
        elif msg_type == 'file_update':
            self.progress_bar['value'] = data['progress']
        
        elif msg_type == 'file_complete':
            self.progress_frame.pack_forget()
            if data.get('success'):
                self.add_chat_message("File transfer completed", 'system')
    
    # ─────────────────────────────────────────────────────────────────────────
    # Utility Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def show_login_status(self, message, color='black'):
        """Show status on login screen."""
        self.login_status.config(text=message, foreground=color)
        self.root.update()
    
    def show_login_error(self, message):
        """Show error on login screen."""
        self.show_login_status(f"❌ {message}", 'red')
    
    def logout(self):
        """Logout from network."""
        # Unregister from STUN
        if self.username and self.stun_client:
            self.stun_client.unregister(self.username)
        
        # Disconnect from peer
        self.disconnect_from_peer()
        
        # Stop TCP server
        self.stop_tcp_server()
        
        # Return to login screen
        self.build_login_screen()
    
    def on_closing(self):
        """Handle window closing."""
        self.logout()
        self.root.destroy()

# ─────────────────────────────────────────────────────────────────────────────
# Main Function
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """Main entry point."""
    root = tk.Tk()
    app = P2PChatGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()