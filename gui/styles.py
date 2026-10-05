"""
Centralized styling for the GUI.

All colors, fonts, and ttk styles are defined here.
Views should import from this module instead of hardcoding values.
"""

import tkinter as tk
from tkinter import ttk


# ─────────────────────────────────────────────────────────────────────────────
# Color Palette
# ─────────────────────────────────────────────────────────────────────────────

class Palette:
    """Application color palette."""
    
    # Backgrounds
    BG = "#f5f6fa"                 # window background
    BG_CARD = "#ffffff"            # card / panel background
    BG_DARK = "#2f3640"            # header / sidebar
    BG_INPUT = "#ffffff"           # entry background
    
    # Text
    FG = "#2f3640"                 # primary text
    FG_MUTED = "#7f8c8d"           # secondary text
    FG_LIGHT = "#ffffff"           # text on dark backgrounds
    FG_DISABLED = "#bdc3c7"
    
    # Accents
    PRIMARY = "#0984e3"            # main blue
    PRIMARY_HOVER = "#0770c4"
    PRIMARY_LIGHT = "#74b9ff"
    
    SUCCESS = "#00b894"            # green
    WARNING = "#fdcb6e"            # yellow
    DANGER = "#d63031"             # red
    DANGER_HOVER = "#b02525"
    
    # Chat
    SELF_BUBBLE = "#dff9fb"        # light cyan for own messages
    PEER_BUBBLE = "#f1f2f6"        # light gray for peer messages
    SYSTEM_TEXT = "#95a5a6"        # system messages
    
    # Borders
    BORDER = "#dcdde1"
    BORDER_FOCUS = "#0984e3"


# ─────────────────────────────────────────────────────────────────────────────
# Fonts
# ─────────────────────────────────────────────────────────────────────────────

class Fonts:
    """Application fonts."""
    
    # Use system default sans-serif
    FAMILY = "Segoe UI"  # falls back to system default on Linux/Mac
    
    # Sizes
    TITLE = (FAMILY, 24, "bold")
    SUBTITLE = (FAMILY, 13)
    HEADING = (FAMILY, 14, "bold")
    BODY = (FAMILY, 11)
    BODY_BOLD = (FAMILY, 11, "bold")
    SMALL = (FAMILY, 9)
    SMALL_MUTED = (FAMILY, 9)
    CHAT = (FAMILY, 11)
    CHAT_BOLD = (FAMILY, 11, "bold")
    MONO = ("Consolas", 10)  # for file paths, hashes, etc.
    
    # Try to pick a nicer font if available
    @classmethod
    def pick_default(cls):
        """Pick a sensible default font for the current OS."""
        try:
            import tkinter.font as tkfont
            families = set(tkfont.families())
            for candidate in ("Segoe UI", "SF Pro Text", "Helvetica Neue",
                              "Ubuntu", "DejaVu Sans", "Helvetica", "Arial"):
                if candidate in families:
                    cls.FAMILY = candidate
                    # Rebuild tuples
                    cls.TITLE = (candidate, 24, "bold")
                    cls.SUBTITLE = (candidate, 13)
                    cls.HEADING = (candidate, 14, "bold")
                    cls.BODY = (candidate, 11)
                    cls.BODY_BOLD = (candidate, 11, "bold")
                    cls.SMALL = (candidate, 9)
                    cls.CHAT = (candidate, 11)
                    cls.CHAT_BOLD = (candidate, 11, "bold")
                    break
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Spacing / Geometry
# ─────────────────────────────────────────────────────────────────────────────

class Spacing:
    """Common spacing values (in pixels)."""
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32


class Sizes:
    """Common sizes."""
    WINDOW_MIN_W = 900
    WINDOW_MIN_H = 600
    WINDOW_DEF_W = 1100
    WINDOW_DEF_H = 720
    SIDEBAR_W = 280
    INPUT_H = 36


# ─────────────────────────────────────────────────────────────────────────────
# Tk style setup
# ─────────────────────────────────────────────────────────────────────────────

