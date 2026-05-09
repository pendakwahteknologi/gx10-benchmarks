#!/usr/bin/env python3
"""Charts for the long-context benchmark.

Reads every results/longctx_*.csv and emits per-model and comparison plots
in the ATOM white theme used elsewhere in this repo.
"""

import csv
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).parent
RESULTS_DIR = ROOT / "results"
OUT_DIR = ROOT / "charts"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PALETTE = ["#4A90D9", "#4CAF50", "#FF9800", "#9C27B0"]


def setup_style():
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.grid": True,
        "grid.alpha": 0.3,
        "grid.color": "#cccccc",
        "axes.edgecolor": "#cccccc",
        "font.family": "sans-serif",
        "font.size": 14,
        "axes.titlesize": 20,
        "axes.titleweight": "bold",
        "axes.labelsize": 14,
        "xtick.labelsize": 13,
        "ytick.labelsize": 12,
    })


def fmt_ctx(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n/1024/1024:.0f}M"
    if n >= 1024:
        return f"{n/1024:.0f}k"
    return str(n)


def fmt_ms(v):
    if v >= 60_000:
        return f"{v/1000:.0f}s"
    if v >= 1000:
        return f"{v/1000:.1f}s"
    return f"{v:.0f}ms"


def load_rows(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            r["target_ctx"] = int(r["target_ctx"])
            r["prompt_tokens"] = int(r["prompt_tokens"])
            r["ttft_ms"] = float(r["ttft_ms"])
            r["prefill_tok_s"] = float(r["prefill_tok_s"])
            r["decode_tok_s"] = float(r["decode_tok_s"])
            rows.append(r)
    return rows


def aggregate(rows):
    by_ctx = defaultdict(list)
    for r in rows:
        by_ctx[r["target_ctx"]].append(r)
    out = []
    for ctx in sorted(by_ctx):
        runs = by_ctx[ctx]
        out.append({
            "ctx": ctx,
            "ttft_ms": statistics.median(r["ttft_ms"] for r in runs),
            "prefill_tok_s": statistics.median(r["prefill_tok_s"] for r in runs),
            "decode_tok_s": statistics.median(r["decode_tok_s"] for r in runs),
            "prompt_tokens_med": statistics.median(r["prompt_tokens"] for r in runs),
        })
    return out


def single_model_chart(agg, ykey, ylabel, title, fname, color, fmt_label):
    setup_style()
    fig, ax = plt.subplots(figsize=(14.8, 7.3))
    xs = [a["ctx"] for a in agg]
    ys = [a[ykey] for a in agg]
    ax.plot(xs, ys, color=color, marker="o", linewidth=2.5, markersize=10,
            markeredgecolor="white", markeredgewidth=1.5)
    for x, y in zip(xs, ys):
        ax.annotate(fmt_label(y), xy=(x, y), xytext=(0, 12),
                    textcoords="offset points", ha="center",
                    fontsize=13, fontweight="bold")
    ax.set_xlabel("Context length (tokens)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_xscale("log", base=2)
    ax.set_xticks(xs)
    ax.set_xticklabels([fmt_ctx(x) for x in xs])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_ylim(bottom=0)
    plt.tight_layout()
    fig.savefig(OUT_DIR / fname, dpi=100, bbox_inches="tight")
    plt.close()
    print(f"Saved {fname}")


def comparison_chart(model_aggs, ykey, ylabel, title, fname, fmt_label, log_y=False):
    setup_style()
    fig, ax = plt.subplots(figsize=(14.8, 7.3))
    all_xs = sorted({a["ctx"] for agg in model_aggs.values() for a in agg})
    for i, (model, agg) in enumerate(model_aggs.items()):
        xs = [a["ctx"] for a in agg]
        ys = [a[ykey] for a in agg]
        color = PALETTE[i % len(PALETTE)]
        ax.plot(xs, ys, color=color, marker="o", linewidth=2.5, markersize=10,
                markeredgecolor="white", markeredgewidth=1.5, label=model)
        for x, y in zip(xs, ys):
            ax.annotate(fmt_label(y), xy=(x, y), xytext=(0, 12),
                        textcoords="offset points", ha="center",
                        fontsize=11, fontweight="bold", color=color)
    ax.set_xlabel("Context length (tokens)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_xscale("log", base=2)
    ax.set_xticks(all_xs)
    ax.set_xticklabels([fmt_ctx(x) for x in all_xs])
    if log_y:
        ax.set_yscale("log")
    else:
        ax.set_ylim(bottom=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="best", frameon=True, fontsize=13)
    plt.tight_layout()
    fig.savefig(OUT_DIR / fname, dpi=100, bbox_inches="tight")
    plt.close()
    print(f"Saved {fname}")


def main():
    csvs = sorted(RESULTS_DIR.glob("longctx_*.csv"))
    if not csvs:
        print("No results CSV found.", file=sys.stderr)
        sys.exit(1)

    model_aggs = {}
    for path in csvs:
        rows = load_rows(path)
        if not rows:
            continue
        model = rows[0]["model"]
        agg = aggregate(rows)
        model_aggs[model] = agg

        print(f"\n=== {model} ({path.name}) ===")
        print("ctx     prompt_tok  ttft         prefill(tok/s)  decode(tok/s)")
        for a in agg:
            print(f"{fmt_ctx(a['ctx']):>5}   {a['prompt_tokens_med']:>10}  "
                  f"{fmt_ms(a['ttft_ms']):>8}    {a['prefill_tok_s']:>11,.0f}     {a['decode_tok_s']:>5.1f}")

        safe = model.replace(":", "_").replace("/", "_")
        single_model_chart(agg, "ttft_ms", "TTFT",
                           f"Time to First Token vs Context Length — {model}",
                           f"ttft_{safe}.png", PALETTE[0], fmt_ms)
        single_model_chart(agg, "prefill_tok_s", "Prefill speed (tok/s)",
                           f"Prefill Throughput vs Context Length — {model}",
                           f"prefill_{safe}.png", PALETTE[1], lambda v: f"{v:,.0f}")
        single_model_chart(agg, "decode_tok_s", "Decode speed (tok/s)",
                           f"Decode Throughput vs Context Length — {model}",
                           f"decode_{safe}.png", PALETTE[2], lambda v: f"{v:.1f}")

    if len(model_aggs) >= 2:
        print("\n=== comparison charts ===")
        comparison_chart(model_aggs, "ttft_ms", "TTFT",
                         "Time to First Token vs Context Length",
                         "ttft_comparison.png", fmt_ms, log_y=True)
        comparison_chart(model_aggs, "prefill_tok_s", "Prefill speed (tok/s)",
                         "Prefill Throughput vs Context Length",
                         "prefill_comparison.png", lambda v: f"{v:,.0f}")
        comparison_chart(model_aggs, "decode_tok_s", "Decode speed (tok/s)",
                         "Decode Throughput vs Context Length",
                         "decode_comparison.png", lambda v: f"{v:.1f}")


if __name__ == "__main__":
    main()
