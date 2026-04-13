#!/bin/bash
# =============================================================================
# Benchmark #06: Embedding Throughput
# Tests how fast the GX10 can embed documents for RAG
#
# Methodology:
#   - Model: Mesolitica Mistral-Embedding 191M (768-dim, Bahasa Melayu)
#   - Devices: CUDA (GB10 GPU) and CPU (ARM Cortex-X925/A725)
#   - Chunk counts: 100, 500, 1000, 5000
#   - Batch sizes: 32, 64, 128, 256
#   - Repetitions: 3 per configuration (for statistical rigor)
#   - Warmup: 5 progressive rounds before measurement
#   - Metrics: chunks/s, latency, GPU temp, GPU memory, power draw
#   - Statistics: mean, stddev, min, max, P50, P95 per config
#
# Output:
#   - results_<timestamp>.csv        — raw per-run results
#   - summary_<timestamp>.csv        — aggregated statistics
#   - metadata_<timestamp>.json      — system info & parameters
#   - log_<timestamp>.txt            — full console log
#   - report_<timestamp>.html        — interactive HTML report
# =============================================================================

set -e
cd /home/gx10/ai/benchmarks/06-inference-embedding

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_FILE="results_${TIMESTAMP}.csv"
SUMMARY_FILE="summary_${TIMESTAMP}.csv"
METADATA_FILE="metadata_${TIMESTAMP}.json"
LOG_FILE="log_${TIMESTAMP}.txt"
REPORT_FILE="report_${TIMESTAMP}.html"

VENV="/opt/jkst-ai/venv"
N_REPS=3

echo "============================================" | tee "$LOG_FILE"
echo "  GX10 Benchmark #06: Embedding Throughput" | tee -a "$LOG_FILE"
echo "  $(date)" | tee -a "$LOG_FILE"
echo "  Reps per config: $N_REPS" | tee -a "$LOG_FILE"
echo "============================================" | tee -a "$LOG_FILE"

source "$VENV/bin/activate"

# ---- Phase 1: Collect system metadata ----
echo "" | tee -a "$LOG_FILE"
echo "[Phase 1] Collecting system metadata..." | tee -a "$LOG_FILE"

python3 << METAEOF > "$METADATA_FILE"
import json, subprocess, platform, os, torch

def cmd(c):
    try:
        return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=10).stdout.strip()
    except:
        return "N/A"

meta = {
    "benchmark": "06-inference-embedding",
    "title": "Embedding Throughput",
    "timestamp": "$TIMESTAMP",
    "n_reps": $N_REPS,
    "system": {
        "hostname": platform.node(),
        "os": cmd("lsb_release -ds 2>/dev/null || cat /etc/os-release | head -1"),
        "kernel": platform.release(),
        "arch": platform.machine(),
        "cpu_model": cmd("lscpu | grep 'Model name' | head -1 | sed 's/.*: *//'"),
        "cpu_cores": int(cmd("nproc")),
        "ram_total_gb": round(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / (1024**3), 1),
    },
    "gpu": {
        "name": cmd("nvidia-smi --query-gpu=name --format=csv,noheader"),
        "driver": cmd("nvidia-smi --query-gpu=driver_version --format=csv,noheader"),
        "cuda_version": torch.version.cuda or "N/A",
        "compute_capability": f"{torch.cuda.get_device_capability()[0]}.{torch.cuda.get_device_capability()[1]}" if torch.cuda.is_available() else "N/A",
        "memory_total_mb": cmd("nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits"),
    },
    "model": {
        "name": "mesolitica/mistral-embedding-191m-8k-contrastive",
        "parameters": "191M",
        "embedding_dim": 768,
        "max_seq_length": 8192,
        "language": "Bahasa Melayu",
    },
    "test_params": {
        "chunk_counts": [100, 500, 1000, 5000],
        "batch_sizes": [32, 64, 128, 256],
        "devices": ["cuda", "cpu"],
        "cpu_max_chunks": 1000,
        "cpu_max_batch": 64,
    },
    "software": {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "sentence_transformers": cmd("python3 -c \"import sentence_transformers; print(sentence_transformers.__version__)\""),
    }
}
print(json.dumps(meta, indent=2))
METAEOF

