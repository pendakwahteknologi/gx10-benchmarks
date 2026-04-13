# GX10 Benchmark Suite

Comprehensive AI benchmarks on the **NVIDIA GX10** desktop supercomputer, powered by the **GB10 Grace Blackwell Superchip**. Eight benchmarks covering inference, training, efficiency, and multimodal workloads.

All results are reproducible. Scripts, raw data, and reports are included for full audit.

---

## Hardware

| Spec | Detail |
|------|--------|
| **GPU** | NVIDIA GB10 (Blackwell, SM 12.1) |
| **CPU** | 20 ARM cores (Cortex-X925 + A725) |
| **Memory** | 128 GB LPDDR5X unified (CPU+GPU via NVLink-C2C) |
| **Storage** | 916 GB NVMe |
| **CUDA** | 13.0 |
| **Driver** | 580.142 |
| **OS** | Ubuntu 24.04 aarch64 |

---

## Results Summary

### Inference

| # | Benchmark | Key Result | Detail |
|---|-----------|-----------|--------|
| 01 | [Model Scaling](01-inference-model-scaling/) | **1.5B to 72B all run** | 173 tok/s (1.5B) down to 4.2 tok/s (72B) |
| 02 | [Engine Comparison](02-inference-engine-comparison/) | **Ollama fastest for single-user** | 43.7 tok/s Ollama vs 43.0 llama.cpp vs 12.5 vLLM |
| 03 | [llama.cpp Multi-Quant](03-inference-llama-cpp/) | **3,077 tok/s prompt processing** | Full quant sweep: Q4/Q5/Q8 across 3B-32B |
| 06 | [Embedding Throughput](06-inference-embedding/) | **3,597 chunks/s on GPU** | 36x faster than CPU (98 chunks/s) |

### Training

| # | Benchmark | Key Result | Detail |
|---|-----------|-----------|--------|
| 04 | [Fine-Tuning](04-training-finetuning/) | **Full FT of 8B model in 5h** | LoRA 164 tok/s, Full FT 151 tok/s, QLoRA 83 tok/s |

### Efficiency

| # | Benchmark | Key Result | Detail |
|---|-----------|-----------|--------|
| 05 | [Token per Watt](05-efficiency-token-per-watt/) | **2.62 tok/W peak** | 3B Q4_K_M at 36W avg, RM 0.058/1K tokens |

### Multimodal

| # | Benchmark | Key Result | Detail |
|---|-----------|-----------|--------|
| 07 | [Image & Video Generation](07-image-video-generation/) | **8.7 images/min (512px)** | Z-Image-Turbo (4 steps) + Wan 2.2 T2V 14B |
| 08 | [Voice STT & TTS](08-voice-stt-tts/) | **TTS: 2,017 chars/s, STT: 1.6x realtime** | MMS-TTS Malay (GPU) + Whisper large-v3 (CPU) |

---

## Detailed Results

### 01 — Inference: Model Scaling

Every popular model size tested via Ollama. The 72B model runs — most desktop GPUs cannot even load it.

| Model | tok/s | TTFT | GPU Temp |
|-------|------:|-----:|---------:|
| Qwen2.5 1.5B | 173 | 12ms | 51C |
| Qwen2.5 3B | 93 | 19ms | 53C |
| Qwen2.5 7B | 43 | 35ms | 51C |
| Qwen2.5 14B | 22 | 65ms | 50C |
| Gemma 4 27B MoE | 55 | 30ms | 55C |
| Qwen2.5 32B | 10 | 134ms | 53C |
| Qwen2.5 72B | 4.2 | 296ms | 59C |

### 02 — Inference: Engine Comparison (Qwen2.5-7B)

Same model, three engines. Ollama wins for single-user; vLLM advantage is concurrent users (128+).

| Engine | Runtime | tok/s | GPU Temp |
|--------|---------|------:|---------:|
| Ollama | Native systemd | 43.7 | 55C |
| llama.cpp | Native binary | 43.0 | 44C |
| vLLM | Docker container | 12.5 | 63C |

llama.cpp prompt processing: **3,077 tok/s**.

### 03 — Inference: llama.cpp Multi-Quantization

Full quantization sweep across 4 model sizes using llama.cpp with CUDA. See [detailed report](03-inference-llama-cpp/results/benchmark_report_gx10.html).

| Model | Quant | Prompt (tok/s) | Generate (tok/s) |
|-------|-------|---------------:|-----------------:|
| 3B | Q4_K_M | 6,762 | 94.4 |
| 3B | Q8_0 | 6,345 | 64.1 |
| 7B | Q4_K_M | 3,894 | 44.3 |
| 7B | Q8_0 | 2,867 | 28.8 |
| 14B | Q4_K_M | 2,277 | 22.9 |
| 14B | Q8_0 | 1,644 | 14.2 |
| 32B | Q4_K_M | 878 | 10.2 |
| 32B | Q8_0 | 658 | 6.3 |

### 04 — Training: Fine-Tuning (Llama 3.1 8B)

Three fine-tuning approaches on the same model, dataset, and hyperparameters. Full FT uses 93.6 GB of 128 GB unified memory.

| Mode | Time | Peak Memory | tok/s | Final Loss |
|------|-----:|------------:|------:|-----------:|
| LoRA | 4h 48m | 87.4 GB | 164 | 1.51 |
| Full FT | 5h 06m | 93.6 GB | 151 | 1.29 |
| QLoRA | 9h 14m | 12.4 GB | 83 | 1.61 |

