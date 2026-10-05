"""
Integration tests for PeerNode.

Covers:
- Registration
- Peer discovery via STUN
- Connection establishment (accept + reject)
- Chat messaging
- Disconnection

These tests spin up two real PeerNodes and connect them locally.
"""

import time
import pytest

from shared.peer_core import PeerNode


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_peer(username, port, stun_url):
    return PeerNode(username, port, stun_url)


def wait_for(predicate, timeout=5.0, interval=0.05):
    """Wait until predicate() is truthy, or fail after timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def two_peers(stun_url, free_port):
    """Two peers registered with the STUN server."""
    # We use free_port twice, once for each peer
    import socket
    
    def free():
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]
    
    p1 = make_peer("alice", free(), stun_url)
    p2 = make_peer("bob", free(), stun_url)
    
    assert p1.start(), "Failed to start alice"
    assert p2.start(), "Failed to start bob"
    
    try:
        yield p1, p2
    finally:
        p1.shutdown()
        p2.shutdown()


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPeerNode:
    
    def test_register(self, stun_url, free_port):
        peer = make_peer("alice", free_port, stun_url)
        try:
            assert peer.register()
        finally:
            peer.shutdown()
    
    def test_register_duplicate(self, stun_url, free_port):
        p1 = make_peer("alice", free_port, stun_url)
        assert p1.start()
        try:
            import socket
            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                port2 = s.getsockname()[1]
            p2 = make_peer("alice", port2, stun_url)
            # p2.start should fail because alice is taken
            assert not p2.start()
            p2.shutdown()
        finally:
            p1.shutdown()
    
    def test_list_peers(self, two_peers):
        alice, bob = two_peers
        peers = alice.list_peers()
        usernames = {p["username"] for p in peers}
        assert "bob" in usernames
        assert "alice" not in usernames  # excluded
    
    def test_connect_and_chat(self, two_peers):
        alice, bob = two_peers
        
        # Setup event collectors
        alice_events = []
        bob_events = []
        alice.events.on("peer_connected", lambda **kw: alice_events.append(("connected", kw)))
        bob.events.on("connection_request", lambda **kw: bob_events.append(("request", kw)))
        bob.events.on("peer_connected", lambda **kw: bob_events.append(("connected", kw)))
        bob.events.on("chat_message", lambda **kw: bob_events.append(("msg", kw)))
        
        # Alice initiates
        assert alice.connect_to_peer("bob")
        
        # Bob should have a pending request
        assert wait_for(bob.has_pending_request, timeout=3)
        
        # Bob accepts
        assert bob.accept_pending()
        
        # Both should be connected
        assert wait_for(lambda: alice.is_chatting and bob.is_chatting, timeout=3)
        
        # Alice sends a message
        assert alice.send_chat("hello bob")
        
        # Bob should receive it
        assert wait_for(
            lambda: any(e[0] == "msg" and e[1].get("message") == "hello bob"
                        for e in bob_events),
            timeout=3,
        )
    
    def test_reject_connection(self, two_peers):
        alice, bob = two_peers
        
        alice_errors = []
        alice.events.on("error", lambda **kw: alice_errors.append(kw.get("message", "")))
        
        # Alice tries to connect
        alice.connect_to_peer("bob")
        
        # Bob rejects
        assert wait_for(bob.has_pending_request, timeout=3)
        bob.reject_pending()
        
        # Alice should receive an error
        assert wait_for(
            lambda: any("rejected" in e.lower() for e in alice_errors),
            timeout=3,
        )
        
        # Both should be idle
        assert not alice.is_chatting
        assert not bob.is_chatting
    
    def test_disconnect(self, two_peers):
        alice, bob = two_peers
        
        alice.connect_to_peer("bob")
        wait_for(bob.has_pending_request, timeout=3)
        bob.accept_pending()
        wait_for(lambda: alice.is_chatting and bob.is_chatting, timeout=3)
        
        # Alice disconnects
        alice.disconnect()
        
        assert wait_for(lambda: not alice.is_chatting, timeout=3)
        assert wait_for(lambda: not bob.is_chatting, timeout=3)