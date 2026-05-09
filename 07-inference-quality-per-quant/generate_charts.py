#!/usr/bin/env python3
"""Charts for the quality-per-quant benchmark.

Reads results/*.json and emits grouped bar charts (HumanEval, GSM8K) by
model size, with quants as the within-group axis. ATOM white theme.
"""

import json
import re
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).parent
RESULTS_DIR = ROOT / "results"
OUT_DIR = ROOT / "charts"
OUT_DIR.mkdir(parents=True, exist_ok=True)

QUANT_ORDER = ["q4_K_M", "q5_K_M", "q8_0"]
SIZE_ORDER = ["3b", "7b", "14b"]
QUANT_COLOR = {"q4_K_M": "#4A90D9", "q5_K_M": "#4CAF50", "q8_0": "#FF9800"}


def setup_style():
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#333333",
        "axes.labelcolor": "#333333",
        "axes.titleweight": "bold",
        "axes.titlepad": 14,
        "xtick.color": "#333333",
        "ytick.color": "#333333",
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": "#e6e6e6",
        "grid.linestyle": "-",
        "grid.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "font.family": "sans-serif",
        "font.size": 10,
    })


def parse_id(model: str):
    # e.g. qwen2.5:3b-instruct-q4_K_M
    m = re.search(r":([0-9]+b)-instruct-(q[0-9_KM]+)", model)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def load_all():
    out = defaultdict(dict)  # out[size][quant] = {humaneval, gsm8k}
    for f in sorted(RESULTS_DIR.glob("*.json")):
        d = json.loads(f.read_text())
        size, quant = parse_id(d["model"])
        if not size:
            continue
        out[size][quant] = {
            "humaneval": d["humaneval"]["pass_rate"],
            "gsm8k": d["gsm8k"]["pass_rate"],
            "model": d["model"],
        }
    return out


def grouped_bar(data, metric, title, fname):
    setup_style()
    sizes = [s for s in SIZE_ORDER if s in data]
    quants = QUANT_ORDER
    n_sizes = len(sizes)
    n_quants = len(quants)
    bar_w = 0.25
    fig, ax = plt.subplots(figsize=(9, 5))

    for qi, q in enumerate(quants):
        xs, ys = [], []
        for si, s in enumerate(sizes):
            if q in data[s]:
                xs.append(si + (qi - n_quants / 2) * bar_w + bar_w / 2)
                ys.append(data[s][q][metric])
        bars = ax.bar(xs, ys, width=bar_w, color=QUANT_COLOR[q], label=q)
        for b, v in zip(bars, ys):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.005, f"{v:.3f}",
                    ha="center", va="bottom", fontsize=8)

    ax.set_xticks(range(n_sizes))
    ax.set_xticklabels([s.upper() for s in sizes])
    ax.set_xlabel("Model size")
    ax.set_ylabel("Pass rate")
    ax.set_title(title)
    ax.set_ylim(0, 1.0)
    ax.legend(title="Quantisation", loc="lower right", frameon=False)
    plt.tight_layout()
    out = OUT_DIR / fname
    plt.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}")


def main():
    data = load_all()
    if not data:
        print(f"No results in {RESULTS_DIR}.")
        return
    grouped_bar(data, "humaneval",
                "HumanEval-164 Pass Rate by Model Size and Quantisation",
                "humaneval_pass_rate.png")
    grouped_bar(data, "gsm8k",
                "GSM8K-200 Pass Rate by Model Size and Quantisation",
                "gsm8k_pass_rate.png")


if __name__ == "__main__":
    main()
