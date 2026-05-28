"""
common_widgets.py  —  Shared UI components: KPICard, ChartFrame, NavButton, Sidebar.

FIXES vs uploaded version:
  • Sidebar.set_status()  was missing — main_window.py calls it after loading a dataset.
"""

from typing import Optional, Dict

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QWidget,
)

from config import C


# ── KPICard ───────────────────────────────────────────────────────────────────

class KPICard(QFrame):
    def __init__(self, icon: str, title: str,
                 value: str = "—", sub: str = "",
                 color: str = C["blue"]) -> None:
        super().__init__()
        self._color = color
        self.setFixedHeight(100)
        self.setMinimumWidth(155)
        self._apply_frame_style(color)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(3)

        top = QHBoxLayout()
        top.setSpacing(5)
        ico = QLabel(icon)
        ico.setFont(QFont("Segoe UI Emoji", 13))
        ttl = QLabel(title)
        ttl.setFont(QFont("Segoe UI", 8))
        ttl.setStyleSheet(f"color:{C['txt2']};")
        top.addWidget(ico)
        top.addWidget(ttl)
        top.addStretch()
        lay.addLayout(top)

        self._val = QLabel(value)
        self._val.setFont(QFont("Segoe UI", 19, QFont.Weight.Bold))
        self._val.setStyleSheet(f"color:{color};")
        lay.addWidget(self._val)

        self._sub = QLabel(sub)
        self._sub.setFont(QFont("Segoe UI", 7))
        self._sub.setStyleSheet(f"color:{C['txt3']};")
        lay.addWidget(self._sub)

    def update(self, value: str, sub: str = "", color: str | None = None) -> None:
        self._val.setText(value)
        if sub:
            self._sub.setText(sub)
        if color:
            self._val.setStyleSheet(f"color:{color};")
            self._apply_frame_style(color)

    def _apply_frame_style(self, color: str) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background:{C['bg3']};
                border:1px solid {C['border']};
                border-left:3px solid {color};
                border-radius:6px;
            }}
            QFrame:hover {{
                border:1px solid {color};
                border-left:3px solid {color};
            }}
        """)


# ── ChartFrame ────────────────────────────────────────────────────────────────

class ChartFrame(QFrame):
    """Embeds a matplotlib Figure inside a QFrame."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{ background:{C['bg1']}; border:1px solid {C['border']}; border-radius:6px; }}"
        )
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(6, 6, 6, 6)
        self._canvas: Optional[FigureCanvas] = None
        self._empty_lbl: Optional[QLabel] = None
        self._placeholder()

    def _placeholder(self, msg: str = "Run analysis to view chart") -> None:
        if self._canvas:
            self._lay.removeWidget(self._canvas)
            self._canvas.close()
            self._canvas = None

        lbl = QLabel(f"📊  {msg}")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color:{C['txt3']}; font-size:11pt; padding:30px;")
        self._lay.addWidget(lbl)
        self._empty_lbl = lbl

    def load(self, fig: Figure) -> None:
        # Remove placeholder
        if self._empty_lbl is not None:
            self._lay.removeWidget(self._empty_lbl)
            self._empty_lbl.deleteLater()
            self._empty_lbl = None

        if self._canvas:
            self._lay.removeWidget(self._canvas)
            self._canvas.close()
            plt.close(fig)

        self._canvas = FigureCanvas(fig)
        self._canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._lay.addWidget(self._canvas)
        self._canvas.draw()

    def clear(self) -> None:
        self._placeholder()


# ── NavButton ─────────────────────────────────────────────────────────────────

class NavButton(QPushButton):
    def __init__(self, key: str, icon: str, label: str) -> None:
        super().__init__(f"  {icon}  {label}")
        self.key = key
        self.setCheckable(True)
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(QFont("Segoe UI", 10))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._set_style(False)

    def set_active(self, active: bool) -> None:
        self._set_style(active)

    def _set_style(self, active: bool) -> None:
        if active:
            self.setStyleSheet(f"""
                QPushButton {{
                    background:{C['bg2']}; color:{C['blue']};
                    border:none; border-left:3px solid {C['blue']};
                    border-radius:4px; text-align:left; padding-left:12px;
                    font-weight:700;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; color:{C['txt2']};
                    border:none; border-left:3px solid transparent;
                    border-radius:4px; text-align:left; padding-left:12px;
                }}
                QPushButton:hover {{ background:{C['bg2']}; color:{C['txt']}; }}
            """)


