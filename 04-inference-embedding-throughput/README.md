# Benchmark #06: Embedding Throughput

Tests how fast the GX10 can embed documents for RAG knowledge base building, measuring
GPU vs CPU performance across varying workload sizes and batch configurations.

## Hardware

- **GPU:** NVIDIA GB10 (Blackwell, SM 12.1)
- **CPU:** 20 ARM cores (Cortex-X925 + A725)
- **Memory:** 122GB unified (shared CPU/GPU)
- **CUDA:** 13.0, Driver 580.142
- **OS:** Ubuntu 24.04 aarch64

## Model

- **Mesolitica Mistral-Embedding 191M**
  - 768 embedding dimensions
  - 8K max sequence length
  - Optimized for Bahasa Melayu
  - Pre-normalized embeddings for cosine similarity

## Methodology

### Test Matrix

| Parameter | Values |
|-----------|--------|
| Devices | CUDA (GPU), CPU (ARM) |
| Chunk counts | 100, 500, 1000, 5000 |
| Batch sizes | 32, 64, 128, 256 |
| Repetitions | 3 per configuration |

- GPU: all 16 configurations (4 chunk counts x 4 batch sizes) x 3 reps = **48 runs**
- CPU: limited to chunks <= 1000, batch <= 64 = **6 configurations** x 3 reps = **18 runs**
- Total: **66 individual measurements**

### Warmup

5 progressive warmup rounds before measurement (16, 32, 64, 128, 256 chunks) to
stabilize GPU state and eliminate cold-start bias.

### Metrics Collected

| Metric | Description |
|--------|-------------|
| chunks/sec | Throughput (primary metric) |
| time_s | Wall-clock time per run |
| gpu_temp_c | GPU temperature after each run |
| gpu_mem_used_mb | GPU memory utilization |
| gpu_power_w | GPU power draw (watts) |

### Statistical Measures (per config)

- Mean, standard deviation, min, max
- P50 (median), P95 percentiles
- All computed from 3 repetitions

### Test Data

10 unique Malay-language text samples simulating real government document chunks
(JPA/JKST style), rotated and tagged with chunk IDs. Each chunk is ~80-120 characters,
representative of actual RAG workloads.

## Output Files

| File | Description |
|------|-------------|
| `results_*.csv` | Raw per-run measurements (66 rows) |
| `summary_*.csv` | Aggregated statistics per config (22 rows) |
| `metadata_*.json` | Full system info, test parameters, software versions |
| `log_*.txt` | Complete console output |
| `report_*.html` | Interactive HTML report with charts and tables |

## How to Run

```bash
# Stop non-essential services to free GPU
sudo systemctl stop jkst-ai jpa-ai visitor-analytics visitor-analytics-worker

# Run benchmark
cd ~/ai/benchmarks/06-inference-embedding
bash run.sh

# Restart services after
sudo systemctl start jkst-ai jpa-ai visitor-analytics visitor-analytics-worker
```

The benchmark takes approximately 3-5 minutes to complete. The HTML report is
generated automatically at the end.

## Key Findings

(Updated after each run — see latest report_*.html for full interactive results)

## Improvements Over v1

- 3 repetitions per config (was 1) for statistical validity
- Mean/stddev/min/max/P50/P95 statistics (was single measurement)
- 5-round progressive warmup (was 1 tiny encode call)
- JSON metadata with full system info (was none)
- GPU memory and power draw tracking (was temperature only)
- torch.cuda.synchronize() for accurate GPU timing
- Interactive HTML report with 6 tabs (was CSV only)
- 10 unique text samples (was 5)

## Created by

Pendakwah Teknologi
