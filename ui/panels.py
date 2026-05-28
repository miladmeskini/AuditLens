"""
panels.py  —  All content panels for the AuditLens application.

FIXES vs uploaded version:
  1. ForensicPanel.__init__ was truncated mid-line (ended with bare `tabs`
     expression). Re-implemented in full with _dup_table, _endings_box,
     and the mandatory update() method.
  2. RiskPanel was missing its update(risk) method entirely.
     main_window._on_analysis_done() calls self._risk_p.update(risk).
  3. SuspiciousPanel method was named update_rows() — renamed to update().
     Attribute access used wrong field names (row_index, reason, details)
     that don't exist on SuspiciousRow; corrected to orig_idx, flags, level.
"""

import os
from pathlib import Path
from collections import Counter
from typing import Optional, Dict, List, Tuple

import pandas as pd
from PySide6.QtCore import Qt, Signal, QThread, QObject
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QPushButton, QProgressBar, QGroupBox, QCheckBox, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QSplitter, QTextEdit, QTabWidget,
)

from config import C, DISCLAIMER
from models import (
    DatasetInfo, ApplicabilityResult, BenfordResult,
    ForensicResult, RiskScore, SuspiciousRow, RiskLevel,
)
from charts import (
    chart_benford_bars, chart_deviation, chart_z_stats,
    chart_cumulative, chart_risk_gauge, chart_risk_components, chart_duplicates,
)
from ui.common_widgets import KPICard, ChartFrame


# ══════════════════════════════════════════════════════════════════════════════
# HomePanel
# ══════════════════════════════════════════════════════════════════════════════

class HomePanel(QWidget):
    go_import = Signal()

    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(48, 48, 48, 48)
        lay.setSpacing(20)

        title = QLabel("AuditLens")
        title.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{C['txt']};")
        lay.addWidget(title)

        sub = QLabel("Forensic Audit Analytics Platform")
        sub.setFont(QFont("Segoe UI", 13))
        sub.setStyleSheet(f"color:{C['txt2']};")
        lay.addWidget(sub)

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background:{C['border']};border:none;")
        lay.addWidget(div)

        features = [
            ("📊", "Benford's Law",    "First, Second, and First-Two digit tests"),
            ("🧮", "Statistical Tests", "MAD, Chi-Square, Z-Statistics, KS Test"),
            ("🔬", "Forensic Analytics","Duplicates, round numbers, suspicious endings"),
            ("🛡",  "Risk Scoring",     "Weighted composite risk at dataset & subgroup level"),
            ("⚠️", "Investigation",    "Drill-down into flagged transactions"),
            ("📋", "Reporting",        "Export to Excel investigation packages"),
        ]
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, (icon, name, desc) in enumerate(features):
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background:{C['bg3']}; border:1px solid {C['border']}; "
                f"border-radius:8px; }} QFrame:hover {{ border-color:{C['blue']}; }}"
            )
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 14, 16, 14)
            cl.setSpacing(4)
            ico_lbl = QLabel(icon)
            ico_lbl.setFont(QFont("Segoe UI Emoji", 18))
            name_lbl = QLabel(name)
            name_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            name_lbl.setStyleSheet(f"color:{C['txt']};")
            desc_lbl = QLabel(desc)
            desc_lbl.setFont(QFont("Segoe UI", 8))
            desc_lbl.setStyleSheet(f"color:{C['txt2']};")
            desc_lbl.setWordWrap(True)
            cl.addWidget(ico_lbl)
            cl.addWidget(name_lbl)
            cl.addWidget(desc_lbl)
            grid.addWidget(card, i // 3, i % 3)
        lay.addLayout(grid)

        btn = QPushButton("  📂   Import Dataset to Begin")
        btn.setFixedHeight(44)
        btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        btn.setStyleSheet(f"""
            QPushButton {{ background:{C['blue']}; color:white; border:none;
                           border-radius:6px; padding:0 24px; }}
            QPushButton:hover {{ background:#4a9eff; }}
        """)
        btn.clicked.connect(self.go_import)
        lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)

        disc = QLabel(DISCLAIMER)
        disc.setWordWrap(True)
        disc.setFont(QFont("Segoe UI", 8))
        disc.setStyleSheet(
            f"color:{C['yellow']};background:{C['bg3']};"
            f"border:1px solid {C['yellow']};border-radius:5px;padding:8px 12px;"
        )
        lay.addWidget(disc)
        lay.addStretch()


# ══════════════════════════════════════════════════════════════════════════════
# File loading helper
# ══════════════════════════════════════════════════════════════════════════════