# ── Sidebar ───────────────────────────────────────────────────────────────────

class Sidebar(QFrame):
    """
    Vertical navigation sidebar.

    FIX: added set_status() which was missing but called by main_window.py.
    FIX: _click() now has a guard so external set_active() calls don't
         re-emit the signal (avoids the recursion in _navigate).
    """

    nav = Signal(str)

    NAV = [
        ("home",          "🏠", "Home"),
        ("import",        "📂", "Import Dataset"),
        ("applicability", "🔍", "Applicability"),
        ("benford",       "📊", "Benford Analysis"),
        ("statistics",    "🧮", "Statistical Tests"),
        ("forensic",      "🔬", "Forensic Analytics"),
        ("risk",          "🛡", "Risk Dashboard"),
        ("suspicious",    "⚠️", "Suspicious Txns"),
        ("settings",      "⚙️", "Settings"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.setFixedWidth(198)
        self.setStyleSheet(f"""
            QFrame {{
                background:{C['bg1']};
                border:none;
                border-right:1px solid {C['border']};
                border-radius:0;
            }}
        """)
        self._btns: Dict[str, NavButton] = {}
        self._status_lbl: Optional[QLabel] = None
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Brand bar
        brand = QFrame()
        brand.setFixedHeight(60)
        brand.setStyleSheet(f"""
            QFrame {{
                background:{C['bg0']};
                border:none;
                border-bottom:1px solid {C['border']};
                border-radius:0;
            }}
        """)
        bl = QVBoxLayout(brand)
        bl.setContentsMargins(14, 8, 14, 8)
        bl.setSpacing(1)
        logo = QLabel("🔍  AuditLens")
        logo.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        logo.setStyleSheet(f"color:{C['txt']};")
        sub = QLabel("Forensic Analytics Platform")
        sub.setFont(QFont("Segoe UI", 7))
        sub.setStyleSheet(f"color:{C['txt3']};")
        bl.addWidget(logo)
        bl.addWidget(sub)
        lay.addWidget(brand)

        # Nav buttons
        nav_w = QWidget()
        nav_w.setStyleSheet("background:transparent;")
        nlay = QVBoxLayout(nav_w)
        nlay.setContentsMargins(6, 10, 6, 10)
        nlay.setSpacing(2)
        for key, icon, label in self.NAV:
            btn = NavButton(key, icon, label)
            btn.clicked.connect(lambda _, k=key: self._click(k))
            self._btns[key] = btn
            nlay.addWidget(btn)
        nlay.addStretch()
        lay.addWidget(nav_w, 1)

        # Status bar at the bottom  ← FIX: was completely absent
        self._status_lbl = QLabel("No dataset loaded")
        self._status_lbl.setFont(QFont("Segoe UI", 7))
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet(
            f"color:{C['txt3']}; padding:6px 14px; "
            f"border-top:1px solid {C['border']}; background:{C['bg0']};"
        )
        lay.addWidget(self._status_lbl)

    def _click(self, key: str) -> None:
        self.set_active(key)
        self.nav.emit(key)

    def set_active(self, key: str) -> None:
        """Highlight the given nav item WITHOUT emitting the nav signal."""
        for k, btn in self._btns.items():
            btn.setChecked(k == key)
            btn.set_active(k == key)

    # FIX: this method was missing — main_window calls it after loading a file
    def set_status(self, text: str, color: str = C["txt3"]) -> None:
        """Update the status bar label at the bottom of the sidebar."""
        if self._status_lbl is not None:
            self._status_lbl.setText(text)
            self._status_lbl.setStyleSheet(
                f"color:{color}; padding:6px 14px; "
                f"border-top:1px solid {C['border']}; background:{C['bg0']};"
            )
