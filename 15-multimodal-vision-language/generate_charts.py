#!/usr/bin/env python3
"""Charts for the vision-language benchmark.

Reads every results/vlm_*.csv and emits per-model and comparison plots
in the ATOM white theme used elsewhere in this repo.
"""

import csv
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).parent
RESULTS_DIR = ROOT / "results"
OUT_DIR = ROOT / "charts"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PALETTE = ["#4A90D9", "#4CAF50", "#FF9800", "#9C27B0",
           "#E91E63", "#00BCD4", "#FFC107", "#795548"]


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
        "grid.color": "#e6e6e6",
        "grid.linestyle": "-",
        "grid.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "font.family": "sans-serif",
        "font.size": 10,
    })


def load_all():
    rows = []
    for f in sorted(RESULTS_DIR.glob("vlm_*.csv")):
        with f.open() as fh:
            for r in csv.DictReader(fh):
                rows.append(r)
    return rows


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return statistics.mean(vals) if vals else 0.0


def aggregate_per_model(rows):
    """Mean prefill/decode/ttft/mem per model, averaged across all images, prompts, runs."""
    by_m = defaultdict(list)
    for r in rows:
        by_m[r["model"]].append(r)
    out = []
    for m, rs in by_m.items():
        out.append({
            "model": m,
            "prefill_tok_s": _mean([float(r["prefill_tok_s"]) for r in rs if r.get("prefill_tok_s")]),
            "decode_tok_s": _mean([float(r["decode_tok_s"]) for r in rs if r.get("decode_tok_s")]),
            "ttft_ms": _mean([float(r["ttft_ms"]) for r in rs if r.get("ttft_ms")]),
            "gpu_mem_mib": _mean([float(r["gpu_mem_after_mib"]) for r in rs if r.get("gpu_mem_after_mib") and float(r["gpu_mem_after_mib"]) >= 0]),
            "n": len(rs),
        })
    out.sort(key=lambda d: d["model"])
    return out


def bar_chart(agg, key, title, ylabel, fname):
    setup_style()
    models = [a["model"] for a in agg]
    vals = [a[key] for a in agg]
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(range(len(models)), vals,
                  color=[PALETTE[i % len(PALETTE)] for i in range(len(models))])
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels(models, rotation=20, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:,.1f}",
                ha="center", va="bottom", fontsize=9)
    plt.tight_layout()
    out = OUT_DIR / fname
    plt.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}")


def main():
    rows = load_all()
    if not rows:
        print(f"No results found under {RESULTS_DIR}. Run vlm_bench.py first.")
        return
    agg = aggregate_per_model(rows)
    bar_chart(agg, "decode_tok_s",
              "VLM Decode Throughput per Model (mean)",
              "tok/s", "decode_per_model.png")
    bar_chart(agg, "prefill_tok_s",
              "VLM Prefill Throughput per Model (mean)",
              "tok/s", "prefill_per_model.png")
    bar_chart(agg, "ttft_ms",
              "VLM Time-to-First-Token per Model (mean)",
              "ms", "ttft_per_model.png")
    bar_chart(agg, "gpu_mem_mib",
              "VLM Peak GPU Memory per Model (mean)",
              "MiB", "gpu_memory_per_model.png")


if __name__ == "__main__":
    main()
