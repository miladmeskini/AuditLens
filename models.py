from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

class RiskLevel(Enum):
    LOW      = ("Low",      "#3fb950")
    MEDIUM   = ("Medium",   "#d29922")
    HIGH     = ("High",     "#f0883e")
    CRITICAL = ("Critical", "#f85149")

    @property
    def label(self):  return self.value[0]
    @property
    def color(self):  return self.value[1]

@dataclass
class DatasetInfo:
    filename:        str
    row_count:       int
    col_count:       int
    numeric_cols:    List[str]
    text_cols:       List[str]
    date_cols:       List[str]
    null_count:      int
    dup_row_count:   int
    file_size_kb:    float

@dataclass
class ApplicabilityResult:
    score:          float          # 0 – 100
    grade:          str
    grade_color:    str
    suitable:       bool
    n:              int
    oom:            float
    unique_ratio:   float
    skewness:       float
    sequential:     bool
    warnings:       List[str]
    recommendation: str

@dataclass
class DigitRow:
    digit:       int
    exp_freq:    float
    obs_freq:    float
    exp_count:   float
    obs_count:   int
    deviation:   float
    pct_dev:     float
    z_stat:      float
    anomalous:   bool
    indices:     List[int]  = field(default_factory=list)

@dataclass
class BenfordResult:
    test:           str           # "First Digit", "Second Digit", "First-Two Digit"
    column:         str
    n:              int
    rows:           List[DigitRow]
    mad:            float
    mad_label:      str
    mad_color:      str
    chi_stat:       float
    chi_p:          float
    chi_critical:   float
    ks_stat:        float
    ks_p:           float
    anomalous_digits: List[int]
    anomalous_rows:   int

@dataclass
class ForensicResult:
    top_duplicates:     List[Tuple[float, int]]   # (amount, count)
    n_duplicates:       int
    dup_pct:            float
    round_pct:          float
    n_round:            int
    suspicious_endings: Dict[str, int]

@dataclass
class RiskScore:
    entity:     str
    score:      float          # 0–1
    level:      RiskLevel
    components: Dict[str, float]
    flags:      List[str]
    n:          int

    @property
    def pct(self): return round(self.score * 100, 1)

@dataclass
class SuspiciousRow:
    orig_idx:   int
    amount:     float
    flags:      List[str]
    risk:       float
    level:      RiskLevel
    extras:     Dict