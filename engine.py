import math
import re
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from PySide6.QtCore import QObject, Signal

from models import (
    ApplicabilityResult, BenfordResult, DigitRow, 
    ForensicResult, RiskLevel, RiskScore, SuspiciousRow
)
from config import BENFORD_FIRST, BENFORD_SECOND, BENFORD_FIRST_TWO, MAD_BANDS

log = logging.getLogger("auditlens")

def _clean_series(raw: pd.Series, zeros: bool = True, negatives: bool = False, floor: float = 0.0) -> pd.Series:
    def _clean(v):
        if isinstance(v, (int, float)):
            return v
        s = str(v).strip()
        if s.startswith("(") and s.endswith(")"):
            s = "-" + s[1:-1]
        s = re.sub(r"[$€£¥₹,\s]", "", s)
        try:
            return float(s)
        except ValueError:
            return float("nan")

    series = raw.apply(_clean)
    series = pd.to_numeric(series, errors="coerce").dropna()
    if zeros:
        series = series[series != 0]
    series = series.abs()
    series = series[series > 0]
    if floor > 0:
        series = series[series >= floor]
    return series.reset_index(drop=True)

def _first_digit(v: float) -> Optional[int]:
    if v <= 0: return None
    s = f"{v:.10e}".split("e")[0].replace(".", "").lstrip("0")
    return int(s[0]) if s else None

def _second_digit(v: float) -> Optional[int]:
    if v <= 0: return None
    s = f"{v:.10e}".split("e")[0].replace(".", "").lstrip("0")
    return int(s[1]) if len(s) >= 2 else None

def _first_two_digits(v: float) -> Optional[int]:
    if v <= 0: return None
    s = f"{v:.10e}".split("e")[0].replace(".", "").lstrip("0")
    if len(s) >= 2:
        d = int(s[:2])
        return d if 10 <= d <= 99 else None
    return None

def _z_stat(obs_count: int, n: int, p: float) -> float:
    denom = math.sqrt(p * (1 - p) / n)
    if denom == 0: return 0.0
    return max(0.0, abs(obs_count / n - p) - 1 / (2 * n)) / denom

def _mad_label(mad: float) -> Tuple[str, str]:
    for threshold, label, color in MAD_BANDS:
        if mad < threshold: return label, color
    return "Nonconformity", "#f85149"

def evaluate_applicability(series: pd.Series, col: str = "value") -> ApplicabilityResult:
    n = len(series)
    warnings = []
    score = 100.0

    if n == 0:
        return ApplicabilityResult(0, "Poor", "#f85149", False, 0, 0, 0, 0, False,
                                   ["No usable values found."], "Column has no valid data.")

    if n < 300:
        deduct = 35 if n < 100 else 20
        score -= deduct
        warnings.append(f"Small sample size (n={n:,}). Minimum 300 recommended.")

    log_vals = np.log10(series[series > 0])
    oom = float(log_vals.max() - log_vals.min()) if len(log_vals) > 1 else 0.0
    if oom < 1.0:
        score -= 30
        warnings.append(f"Very low numeric dispersion ({oom:.2f} orders of magnitude).")
    elif oom < 2.0:
        score -= 15
        warnings.append(f"Limited numeric dispersion ({oom:.2f} orders of magnitude).")

    unique_ratio = series.nunique() / n
    if unique_ratio < 0.05:
        score -= 25
        warnings.append(f"Excessive repetition — only {unique_ratio*100:.1f}% unique values.")
    elif unique_ratio > 0.98 and n > 500:
        warnings.append("All values unique — check for sequential ID fields.")

    sorted_s = series.sort_values().values
    diffs = np.diff(sorted_s)
    sequential = bool(len(diffs) > 10 and np.std(diffs) < 1e-6 * (np.mean(sorted_s) + 1))
    if sequential:
        score -= 40
        warnings.append("Data appears to be sequentially numbered — not suitable for Benford.")

    sk = float(stats.skew(series))
    if abs(sk) < 0.5:
        score -= 10
        warnings.append("Distribution appears symmetric. Benford works best on right-skewed data.")

    score = max(0.0, min(100.0, score))

    if score >= 80:   grade, gcol = "Excellent", "#3fb950"
    elif score >= 60: grade, gcol = "Good",      "#d29922"
    elif score >= 40: grade, gcol = "Marginal",  "#f0883e"
    else:             grade, gcol = "Poor",       "#f85149"

    suitable = score >= 40 and not sequential

    if not suitable:
        rec = "Dataset is NOT recommended for Benford analysis. Proceed with extreme caution."
    elif score < 60:
        rec = "Dataset is marginally suitable. Document limitations in working papers."
    else:
        rec = "Dataset is suitable. Apply standard professional procedures."

    return ApplicabilityResult(
        score=round(score, 1), grade=grade, grade_color=gcol, suitable=suitable, 
        n=n, oom=round(oom, 2), unique_ratio=round(unique_ratio, 3), skewness=round(sk, 3),
        sequential=sequential, warnings=warnings, recommendation=rec,
    )

