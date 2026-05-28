import math
import numpy as np
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.figure import Figure
import matplotlib.ticker as ticker

from config import C
from models import BenfordResult, RiskScore, ForensicResult

plt.rcParams.update({
    "figure.facecolor":     C["bg1"],
    "axes.facecolor":       C["bg2"],
    "axes.edgecolor":       C["border"],
    "axes.labelcolor":      C["txt2"],
    "axes.titlecolor":      C["txt"],
    "xtick.color":          C["txt2"],
    "ytick.color":          C["txt2"],
    "grid.color":           C["border"],
    "grid.alpha":           0.6,
    "legend.facecolor":     C["bg3"],
    "legend.edgecolor":     C["border"],
    "legend.labelcolor":    C["txt"],
    "text.color":           C["txt"],
    "font.family":          "DejaVu Sans",
    "font.size":            9,
})

def _make_fig(w: int = 8, h: int = 4) -> tuple[Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=(w, h))
    fig.patch.set_facecolor(C["bg1"])
    ax.set_facecolor(C["bg2"])
    return fig, ax

def chart_benford_bars(result: BenfordResult) -> Figure:
    fig, ax = _make_fig(9, 4)
    rows, labels = result.rows, [str(r.digit) for r in result.rows]
    exp, obs = [r.exp_freq * 100 for r in rows], [r.obs_freq * 100 for r in rows]
    anom, x, w = [r.anomalous for r in rows], np.arange(len(labels)), 0.38
    bar_colors = [C["red"] if a else C["orange"] for a in anom]

    ax.bar(x - w/2, exp, width=w, color=C["blue"],   alpha=0.75, label="Expected (Benford)", zorder=2)
    ax.bar(x + w/2, obs, width=w, color=bar_colors,  alpha=0.90, label="Observed",           zorder=2)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_xlabel("Digit"); ax.set_ylabel("Frequency (%)")
    ax.set_title(f"{result.test} Test  ·  MAD={result.mad:.4f} ({result.mad_label})  ·  n={result.n:,}", pad=10, fontsize=10, color=C["txt"])
    ax.yaxis.grid(True, zorder=0)
    ax.legend(framealpha=0.8)

    for i, (xi, a) in enumerate(zip(x, anom)):
        if a: ax.annotate("⚠", xy=(xi + w/2, obs[i] + 0.3), ha="center", fontsize=10, color=C["red"])
    fig.tight_layout(pad=1.2)
    return fig

def chart_deviation(result: BenfordResult) -> Figure:
    fig, ax = _make_fig(9, 3.5)
    rows, labels, devs = result.rows, [str(r.digit) for r in result.rows], [r.pct_dev for r in result.rows]
    anom, x = [r.anomalous for r in rows], np.arange(len(labels))
    colors = [C["red"] if a else (C["green"] if d >= 0 else "#5c6bc0") for a, d in zip(anom, devs)]
    
    ax.bar(x, devs, color=colors, alpha=0.85, zorder=2)
    ax.axhline(0, color=C["txt2"], linewidth=0.8)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_xlabel("Digit"); ax.set_ylabel("Deviation from Expected (%)")
    ax.set_title("Digit Deviation from Benford Expected", pad=8, fontsize=10)
    ax.yaxis.grid(True, zorder=0)
    fig.tight_layout(pad=1.2)
    return fig

def chart_z_stats(result: BenfordResult) -> Figure:
    fig, ax = _make_fig(9, 3.5)
    rows, labels, zs = result.rows, [str(r.digit) for r in result.rows], [r.z_stat for r in result.rows]
    anom, x = [r.anomalous for r in rows], np.arange(len(labels))
    colors = [C["red"] if a else C["blue"] for a in anom]
    
    ax.bar(x, zs, color=colors, alpha=0.85, zorder=2)
    ax.axhline(1.96,  color=C["yellow"], linewidth=1.2, linestyle="--", label="95% critical (1.96)")
    ax.axhline(2.576, color=C["red"],    linewidth=1.2, linestyle="--", label="99% critical (2.576)")
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_xlabel("Digit"); ax.set_ylabel("|Z| Statistic")
    ax.set_title("Z-Statistics per Digit", pad=8, fontsize=10)
    ax.yaxis.grid(True, zorder=0)
    ax.legend(framealpha=0.8)
    fig.tight_layout(pad=1.2)
    return fig

