"""Temporary test for LoginView."""
import tkinter as tk
from gui.styles import apply_theme
from gui.login_view import LoginView


def on_connect(username, port, stun_url):
    print(f"[TEST] Would connect as '{username}' to {stun_url} on port {port}")


root = tk.Tk()
root.title("Login View Test")
root.geometry("800x600")
apply_theme(root)

view = LoginView(root, on_connect=on_connect)
view.pack(fill="both", expand=True)

root.mainloop()