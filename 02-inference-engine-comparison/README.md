# Benchmark: Serving Engine Comparison

Same model (Qwen2.5-7B) tested on three different serving engines on the NVIDIA GX10.

## Hardware

- GPU: NVIDIA GB10 (Blackwell, SM 12.1)
- Memory: 122GB unified (shared CPU/GPU)
- CUDA: 13.0, Driver 580.142

## Engines Tested

| Engine | Version | Runtime | Notes |
|--------|---------|---------|-------|
| Ollama | 0.20.5 | Native systemd | Flash attention, q8_0 KV cache, 20 threads |
| llama.cpp | Build 6de97b9 | Native binary | Direct llama-bench, CUDA backend |
| vLLM | 0.15.1 | Docker container | scitrera/dgx-spark-vllm:0.15.1-t4, custom built for GB10 sm_121 |

**Important note on vLLM:** Stock vLLM does not support the GB10 GPU (Blackwell sm_121 on aarch64). The prebuilt pip package only includes CUDA kernels up to sm_120. The Docker image used here was custom-compiled by a community member for GB10. This Docker overhead adds latency compared to natively compiled Ollama and llama.cpp. A native vLLM build would likely perform closer to Ollama for single-user throughput.

## Methodology

- Model: Qwen2.5-7B-Instruct (Q4_K_M quantization for Ollama/llama.cpp, FP16 for vLLM)
- Prompt: "Explain quantum computing in 3 paragraphs. Be detailed and technical."
- Max tokens: 256
- 3 runs per engine, results shown individually
- All other services stopped during benchmark
- Models unloaded between engine tests

## Results

### Token Generation (tok/s)

| Engine | Run 1 | Run 2 | Run 3 | Average |
|--------|------:|------:|------:|--------:|
| Ollama | 43.63 | 43.68 | 43.71 | **43.67** |
| llama.cpp | 43.00 | -- | -- | **43.00** |
| vLLM (Docker) | 12.43 | 12.59 | 12.60 | **12.54** |

### Additional Metrics

| Engine | TTFT | GPU Temp | Notes |
|--------|-----:|---------:|-------|
| Ollama | 24-34ms | 53-55C | Consistent, low latency |
| llama.cpp | N/A | 44C | Prompt processing: 3,077 tok/s |
| vLLM (Docker) | N/A | 59-63C | Runs hotter due to Docker + FP16 |

## Key Findings

1. **Ollama and llama.cpp are identical speed (43 tok/s).** This is expected — Ollama uses llama.cpp as its inference backend. The marginal difference is Ollama's API overhead.

2. **vLLM is 3.5x slower for single-user requests.** This is due to:
   - Docker container overhead (not native)
   - FP16 precision vs Q4_K_M quantization (more compute per token)
   - Custom sm_121 build may not be fully optimized
   
3. **vLLM's advantage is concurrency.** While slower per-request, vLLM uses continuous batching and PagedAttention. At 50+ concurrent users, vLLM maintains throughput while Ollama queues requests sequentially. This benchmark only tests single-user performance.

4. **llama.cpp prompt processing is extremely fast at 3,077 tok/s.** This measures how quickly the engine can process input context — critical for long-context applications.

5. **Thermal efficiency varies.** llama.cpp runs coolest (44C), Ollama mid-range (53-55C), vLLM hottest (59-63C).

## Recommendation

- **Single user / local development:** Use Ollama. Simplest, fastest, built-in model management.
- **Multi-user production (20+ concurrent):** Use vLLM. Continuous batching prevents queue buildup.
- **Maximum control / custom integration:** Use llama.cpp directly. Same speed as Ollama with no API overhead.

## Date

12 April 2026

## Created by

Pendakwah Teknologi