echo "  Metadata saved to $METADATA_FILE" | tee -a "$LOG_FILE"
cat "$METADATA_FILE" | tee -a "$LOG_FILE"

# ---- Phase 2: Run benchmark ----
echo "" | tee -a "$LOG_FILE"
echo "[Phase 2] Running embedding benchmark ($N_REPS reps per config)..." | tee -a "$LOG_FILE"

# Create output files so Python can find them via glob
echo "run,device,num_chunks,batch_size,time_s,chunks_per_sec,gpu_temp_c,gpu_mem_used_mb,gpu_power_w" > "$RESULTS_FILE"
touch "$SUMMARY_FILE"

python3 << 'PYEOF' 2>&1 | tee -a "$LOG_FILE"
import time
import torch
import subprocess
import os
import glob
import json
import statistics

N_REPS = 3

def gpu_stats():
    """Get GPU temperature, memory used, and power draw."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu,memory.used,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        parts = [p.strip() for p in r.stdout.strip().split(",")]
        def parse_val(s, cast=float):
            s = s.strip()
            if s in ("[N/A]", "N/A", ""):
                return -1
            return cast(s)
        return {
            "temp": parse_val(parts[0], int),
            "mem_mb": parse_val(parts[1], lambda x: int(float(x))),
            "power_w": round(parse_val(parts[2], float), 1) if parse_val(parts[2]) != -1 else -1.0
        }
    except:
        return {"temp": -1, "mem_mb": -1, "power_w": -1}

# Load model
print("\nLoading Mesolitica Mistral-Embedding 191M...")
os.environ["HF_HOME"] = "/opt/jkst-ai/.hf_cache"
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("mesolitica/mistral-embedding-191m-8k-contrastive")

# Prepare test data — realistic Malay RAG chunks
sample_texts = [
    "Jabatan Perkhidmatan Awam Malaysia bertanggungjawab dalam pengurusan sumber manusia perkhidmatan awam.",
    "Prosedur permohonan cuti rehat bagi penjawat awam adalah tertakluk kepada pekeliling yang berkuat kuasa.",
    "Mahkamah Syariah Terengganu mengendalikan kes-kes berkaitan perkahwinan, perceraian, dan nafkah.",
    "Pembangunan kompetensi pegawai awam dilaksanakan melalui program latihan berstruktur di INTAN.",
    "Skim perkhidmatan awam Malaysia merangkumi pelbagai gred jawatan dari gred 1 hingga JUSA.",
    "Dasar kerajaan mengenai pendigitalan perkhidmatan awam bertujuan meningkatkan kecekapan penyampaian.",
    "Pihak berkuasa tempatan bertanggungjawab dalam pengurusan sisa pepejal dan kebersihan kawasan.",
    "Sistem ePenyata Gaji membolehkan penjawat awam menyemak penyata gaji secara dalam talian.",
    "Pekeliling Perkhidmatan Bilangan 4 Tahun 2024 mengemas kini syarat-syarat kenaikan pangkat.",
    "Unit Pemodenan Tadbiran dan Perancangan Pengurusan Malaysia memantau prestasi agensi kerajaan.",
]

def make_chunks(n):
    """Generate n realistic chunks."""
    return [f"{sample_texts[i % len(sample_texts)]} [Dokumen {i+1}/{n}]" for i in range(n)]

all_results = []

for device_name in ["cuda", "cpu"]:
    print(f"\n{'='*60}")
    print(f"  Device: {device_name.upper()}")
    print(f"{'='*60}")

    model = model.to(device_name)

    # ---- Warmup: 5 progressive rounds ----
    print(f"\n  Warmup ({device_name})...")
    warmup_sizes = [16, 32, 64, 128, 256]
    for ws in warmup_sizes:
        warmup_chunks = make_chunks(min(ws, 256))
        _ = model.encode(warmup_chunks, device=device_name, batch_size=min(ws, 64),
                        normalize_embeddings=True, show_progress_bar=False)
    if device_name == "cuda":
        torch.cuda.synchronize()
    print(f"  Warmup complete.")

    chunk_counts = [100, 500, 1000, 5000]
    batch_sizes = [32, 64, 128, 256]

    for num_chunks in chunk_counts:
        if device_name == "cpu" and num_chunks > 1000:
            continue

        chunks = make_chunks(num_chunks)

        for batch_size in batch_sizes:
            if device_name == "cpu" and batch_size > 64:
                continue

            config_results = []
            print(f"\n  {num_chunks} chunks, batch={batch_size}:")

            for rep in range(1, N_REPS + 1):
                if device_name == "cuda":
                    torch.cuda.synchronize()

                stats_before = gpu_stats()

                t0 = time.time()
                embeddings = model.encode(
                    chunks,
                    batch_size=batch_size,
                    device=device_name,
                    normalize_embeddings=True,
                    show_progress_bar=False
                )
                if device_name == "cuda":
                    torch.cuda.synchronize()
                elapsed = time.time() - t0

                stats_after = gpu_stats()
                cps = round(num_chunks / elapsed, 1)

                result = {
                    "run": rep,
                    "device": device_name,
                    "num_chunks": num_chunks,
                    "batch_size": batch_size,
                    "time_s": round(elapsed, 4),
                    "chunks_per_sec": cps,
                    "gpu_temp": stats_after["temp"],
                    "gpu_mem_mb": stats_after["mem_mb"],
                    "gpu_power_w": stats_after["power_w"],
                }
                config_results.append(result)
                all_results.append(result)

                print(f"    Run {rep}/{N_REPS}: {elapsed:.3f}s ({cps} chunks/s) "
                      f"GPU: {stats_after['temp']}C, {stats_after['mem_mb']}MB, {stats_after['power_w']}W")

            # Print config stats
            times = [r["time_s"] for r in config_results]
            cps_vals = [r["chunks_per_sec"] for r in config_results]
            mean_cps = statistics.mean(cps_vals)
            std_cps = statistics.stdev(cps_vals) if len(cps_vals) > 1 else 0
            print(f"    => Mean: {mean_cps:.1f} chunks/s (stddev: {std_cps:.1f})")

# ---- Write raw CSV ----
print("\n=== Writing raw results ===")
csv_files = sorted(glob.glob("results_*.csv"))
if csv_files:
    csv_file = csv_files[-1]
    with open(csv_file, 'a') as f:
        for r in all_results:
            f.write(f"{r['run']},{r['device']},{r['num_chunks']},{r['batch_size']},"
                    f"{r['time_s']},{r['chunks_per_sec']},{r['gpu_temp']},"
                    f"{r['gpu_mem_mb']},{r['gpu_power_w']}\n")
    print(f"  Raw results: {csv_file} ({len(all_results)} rows)")

# ---- Compute & write summary CSV ----
print("\n=== Computing summary statistics ===")

# Group by (device, num_chunks, batch_size)
configs = {}
for r in all_results:
    key = (r["device"], r["num_chunks"], r["batch_size"])
    configs.setdefault(key, []).append(r)

# Find the summary file created by bash (or create one)
summary_files = sorted(glob.glob("summary_*.csv"))
summary_file = summary_files[-1] if summary_files else "summary_results.csv"

with open(summary_file, 'w') as f:
    f.write("device,num_chunks,batch_size,mean_time_s,stddev_time_s,min_time_s,max_time_s,"
            "mean_cps,stddev_cps,min_cps,max_cps,p50_cps,p95_cps,"
            "mean_gpu_temp,mean_gpu_mem_mb,mean_gpu_power_w\n")

    for key in sorted(configs.keys()):
        runs = configs[key]
        times = [r["time_s"] for r in runs]
        cps_vals = [r["chunks_per_sec"] for r in runs]
        temps = [r["gpu_temp"] for r in runs]
        mems = [r["gpu_mem_mb"] for r in runs]
        powers = [r["gpu_power_w"] for r in runs]

        sorted_cps = sorted(cps_vals)
        n = len(sorted_cps)
        p50 = sorted_cps[n // 2]
        p95_idx = min(int(n * 0.95), n - 1)
        p95 = sorted_cps[p95_idx]

        f.write(f"{key[0]},{key[1]},{key[2]},"
                f"{statistics.mean(times):.4f},{statistics.stdev(times) if n > 1 else 0:.4f},"
                f"{min(times):.4f},{max(times):.4f},"
                f"{statistics.mean(cps_vals):.1f},{statistics.stdev(cps_vals) if n > 1 else 0:.1f},"
                f"{min(cps_vals):.1f},{max(cps_vals):.1f},"
                f"{p50:.1f},{p95:.1f},"
                f"{statistics.mean(temps):.0f},{statistics.mean(mems):.0f},{statistics.mean(powers):.1f}\n")

print(f"  Summary: {summary_file}")

# ---- Print final summary table ----
print("\n" + "=" * 100)
print(f"{'Device':<6} {'Chunks':<8} {'Batch':<6} {'Mean CPS':<12} {'StdDev':<10} {'Min':<10} {'Max':<10} {'GPU C':<7} {'Mem MB':<8} {'Watts'}")
print("-" * 100)

for key in sorted(configs.keys()):
    runs = configs[key]
    cps_vals = [r["chunks_per_sec"] for r in runs]
    temps = [r["gpu_temp"] for r in runs]
    mems = [r["gpu_mem_mb"] for r in runs]
    powers = [r["gpu_power_w"] for r in runs]
    n = len(cps_vals)

    print(f"{key[0]:<6} {key[1]:<8} {key[2]:<6} "
          f"{statistics.mean(cps_vals):<12.1f} {statistics.stdev(cps_vals) if n > 1 else 0:<10.1f} "
          f"{min(cps_vals):<10.1f} {max(cps_vals):<10.1f} "
          f"{statistics.mean(temps):<7.0f} {statistics.mean(mems):<8.0f} {statistics.mean(powers):.1f}")

# Peak results
print("\n=== PEAK PERFORMANCE ===")
gpu_results = [r for r in all_results if r['device'] == 'cuda']
cpu_results = [r for r in all_results if r['device'] == 'cpu']

if gpu_results:
    # Use mean CPS per config for peak
    gpu_configs = {}
    for r in gpu_results:
        key = (r["num_chunks"], r["batch_size"])
        gpu_configs.setdefault(key, []).append(r["chunks_per_sec"])
    best_gpu_key = max(gpu_configs, key=lambda k: statistics.mean(gpu_configs[k]))
    best_gpu_mean = statistics.mean(gpu_configs[best_gpu_key])
    print(f"  GPU peak (mean): {best_gpu_mean:.1f} chunks/s "
          f"(chunks={best_gpu_key[0]}, batch={best_gpu_key[1]})")

if cpu_results:
    cpu_configs = {}
    for r in cpu_results:
        key = (r["num_chunks"], r["batch_size"])
        cpu_configs.setdefault(key, []).append(r["chunks_per_sec"])
    best_cpu_key = max(cpu_configs, key=lambda k: statistics.mean(cpu_configs[k]))
    best_cpu_mean = statistics.mean(cpu_configs[best_cpu_key])
    print(f"  CPU peak (mean): {best_cpu_mean:.1f} chunks/s "
          f"(chunks={best_cpu_key[0]}, batch={best_cpu_key[1]})")

    if gpu_results:
        speedup = best_gpu_mean / best_cpu_mean
        print(f"  GPU speedup: {speedup:.1f}x over CPU")

PYEOF

echo "" | tee -a "$LOG_FILE"
echo "============================================" | tee -a "$LOG_FILE"
echo "  Benchmark Complete!" | tee -a "$LOG_FILE"
echo "  Raw results:  $(pwd)/$RESULTS_FILE" | tee -a "$LOG_FILE"
echo "  Summary:      $(pwd)/$SUMMARY_FILE" | tee -a "$LOG_FILE"
echo "  Metadata:     $(pwd)/$METADATA_FILE" | tee -a "$LOG_FILE"
echo "============================================" | tee -a "$LOG_FILE"

# ---- Phase 3: Generate HTML report ----
echo "" | tee -a "$LOG_FILE"
echo "[Phase 3] Generating HTML report..." | tee -a "$LOG_FILE"

python3 generate_report.py "$RESULTS_FILE" "$SUMMARY_FILE" "$METADATA_FILE" "$REPORT_FILE" 2>&1 | tee -a "$LOG_FILE"

echo "  Report: $(pwd)/$REPORT_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "All done!" | tee -a "$LOG_FILE"