def _load_file(filepath: str, sheet=0) -> Tuple[pd.DataFrame, DatasetInfo]:
    path   = Path(filepath)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            df = pd.read_csv(filepath, encoding="utf-8", low_memory=False)
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding="latin-1", low_memory=False)
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(filepath, sheet_name=sheet, engine="openpyxl")
    else:
        raise ValueError(f"Unsupported format: {suffix}")

    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all").reset_index(drop=True)

    num_cols, date_cols, txt_cols = [], [], []
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            num_cols.append(col)
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            date_cols.append(col)
        else:
            coerced = pd.to_numeric(df[col], errors="coerce")
            if coerced.notna().sum() / max(len(df[col].dropna()), 1) >= 0.7:
                num_cols.append(col)
            else:
                txt_cols.append(col)

    info = DatasetInfo(
        filename=path.name,
        row_count=len(df),
        col_count=len(df.columns),
        numeric_cols=num_cols,
        text_cols=txt_cols,
        date_cols=date_cols,
        null_count=int(df.isnull().sum().sum()),
        dup_row_count=int(df.duplicated().sum()),
        file_size_kb=round(os.path.getsize(filepath) / 1024, 1),
    )
    return df, info


# ══════════════════════════════════════════════════════════════════════════════
# ImportPanel
# ══════════════════════════════════════════════════════════════════════════════

