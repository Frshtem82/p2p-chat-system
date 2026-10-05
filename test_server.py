# test_server.py

import urllib.request
import urllib.error
import json


BASE_URL = "http://localhost:8000"


def make_request(method, endpoint, data=None):
    """Make HTTP request and return response"""
    url = f"{BASE_URL}{endpoint}"
    headers = {'Content-Type': 'application/json'}

    body = None
    if data:
        body = json.dumps(data).encode('utf-8')

    request = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request) as response:
            status_code = response.getcode()
            resp_body = json.loads(response.read().decode('utf-8'))
            return status_code, resp_body
    except urllib.error.HTTPError as e:
        status_code = e.code
        resp_body = json.loads(e.read().decode('utf-8'))
        return status_code, resp_body
    except urllib.error.URLError as e:
        return None, {'error': str(e.reason)}


def print_result(test_name, status_code, response):
    """Pretty print test result"""
    passed = "PASS" if status_code and status_code < 400 else "FAIL"
    icon = "+" if passed == "PASS" else "-"
    print(f"\n  [{icon}] {test_name}")
    print(f"      Status : {status_code}")
    print(f"      Response: {json.dumps(response, indent=6)}")


def run_tests():
    print()
    print("=" * 60)
    print("        STUN Server - Test Suite")
    print("=" * 60)

    # --- Test 1: Register peers ---
    print("\n--- Registration Tests ---")

    print_result(
        "Register 'alice'",
        *make_request('POST', '/register', {
            'username': 'alice',
            'ip': '192.168.1.10',
            'port': 5001
        })
    )

    print_result(
        "Register 'bob'",
        *make_request('POST', '/register', {
            'username': 'bob',
            'ip': '192.168.1.20',
            'port': 5002
        })
    )

    print_result(
        "Register 'charlie'",
        *make_request('POST', '/register', {
            'username': 'charlie',
            'ip': '192.168.1.30',
            'port': 5003
        })
    )

    # --- Test 2: Duplicate registration ---
    print("\n--- Error Handling Tests ---")

    print_result(
        "Duplicate 'alice' (expect 409)",
        *make_request('POST', '/register', {
            'username': 'alice',
            'ip': '10.0.0.1',
            'port': 9999
        })
    )

    print_result(
        "Missing fields (expect 400)",
        *make_request('POST', '/register', {
            'username': 'dave'
        })
    )

    print_result(
        "Invalid JSON (expect 400)",
        *make_request('POST', '/register')
    )

    # --- Test 3: Get all peers ---
    print("\n--- Query Tests ---")

    print_result(
        "Get all peers",
        *make_request('GET', '/peers')
    )

    # --- Test 4: Get specific peer ---
    print_result(
        "Get peer info for 'bob'",
        *make_request('GET', '/peerinfo?username=bob')
    )

    print_result(
        "Get unknown peer (expect 404)",
        *make_request('GET', '/peerinfo?username=unknown')
    )

    print_result(
        "Missing username param (expect 400)",
        *make_request('GET', '/peerinfo')
    )

    print()
    print("=" * 60)
    print("        All Tests Completed!")
    print("=" * 60)
    print()


if __name__ == '__main__':
    run_tests()
