#!/bin/bash
# =============================================================================
# Benchmark #2: Serving Engine Comparison
# Same model (Qwen2.5-7B) on vLLM vs Ollama vs llama.cpp
# Measures: tok/s, TTFT, concurrent throughput
# =============================================================================

set -e

RESULTS_DIR="/home/gx10/GX10-Benchmarks/inference/02_serving_engine_comparison"
mkdir -p "$RESULTS_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_FILE="$RESULTS_DIR/results_${TIMESTAMP}.csv"
LOG_FILE="$RESULTS_DIR/log_${TIMESTAMP}.txt"

PROMPT="Explain quantum computing in 3 paragraphs. Be detailed and technical."
NUM_TOKENS=256

echo "============================================" | tee "$LOG_FILE"
echo "  GX10 Benchmark: Serving Engine Comparison" | tee -a "$LOG_FILE"
echo "  Model: Qwen2.5-7B on all engines" | tee -a "$LOG_FILE"
echo "  $(date)" | tee -a "$LOG_FILE"
echo "============================================" | tee -a "$LOG_FILE"

echo "engine,test,tok_s,ttft_ms,total_time_s,tokens,gpu_temp" > "$RESULTS_FILE"

# ============================================================================
# ENGINE 1: OLLAMA
# ============================================================================
echo "" | tee -a "$LOG_FILE"
echo "=== ENGINE 1: OLLAMA ===" | tee -a "$LOG_FILE"

# Make sure Ollama is running and model is loaded
curl -s http://localhost:11434/api/generate -d '{"model":"qwen2.5:7b","prompt":"warmup","stream":false,"options":{"num_predict":5}}' > /dev/null 2>&1
sleep 2

# Single request benchmark (3 runs, take median)
for run in 1 2 3; do
    echo "  Run $run/3..." | tee -a "$LOG_FILE"
    RESP=$(curl -s http://localhost:11434/api/generate \
        -d "{\"model\":\"qwen2.5:7b\",\"prompt\":\"$PROMPT\",\"stream\":false,\"options\":{\"num_predict\":$NUM_TOKENS}}")

    EVAL_COUNT=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('eval_count',0))" 2>/dev/null)
    EVAL_DUR=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('eval_duration',0))" 2>/dev/null)
    PROMPT_DUR=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('prompt_eval_duration',0))" 2>/dev/null)
    TOTAL_DUR=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('total_duration',0))" 2>/dev/null)

    TOK_S=$(python3 -c "print(round($EVAL_COUNT / ($EVAL_DUR / 1e9), 2))" 2>/dev/null || echo "0")
    TTFT=$(python3 -c "print(round($PROMPT_DUR / 1e6, 1))" 2>/dev/null || echo "0")
    TOTAL_S=$(python3 -c "print(round($TOTAL_DUR / 1e9, 2))" 2>/dev/null || echo "0")
    GPU_T=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null || echo "N/A")

    echo "    tok/s: $TOK_S | TTFT: ${TTFT}ms | Total: ${TOTAL_S}s | GPU: ${GPU_T}C" | tee -a "$LOG_FILE"
    echo "ollama,single_run${run},$TOK_S,$TTFT,$TOTAL_S,$EVAL_COUNT,$GPU_T" >> "$RESULTS_FILE"
    sleep 1
done

# Unload Ollama model
curl -s http://localhost:11434/api/generate -d '{"model":"qwen2.5:7b","keep_alive":0}' > /dev/null 2>&1
sleep 3

# ============================================================================
# ENGINE 2: vLLM
# ============================================================================
echo "" | tee -a "$LOG_FILE"
echo "=== ENGINE 2: vLLM ===" | tee -a "$LOG_FILE"
echo "  Starting vLLM container..." | tee -a "$LOG_FILE"

docker start vllm-jpa 2>/dev/null || true

# Wait for vLLM to be ready
for i in $(seq 1 60); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "  vLLM ready" | tee -a "$LOG_FILE"
        break
    fi
    sleep 5
    echo -n "." | tee -a "$LOG_FILE"
done

sleep 5