class ImportPanel(QWidget):
    dataset_ready = Signal(object, object, str, str, bool, bool, float)

    def __init__(self) -> None:
        super().__init__()
        self._df:     Optional[pd.DataFrame]  = None
        self._info:   Optional[DatasetInfo]   = None
        self._thread: Optional[QThread]       = None
        self._setup()
        self.setAcceptDrops(True)

    def _setup(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 22)
        lay.setSpacing(16)

        t = QLabel("Import Dataset")
        t.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        lay.addWidget(t)

        # Drop zone
        self._dropzone = QFrame()
        self._dropzone.setFixedHeight(110)
        self._dropzone.setObjectName("dz")
        self._dropzone.setStyleSheet("""
            QFrame#dz { background:#161b22; border:2px dashed #30363d; border-radius:10px; }
            QFrame#dz:hover { border-color:#2f81f7; background:#21262d; }
        """)
        dz_lay = QVBoxLayout(self._dropzone)
        dz_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dz_lay.setSpacing(6)
        dz_ico = QLabel("📂")
        dz_ico.setFont(QFont("Segoe UI Emoji", 20))
        dz_ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dz_txt = QLabel("Drop CSV or XLSX here, or click Browse")
        dz_txt.setStyleSheet(f"color:{C['txt2']};font-size:10pt;")
        dz_txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        browse = QPushButton("Browse…")
        browse.setFixedWidth(120)
        browse.clicked.connect(self._browse)
        dz_lay.addWidget(dz_ico)
        dz_lay.addWidget(dz_txt)
        dz_lay.addWidget(browse, alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._dropzone)

        # Progress
        self._prog = QProgressBar()
        self._prog.setRange(0, 0)
        self._prog.setFixedHeight(4)
        self._prog.setVisible(False)
        lay.addWidget(self._prog)

        self._prog_lbl = QLabel("")
        self._prog_lbl.setFont(QFont("Segoe UI", 8))
        self._prog_lbl.setStyleSheet(f"color:{C['txt2']};")
        self._prog_lbl.setVisible(False)
        lay.addWidget(self._prog_lbl)

        # Options
        opt = QGroupBox("Options")
        og = QGridLayout(opt)
        og.setSpacing(10)
        self._excl_z = QCheckBox("Exclude zeros")
        self._excl_z.setChecked(True)
        self._excl_n = QCheckBox("Absolute value of negatives")
        self._excl_n.setChecked(True)
        og.addWidget(self._excl_z, 0, 0)
        og.addWidget(self._excl_n, 0, 1)
        og.addWidget(QLabel("Materiality floor (min amount, 0=none):"), 1, 0)
        self._mat = QLineEdit("0")
        self._mat.setFixedWidth(120)
        og.addWidget(self._mat, 1, 1)
        og.addWidget(QLabel("Excel sheet:"), 2, 0)
        self._sheet = QComboBox()
        self._sheet.setEnabled(False)
        og.addWidget(self._sheet, 2, 1)
        lay.addWidget(opt)

        # Dataset summary
        self._info_grp = QGroupBox("Dataset Summary")
        ig = QGridLayout(self._info_grp)
        ig.setSpacing(8)
        self._ilabels: Dict[str, QLabel] = {}
        fields = [
            ("File", "file"), ("Rows", "rows"), ("Columns", "cols"),
            ("Numeric cols", "num"), ("Null values", "nulls"),
            ("File size", "size"), ("Duplicate rows", "dups"),
        ]
        for i, (lbl, key) in enumerate(fields):
            r, c = divmod(i, 2)
            ql = QLabel(lbl + ":")
            ql.setStyleSheet(f"color:{C['txt2']};font-size:9pt;")
            vl = QLabel("—")
            vl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            ig.addWidget(ql, r, c * 2)
            ig.addWidget(vl, r, c * 2 + 1)
            self._ilabels[key] = vl
        lay.addWidget(self._info_grp)

        # Preview table
        prev_grp = QGroupBox("Preview (first 50 rows)")
        pl = QVBoxLayout(prev_grp)
        self._preview = QTableWidget()
        self._preview.setAlternatingRowColors(True)
        self._preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._preview.setFixedHeight(180)
        pl.addWidget(self._preview)
        lay.addWidget(prev_grp)

        # Column selector bar
        sel_frame = QFrame()
        sel_frame.setStyleSheet(
            f"QFrame {{background:{C['bg3']};border:1px solid {C['border']};border-radius:6px;}}"
        )
        sfl = QHBoxLayout(sel_frame)
        sfl.setContentsMargins(14, 10, 14, 10)
        sfl.setSpacing(14)
        sfl.addWidget(QLabel("Amount column:"))
        self._col_combo = QComboBox()
        self._col_combo.setMinimumWidth(180)
        sfl.addWidget(self._col_combo)
        sfl.addWidget(QLabel("Group by (optional):"))
        self._grp_combo = QComboBox()
        self._grp_combo.setMinimumWidth(150)
        sfl.addWidget(self._grp_combo)
        sfl.addStretch()
        self._run_btn = QPushButton("  Run Analysis  →")
        self._run_btn.setEnabled(False)
        self._run_btn.setFixedHeight(34)
        self._run_btn.setStyleSheet(f"""
            QPushButton {{ background:{C['blue']};color:white;border:none;
                           border-radius:5px;font-weight:700;padding:0 18px; }}
            QPushButton:disabled {{ background:{C['bg2']};color:{C['txt3']}; }}
            QPushButton:hover:!disabled {{ background:#4a9eff; }}
        """)
        self._run_btn.clicked.connect(self._emit)
        sfl.addWidget(self._run_btn)
        lay.addWidget(sel_frame)

    # ── internal slots ────────────────────────────────────────────────────────

    def _browse(self) -> None:
        fp, _ = QFileDialog.getOpenFileName(
            self, "Open Dataset", "",
            "Data Files (*.csv *.xlsx *.xls);;All Files (*)",
        )
        if fp:
            self._load(fp)

    def _load(self, fp: str) -> None:
        self._prog.setVisible(True)
        self._prog_lbl.setVisible(True)
        self._prog_lbl.setText("Reading file…")
        self._run_btn.setEnabled(False)

        suffix = Path(fp).suffix.lower()
        if suffix in (".xlsx", ".xls"):
            try:
                xf = pd.ExcelFile(fp, engine="openpyxl")
                self._sheet.clear()
                self._sheet.addItems(xf.sheet_names)
                self._sheet.setEnabled(True)
            except Exception:
                self._sheet.setEnabled(False)
        else:
            self._sheet.setEnabled(False)

        class _Loader(QObject):
            done = Signal(object, object)
            err  = Signal(str)

            def __init__(self, fp, sheet):
                super().__init__()
                self._fp, self._sh = fp, sheet

            def run(self):
                try:
                    df, info = _load_file(self._fp, self._sh)
                    self.done.emit(df, info)
                except Exception as e:
                    self.err.emit(str(e))

        sh = self._sheet.currentText() if self._sheet.isEnabled() else 0
        self._thread  = QThread()
        self._lworker = _Loader(fp, sh)
        self._lworker.moveToThread(self._thread)
        self._thread.started.connect(self._lworker.run)
        self._lworker.done.connect(self._on_loaded)
        self._lworker.err.connect(self._on_err)
        self._thread.start()

    def _on_loaded(self, df: pd.DataFrame, info: DatasetInfo) -> None:
        self._df, self._info = df, info
        self._prog.setVisible(False)
        self._prog_lbl.setVisible(False)
        self._update_info(info)
        self._populate_preview(df)
        self._col_combo.clear()
        self._col_combo.addItems(info.numeric_cols)
        self._grp_combo.clear()
        self._grp_combo.addItem("— None —")
        self._grp_combo.addItems(info.text_cols + info.date_cols)
        self._run_btn.setEnabled(True)
        if self._thread:
            self._thread.quit()

    def _on_err(self, msg: str) -> None:
        self._prog.setVisible(False)
        self._prog_lbl.setVisible(False)
        QMessageBox.critical(self, "Load Error", f"Could not load file:\n\n{msg}")
        if self._thread:
            self._thread.quit()

    def _update_info(self, info: DatasetInfo) -> None:
        self._ilabels["file"].setText(info.filename)
        self._ilabels["rows"].setText(f"{info.row_count:,}")
        self._ilabels["cols"].setText(str(info.col_count))
        self._ilabels["num"].setText(str(len(info.numeric_cols)))
        self._ilabels["nulls"].setText(f"{info.null_count:,}")
        self._ilabels["size"].setText(f"{info.file_size_kb:.1f} KB")
        self._ilabels["dups"].setText(f"{info.dup_row_count:,}")

    def _populate_preview(self, df: pd.DataFrame) -> None:
        p = df.head(50)
        self._preview.setColumnCount(len(p.columns))
        self._preview.setRowCount(len(p))
        self._preview.setHorizontalHeaderLabels(list(p.columns))
        for ri, (_, row) in enumerate(p.iterrows()):
            for ci, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._preview.setItem(ri, ci, item)
        self._preview.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

    def _emit(self) -> None:
        if self._df is None:
            return
        col = self._col_combo.currentText()
        if not col:
            return
        grp = self._grp_combo.currentText()
        grp = None if grp.startswith("—") else grp
        try:
            floor = float(self._mat.text() or "0")
        except ValueError:
            floor = 0.0
        self.dataset_ready.emit(
            self._df, self._info, col, grp or "",
            self._excl_z.isChecked(), self._excl_n.isChecked(), floor,
        )

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls:
            fp = urls[0].toLocalFile()
            if any(fp.lower().endswith(x) for x in (".csv", ".xlsx", ".xls")):
                self._load(fp)


