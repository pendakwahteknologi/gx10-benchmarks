#!/bin/bash
# =============================================================================
# Benchmark #07: Image & Video Generation Speed
# Tests ComfyUI generation performance on the GX10
#
# Models:
#   1. Z-Image-Turbo (bf16) — text-to-image, 4 steps
#   2. Wan 2.2 T2V 14B (fp8) — text-to-video, 4 steps (LightX2V LoRA)
#
# Test matrix:
#   Image: 512x512, 768x768, 1024x1024, 1280x1280 (4 steps) + 1024x1024 (8 steps)
#   Video: 640x640 (33/49/81 frames) + 480x480 (33 frames)
#   Repetitions: 3 per config
#
# Output:
#   results_*.csv, summary_*.csv, metadata_*.json, log_*.txt, report_*.html
# =============================================================================

set -e
cd /home/gx10/ai/benchmarks/07-efficiency-image-generation

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="log_${TIMESTAMP}.txt"
VENV="/home/gx10/ai/ComfyUI/.venv"
N_REPS=3

echo "============================================" | tee "$LOG_FILE"
echo "  GX10 Benchmark #07: Image & Video Gen"    | tee -a "$LOG_FILE"
echo "  $(date)"                                    | tee -a "$LOG_FILE"
echo "  Reps per config: $N_REPS"                  | tee -a "$LOG_FILE"
echo "============================================" | tee -a "$LOG_FILE"

# ---- Ensure ComfyUI is running ----
echo "" | tee -a "$LOG_FILE"
echo "[Setup] Checking ComfyUI..." | tee -a "$LOG_FILE"

if ! curl -s http://127.0.0.1:8188/system_stats > /dev/null 2>&1; then
    echo "  ComfyUI is not running. Starting..." | tee -a "$LOG_FILE"
    sudo systemctl start comfyui
    echo "  Waiting for ComfyUI to be ready..." | tee -a "$LOG_FILE"
    for i in $(seq 1 60); do
        if curl -s http://127.0.0.1:8188/system_stats > /dev/null 2>&1; then
            echo "  ComfyUI is ready (took ${i}s)" | tee -a "$LOG_FILE"
            break
        fi
        sleep 1
    done
    if ! curl -s http://127.0.0.1:8188/system_stats > /dev/null 2>&1; then
        echo "  ERROR: ComfyUI failed to start!" | tee -a "$LOG_FILE"
        exit 1
    fi
else
    echo "  ComfyUI is already running." | tee -a "$LOG_FILE"
fi

# ---- Stop non-essential services ----
echo "" | tee -a "$LOG_FILE"
echo "[Setup] Stopping non-essential services..." | tee -a "$LOG_FILE"
sudo systemctl stop jkst-ai jpa-ai visitor-analytics visitor-analytics-worker 2>/dev/null || true
echo "  Done." | tee -a "$LOG_FILE"

# ---- Ensure websocket-client is available ----
echo "" | tee -a "$LOG_FILE"
echo "[Setup] Checking websocket-client..." | tee -a "$LOG_FILE"
if ! "$VENV/bin/python3" -c "import websocket" 2>/dev/null; then
    echo "  Installing websocket-client..." | tee -a "$LOG_FILE"
    "$VENV/bin/pip" install websocket-client -q 2>&1 | tee -a "$LOG_FILE"
fi
echo "  OK" | tee -a "$LOG_FILE"

# ---- Run benchmark ----
echo "" | tee -a "$LOG_FILE"
N_VIDEO_REPS=2
"$VENV/bin/python3" benchmark.py --reps "$N_REPS" --video-reps "$N_VIDEO_REPS" 2>&1 | tee -a "$LOG_FILE"

# ---- Generate report ----
echo "" | tee -a "$LOG_FILE"
echo "[Phase 3] Generating HTML report..." | tee -a "$LOG_FILE"

# Find the latest results files
RESULTS=$(ls -t results_*.csv 2>/dev/null | head -1)
SUMMARY=$(ls -t summary_*.csv 2>/dev/null | head -1)
METADATA=$(ls -t metadata_*.json 2>/dev/null | head -1)
REPORT="report_${TIMESTAMP}.html"

if [ -n "$RESULTS" ] && [ -n "$SUMMARY" ] && [ -n "$METADATA" ]; then
    "$VENV/bin/python3" generate_report.py "$RESULTS" "$SUMMARY" "$METADATA" "$REPORT" 2>&1 | tee -a "$LOG_FILE"
else
    echo "  ERROR: Missing result files!" | tee -a "$LOG_FILE"
fi

# ---- Restart services ----
echo "" | tee -a "$LOG_FILE"
echo "[Cleanup] Restarting services..." | tee -a "$LOG_FILE"
sudo systemctl start jkst-ai jpa-ai visitor-analytics visitor-analytics-worker 2>/dev/null || true
echo "  Done." | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "============================================" | tee -a "$LOG_FILE"
echo "  Benchmark Complete!" | tee -a "$LOG_FILE"
echo "  Results: $(pwd)/$RESULTS" | tee -a "$LOG_FILE"
echo "  Summary: $(pwd)/$SUMMARY" | tee -a "$LOG_FILE"
echo "  Report:  $(pwd)/$REPORT" | tee -a "$LOG_FILE"
echo "============================================" | tee -a "$LOG_FILE"
