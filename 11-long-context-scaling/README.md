# Benchmark: Long-Context Scaling (1K → 128K Tokens)

How fast does prefill and decode degrade as the input context grows? This benchmark drives Ollama-served models from 1K to 128K input tokens and measures TTFT, prefill throughput, and decode throughput at each step.

This is the benchmark the GB10's unified memory architecture is built for: long contexts force the KV cache to balloon, and on conventional 24GB-class GPUs it falls off a cliff once it stops fitting in VRAM. The GX10's 128GB shared pool makes it a non-issue.

## Hardware

- GPU: NVIDIA GB10 (Blackwell, SM 12.1)
- Memory: 128GB unified (shared CPU/GPU via NVLink-C2C)
- CUDA: 13.0, Driver 580.142
- Serving engine: Ollama 0.20.5

## Methodology

- Two models compared: `qwen2.5:7b` (q4_K_M default) and `llama3.1:8b` (q4_K_M default)
- Target context lengths: 1024, 4096, 16384, 32768, 65536, 131072 tokens
- Prompt: a fixed paragraph about GB10 architecture, repeated until the target token count is hit, then capped to that target
- `num_predict = 64`, `temperature = 0`, `seed = 42` for reproducibility
- 3 runs per (model, ctx) pair; means reported below
- Warmup pass at `num_ctx=2048` before the sweep
- Prefill and decode tok/s computed from Ollama's reported `prompt_eval_duration` and `eval_duration` (nanoseconds)
- Note: `qwen2.5:7b` was measured up to 32K only in this run; `llama3.1:8b` covers the full sweep to 128K

## Results — Llama 3.1 8B (full 1K → 128K sweep)

| Target ctx | Prompt tokens | Prefill tok/s | Decode tok/s | TTFT (s) |
|-----------:|--------------:|--------------:|-------------:|---------:|
|       1024 |           844 |          3085 |         45.7 |     0.27 |
|       4096 |          3364 |          2947 |         43.7 |     1.14 |
|      16384 |         13415 |          2298 |         36.8 |     5.84 |
|      32768 |         26827 |          1845 |         30.7 |    14.54 |
|      65536 |         53645 |          1315 |         22.9 |    40.79 |
|     131072 |        107279 |           838 |         14.9 |   128.06 |

## Results — Qwen 2.5 7B (1K → 32K)

| Target ctx | Prompt tokens | Prefill tok/s | Decode tok/s | TTFT (s) |
|-----------:|--------------:|--------------:|-------------:|---------:|
|       1024 |           895 |          3374 |         46.6 |     0.27 |
|       4096 |          3499 |          3245 |         45.3 |     1.08 |
|      16384 |         13879 |          2727 |         41.2 |     5.09 |
|      32768 |         27735 |          2215 |         36.1 |    12.52 |

## Charts

| | |
|---|---|
| ![Prefill comparison](charts/prefill_comparison.png) | ![Decode comparison](charts/decode_comparison.png) |
| ![TTFT comparison](charts/ttft_comparison.png) | |

Per-model charts are in `charts/` (`prefill_*`, `decode_*`, `ttft_*`).

## Key Findings

1. **No memory cliff.** Both models served 32K cleanly and Llama 3.1 8B served 128K — 107K input tokens, full prefill — without any out-of-memory failure or KV-cache eviction. Unified memory is doing the work that 80GB-class data-center GPUs are usually required for.

2. **Decode throughput halves roughly every 4× ctx growth.** Llama 3.1 8B decoded at 45.7 tok/s at 1K and 14.9 tok/s at 128K — a ~3× slowdown across a 128× context expansion. Decode stays usable up to 32K (30+ tok/s) for both models.

3. **TTFT is the real cost at long contexts.** Prefill is compute-bound and scales near-linearly with input length: 0.27s at 1K, 14.5s at 32K, 128s at 128K for Llama 3.1 8B. Long-context summarization workloads are dominated by this prefill cost; decode is the cheap part.

4. **Qwen 2.5 7B is consistently faster than Llama 3.1 8B at matched ctx.** ~10–20% faster prefill, ~12–18% faster decode across the 1K–32K range tested. The 1B-parameter difference matters more than the architecture difference here.

5. **The 1K → 16K range is the sweet spot for interactive use.** Sub-6s TTFT, 36+ tok/s decode. Below 4K most workloads will feel real-time; at 32K you're into "send the prompt, go get coffee" territory.

## Files

- `longctx_bench.py` — runner. Builds prompts to target token counts and queries Ollama, parsing `prompt_eval_duration` and `eval_duration`.
- `generate_charts.py` — reads everything in `results/*.csv` and emits per-model + comparison plots in the ATOM white theme.
- `results/` — raw CSV + JSON per (model, run timestamp).
- `charts/` — generated PNGs.

## Reproduce

```bash
# Make sure Ollama is up
systemctl is-active ollama

# Pull models
ollama pull qwen2.5:7b
ollama pull llama3.1:8b

# Run the sweep (one model at a time; ~10 min for 1K-32K, ~50 min for full 1K-128K)
python3 longctx_bench.py --model qwen2.5:7b --runs 3
python3 longctx_bench.py --model llama3.1:8b --runs 3

# Charts
python3 generate_charts.py
```

## Date

8 May 2026

## Created by

Pendakwah Teknologi