# ══════════════════════════════════════════════════════════════════════════════
# ApplicabilityPanel
# ══════════════════════════════════════════════════════════════════════════════

class ApplicabilityPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(14)

        t = QLabel("Benford Applicability Assessment")
        t.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lay.addWidget(t)

        top = QHBoxLayout()
        self._score_card = KPICard("📐", "Applicability Score", color=C["blue"])
        self._grade_card = KPICard("🏅", "Grade",               color=C["green"])
        self._n_card     = KPICard("🔢", "Sample Size",         color=C["txt2"])
        self._oom_card   = KPICard("📏", "OOM Spread",          color=C["txt2"])
        for c in (self._score_card, self._grade_card, self._n_card, self._oom_card):
            top.addWidget(c)
        lay.addLayout(top)

        split = QSplitter(Qt.Orientation.Horizontal)
        self._warn_box = QTextEdit()
        self._warn_box.setReadOnly(True)
        self._warn_box.setPlaceholderText("Warnings will appear here after loading a dataset.")
        split.addWidget(self._warn_box)

        self._rec_box = QTextEdit()
        self._rec_box.setReadOnly(True)
        self._rec_box.setPlaceholderText("Recommendation will appear here.")
        split.addWidget(self._rec_box)
        split.setSizes([400, 400])
        lay.addWidget(split)
        lay.addStretch()

    def update(self, r: ApplicabilityResult) -> None:
        self._score_card.update(f"{r.score:.0f}%", color=r.grade_color)
        self._grade_card.update(r.grade,            color=r.grade_color)
        self._n_card.update(f"{r.n:,}")
        self._oom_card.update(f"{r.oom:.2f}")

        if r.warnings:
            self._warn_box.setHtml(
                "<b style='color:#e3b341'>Warnings:</b><br>" +
                "".join(f"<p style='color:#f0883e;margin:4px'>⚠ {w}</p>" for w in r.warnings)
            )
        else:
            self._warn_box.setHtml("<p style='color:#3fb950'>✓ No warnings detected.</p>")

        suitability = "✅ SUITABLE" if r.suitable else "❌ NOT RECOMMENDED"
        color = C["green"] if r.suitable else C["red"]
        self._rec_box.setHtml(
            f"<b style='color:{color}'>{suitability}</b><br><br>"
            f"<p style='color:{C['txt2']}'>{r.recommendation}</p><br>"
            f"<hr><p style='color:{C['txt3']};font-size:8pt'>{DISCLAIMER}</p>"
        )


# ══════════════════════════════════════════════════════════════════════════════
# BenfordPanel
# ══════════════════════════════════════════════════════════════════════════════

class BenfordPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(12)

        t = QLabel("Benford's Law Analysis")
        t.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lay.addWidget(t)

        sel = QHBoxLayout()
        sel.addWidget(QLabel("Test:"))
        self._test_combo = QComboBox()
        self._test_combo.addItems(["First Digit", "Second Digit", "First-Two Digit"])
        self._test_combo.currentIndexChanged.connect(self._switch_test)
        sel.addWidget(self._test_combo)
        sel.addStretch()
        lay.addLayout(sel)

        kpi = QHBoxLayout()
        self._mad_card  = KPICard("📉", "MAD",             color=C["blue"])
        self._chi_card  = KPICard("χ²", "Chi-Square",      color=C["blue"])
        self._ks_card   = KPICard("🌊", "KS Stat",         color=C["blue"])
        self._anom_card = KPICard("⚠️", "Anomalous Digits", color=C["orange"])
        for c in (self._mad_card, self._chi_card, self._ks_card, self._anom_card):
            kpi.addWidget(c)
        lay.addLayout(kpi)

        tabs = QTabWidget()
        self._bar_frame = ChartFrame()
        self._dev_frame = ChartFrame()
        self._z_frame   = ChartFrame()
        self._cum_frame = ChartFrame()
        tabs.addTab(self._bar_frame, "Expected vs Observed")
        tabs.addTab(self._dev_frame, "Deviation")
        tabs.addTab(self._z_frame,   "Z-Statistics")
        tabs.addTab(self._cum_frame, "Cumulative Distribution")

        self._result_table = QTableWidget()
        self._result_table.setAlternatingRowColors(True)
        self._result_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabs.addTab(self._result_table, "Digit Table")
        lay.addWidget(tabs, 1)

        self._b1 = self._b2 = self._b12 = None

    def update(self, b1, b2, b12) -> None:
        self._b1, self._b2, self._b12 = b1, b2, b12
        self._switch_test(self._test_combo.currentIndex())

    def _current(self) -> Optional[BenfordResult]:
        return [self._b1, self._b2, self._b12][self._test_combo.currentIndex()]

    def _switch_test(self, idx: int) -> None:
        r = self._current()
        if r is None:
            return
        self._mad_card.update(f"{r.mad:.4f}", sub=r.mad_label, color=r.mad_color)
        chi_sig = "✓ Significant" if r.chi_stat > r.chi_critical else "Not significant"
        self._chi_card.update(
            f"{r.chi_stat:.2f}",
            sub=f"{chi_sig} (crit {r.chi_critical:.2f})",
            color=C["red"] if r.chi_stat > r.chi_critical else C["green"],
        )
        self._ks_card.update(f"{r.ks_stat:.4f}")
        self._anom_card.update(
            str(len(r.anomalous_digits)),
            sub=f"{r.anomalous_rows:,} transactions",
            color=C["red"] if r.anomalous_digits else C["green"],
        )
        self._bar_frame.load(chart_benford_bars(r))
        self._dev_frame.load(chart_deviation(r))
        self._z_frame.load(chart_z_stats(r))
        self._cum_frame.load(chart_cumulative(r))
        self._fill_table(r)

    def _fill_table(self, r: BenfordResult) -> None:
        cols = ["Digit", "Expected %", "Observed %", "Exp Count",
                "Obs Count", "Deviation %", "Z-Stat", "Anomalous"]
        self._result_table.setColumnCount(len(cols))
        self._result_table.setRowCount(len(r.rows))
        self._result_table.setHorizontalHeaderLabels(cols)
        for ri, row in enumerate(r.rows):
            vals = [
                str(row.digit),
                f"{row.exp_freq * 100:.3f}%",
                f"{row.obs_freq * 100:.3f}%",
                f"{row.exp_count:.1f}",
                str(row.obs_count),
                f"{row.pct_dev:+.2f}%",
                f"{row.z_stat:.3f}",
                "⚠ YES" if row.anomalous else "—",
            ]
            for ci, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if row.anomalous:
                    item.setForeground(QColor(C["red"]))
                self._result_table.setItem(ri, ci, item)
        self._result_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )


# ══════════════════════════════════════════════════════════════════════════════
# StatisticsPanel
# ══════════════════════════════════════════════════════════════════════════════

class StatisticsPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(14)

        t = QLabel("Statistical Test Results")
        t.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lay.addWidget(t)

        self._box = QTextEdit()
        self._box.setReadOnly(True)
        lay.addWidget(self._box)

        self._tab = QTableWidget()
        self._tab.setAlternatingRowColors(True)
        self._tab.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self._tab, 1)

    def update(self, b1, b2, b12) -> None:
        rows_data = []
        for r in (b1, b2, b12):
            chi_sig = r.chi_stat > r.chi_critical
            rows_data.append({
                "Test":             r.test,
                "n":                f"{r.n:,}",
                "MAD":              f"{r.mad:.4f}",
                "Conformity":       r.mad_label,
                "χ² Stat":          f"{r.chi_stat:.2f}",
                "χ² Critical":      f"{r.chi_critical:.2f}",
                "χ² p-value":       f"{r.chi_p:.4f}",
                "Significant":      "YES ⚠" if chi_sig else "No",
                "KS Stat":          f"{r.ks_stat:.4f}",
                "KS p-value":       f"{r.ks_p:.4f}",
                "Anomalous Digits": str(len(r.anomalous_digits)),
            })

        cols = list(rows_data[0].keys())
        self._tab.setColumnCount(len(cols))
        self._tab.setRowCount(len(rows_data))
        self._tab.setHorizontalHeaderLabels(cols)
        for ri, row_dict in enumerate(rows_data):
            for ci, key in enumerate(cols):
                item = QTableWidgetItem(row_dict[key])
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if key == "Significant" and "YES" in row_dict[key]:
                    item.setForeground(QColor(C["red"]))
                self._tab.setItem(ri, ci, item)
        self._tab.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

        lines = []
        for r in (b1, b2, b12):
            chi_sig = r.chi_stat > r.chi_critical
            lines.append(
                f"<b style='color:{C['txt']}'>{r.test}</b> (n={r.n:,})<br>"
                f"• MAD = {r.mad:.4f} — <span style='color:{r.mad_color}'>{r.mad_label}</span><br>"
                f"• χ² = {r.chi_stat:.2f} (critical {r.chi_critical:.2f}) — "
                f"<span style='color:{C['red'] if chi_sig else C['green']}'>"
                f"{'statistically significant' if chi_sig else 'not significant'}</span><br>"
                f"• KS stat = {r.ks_stat:.4f} (p={r.ks_p:.4f})<br>"
                f"• Anomalous digits: {r.anomalous_digits if r.anomalous_digits else 'None'}<br><br>"
            )
        self._box.setHtml(
            f"<p style='color:{C['txt2']};font-size:9pt'>{''.join(lines)}</p>"
            f"<p style='color:{C['txt3']};font-size:8pt'>{DISCLAIMER}</p>"
        )


# ══════════════════════════════════════════════════════════════════════════════
# ForensicPanel   ← FIX: was truncated / incomplete
# ══════════════════════════════════════════════════════════════════════════════

class ForensicPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(14)

        t = QLabel("Forensic Analytics")
        t.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lay.addWidget(t)

        # KPI cards
        kpi = QHBoxLayout()
        self._dup_card  = KPICard("🔁", "Duplicate Amounts", color=C["orange"])
        self._dpct_card = KPICard("📊", "Duplicate %",       color=C["orange"])
        self._rnd_card  = KPICard("🔵", "Round Numbers",     color=C["yellow"])
        self._rpct_card = KPICard("📊", "Round Number %",    color=C["yellow"])
        for c in (self._dup_card, self._dpct_card, self._rnd_card, self._rpct_card):
            kpi.addWidget(c)
        lay.addLayout(kpi)

        # Tabs
        tabs = QTabWidget()

        # Tab 1 — duplicate chart
        self._dup_chart = ChartFrame()
        tabs.addTab(self._dup_chart, "Duplicate Amounts")

        # Tab 2 — suspicious endings
        self._endings_box = QTextEdit()
        self._endings_box.setReadOnly(True)
        tabs.addTab(self._endings_box, "Suspicious Endings")

        # Tab 3 — duplicate table
        self._dup_table = QTableWidget()
        self._dup_table.setAlternatingRowColors(True)
        self._dup_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabs.addTab(self._dup_table, "Duplicate Table")

        lay.addWidget(tabs, 1)

    # FIX: update() was completely missing from the original file
    def update(self, f: ForensicResult) -> None:
        # Update KPI cards
        dup_color  = C["red"]    if f.n_duplicates > 0    else C["green"]
        dpct_color = C["red"]    if f.dup_pct > 5         else C["green"]
        rnd_color  = C["yellow"] if f.n_round > 0         else C["green"]
        rpct_color = C["orange"] if f.round_pct > 15      else C["green"]

        self._dup_card.update(str(f.n_duplicates),   color=dup_color)
        self._dpct_card.update(f"{f.dup_pct:.1f}%",  color=dpct_color)
        self._rnd_card.update(str(f.n_round),         color=rnd_color)
        self._rpct_card.update(f"{f.round_pct:.1f}%", color=rpct_color)

        # Duplicate chart
        self._dup_chart.load(chart_duplicates(f))

        # Suspicious endings
        if f.suspicious_endings:
            html = "<b style='color:#e3b341'>Suspicious Cent Endings Detected:</b><br><br>"
            for ending, cnt in f.suspicious_endings.items():
                html += f"<p style='color:#f0883e'>  {ending}  —  {cnt:,} occurrences</p>"
        else:
            html = "<p style='color:#3fb950'>No suspicious cent endings detected.</p>"
        self._endings_box.setHtml(html)

        # Duplicate table
        self._dup_table.setColumnCount(3)
        self._dup_table.setRowCount(len(f.top_duplicates))
        self._dup_table.setHorizontalHeaderLabels(["Amount", "Occurrences", "Flag"])
        for ri, (amt, cnt) in enumerate(f.top_duplicates):
            for ci, val in enumerate([f"${amt:,.2f}", str(cnt), "Duplicate ⚠"]):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if ci == 2:
                    item.setForeground(QColor(C["orange"]))
                self._dup_table.setItem(ri, ci, item)
        self._dup_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )


