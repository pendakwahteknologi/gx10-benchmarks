# Benchmark 15: Vision-Language Models — Image Understanding

How fast does GX10 run vision-language models, and how big can it go? This benchmark measures TTFT, prefill, decode tok/s, and GPU memory across the **Qwen 2.5-VL**, **Llama 3.2-Vision**, **LLaVA**, and **Moondream** families on Ollama.

The 128 GB unified-memory pool is the differentiator: VLMs swallow VRAM faster than text models because they carry both LLM weights and a vision encoder, and the largest open-weight VLMs (Llama 3.2-Vision 90B, Qwen 2.5-VL 32B+) typically demand data-centre-class GPUs. GB10 should fit them in the shared pool.

## Status

PLANNED. Will run after the inference pipeline (07/08/09) drains.

## Hardware

- GPU: NVIDIA GB10 (Blackwell, SM 12.1)
- Memory: 128 GB unified (shared CPU/GPU via NVLink-C2C)
- CUDA: 13.0, Driver 580.142
- Serving engine: Ollama 0.20.5

## Methodology

### Models

Tentative roster — subject to confirmation that each tag is published in the Ollama registry at run time. The runner can be pointed at any subset.

| Model | Tag | Class | Notes |
|-------|-----|-------|-------|
| Moondream 2 | `moondream:1.8b-v2` | Small | Sanity baseline; ~2B params |
| LLaVA 1.6 | `llava:7b-v1.6` | Medium-small | Mature, well-known |
| LLaVA 1.6 | `llava:13b-v1.6` | Medium | |
| Llama 3.2-Vision | `llama3.2-vision:11b` | Medium | Meta, modern |
| Qwen 2.5-VL | `qwen2.5vl:7b` | Medium | If available on Ollama |
| Qwen 2.5-VL | `qwen2.5vl:32b` | Large | The unified-memory showcase |
| Llama 3.2-Vision | `llama3.2-vision:90b` | Very large | The killer demo — typical desktops can't load this |

### Test images

5 fixed images covering varied content. Place them in `test_images/` before running:

1. **People scene** — multiple people, varied poses (e.g., a busy plaza or sports event)
2. **Product/object** — a clear product photo with packaging text
3. **Document** — a page of printed text (for OCR difficulty)
4. **Landscape** — outdoor nature scene with depth
5. **Chart/diagram** — a graph, infographic, or technical diagram

All images at native resolution; the benchmark also runs at downsampled 512x512 and 256x256 to capture the resolution-vs-speed curve. Image set documented in `test_images/README.md` once finalised.

### Prompts

| # | Prompt | Tests |
|---|--------|-------|
| 1 | "Describe this image in detail." | Captioning |
| 2 | "What is the main subject of this image?" | Quick recognition |
| 3 | "How many distinct objects/people are in this image?" | Counting |
| 4 | "Transcribe any text visible in this image." | OCR |
| 5 | "What is unusual or interesting about this image?" | Reasoning |

### Per-run protocol

For each `(model, image, prompt)` triple:
1. Pull model if not already present.
2. Warmup pass (single short text-only call).
3. Three measurement runs at `temperature=0`, `seed=42`, `num_predict=256`.
4. Record: `prompt_eval_duration` (TTFT), `eval_duration` + `eval_count` (decode tok/s), `prompt_eval_count` (vision-encoded tokens), wall time, `gpu_memory_used_mib` (from `nvidia-smi`).
5. Unload + delete model between models to ensure clean memory state.

### What we measure

- **TTFT** — time-to-first-token, includes vision encoding cost
- **Prefill tok/s** — `prompt_eval_count / prompt_eval_duration` (tokens-per-second through the encoder + LLM prefill stage)
- **Decode tok/s** — output generation throughput, same as text-only benches
- **Peak GPU memory** — to show how unified memory absorbs the largest models
- **Total wall time** — practical end-to-end latency

### What we explicitly do NOT measure

- Accuracy / answer correctness — this is a performance benchmark, not an eval harness. Use MMMU, ChartQA, or OCRBench for accuracy.
- Multi-image reasoning, video understanding, or grounded bounding boxes — single-image, single-prompt only.

## Files

- `vlm_bench.py` — runner. Iterates models × images × prompts, parses Ollama timings, dumps CSV + JSON.
- `generate_charts.py` — reads `results/*.csv` and emits per-model + comparison plots in the ATOM white theme.
- `prompts.txt` — the 5 prompts above (one per line).
- `test_images/` — input images (gitignored; populated locally per the spec above).
- `results/` — raw CSV + JSON per run.
- `charts/` — generated PNGs.

## Reproduce

```bash
# 1. Place 5 test images per the spec into test_images/
# 2. Make sure Ollama is up
systemctl is-active ollama

# 3. Run the sweep (models can be subset via --models)
python3 vlm_bench.py --runs 3
# or pick specific models
python3 vlm_bench.py --runs 3 --models llava:7b-v1.6,qwen2.5vl:7b

# 4. Charts
python3 generate_charts.py
```

## Date

Planned 2026-05-09. Will run after the inference pipeline (07/08/09) finishes.

## Created by

Pendakwah Teknologi