def run_benford(series: pd.Series, test: str, col: str = "value") -> BenfordResult:
    if test == "first":
        extractor, expected, digit_range, label = _first_digit, BENFORD_FIRST, list(range(1, 10)), "First Digit"
    elif test == "second":
        extractor, expected, digit_range, label = _second_digit, BENFORD_SECOND, list(range(0, 10)), "Second Digit"
    else:
        extractor, expected, digit_range, label = _first_two_digits, BENFORD_FIRST_TWO, list(range(10, 100)), "First-Two Digit"

    bucket: Dict[int, List[int]] = {d: [] for d in digit_range}
    for idx, val in enumerate(series.values):
        d = extractor(float(val))
        if d is not None and d in bucket:
            bucket[d].append(idx)

    n = sum(len(v) for v in bucket.values())
    if n == 0:
        raise ValueError("No valid digits extracted.")

    rows: List[DigitRow] = []
    for digit in digit_range:
        obs_count = len(bucket[digit])
        obs_freq  = obs_count / n
        exp_freq  = expected[digit]
        dev       = obs_freq - exp_freq
        pct_dev   = dev / exp_freq * 100 if exp_freq else 0.0
        z         = _z_stat(obs_count, n, exp_freq)
        rows.append(DigitRow(
            digit=digit, exp_freq=exp_freq, obs_freq=obs_freq,
            exp_count=exp_freq * n, obs_count=obs_count,
            deviation=dev, pct_dev=round(pct_dev, 2), z_stat=round(z, 3), 
            anomalous=z > 1.96, indices=bucket[digit],
        ))

    mad = float(np.mean([abs(r.deviation) for r in rows]))
    mlabel, mcolor = _mad_label(mad)

    obs_arr, exp_arr = np.array([r.obs_count for r in rows], dtype=float), np.array([r.exp_count for r in rows], dtype=float)
    mask = exp_arr >= 5
    if mask.sum() >= 2: chi, chi_p = stats.chisquare(obs_arr[mask], f_exp=exp_arr[mask])
    else: chi, chi_p = 0.0, 1.0

    chi_crit = float(stats.chi2.ppf(0.95, df=len(digit_range) - 1))
    ks, ks_p = stats.ks_2samp(np.array([r.obs_freq for r in rows]), np.array([r.exp_freq for r in rows]))

    anomalous_digits = [r.digit for r in rows if r.anomalous]
    anomalous_rows   = sum(len(bucket[d]) for d in anomalous_digits)

    return BenfordResult(
        test=label, column=col, n=n, rows=rows, mad=round(mad, 6), mad_label=mlabel, 
        mad_color=mcolor, chi_stat=round(float(chi), 4), chi_p=round(float(chi_p), 6), 
        chi_critical=round(chi_crit, 4), ks_stat=round(float(ks), 6), ks_p=round(float(ks_p), 6),
        anomalous_digits=anomalous_digits, anomalous_rows=anomalous_rows,
    )

