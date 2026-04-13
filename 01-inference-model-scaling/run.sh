#!/bin/bash
# =============================================================================
# Benchmark #1: Can It Run X?
# Tests every popular model size from 1B to 72B on the GX10
# Measures: tok/s, TTFT, total time, memory usage
# =============================================================================

set -e

RESULTS_DIR="/home/gx10/GX10-Benchmarks/inference/01_model_size_scaling"
mkdir -p "$RESULTS_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_FILE="$RESULTS_DIR/results_${TIMESTAMP}.csv"
LOG_FILE="$RESULTS_DIR/log_${TIMESTAMP}.txt"
PROMPT="Explain quantum computing in 3 paragraphs. Be detailed and technical."

# Models to test (smallest to largest)
MODELS=(
    "qwen2.5:1.5b"
    "qwen2.5:3b"
    "qwen2.5:7b"
    "qwen2.5:14b"
    "gemma4:latest"
    "qwen2.5:32b"
    "qwen2.5:72b"
)

MODEL_SIZES=(
    "1.5B"
    "3B"
    "7B"
    "14B"
    "27B"
    "32B"
    "72B"
)

echo "============================================" | tee "$LOG_FILE"
echo "  GX10 Benchmark: Can It Run X?" | tee -a "$LOG_FILE"
echo "  $(date)" | tee -a "$LOG_FILE"
echo "============================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# CSV header
echo "model,size,download_gb,tok_s,ttft_ms,total_time_s,tokens_generated,gpu_temp_c" > "$RESULTS_FILE"

for i in "${!MODELS[@]}"; do
    MODEL="${MODELS[$i]}"
    SIZE="${MODEL_SIZES[$i]}"

    echo "" | tee -a "$LOG_FILE"
    echo "--- Testing $MODEL ($SIZE) ---" | tee -a "$LOG_FILE"

    # Pull if not exists
    if ! ollama list 2>/dev/null | grep -q "$(echo $MODEL | cut -d: -f1).*$(echo $MODEL | cut -d: -f2)"; then
        echo "  Pulling $MODEL..." | tee -a "$LOG_FILE"
        ollama pull "$MODEL" 2>&1 | tail -3 | tee -a "$LOG_FILE"
    else
        echo "  Already installed" | tee -a "$LOG_FILE"
    fi

    # Get model file size
    DL_SIZE=$(ollama list 2>/dev/null | grep "$(echo $MODEL | sed 's/:/\\s/')" | awk '{print $3}' | head -1)

    # Warm up (first run loads model into GPU)
    echo "  Warming up..." | tee -a "$LOG_FILE"
    curl -s http://localhost:11434/api/generate -d "{\"model\":\"$MODEL\",\"prompt\":\"hello\",\"stream\":false}" > /dev/null 2>&1
    sleep 2

    # Get GPU temp before
    GPU_TEMP=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null || echo "N/A")

    # Run benchmark — measure TTFT and total generation
    echo "  Running benchmark..." | tee -a "$LOG_FILE"

    START_NS=$(date +%s%N)
    FIRST_TOKEN_NS=""
    TOTAL_TOKENS=0
    RESPONSE=""

    # Use the API with streaming to measure TTFT
    BENCH_OUTPUT=$(curl -s -w "\n__TOTAL_TIME__%{time_total}" \
        http://localhost:11434/api/generate \
        -d "{\"model\":\"$MODEL\",\"prompt\":\"$PROMPT\",\"stream\":false,\"options\":{\"num_predict\":256}}" 2>&1)

    END_NS=$(date +%s%N)

    # Parse response
    TOTAL_TIME_S=$(echo "$BENCH_OUTPUT" | grep "__TOTAL_TIME__" | sed 's/__TOTAL_TIME__//')
    RESPONSE_JSON=$(echo "$BENCH_OUTPUT" | grep -v "__TOTAL_TIME__")

    # Extract metrics from Ollama response
    EVAL_COUNT=$(echo "$RESPONSE_JSON" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('eval_count',0))" 2>/dev/null || echo "0")
    EVAL_DURATION=$(echo "$RESPONSE_JSON" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('eval_duration',0))" 2>/dev/null || echo "0")
    PROMPT_EVAL_DURATION=$(echo "$RESPONSE_JSON" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('prompt_eval_duration',0))" 2>/dev/null || echo "0")

    # Calculate tok/s and TTFT
    if [ "$EVAL_DURATION" -gt 0 ] 2>/dev/null; then
        TOK_S=$(python3 -c "print(round($EVAL_COUNT / ($EVAL_DURATION / 1e9), 2))")
    else
        TOK_S="0"
    fi

    if [ "$PROMPT_EVAL_DURATION" -gt 0 ] 2>/dev/null; then
        TTFT_MS=$(python3 -c "print(round($PROMPT_EVAL_DURATION / 1e6, 1))")
    else
        TTFT_MS="0"
    fi

    GPU_TEMP_AFTER=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null || echo "N/A")

    echo "  Results: ${TOK_S} tok/s | TTFT: ${TTFT_MS}ms | ${EVAL_COUNT} tokens | ${TOTAL_TIME_S}s total | GPU: ${GPU_TEMP_AFTER}C" | tee -a "$LOG_FILE"

    # Write CSV row
    echo "$MODEL,$SIZE,$DL_SIZE,$TOK_S,$TTFT_MS,$TOTAL_TIME_S,$EVAL_COUNT,$GPU_TEMP_AFTER" >> "$RESULTS_FILE"

    # Unload model to free memory for next test
    curl -s http://localhost:11434/api/generate -d "{\"model\":\"$MODEL\",\"keep_alive\":0}" > /dev/null 2>&1
    sleep 3
done

echo "" | tee -a "$LOG_FILE"
echo "============================================" | tee -a "$LOG_FILE"
echo "  Benchmark Complete!" | tee -a "$LOG_FILE"
echo "  Results: $RESULTS_FILE" | tee -a "$LOG_FILE"
echo "============================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Print summary table
echo "SUMMARY:" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
printf "%-25s %-8s %-10s %-12s %-10s\n" "MODEL" "SIZE" "TOK/S" "TTFT(ms)" "GPU(C)" | tee -a "$LOG_FILE"
printf "%-25s %-8s %-10s %-12s %-10s\n" "-------------------------" "--------" "----------" "------------" "----------" | tee -a "$LOG_FILE"
tail -n +2 "$RESULTS_FILE" | while IFS=, read -r model size dl toks ttft total tokens gpu; do
    printf "%-25s %-8s %-10s %-12s %-10s\n" "$model" "$size" "$toks" "$ttft" "$gpu" | tee -a "$LOG_FILE"
done
