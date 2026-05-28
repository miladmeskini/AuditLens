import math
from typing import Dict

BENFORD_FIRST: Dict[int, float] = {
    1: 0.30103, 2: 0.17609, 3: 0.12494, 4: 0.09691,
    5: 0.07918, 6: 0.06695, 7: 0.05799, 8: 0.05115, 9: 0.04576,
}

BENFORD_SECOND: Dict[int, float] = {
    0: 0.11968, 1: 0.11389, 2: 0.10882, 3: 0.10433,
    4: 0.10031, 5: 0.09668, 6: 0.09337, 7: 0.09035,
    8: 0.08757, 9: 0.08500,
}

BENFORD_FIRST_TWO: Dict[int, float] = {
    d: math.log10(1 + 1 / d) for d in range(10, 100)
}

MAD_BANDS = [
    (0.006, "Close Conformity",       "#3fb950"),
    (0.012, "Acceptable Conformity",  "#d29922"),
    (0.015, "Marginally Acceptable",  "#f0883e"),
    (9999,  "Nonconformity",          "#f85149"),
]

# Dark theme palette
C = {
    "bg0":      "#0d1117",
    "bg1":      "#161b22",
    "bg2":      "#21262d",
    "bg3":      "#1c2128",
    "border":   "#30363d",
    "blue":     "#2f81f7",
    "cyan":     "#39d353",
    "orange":   "#f0883e",
    "red":      "#f85149",
    "yellow":   "#e3b341",
    "green":    "#3fb950",
    "txt":      "#e6edf3",
    "txt2":     "#8b949e",
    "txt3":     "#484f58",
}

DISCLAIMER = (
    "⚠  Benford's Law analysis is an anomaly-screening technique. "
    "Deviation from Benford's Law does NOT constitute proof of fraud, "
    "error, or misconduct.  All findings require professional judgement "
    "and further investigation. "
    "Developed by Milad Meskini, 2026 "
)

GLOBAL_QSS = f"""
* {{
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
    color: {C['txt']};
}}
QWidget, QMainWindow {{
    background-color: {C['bg0']};
}}
QFrame {{
    background-color: {C['bg1']};
    border: 1px solid {C['border']};
    border-radius: 6px;
}}
QGroupBox {{
    color: {C['txt2']};
    border: 1px solid {C['border']};
    border-radius: 6px;
    margin-top: 10px;
    font-size: 9pt;
    font-weight: 600;
    background-color: {C['bg1']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: {C['txt2']};
}}
QPushButton {{
    background-color: {C['bg2']};
    border: 1px solid {C['border']};
    border-radius: 5px;
    padding: 6px 14px;
    font-weight: 600;
    color: {C['txt']};
}}
QPushButton:hover  {{ background-color: {C['blue']};  border-color: {C['blue']}; color: white; }}
QPushButton:pressed {{ background-color: #1a6fd4; }}
QPushButton:disabled {{ color: {C['txt3']}; background-color: {C['bg2']}; }}
QComboBox {{
    background-color: {C['bg2']};
    border: 1px solid {C['border']};
    border-radius: 4px;
    padding: 4px 8px;
    color: {C['txt']};
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: {C['bg2']};
    color: {C['txt']};
    selection-background-color: {C['blue']};
    border: 1px solid {C['border']};
}}
QLineEdit {{
    background-color: {C['bg2']};
    border: 1px solid {C['border']};
    border-radius: 4px;
    padding: 4px 8px;
    color: {C['txt']};
}}
QCheckBox {{ color: {C['txt2']}; background: transparent; }}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {C['border']};
    border-radius: 3px;
    background: {C['bg2']};
}}
QCheckBox::indicator:checked {{ background: {C['blue']}; border-color: {C['blue']}; }}
QTableWidget, QTableView {{
    background-color: {C['bg1']};
    gridline-color: {C['border']};
    border: 1px solid {C['border']};
    border-radius: 4px;
    selection-background-color: {C['blue']};
    alternate-background-color: {C['bg3']};
}}
QHeaderView::section {{
    background-color: {C['bg2']};
    color: {C['txt2']};
    border: none;
    border-right: 1px solid {C['border']};
    border-bottom: 1px solid {C['border']};
    padding: 5px 8px;
    font-weight: 600;
}}
QScrollBar:vertical {{
    background: {C['bg1']};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {C['bg2']};
    border-radius: 4px;
    min-height: 20px;
}}
QTabWidget::pane {{
    border: 1px solid {C['border']};
    background: {C['bg1']};
    border-radius: 6px;
}}
QTabBar::tab {{
    background: {C['bg2']};
    color: {C['txt2']};
    border: 1px solid {C['border']};
    border-bottom: none;
    padding: 6px 18px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {C['bg1']};
    color: {C['txt']};
    border-bottom: 2px solid {C['blue']};
}}
QProgressBar {{
    background-color: {C['bg2']};
    border: none;
    border-radius: 3px;
    height: 4px;
}}
QProgressBar::chunk {{
    background-color: {C['blue']};
    border-radius: 3px;
}}
QTextEdit {{
    background-color: {C['bg2']};
    border: 1px solid {C['border']};
    border-radius: 4px;
    color: {C['txt2']};
    font-size: 9pt;
}}
QLabel {{ background: transparent; }}
QScrollArea {{ border: none; background: transparent; }}
"""