See [cross-comparison report](04-training-finetuning/results/cross_comparison/cross_comparison.html).

### 05 — Efficiency: Token per Watt

Energy efficiency measured across model sizes and quantizations using llama.cpp with power monitoring.

| Model | Quant | tok/s | Avg Power | tok/W | RM/1M tokens |
|-------|-------|------:|----------:|------:|-------------:|
| 3B | Q4_K_M | 95.9 | 36.6W | **2.62** | RM 0.06 |
| 3B | Q8_0 | 64.0 | 32.7W | 1.96 | RM 0.08 |
| 7B | Q4_K_M | 44.3 | 40.0W | 1.11 | RM 0.14 |
| 7B | Q8_0 | 28.7 | 33.4W | 0.86 | RM 0.18 |
| 14B | Q4_K_M | 22.8 | 41.5W | 0.55 | RM 0.28 |
| 32B | Q4_K_M | 10.1 | 44.3W | 0.23 | RM 0.67 |

Electricity cost based on Malaysian tariff (RM 0.55/kWh).

### 06 — Inference: Embedding Throughput

Mesolitica Mistral 191M embedding model benchmarked on CPU vs GPU.

| Device | Batch | Chunks/s | Power |
|--------|------:|---------:|------:|
| CPU | 64 | 98 | 13W |
| GPU | 32 | 2,810 | 49W |
| GPU | 128 | **3,597** | 58W |
| GPU | 256 | 3,495 | 59W |

GPU is **36x faster** than CPU at optimal batch size. See [HTML report](06-inference-embedding/results/embedding-throughput-report.html).

### 07 — Image & Video Generation

ComfyUI with Z-Image-Turbo (text-to-image, bf16) and Wan 2.2 T2V 14B (text-to-video, fp8).

**Image Generation (Z-Image-Turbo, 4 steps):**

| Resolution | Time | Images/min |
|------------|-----:|-----------:|
| 512x512 | 6.9s | 8.7 |
| 768x768 | 14.0s | 4.3 |
| 1024x1024 | 24.3s | 2.5 |
| 1280x1280 | 38.3s | 1.6 |

**Video Generation (Wan 2.2 T2V 14B, 4 steps):**

| Resolution | Frames | Time | FPS |
|------------|-------:|-----:|----:|
| 480x480 | 17 | 12.2s* | 1.4 |
| 640x640 | 33 | 59.3s | 0.56 |

*After model warm-up. Sample images and video frames in [samples/](07-image-video-generation/samples/).

### 08 — Voice: STT & TTS

Whisper large-v3 (speech-to-text, CPU int8) and MMS-TTS Malay (text-to-speech, GPU).

**TTS — MMS-TTS Malay (facebook/mms-tts-zlm):**

| Text Length | Chars | Synthesis Time | Audio Output | Chars/s |
|-------------|------:|---------------:|-------------:|--------:|
| Short | 25 | 0.02s | 2.3s | 478 |
| Medium | 234 | 0.18s | 16.0s | 1,428 |
| Long | 558 | 0.29s | 38.3s | 1,914 |
| Very Long | 1,199 | 0.59s | 77.5s | **2,017** |

TTS generates 77 seconds of audio in 0.6 seconds (RTF 0.008).

**STT — Whisper large-v3 (faster-whisper, CPU int8):**

| Audio Duration | Transcribe Time | Speed |
|---------------:|----------------:|------:|
| 3.6s | 7.8s | 0.5x |
| 10.9s | 10.1s | 1.1x |
| 21.8s | 14.6s | 1.5x |
| 43.5s | 26.7s | **1.6x** |
| 87.1s | 57.3s | 1.5x |
| 217.7s | 359.8s | 0.6x |

Note: CTranslate2 on aarch64 lacks CUDA wheels, so Whisper runs on CPU. GPU would be significantly faster. Sample audio in [samples/](08-voice-stt-tts/samples/).

---

## Repository Structure

```
gx10-benchmarks/
├── 01-inference-model-scaling/      1.5B to 72B model speed test
├── 02-inference-engine-comparison/  Ollama vs llama.cpp vs vLLM
├── 03-inference-llama-cpp/          Multi-quant benchmarks (Q4/Q5/Q8)
├── 04-training-finetuning/          LoRA / QLoRA / Full Fine-Tune
├── 05-efficiency-token-per-watt/    Energy efficiency per token
├── 06-inference-embedding/          Embedding throughput (CPU vs GPU)
├── 07-image-video-generation/       ComfyUI image + video speed
└── 08-voice-stt-tts/                Whisper STT + MMS-TTS Malay
```

Each benchmark folder contains:
- `README.md` — methodology, configuration, and results
- `run.sh` / `benchmark.py` — reproducible run scripts
- `results/` — raw CSVs, JSON metadata, HTML reports, logs
- `samples/` — generated images, video frames, or audio (where applicable)

## Reproducibility

All benchmarks were run on the same GX10 hardware with no other GPU workloads. To reproduce:

1. Set up the software stack (Ollama, llama.cpp, ComfyUI, etc.) per each benchmark's README
2. Download the required models
3. Run `./run.sh` or `python3 benchmark.py` in each folder
4. Results appear in the `results/` directory

## License

MIT

---

*Pendakwah Teknologi — April 2026*
