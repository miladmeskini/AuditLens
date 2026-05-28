"""
main_window.py  —  Application shell, KPI bar, panel routing.

FIXES vs uploaded version:
  • _navigate() was calling self._sidebar._click(key) which re-emits the
    nav signal → _navigate() → _click() → infinite recursion.
    Fixed: call self._sidebar.set_active(key) instead.
  • _on_analysis_done() was calling self._susp_p.update(susp) but
    SuspiciousPanel's method was named update_rows() — both are fixed
    (SuspiciousPanel now exposes update(), see panels.py).
"""

import logging
from typing import Optional, Dict

import pandas as pd
from PySide6.QtCore import QThread
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame,
    QProgressBar, QLabel, QStackedWidget, QScrollArea, QMessageBox,
)

from config import C
from models import DatasetInfo
from engine import AnalysisWorker
from ui.common_widgets import Sidebar, KPICard
from ui.panels import (
    HomePanel, ImportPanel, ApplicabilityPanel, BenfordPanel,
    StatisticsPanel, ForensicPanel, RiskPanel, SuspiciousPanel, SettingsPanel,
)

log = logging.getLogger("auditlens")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AuditLens  —  Forensic Audit Analytics")
        self.resize(1500, 880)

        self._df:      Optional[pd.DataFrame]  = None
        self._info:    Optional[DatasetInfo]    = None
        self._results: Optional[Dict]           = None
        self._thread:  Optional[QThread]        = None
        self._worker:  Optional[AnalysisWorker] = None

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar — connect nav signal
        self._sidebar = Sidebar()
        self._sidebar.nav.connect(self._navigate)
        layout.addWidget(self._sidebar)

        # Right panel
        right = QWidget()
        right.setStyleSheet(f"background:{C['bg0']};")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        # Top KPI strip
        self._kpi_bar = self._build_kpi_bar()
        rl.addWidget(self._kpi_bar)

        # Progress indicators
        self._prog_bar = QProgressBar()
        self._prog_bar.setRange(0, 0)
        self._prog_bar.setFixedHeight(3)
        self._prog_bar.setVisible(False)
        rl.addWidget(self._prog_bar)

        self._prog_lbl = QLabel("")
        self._prog_lbl.setFont(QFont("Segoe UI", 8))
        self._prog_lbl.setStyleSheet(f"color:{C['blue']};padding:0 16px;")
        self._prog_lbl.setVisible(False)
        rl.addWidget(self._prog_lbl)

        # Pages (stacked)
        self._stack = QStackedWidget()
        self._panels: Dict[str, QWidget] = {}

        self._home_p   = HomePanel()
        self._import_p = ImportPanel()
        self._appl_p   = ApplicabilityPanel()
        self._benf_p   = BenfordPanel()
        self._stat_p   = StatisticsPanel()
        self._fors_p   = ForensicPanel()
        self._risk_p   = RiskPanel()
        self._susp_p   = SuspiciousPanel()
        self._sett_p   = SettingsPanel()

        # Wire up cross-panel signals
        self._home_p.go_import.connect(lambda: self._navigate("import"))
        self._import_p.dataset_ready.connect(self._on_dataset_ready)

        page_map = [
            ("home",          self._home_p),
            ("import",        self._import_p),
            ("applicability", self._appl_p),
            ("benford",       self._benf_p),
            ("statistics",    self._stat_p),
            ("forensic",      self._fors_p),
            ("risk",          self._risk_p),
            ("suspicious",    self._susp_p),
            ("settings",      self._sett_p),
        ]
        for key, panel in page_map:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(panel)
            scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
            self._stack.addWidget(scroll)
            self._panels[key] = scroll

        rl.addWidget(self._stack, 1)
        layout.addWidget(right, 1)

    def _build_kpi_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(90)
        bar.setStyleSheet(
            f"QFrame {{ background:{C['bg1']}; border:none; "
            f"border-bottom:1px solid {C['border']}; border-radius:0; }}"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 6, 16, 6)
        lay.setSpacing(10)

        self._k_appl = KPICard("📐", "Applicability",   "—", color=C["txt2"])
        self._k_mad  = KPICard("📉", "MAD Score",       "—", color=C["txt2"])
        self._k_chi  = KPICard("χ²", "Chi-Square",      "—", color=C["txt2"])
        self._k_risk = KPICard("🛡",  "Risk Level",      "—", color=C["txt2"])
        self._k_susp = KPICard("⚠️", "Suspicious Rows", "—", color=C["txt2"])
        self._k_dups = KPICard("🔁", "Duplicates",      "—", color=C["txt2"])

        for k in (self._k_appl, self._k_mad, self._k_chi,
                  self._k_risk, self._k_susp, self._k_dups):
            k.setFixedHeight(80)
            lay.addWidget(k)
        lay.addStretch()
        return bar

    # ── Navigation ────────────────────────────────────────────────────────────

    def _navigate(self, key: str) -> None:
        """Switch visible panel and highlight the sidebar button.

        FIX: the original code called self._sidebar._click(key) here, which
        re-emits nav → _navigate() → _click() → infinite recursion.
        We now call set_active() instead, which only updates the visual state.
        """
        if key in self._panels:
            self._stack.setCurrentWidget(self._panels[key])
            self._sidebar.set_active(key)   # ← FIX: was _click(), causing recursion

    # ── Dataset / Analysis ────────────────────────────────────────────────────

    def _on_dataset_ready(self, df, info, col, grp, excl_z, excl_n, mat) -> None:
        self._df   = df
        self._info = info
        self._sidebar.set_status(
            f"📁 {info.filename}\n{info.row_count:,} rows",
            color=C["cyan"],
        )
        self._run_analysis(df, col, grp or None, excl_z, excl_n, mat)
        self._navigate("applicability")

    def _run_analysis(self, df, col, grp, excl_z, excl_n, mat) -> None:
        self._prog_bar.setVisible(True)
        self._prog_lbl.setVisible(True)

        self._thread = QThread()
        self._worker = AnalysisWorker(df, col, grp, excl_z, excl_n, mat)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_analysis_done)
        self._worker.error.connect(self._on_analysis_error)
        self._thread.start()

    def _on_progress(self, msg: str) -> None:
        self._prog_lbl.setText(f"⟳  {msg}")

    def _on_analysis_done(self, results: Dict) -> None:
        self._results = results
        self._prog_bar.setVisible(False)
        self._prog_lbl.setVisible(False)
        if self._thread:
            self._thread.quit()

        appl     = results["appl"]
        b1       = results["b1"]
        b2       = results["b2"]
        b12      = results["b12"]
        forensic = results["forensic"]
        risk     = results["risk"]
        susp     = results["suspicious"]

        # Update top KPI strip
        self._k_appl.update(f"{appl.score:.0f}%",        sub=appl.grade,           color=appl.grade_color)
        self._k_mad.update(f"{b1.mad:.4f}",              sub=b1.mad_label,         color=b1.mad_color)
        chi_color = C["red"] if b1.chi_stat > b1.chi_critical else C["green"]
        self._k_chi.update(f"{b1.chi_stat:.2f}",         sub="1st digit",          color=chi_color)
        self._k_risk.update(risk.level.label,             sub=f"{risk.pct}%",       color=risk.level.color)
        susp_color = C["red"] if susp else C["green"]
        self._k_susp.update(str(len(susp)),               sub="flagged rows",       color=susp_color)
        dup_color  = C["orange"] if forensic.n_duplicates else C["green"]
        self._k_dups.update(str(forensic.n_duplicates),   sub=f"{forensic.dup_pct:.1f}%", color=dup_color)

        # Update all panels
        self._appl_p.update(appl)
        self._benf_p.update(b1, b2, b12)
        self._stat_p.update(b1, b2, b12)
        self._fors_p.update(forensic)
        self._risk_p.update(risk)
        self._susp_p.update(susp)   # FIX: SuspiciousPanel method renamed to update()

        log.info("Analysis complete. Risk=%s, Suspicious=%d", risk.level.label, len(susp))

    def _on_analysis_error(self, msg: str) -> None:
        self._prog_bar.setVisible(False)
        self._prog_lbl.setVisible(False)
        if self._thread:
            self._thread.quit()
        QMessageBox.critical(self, "Analysis Error", f"Analysis failed:\n\n{msg}")