# ══════════════════════════════════════════════════════════════════════════════
# RiskPanel   ← FIX: update() was completely absent
# ══════════════════════════════════════════════════════════════════════════════

class RiskPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(14)

        t = QLabel("Risk Dashboard")
        t.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lay.addWidget(t)

        # Charts side by side
        charts_row = QSplitter(Qt.Orientation.Horizontal)
        self._gauge_frame = ChartFrame()
        self._comp_frame  = ChartFrame()
        charts_row.addWidget(self._gauge_frame)
        charts_row.addWidget(self._comp_frame)
        charts_row.setSizes([450, 450])
        lay.addWidget(charts_row)

        # Risk flags
        flags_grp = QGroupBox("Risk Indicators")
        fl = QVBoxLayout(flags_grp)
        self._flags_box = QTextEdit()
        self._flags_box.setReadOnly(True)
        self._flags_box.setFixedHeight(140)
        fl.addWidget(self._flags_box)
        lay.addWidget(flags_grp)

        # Disclaimer
        disc = QLabel(DISCLAIMER)
        disc.setWordWrap(True)
        disc.setFont(QFont("Segoe UI", 8))
        disc.setStyleSheet(
            f"color:{C['yellow']};background:{C['bg3']};"
            f"border:1px solid {C['yellow']};border-radius:5px;padding:8px 12px;"
        )
        lay.addWidget(disc)
        lay.addStretch()

    # FIX: this method was entirely missing
    def update(self, risk: RiskScore) -> None:
        self._gauge_frame.load(chart_risk_gauge(risk))
        self._comp_frame.load(chart_risk_components(risk))

        if risk.flags:
            html = "".join(
                f"<p style='color:{C['orange']};margin:3px 0'>⚠ {flag}</p>"
                for flag in risk.flags
            )
        else:
            html = f"<p style='color:{C['green']}'>✓ No risk indicators flagged.</p>"
        self._flags_box.setHtml(html)


# ══════════════════════════════════════════════════════════════════════════════
# SuspiciousPanel   ← FIX: method renamed update_rows→update; wrong attributes
# ══════════════════════════════════════════════════════════════════════════════

class SuspiciousPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(14)

        t = QLabel("Suspicious Transactions")
        t.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lay.addWidget(t)

        # Summary KPI cards
        top = QHBoxLayout()
        self._total_card = KPICard("⚠️", "Flagged Transactions", color=C["orange"])
        self._crit_card  = KPICard("🔴", "Critical Risk",        color=C["red"])
        self._high_card  = KPICard("🟠", "High Risk",            color=C["orange"])
        self._med_card   = KPICard("🟡", "Medium Risk",          color=C["yellow"])
        for c in (self._total_card, self._crit_card, self._high_card, self._med_card):
            top.addWidget(c)
        lay.addLayout(top)

        # Filter bar
        fbar = QHBoxLayout()
        fbar.addWidget(QLabel("Search:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter by amount or flag…")
        self._search.setFixedWidth(220)
        self._search.textChanged.connect(self._filter)
        fbar.addWidget(self._search)
        fbar.addWidget(QLabel("Risk level:"))
        self._level_filter = QComboBox()
        self._level_filter.addItems(["All", "Critical", "High", "Medium", "Low"])
        self._level_filter.currentTextChanged.connect(self._filter)
        fbar.addWidget(self._level_filter)
        fbar.addStretch()
        export_btn = QPushButton("Export to Excel")
        export_btn.clicked.connect(self._export)
        fbar.addWidget(export_btn)
        lay.addLayout(fbar)

        # Table
        self._table = QTableWidget()
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        lay.addWidget(self._table, 1)

        self._all_rows: List[SuspiciousRow] = []

    # FIX: was named update_rows(); main_window calls .update()
    def update(self, rows: List[SuspiciousRow]) -> None:
        self._all_rows = rows
        counts = Counter(r.level for r in rows)

        self._total_card.update(
            str(len(rows)),
            color=C["orange"] if rows else C["green"],
        )
        self._crit_card.update(
            str(counts.get(RiskLevel.CRITICAL, 0)),
            color=C["red"] if counts.get(RiskLevel.CRITICAL, 0) else C["txt2"],
        )
        self._high_card.update(
            str(counts.get(RiskLevel.HIGH, 0)),
            color=C["orange"] if counts.get(RiskLevel.HIGH, 0) else C["txt2"],
        )
        self._med_card.update(
            str(counts.get(RiskLevel.MEDIUM, 0)),
            color=C["yellow"] if counts.get(RiskLevel.MEDIUM, 0) else C["txt2"],
        )
        self._fill_table(rows[:2000])

    def _fill_table(self, rows: List[SuspiciousRow]) -> None:
        cols = ["Row #", "Amount", "Risk Score", "Risk Level", "Flags"]
        self._table.setColumnCount(len(cols))
        self._table.setRowCount(len(rows))
        self._table.setHorizontalHeaderLabels(cols)
        for ri, row in enumerate(rows):
            # FIX: original used row_index/reason/details which don't exist on
            # SuspiciousRow. Correct attributes are orig_idx, flags, level, risk.
            vals = [
                str(row.orig_idx),
                f"${row.amount:,.2f}",
                f"{row.risk:.2f}",
                row.level.label,
                " | ".join(row.flags),
            ]
            for ci, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if ci == 3:                              # Risk Level column
                    item.setForeground(QColor(row.level.color))
                if ci == 4 and row.level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
                    item.setForeground(QColor(C["orange"]))
                self._table.setItem(ri, ci, item)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

    def _filter(self) -> None:
        search = self._search.text().lower()
        level  = self._level_filter.currentText()
        result = [
            r for r in self._all_rows
            if (not search
                or search in f"${r.amount:.2f}"
                or any(search in f.lower() for f in r.flags))
            and (level == "All" or r.level.label == level)
        ]
        self._fill_table(result[:2000])

    def _export(self) -> None:
        if not self._all_rows:
            QMessageBox.information(self, "No Data", "No suspicious transactions to export.")
            return
        fp, _ = QFileDialog.getSaveFileName(
            self, "Export Suspicious Transactions",
            "suspicious_transactions.xlsx", "Excel Files (*.xlsx)",
        )
        if not fp:
            return
        try:
            data = [
                {
                    "Original Index": r.orig_idx,
                    "Amount":         r.amount,
                    "Risk Score":     r.risk,
                    "Risk Level":     r.level.label,
                    "Flags":          " | ".join(r.flags),
                }
                for r in self._all_rows
            ]
            pd.DataFrame(data).to_excel(fp, index=False)
            QMessageBox.information(self, "Exported", f"Saved to:\n{fp}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))


# ══════════════════════════════════════════════════════════════════════════════
# SettingsPanel
# ══════════════════════════════════════════════════════════════════════════════

class SettingsPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(14)

        t = QLabel("Settings")
        t.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        lay.addWidget(t)

        box = QGroupBox("General")
        bl = QVBoxLayout(box)
        chk1 = QCheckBox("Enable dark theme");        chk1.setChecked(True)
        chk2 = QCheckBox("Enable export logging")
        chk3 = QCheckBox("Show forensic warnings");   chk3.setChecked(True)
        bl.addWidget(chk1); bl.addWidget(chk2); bl.addWidget(chk3)
        lay.addWidget(box)

        mad_grp = QGroupBox("MAD Conformity Thresholds")
        mg = QGridLayout(mad_grp)
        mg.setSpacing(10)
        mg.addWidget(QLabel("Close conformity (<):"), 0, 0)
        self._mad_close = QLineEdit("0.006"); mg.addWidget(self._mad_close, 0, 1)
        mg.addWidget(QLabel("Acceptable (<):"), 1, 0)
        self._mad_acc   = QLineEdit("0.012"); mg.addWidget(self._mad_acc, 1, 1)
        mg.addWidget(QLabel("Marginal (<):"), 2, 0)
        self._mad_marg  = QLineEdit("0.015"); mg.addWidget(self._mad_marg, 2, 1)
        lay.addWidget(mad_grp)

        disc_box = QFrame()
        disc_box.setStyleSheet(
            f"QFrame {{ background:{C['bg3']};border:1px solid {C['yellow']};border-radius:6px; }}"
        )
        dl = QVBoxLayout(disc_box)
        dl.setContentsMargins(14, 12, 14, 12)
        disc_lbl = QLabel(DISCLAIMER)
        disc_lbl.setWordWrap(True)
        disc_lbl.setFont(QFont("Segoe UI", 8))
        disc_lbl.setStyleSheet(f"color:{C['yellow']};")
        dl.addWidget(disc_lbl)
        lay.addWidget(disc_box)
        lay.addStretch()