def run_forensics(df: pd.DataFrame, col: str) -> ForensicResult:
    raw = pd.to_numeric(df[col], errors="coerce").dropna().abs()
    raw = raw[raw > 0]
    n = len(raw)

    counts = raw.value_counts()
    dups   = counts[counts >= 2]
    top_dups = [(float(v), int(c)) for v, c in dups.head(20).items()]
    n_dups = int(dups.sum()) if len(dups) else 0

    round_mask = ((raw % 1000 == 0) | (raw % 500 == 0) | (raw % 100 == 0)) & (raw != 0)
    n_round = int(round_mask.sum())
    cent_end = ((raw * 100).round().astype(int) % 100)
    endings: Dict[str, int] = {f".{e:02d}": int((cent_end == e).sum()) for e in [0, 50, 95, 99] if int((cent_end == e).sum())}

    return ForensicResult(top_duplicates=top_dups, n_duplicates=n_dups, dup_pct=round(n_dups / max(n, 1) * 100, 2), 
                          round_pct=round(n_round / max(n, 1) * 100, 2), n_round=n_round, suspicious_endings=endings)

def compute_risk(benford: BenfordResult, forensic: ForensicResult, n: int) -> RiskScore:
    flags: List[str] = []
    comp: Dict[str, float] = {}

    mad = benford.mad
    if mad < 0.006:   ms = 0.05
    elif mad < 0.012: ms = 0.30
    elif mad < 0.015: ms = 0.65
    else: ms = 1.0; flags.append(f"MAD nonconformity ({benford.mad_label}, MAD={mad:.4f})")
    comp["MAD"] = ms

    if benford.chi_stat > benford.chi_critical:
        cs = min(1.0, 0.5 + (benford.chi_stat - benford.chi_critical) / benford.chi_critical)
        flags.append(f"Chi-square significant (χ²={benford.chi_stat:.2f}, crit={benford.chi_critical:.2f})")
    else: cs = 0.10
    comp["Chi-Square"] = cs

    dp = min(1.0, forensic.dup_pct / 100 * 3)
    if forensic.dup_pct > 10: flags.append(f"High duplicates: {forensic.dup_pct:.1f}% of transactions")
    comp["Duplicates"] = dp

    rp = min(1.0, forensic.round_pct / 100 * 2.5)
    if forensic.round_pct > 15: flags.append(f"Elevated round-number concentration: {forensic.round_pct:.1f}%")
    comp["Round Numbers"] = rp

    anomaly_ratio = len(benford.anomalous_digits) / max(len(benford.rows), 1)
    zp = min(1.0, anomaly_ratio * 2.5)
    if anomaly_ratio > 0.3: flags.append(f"{len(benford.anomalous_digits)}/{len(benford.rows)} digits anomalous by Z-test")
    comp["Z-Anomalies"] = zp

    score = min(1.0, max(0.0, sum(comp[k] * {"MAD": 0.35, "Chi-Square": 0.20, "Duplicates": 0.15, "Round Numbers": 0.15, "Z-Anomalies": 0.15}[k] for k in comp)))

    if score < 0.25:   level = RiskLevel.LOW
    elif score < 0.50: level = RiskLevel.MEDIUM
    elif score < 0.75: level = RiskLevel.HIGH
    else:              level = RiskLevel.CRITICAL

    return RiskScore(entity="Dataset", score=round(score, 4), level=level, components=comp, flags=flags, n=n)