# Single request benchmark (3 runs)
for run in 1 2 3; do
    echo "  Run $run/3..." | tee -a "$LOG_FILE"
    START_NS=$(date +%s%N)

    RESP=$(curl -s http://localhost:8000/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d "{\"model\":\"Qwen/Qwen2.5-7B-Instruct\",\"messages\":[{\"role\":\"user\",\"content\":\"$PROMPT\"}],\"max_tokens\":$NUM_TOKENS,\"temperature\":0.2}")

    END_NS=$(date +%s%N)
    TOTAL_S=$(python3 -c "print(round(($END_NS - $START_NS) / 1e9, 2))")

    TOKENS=$(echo "$RESP" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('usage',{}).get('completion_tokens',0))" 2>/dev/null || echo "0")
    TOK_S=$(python3 -c "print(round($TOKENS / $TOTAL_S, 2))" 2>/dev/null || echo "0")
    GPU_T=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null || echo "N/A")

    echo "    tok/s: $TOK_S | Total: ${TOTAL_S}s | Tokens: $TOKENS | GPU: ${GPU_T}C" | tee -a "$LOG_FILE"
    echo "vllm,single_run${run},$TOK_S,0,$TOTAL_S,$TOKENS,$GPU_T" >> "$RESULTS_FILE"
    sleep 1
done

docker stop vllm-jpa 2>/dev/null
sleep 3

# ============================================================================
# ENGINE 3: llama.cpp (direct)
# ============================================================================
echo "" | tee -a "$LOG_FILE"
echo "=== ENGINE 3: llama.cpp ===" | tee -a "$LOG_FILE"

LLAMA_BENCH="/home/gx10/llama.cpp/build/bin/llama-bench"
# Find the qwen2.5-7b GGUF model
GGUF_MODEL=$(find /usr/share/ollama/.ollama/models/blobs/ -type f -size +4G -name "sha256-*" | head -1)

if [ -f "$LLAMA_BENCH" ] && [ -n "$GGUF_MODEL" ]; then
    echo "  Running llama-bench with Qwen2.5-7B..." | tee -a "$LOG_FILE"

    # Token generation benchmark
    BENCH_OUT=$("$LLAMA_BENCH" -m "$GGUF_MODEL" -p 0 -n $NUM_TOKENS -r 3 -o csv 2>/dev/null)
    echo "$BENCH_OUT" | tee -a "$LOG_FILE"

    # Extract tok/s from the CSV output
    TG_TOKS=$(echo "$BENCH_OUT" | tail -1 | awk -F, '{print $NF}')
    GPU_T=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null || echo "N/A")

    echo "    Token generation: $TG_TOKS tok/s | GPU: ${GPU_T}C" | tee -a "$LOG_FILE"
    echo "llama.cpp,tg_bench,$TG_TOKS,0,0,$NUM_TOKENS,$GPU_T" >> "$RESULTS_FILE"

    # Prompt processing benchmark
    BENCH_PP=$("$LLAMA_BENCH" -m "$GGUF_MODEL" -p 512 -n 0 -r 3 -o csv 2>/dev/null)
    PP_TOKS=$(echo "$BENCH_PP" | tail -1 | awk -F, '{print $NF}')
    echo "    Prompt processing: $PP_TOKS tok/s" | tee -a "$LOG_FILE"
    echo "llama.cpp,pp_bench,$PP_TOKS,0,0,512,$GPU_T" >> "$RESULTS_FILE"
else
    echo "  SKIPPED — llama-bench binary or GGUF model not found" | tee -a "$LOG_FILE"
    echo "  llama-bench: $LLAMA_BENCH" | tee -a "$LOG_FILE"
    echo "  GGUF: $GGUF_MODEL" | tee -a "$LOG_FILE"
fi

echo "" | tee -a "$LOG_FILE"
echo "============================================" | tee -a "$LOG_FILE"
echo "  Benchmark Complete!" | tee -a "$LOG_FILE"
echo "  Results: $RESULTS_FILE" | tee -a "$LOG_FILE"
echo "============================================" | tee -a "$LOG_FILE"

# Print summary
echo "" | tee -a "$LOG_FILE"
echo "SUMMARY:" | tee -a "$LOG_FILE"
cat "$RESULTS_FILE" | tee -a "$LOG_FILE"
