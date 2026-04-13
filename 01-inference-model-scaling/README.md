# Benchmark: Can It Run X? (Model Size Scaling)

Tests every popular model size from 1.5B to 72B on the NVIDIA GX10 Grace Blackwell.

## Hardware

- GPU: NVIDIA GB10 (Blackwell, SM 12.1)
- Memory: 122GB unified (shared CPU/GPU)
- CUDA: 13.0, Driver 580.142
- Serving engine: Ollama 0.20.5

## Methodology

- Each model is pulled, warmed up (1 short inference to load into GPU), then benchmarked
- Standard prompt: "Explain quantum computing in 3 paragraphs. Be detailed and technical."
- Max tokens: 256
- Models unloaded between tests to ensure clean GPU state
- All services stopped during benchmark (clean GPU, no contention)
- Ollama optimized: flash attention, q8_0 KV cache, 20 threads, GPU overhead 0

## Results

| Model | Size | tok/s | TTFT | Total Time | GPU Temp |
|-------|------|------:|-----:|-----------:|---------:|
| Qwen2.5 | 1.5B | 173.25 | 11.8ms | 1.7s | 51C |
| Qwen2.5 | 3B | 93.49 | 18.9ms | 3.0s | 53C |
| Qwen2.5 | 7B | 43.20 | 34.7ms | 6.2s | 51C |
| Qwen2.5 | 14B | 22.24 | 64.6ms | 11.9s | 50C |
| Gemma 4 | 27B (MoE) | 55.03 | 30.1ms | 5.0s | 55C |
| Qwen2.5 | 32B | 10.00 | 134.1ms | 26.0s | 53C |
| Qwen2.5 | 72B | 4.24 | 296.0ms | 61.2s | 59C |

## Key Findings

1. **72B model runs on this machine.** Most consumer GPUs with 24GB or even 48GB VRAM cannot load a 72B model at all. The GX10's 122GB unified memory handles it comfortably.

2. **GPU stays cool throughout.** Temperatures range from 50-59C across all model sizes. No thermal throttling.

3. **Gemma 4 27B MoE is faster than dense 14B.** Despite being a 27B parameter model, Gemma 4 only activates 3.8B parameters per inference (Mixture of Experts architecture), resulting in 55 tok/s — faster than the dense 14B Qwen2.5 at 22 tok/s.

4. **Sweet spots by use case:**
   - Real-time chat (40+ tok/s): up to 7B, or Gemma 4 27B MoE
   - Comfortable chat (20+ tok/s): up to 14B
   - Usable but noticeable delay: 32B at 10 tok/s
   - Batch/offline workloads: 72B at 4.2 tok/s

5. **Unified memory advantage.** No model loading failures at any size. The 72B model requires ~47GB which fits entirely in the unified memory pool without any CPU-GPU transfer overhead.

## Date

12 April 2026

## Created by

Pendakwah Teknologi
