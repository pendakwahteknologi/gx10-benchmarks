# Benchmark #09: Coding LLM Webpage Generation

Can the GX10 run coding LLMs locally and produce real, working code? This benchmark tests 3 top coding models generating the same complex interactive webpage from a single prompt.

## Models Tested

| Model | Parameters | VRAM (Q4_K_M) | Architecture |
|-------|----------:|-------:|-------------|
| Qwen3-Coder | 30B | 18 GB | Dense transformer |
| Devstral | 24B | 14 GB | Mistral-based |
| DeepCoder | 14B | 9 GB | DeepSeek-based |

All models run via Ollama with Q4_K_M quantization.

## The Prompt

A single prompt asking each model to generate a complete interactive 3D solar system visualization in pure HTML/CSS/JS — no external libraries. The prompt tests:

- Complex CSS 3D transforms and animations
- JavaScript interactivity (click, hover, controls)
- Responsive layout
- Visual polish (stars, glow effects, orbital paths)
- UI panel with planet list

See [`prompt.txt`](prompt.txt) for the full prompt.

## Results (Median of 3 Runs)

| Model | tok/s | Gen Time | Tokens | Output Size | TTFT (warm) |
|-------|------:|---------:|-------:|------------:|------------:|
| **Qwen3-Coder:30B** | **71.1** | **62s** | 4,360 | 18.2 KB | 0.085s |
| DeepCoder:14B | 22.4 | 129s | 2,903 | 8.8 KB | 0.15s |
| Devstral:24B | 14.0 | 213s | 2,978 | 10.4 KB | 0.21s |

### Key Findings

- **Qwen3-Coder is 5x faster** than Devstral and **3x faster** than DeepCoder
- All models produced valid, complete HTML on every run
- Qwen3-Coder generates the most code (~19KB, 550+ lines) with the most features
- Warm TTFT is under 250ms for all models
- The GX10's 128 GB unified memory has headroom — largest model uses only 18 GB

## Methodology

- Same prompt for all models (no system prompt variation)
- 3 runs per model, median reported
- Temperature: 0.7
- Context window: 16,384 tokens
- Max output: 16,384 tokens
- Models pre-loaded before timing (warm runs measured separately from cold)
- Other models unloaded between test sets for clean GPU state

## Usage

```bash
./run_benchmark.sh
```

## Output

- `outputs/*.html` — generated webpages (3 per model)
- `results/*.json` — per-run metrics (timing, token counts, validity)
- `index.html` — visual comparison report with charts and live previews
- `prompt.txt` — the exact prompt used
