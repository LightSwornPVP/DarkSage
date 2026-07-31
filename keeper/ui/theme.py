from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class KeeperTheme:
    background: str = "#08090B"
    sidebar: str = "#0D0F12"
    surface: str = "#13161A"
    surface_raised: str = "#191D22"
    border: str = "#34302A"
    gold: str = "#D6B25E"
    gold_hover: str = "#E2C77C"
    text: str = "#F2F3F5"
    muted: str = "#9A9FA8"
    subtle: str = "#6F747D"
    success: str = "#71B68C"
    danger: str = "#D77B7B"
    warning: str = "#D6A65E"


THEME = KeeperTheme()


def configure_ttk(root: Any, ttk: Any, theme: KeeperTheme = THEME) -> None:
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    root.configure(background=theme.background)
    style.configure(
        ".",
        background=theme.background,
        foreground=theme.text,
        font=("Segoe UI", 10),
    )
    style.configure("App.TFrame", background=theme.background)
    style.configure("Sidebar.TFrame", background=theme.sidebar)
    style.configure("Surface.TFrame", background=theme.surface)
    style.configure(
        "Card.TFrame",
        background=theme.surface_raised,
        bordercolor=theme.border,
        relief="solid",
        borderwidth=1,
    )
    style.configure("Rail.TFrame", background=theme.sidebar)
    style.configure(
        "Title.TLabel",
        background=theme.background,
        foreground=theme.text,
        font=("Segoe UI Semibold", 22),
    )
    style.configure(
        "Heading.TLabel",
        background=theme.surface_raised,
        foreground=theme.text,
        font=("Segoe UI Semibold", 12),
    )
    style.configure(
        "Body.TLabel",
        background=theme.surface_raised,
        foreground=theme.text,
    )
    style.configure(
        "Muted.TLabel",
        background=theme.surface_raised,
        foreground=theme.muted,
    )
    style.configure(
        "Gold.TLabel",
        background=theme.surface_raised,
        foreground=theme.gold,
        font=("Segoe UI Semibold", 10),
    )
    style.configure(
        "RailHeading.TLabel",
        background=theme.sidebar,
        foreground=theme.gold,
        font=("Segoe UI Semibold", 10),
    )
    style.configure(
        "RailBody.TLabel",
        background=theme.sidebar,
        foreground=theme.text,
    )
    style.configure(
        "Nav.TButton",
        background=theme.sidebar,
        foreground=theme.muted,
        borderwidth=0,
        anchor="w",
        padding=(18, 11),
    )
    style.map(
        "Nav.TButton",
        background=[("active", theme.surface_raised)],
        foreground=[("active", theme.text)],
    )
    style.configure(
        "Accent.TButton",
        background=theme.gold,
        foreground="#111111",
        borderwidth=0,
        padding=(16, 9),
        font=("Segoe UI Semibold", 10),
    )
    style.map("Accent.TButton", background=[("active", theme.gold_hover)])
    style.configure(
        "Quiet.TButton",
        background=theme.surface_raised,
        foreground=theme.text,
        bordercolor=theme.border,
        padding=(12, 8),
    )
    style.configure(
        "Keeper.TEntry",
        fieldbackground=theme.surface_raised,
        foreground=theme.text,
        insertcolor=theme.gold,
        bordercolor=theme.border,
        padding=9,
    )
    style.configure(
        "Keeper.Treeview",
        background=theme.surface,
        fieldbackground=theme.surface,
        foreground=theme.text,
        rowheight=30,
        borderwidth=0,
    )
    style.configure(
        "Keeper.Treeview.Heading",
        background=theme.surface_raised,
        foreground=theme.gold,
        relief="flat",
        font=("Segoe UI Semibold", 9),
    )
    style.map(
        "Keeper.Treeview",
        background=[("selected", theme.border)],
        foreground=[("selected", theme.text)],
    )
