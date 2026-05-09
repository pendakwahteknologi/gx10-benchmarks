# GX10 Benchmark Suite — Source of Truth

Canonical numbering and roster for every benchmark in this repo. The README is generated from this list — when a benchmark moves between statuses (RUNNING → DONE, PLANNED → RUNNING, etc.), update the **Status** column here and refresh the README.

**Last updated:** 2026-05-09

## Category Counts

| Category | Count | Status mix |
|----------|------:|-----------|
| Inference | 9 | 6 done · 1 running · 2 queued |
| Training | 1 | 1 done |
| Efficiency | 2 | 1 done · 1 planned |
| Generation | 1 | 1 done |
| Voice | 1 | 1 done |
| Multimodal | 1 | 1 planned |
| **Total** | **15** | **9 done · 1 running · 2 queued · 2 planned** |

The inference roster is **locked at 9** — no further inference benchmarks are planned. New ideas go into existing categories or open a new one.

## Roster

| # | Folder | Category | Title | Status |
|---|--------|----------|-------|--------|
| 01 | `01-inference-model-scaling/`            | Inference   | Model Scaling — Qwen 2.5 1.5B → 72B + Gemma 4 | DONE |
| 02 | `02-inference-engine-comparison/`        | Inference   | Engine Comparison — Ollama vs llama.cpp vs vLLM | DONE |
| 03 | `03-inference-llama-cpp/`                | Inference   | llama.cpp Multi-Quantization — Q4/Q5/Q8 × 3B–32B | DONE |
| 04 | `04-inference-embedding-throughput/`     | Inference   | Embedding Throughput — Mesolitica Mistral 191M, GPU vs CPU | DONE |
| 05 | `05-inference-coding-llm-webpage/`       | Inference   | Coding LLM — Qwen3-Coder + DeepCoder + Devstral, webpage gen | DONE |
| 06 | `06-inference-long-context-scaling/`     | Inference   | Long-Context Scaling — Qwen 2.5 7B + Llama 3.1 8B, 1K → 128K | DONE |
| 07 | `07-inference-quality-per-quant/`        | Inference   | Quality per Quant — HumanEval-164 + GSM8K-200 across Q4/Q5/Q8 × 3B–14B | RUNNING |
| 08 | `08-inference-model-breadth/`            | Inference   | Model Breadth — Llama 3.x + Gemma 3, 1B → 70B tok/s + TTFT | QUEUED |
| 09 | `09-inference-vllm-concurrency/`         | Inference   | vLLM Concurrency — concurrency 1 → 128, aggregate tok/s, p50/p95 | QUEUED |
| 10 | `10-training-finetuning/`                | Training    | Fine-Tuning — LoRA / QLoRA / Full FT on Llama 3.1 8B | DONE |
| 11 | `11-efficiency-token-per-watt/`          | Efficiency  | Token per Watt — power monitoring, RM cost per 1M tokens | DONE |
| 12 | `12-efficiency-multi-model-concurrent/`  | Efficiency  | Multi-Model Concurrent Serving — 3 models loaded simultaneously, cross-tenant | PLANNED |
| 13 | `13-generation-image-video/`             | Generation  | Image & Video Generation — Z-Image-Turbo + Wan 2.2 T2V | DONE |
| 14 | `14-voice-stt-tts/`                      | Voice       | Voice STT & TTS — Whisper large-v3 + MMS-TTS Malay | DONE |
| 15 | `15-multimodal-vision-language/`         | Multimodal  | Vision-Language — Qwen 2-VL 7B/72B + LLaVA, image understanding | PLANNED |

## Status Legend

- **DONE** — results published in this repo
- **RUNNING** — actively in progress on GX10 (results land in this repo when complete)
- **QUEUED** — scheduled to run after the current job completes
- **PLANNED** — committed to add but not yet started

## Migration Notes

This canonical numbering was set on **2026-05-09**. Earlier versions of the repo used a different scheme:

| Old folder | New folder |
|-----------|-----------|
| `04-training-finetuning/`           | `10-training-finetuning/` |
| `05-efficiency-token-per-watt/`     | `11-efficiency-token-per-watt/` |
| `06-inference-embedding/`           | `04-inference-embedding-throughput/` |
| `07-efficiency-image-generation/`   | `13-generation-image-video/` |
| `08-voice-stt-tts/`                 | `14-voice-stt-tts/` |
| `09-coding-llm-webpage/`            | `05-inference-coding-llm-webpage/` |
| `11-long-context-scaling/`          | `06-inference-long-context-scaling/` |

Folders 01, 02, 03 are unchanged. Older external links to the old paths will 404 after the rename — the new paths above are canonical going forward.

## Reranker note

A reranker throughput benchmark was considered and dropped to keep the inference count locked at 9. If a reranker is added later it will go under a separate **Retrieval** category alongside embedding (which would also move there).

## How to update this file

When a benchmark transitions:
1. Edit the **Status** cell for that row.
2. If the transition is into DONE: also add the section to the top-level README (results table + inline section).
3. Bump the **Last updated** date at the top.
4. Refresh the **Category Counts** table.