def chart_cumulative(result: BenfordResult) -> Figure:
    fig, ax = _make_fig(9, 3.5)
    rows, labels = result.rows, [str(r.digit) for r in result.rows]
    cum_exp = np.cumsum([r.exp_freq for r in rows]) * 100
    cum_obs = np.cumsum([r.obs_freq for r in rows]) * 100
    x = np.arange(len(labels))

    ax.plot(x, cum_exp, color=C["blue"], linewidth=2, linestyle="--", marker="o", markersize=4, label="Expected")
    ax.plot(x, cum_obs, color=C["orange"], linewidth=2, marker="o", markersize=4, label="Observed")
    ax.fill_between(x, cum_exp, cum_obs, alpha=0.12, color=C["orange"])
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_xlabel("Digit"); ax.set_ylabel("Cumulative Frequency (%)")
    ax.set_title(f"Cumulative Distribution  ·  KS stat={result.ks_stat:.4f}", pad=8, fontsize=10)
    ax.yaxis.grid(True, zorder=0)
    ax.legend(framealpha=0.8)
    fig.tight_layout(pad=1.2)
    return fig

def chart_risk_gauge(risk: RiskScore) -> Figure:
    fig, ax = _make_fig(5, 4)
    ax.set_xlim(-1.2, 1.2); ax.set_ylim(-0.3, 1.2); ax.axis("off")

    bands = [(0.25, "#1e3a2a"), (0.25, "#3a3310"), (0.25, "#3a2010"), (0.25, "#3a1015")]
    start = 0.0
    for pct, bg in bands:
        theta1, theta2 = 180 - start * 180, 180 - (start + pct) * 180
        wedge = mpatches.Wedge((0, 0), 1.0, theta2, theta1, width=0.28, facecolor=bg, edgecolor=C["bg2"], linewidth=1)
        ax.add_patch(wedge)
        start += pct

    angle_rad = math.radians(180 - risk.score * 180)
    nx, ny = math.cos(angle_rad) * 0.75, math.sin(angle_rad) * 0.75
    ax.annotate("", xy=(nx, ny), xytext=(0, 0), arrowprops=dict(arrowstyle="-|>", color=risk.level.color, lw=2.5, mutation_scale=15))
    ax.add_patch(plt.Circle((0, 0), 0.06, color=C["bg2"], zorder=5))
    ax.add_patch(plt.Circle((0, 0), 0.04, color=risk.level.color, zorder=6))

    ax.text(0, -0.15, f"{risk.pct}%", ha="center", va="center", fontsize=22, fontweight="bold", color=risk.level.color)
    ax.text(0, -0.28, f"Risk Level: {risk.level.label}", ha="center", fontsize=11, color=risk.level.color, fontweight="bold")
    labels = [("Low", -0.98, 0.02), ("Medium", -0.05, 1.05), ("High", 0.55, 0.65), ("Critical", 0.95, 0.02)]
    small_colors = ["#2ea043", "#c9961b", "#c26c15", "#c62626"]
    for (lbl, lx, ly), lc in zip(labels, small_colors): ax.text(lx, ly, lbl, fontsize=7, color=lc, ha="center")
    
    ax.set_title("Composite Risk Score", fontsize=11, pad=4, color=C["txt"])
    fig.tight_layout(pad=0.5)
    return fig

def chart_risk_components(risk: RiskScore) -> Figure:
    fig, ax = _make_fig(6, 3.5)
    names, values = list(risk.components.keys()), [risk.components[k] * 100 for k in risk.components.keys()]
    colors = [C["red"] if v > 60 else C["orange"] if v > 30 else C["green"] for v in values]
    y = np.arange(len(names))

    bars = ax.barh(y, values, color=colors, alpha=0.85, height=0.55)
    ax.set_yticks(y); ax.set_yticklabels(names)
    ax.set_xlabel("Risk Contribution (%)"); ax.set_title("Risk Component Breakdown", pad=8, fontsize=10)
    ax.set_xlim(0, 105); ax.xaxis.grid(True, zorder=0)
    for bar, v in zip(bars, values): ax.text(v + 1.5, bar.get_y() + bar.get_height() / 2, f"{v:.0f}%", va="center", fontsize=8, color=C["txt2"])
    fig.tight_layout(pad=1.2)
    return fig

def chart_duplicates(forensic: ForensicResult) -> Figure:
    fig, ax = _make_fig(9, 4)
    top = forensic.top_duplicates[:15]
    if not top:
        ax.text(0.5, 0.5, "No duplicates detected", ha="center", va="center", transform=ax.transAxes, color=C["txt2"], fontsize=12)
        ax.axis("off"); fig.tight_layout(); return fig

    labels, counts = [f"${a:,.2f}" for a, _ in top], [c for _, c in top]
    x = np.arange(len(labels))
    ax.bar(x, counts, color=C["orange"], alpha=0.85, zorder=2)
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=8)
    ax.set_ylabel("Occurrences"); ax.set_title("Top Duplicate Transaction Amounts", pad=8, fontsize=10)
    ax.yaxis.grid(True, zorder=0)
    fig.tight_layout(pad=1.2)
    return fig