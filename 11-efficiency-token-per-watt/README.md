# Benchmark #05: Token per Watt Efficiency

Measures energy efficiency of LLM inference on the GX10, calculating tokens generated per watt across model sizes and quantizations.

## Method

- Engine: llama.cpp with CUDA
- Models: Qwen2.5 Instruct (3B, 7B, 14B, 32B)
- Quantizations: Q4_K_M, Q5_K_M, Q8_0
- 512 tokens generated per run
- GPU power sampled via nvidia-smi during generation
- Electricity cost: RM 0.55/kWh (Malaysian tariff)

## Results

| Model | Quant | tok/s | Avg Power | tok/W | RM/1M tokens |
|-------|-------|------:|----------:|------:|-------------:|
| 3B | Q4_K_M | 95.9 | 36.6W | **2.62** | RM 0.06 |
| 3B | Q5_K_M | 82.5 | 37.5W | 2.20 | RM 0.07 |
| 3B | Q8_0 | 64.0 | 32.7W | 1.96 | RM 0.08 |
| 7B | Q4_K_M | 44.3 | 40.0W | 1.11 | RM 0.14 |
| 7B | Q5_K_M | 37.4 | 39.7W | 0.94 | RM 0.16 |
| 7B | Q8_0 | 28.7 | 33.4W | 0.86 | RM 0.18 |
| 14B | Q4_K_M | 22.8 | 41.5W | 0.55 | RM 0.28 |
| 14B | Q5_K_M | 18.7 | 47.1W | 0.40 | RM 0.38 |
| 14B | Q8_0 | 14.2 | 32.6W | 0.44 | RM 0.35 |
| 32B | Q4_K_M | 10.1 | 44.3W | 0.23 | RM 0.67 |
| 32B | Q5_K_M | 8.5 | 42.4W | 0.20 | RM 0.76 |
| 32B | Q8_0 | 6.3 | 42.8W | 0.15 | RM 1.03 |

## Key Findings

- Best efficiency: **3B Q4_K_M at 2.62 tok/W** (RM 0.058 per 1K tokens)
- Smaller quants are more power-efficient despite similar wattage
- 14B Q8_0 is more efficient than 14B Q5_K_M due to lower power draw (32.6W vs 47.1W)
- Running a million tokens on the most efficient config costs less than RM 0.06 in electricity

## Output

- `results/token-per-watt-results.csv` — raw data
- `results/token-per-watt-results.json` — structured data
- `results/token-per-watt-log.txt` — run log