def flag_suspicious(df: pd.DataFrame, col: str, benford: BenfordResult) -> List[SuspiciousRow]:
    raw_clean = pd.to_numeric(df[col], errors="coerce").abs()
    raw_clean = raw_clean[raw_clean > 0]
    
    val_counts  = raw_clean.value_counts()
    dup_set     = set(val_counts[val_counts >= 2].index.tolist())
    round_mask  = ((raw_clean % 1000 == 0) | (raw_clean % 500 == 0)) & (raw_clean != 0)
    round_set   = set(raw_clean[round_mask].index.tolist())
    cent_end    = ((raw_clean * 100).round().astype(int) % 100)
    susp_ending = set(raw_clean[cent_end.isin([0, 95, 99])].index.tolist())

    benford_set: set = set()
    for r in benford.rows:
        if r.anomalous: benford_set.update(r.indices)

    log_vals = np.log1p(raw_clean.values)
    std = log_vals.std() + 1e-10
    z_scores = (log_vals - log_vals.mean()) / std

    results: List[SuspiciousRow] = []
    for i, (idx, amount) in enumerate(raw_clean.items()):
        flags_list: List[str] = []
        if idx in benford_set: flags_list.append("Anomalous leading digit (Benford)")
        if float(amount) in dup_set: flags_list.append(f"Duplicate amount (×{int(val_counts.get(float(amount), 1))})")
        if idx in round_set: flags_list.append("Round-number pattern")
        if abs(z_scores[i]) >= 3.0: flags_list.append(f"Extreme value (Z={z_scores[i]:.1f})")
        if idx in susp_ending: flags_list.append(f"Suspicious ending (.{int(cent_end.get(idx, 0)):02d})")

        if flags_list:
            risk_raw = min(1.0, len(flags_list) * 0.25)
            if risk_raw < 0.25:   lvl = RiskLevel.LOW
            elif risk_raw < 0.50: lvl = RiskLevel.MEDIUM
            elif risk_raw < 0.75: lvl = RiskLevel.HIGH
            else:                 lvl = RiskLevel.CRITICAL

            row = df.loc[idx] if idx in df.index else pd.Series()
            extras = {k: v for k, v in row.items() if k != col} if isinstance(row, pd.Series) else {}
            results.append(SuspiciousRow(orig_idx=int(idx), amount=round(float(amount), 2), flags=flags_list, risk=round(risk_raw, 3), level=lvl, extras=extras))

    results.sort(key=lambda r: r.risk, reverse=True)
    return results

class AnalysisWorker(QObject):
    finished = Signal(object)
    error    = Signal(str)
    progress = Signal(str)

    def __init__(self, df: pd.DataFrame, col: str, group_col: Optional[str], excl_zeros: bool, excl_neg: bool, mat_floor: float) -> None:
        super().__init__()
        self.df = df
        self.col = col
        self.group_col = group_col
        self.excl_zeros = excl_zeros
        self.excl_neg = excl_neg
        self.mat_floor = mat_floor

    def run(self) -> None:
        try:
            self.progress.emit("Cleaning data…")
            series = _clean_series(self.df[self.col], self.excl_zeros, self.excl_neg, self.mat_floor)
            self.progress.emit("Evaluating Benford applicability…")
            appl = evaluate_applicability(series, self.col)
            self.progress.emit("Running first-digit test…")
            b1 = run_benford(series, "first", self.col)
            self.progress.emit("Running second-digit test…")
            b2 = run_benford(series, "second", self.col)
            self.progress.emit("Running first-two-digit test…")
            b12 = run_benford(series, "first_two", self.col)
            self.progress.emit("Forensic pattern analysis…")
            forensic = run_forensics(self.df, self.col)
            self.progress.emit("Computing risk score…")
            risk = compute_risk(b1, forensic, len(series))
            self.progress.emit("Flagging suspicious transactions…")
            suspicious = flag_suspicious(self.df, self.col, b1)

            self.finished.emit({
                "series": series, "appl": appl, "b1": b1, "b2": b2, "b12": b12,
                "forensic": forensic, "risk": risk, "suspicious": suspicious,
            })
        except Exception as exc:
            log.exception("Analysis failed")
            self.error.emit(str(exc))