def apply_theme(root: tk.Tk) -> ttk.Style:
    """
    Apply the application theme.
    
    Should be called once after creating the root window.
    
    Returns:
        The configured ttk.Style instance.
    """
    Fonts.pick_default()
    
    style = ttk.Style(root)
    # 'clam' is the most themable built-in theme
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    
    # ── Root ─────────────────────────────────────────────────────────────
    root.configure(bg=Palette.BG)
    
    # ── Frames ───────────────────────────────────────────────────────────
    style.configure("TFrame", background=Palette.BG)
    style.configure("Card.TFrame", background=Palette.BG_CARD)
    style.configure("Dark.TFrame", background=Palette.BG_DARK)
    
    # ── Labels ───────────────────────────────────────────────────────────
    style.configure(
        "TLabel",
        background=Palette.BG, foreground=Palette.FG,
        font=Fonts.BODY,
    )
    style.configure(
        "Card.TLabel",
        background=Palette.BG_CARD, foreground=Palette.FG,
    )
    style.configure(
        "Title.TLabel",
        background=Palette.BG, foreground=Palette.FG,
        font=Fonts.TITLE,
    )
    style.configure(
        "Subtitle.TLabel",
        background=Palette.BG, foreground=Palette.FG_MUTED,
        font=Fonts.SUBTITLE,
    )
    style.configure(
        "Heading.TLabel",
        background=Palette.BG, foreground=Palette.FG,
        font=Fonts.HEADING,
    )
    style.configure(
        "Muted.TLabel",
        background=Palette.BG, foreground=Palette.FG_MUTED,
        font=Fonts.SMALL,
    )
    style.configure(
        "Dark.TLabel",
        background=Palette.BG_DARK, foreground=Palette.FG_LIGHT,
        font=Fonts.BODY,
    )
    style.configure(
        "DarkTitle.TLabel",
        background=Palette.BG_DARK, foreground=Palette.FG_LIGHT,
        font=Fonts.HEADING,
    )
    
    # ── Buttons ──────────────────────────────────────────────────────────
    style.configure(
        "TButton",
        font=Fonts.BODY,
        padding=(Spacing.MD, Spacing.SM),
        background=Palette.PRIMARY,
        foreground=Palette.FG_LIGHT,
        borderwidth=0,
        focusthickness=0,
    )
    style.map(
        "TButton",
        background=[("active", Palette.PRIMARY_HOVER),
                    ("disabled", Palette.FG_DISABLED)],
        foreground=[("disabled", Palette.FG_LIGHT)],
    )
    
    style.configure(
        "Secondary.TButton",
        background=Palette.BG_CARD,
        foreground=Palette.FG,
        borderwidth=1,
        relief="solid",
    )
    style.map(
        "Secondary.TButton",
        background=[("active", Palette.BG),
                    ("disabled", Palette.BG)],
        foreground=[("disabled", Palette.FG_DISABLED)],
    )
    
    style.configure(
        "Danger.TButton",
        background=Palette.DANGER,
        foreground=Palette.FG_LIGHT,
    )
    style.map(
        "Danger.TButton",
        background=[("active", Palette.DANGER_HOVER)],
    )
    
    style.configure(
        "Success.TButton",
        background=Palette.SUCCESS,
        foreground=Palette.FG_LIGHT,
    )
    
    # ── Entry ────────────────────────────────────────────────────────────
    style.configure(
        "TEntry",
        fieldbackground=Palette.BG_INPUT,
        foreground=Palette.FG,
        bordercolor=Palette.BORDER,
        lightcolor=Palette.BORDER,
        darkcolor=Palette.BORDER,
        insertcolor=Palette.FG,
        padding=Spacing.SM,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", Palette.BORDER_FOCUS)],
        lightcolor=[("focus", Palette.BORDER_FOCUS)],
        darkcolor=[("focus", Palette.BORDER_FOCUS)],
    )
    
    # ── Labelframe ───────────────────────────────────────────────────────
    style.configure(
        "TLabelframe",
        background=Palette.BG,
        bordercolor=Palette.BORDER,
        borderwidth=1,
        relief="solid",
    )
    style.configure(
        "TLabelframe.Label",
        background=Palette.BG,
        foreground=Palette.FG_MUTED,
        font=Fonts.SMALL,
    )
    
    # ── Separator ────────────────────────────────────────────────────────
    style.configure("TSeparator", background=Palette.BORDER)
    
    # ── Progressbar ──────────────────────────────────────────────────────
    style.configure(
        "TProgressbar",
        background=Palette.PRIMARY,
        troughcolor=Palette.BG_CARD,
        borderwidth=0,
        thickness=8,
    )
    
    # ── Scrollbar ────────────────────────────────────────────────────────
    style.configure(
        "Vertical.TScrollbar",
        background=Palette.BG,
        troughcolor=Palette.BG,
        bordercolor=Palette.BG,
        arrowcolor=Palette.FG_MUTED,
    )
    
    return style


# ─────────────────────────────────────────────────────────────────────────────
# Small helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_button(parent, text, command=None, style="TButton",
                width=None, state="normal"):
    """Convenience for creating a ttk.Button."""
    btn = ttk.Button(parent, text=text, command=command,
                     style=style, state=state)
    if width:
        btn.configure(width=width)
    return btn


def make_entry(parent, textvariable=None, width=None, show=None):
    """Convenience for creating a ttk.Entry."""
    entry = ttk.Entry(parent, textvariable=textvariable, font=Fonts.BODY)
    if width:
        entry.configure(width=width)
    if show:
        entry.configure(show=show)
    return entry