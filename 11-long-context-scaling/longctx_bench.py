#!/usr/bin/env python3
"""
Long-context inference benchmark for Ollama-hosted models on GX10.

For each target context length, builds a prompt of ~that many input tokens,
measures prefill (TTFT) and decode tok/s using Ollama's API timings.

Output: CSV at results/longctx_<model>_<timestamp>.csv plus a JSON dump.
"""

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")

BASE_PARAGRAPH = (
    "The Grace Blackwell GB10 superchip pairs an ARM CPU with a Blackwell GPU "
    "over NVLink-C2C, sharing a unified memory pool that allows large language "
    "models and their key-value caches to coexist without copies. This design "
    "is particularly relevant for long-context inference, because the KV cache "
    "grows linearly with context length and quickly outsizes the typical "
    "consumer GPU memory budget. On the GX10 desktop, that constraint is "
    "loosened: a 32B parameter model at 128k context fits in tens of gigabytes, "
    "leaving the remainder for the operating system, other workloads, and "
    "tool-use scratch space. The benchmarks in this section quantify the "
    "prefill and decode performance at varying context depths so practitioners "
    "can plan their workloads around realistic latency expectations. "
)


def build_prompt(target_tokens: int, salt: str = "") -> str:
    """Build a prompt that hits roughly target_tokens after tokenization.

    `salt` is prepended verbatim so each run hits a different prefix and
    Ollama / llama.cpp's prompt-prefix cache does not artificially shrink
    prefill time on subsequent runs.
    """
    chars_per_token = 4.2
    target_chars = int(target_tokens * chars_per_token) - 200 - len(salt)
    text = ""
    while len(text) < target_chars:
        text += BASE_PARAGRAPH
    text = text[:target_chars]
    text += (
        "\n\nAfter reading the passage above, state in one short sentence "
        "what general topic it discusses."
    )
    return salt + text


def gpu_mem_used_mib() -> int:
    """Return GPU memory used in MiB. Returns -1 on failure."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True, timeout=5,
        ).strip()
        return int(out.splitlines()[0])
    except Exception:
        return -1


def run_one(model: str, prompt: str, num_ctx: int, num_predict: int = 64) -> dict:
    """Single Ollama generate call. Returns parsed metrics."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "temperature": 0,
            "seed": 42,
        },
    }
    mem_before = gpu_mem_used_mib()
    t0 = time.perf_counter()
    r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=900)
    wall = time.perf_counter() - t0
    r.raise_for_status()
    data = r.json()
    mem_after = gpu_mem_used_mib()

    prompt_eval_count = data.get("prompt_eval_count", 0)
    prompt_eval_dur_ns = data.get("prompt_eval_duration", 0)
    eval_count = data.get("eval_count", 0)
    eval_dur_ns = data.get("eval_duration", 0)
    total_dur_ns = data.get("total_duration", 0)

    prefill_s = prompt_eval_dur_ns / 1e9 if prompt_eval_dur_ns else 0
    decode_s = eval_dur_ns / 1e9 if eval_dur_ns else 0

    return {
        "wall_s": wall,
        "prompt_tokens": prompt_eval_count,
        "gen_tokens": eval_count,
        "ttft_ms": prefill_s * 1000.0,
        "prefill_tok_s": prompt_eval_count / prefill_s if prefill_s else 0,
        "decode_tok_s": eval_count / decode_s if decode_s else 0,
        "total_s": total_dur_ns / 1e9,
        "gpu_mem_before_mib": mem_before,
        "gpu_mem_after_mib": mem_after,
        "gpu_mem_delta_mib": (mem_after - mem_before) if (mem_before >= 0 and mem_after >= 0) else -1,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5:7b")
    ap.add_argument("--contexts", default="1024,4096,16384,32768,65536,131072")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out-dir", default=str(Path(__file__).parent / "results"))
    ap.add_argument("--num-predict", type=int, default=64)
    ap.add_argument("--smoke", action="store_true",
                    help="Quick single-context smoke test at 4k.")
    args = ap.parse_args()

    Path(args.out_dir).mkdir(parents=True, exist_ok=True)

    if args.smoke:
        contexts = [4096]
        runs = 1
    else:
        contexts = [int(x) for x in args.contexts.split(",")]
        runs = args.runs

    print(f"Model: {args.model}")
    print(f"Contexts: {contexts}")
    print(f"Runs per context: {runs}")
    print(f"Ollama URL: {OLLAMA_URL}")
    print()

    # Warmup
    print("Warmup...")
    warmup = run_one(args.model, "Hello.", num_ctx=2048, num_predict=8)
    print(f"  warmup decode: {warmup['decode_tok_s']:.1f} tok/s")
    print()

    import secrets
    rows = []
    for ctx in contexts:
        # add 256-token buffer so generation has room
        num_ctx = ctx + 256
        print(f"=== ctx target {ctx} (num_ctx={num_ctx}) ===")
        per_run = []
        for i in range(runs):
            # per-run unique prefix to defeat prompt-prefix caching
            salt = f"[run-id {secrets.token_hex(12)}] "
            prompt = build_prompt(ctx, salt=salt)
            try:
                m = run_one(args.model, prompt, num_ctx=num_ctx, num_predict=args.num_predict)
                m["run"] = i + 1
                m["target_ctx"] = ctx
                m["model"] = args.model
                m["timestamp"] = datetime.utcnow().isoformat() + "Z"
                per_run.append(m)
                print(
                    f"  run {i+1}: prompt_tok={m['prompt_tokens']:>6} "
                    f"ttft={m['ttft_ms']:>8.0f}ms  "
                    f"prefill={m['prefill_tok_s']:>7.1f} tok/s  "
                    f"decode={m['decode_tok_s']:>5.1f} tok/s  "
                    f"gpu_mem_after={m['gpu_mem_after_mib']} MiB"
                )
                rows.append(m)
            except requests.exceptions.HTTPError as e:
                print(f"  run {i+1}: HTTP error {e} -- skipping rest of this ctx")
                break
            except Exception as e:
                print(f"  run {i+1}: error {e!r}")
                break
        if per_run:
            ttft_med = statistics.median(r["ttft_ms"] for r in per_run)
            pf_med = statistics.median(r["prefill_tok_s"] for r in per_run)
            dec_med = statistics.median(r["decode_tok_s"] for r in per_run)
            print(f"  median: ttft={ttft_med:.0f}ms prefill={pf_med:.1f} tok/s decode={dec_med:.1f} tok/s")
        print()

    if not rows:
        print("No successful runs.")
        sys.exit(1)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_model = args.model.replace(":", "_").replace("/", "_")
    csv_path = Path(args.out_dir) / f"longctx_{safe_model}_{ts}.csv"
    json_path = Path(args.out_dir) / f"longctx_{safe_model}_{ts}.json"

    cols = [
        "timestamp", "model", "target_ctx", "run",
        "prompt_tokens", "gen_tokens",
        "ttft_ms", "prefill_tok_s", "decode_tok_s", "total_s", "wall_s",
        "gpu_mem_before_mib", "gpu_mem_after_mib", "gpu_mem_delta_mib",
    ]
    with open(csv_path, "w") as f:
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join(str(r.get(c, "")) for c in cols) + "\n")
    with open(json_path, "w") as f:
        json.dump(rows, f, indent=2)

    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")


if __name__ == "__main__":
    main()
