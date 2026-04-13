#!/bin/bash
# Benchmark 09: Coding LLM Webpage Generation
# Tests 3 coding LLMs generating the same interactive webpage
# Measures: TTFT, total time, tokens/sec, total tokens

BENCHMARK_DIR="$(cd "$(dirname "$0")" && pwd)"
PROMPT_FILE="$BENCHMARK_DIR/prompt.txt"
OUTPUT_DIR="$BENCHMARK_DIR/outputs"
RESULTS_DIR="$BENCHMARK_DIR/results"

PROMPT=$(cat "$PROMPT_FILE")

# Models to test
MODELS=("qwen3-coder:30b" "devstral:24b" "deepcoder:14b")
RUNS=3  # 3 runs per model, take median

echo "=============================================="
echo "  Benchmark 09: Coding LLM Webpage Generation"
echo "=============================================="
echo "Date: $(date -Iseconds)"
echo "Models: ${MODELS[*]}"
echo "Runs per model: $RUNS"
echo ""

# Warm up each model first (load into memory)
for model in "${MODELS[@]}"; do
    safe_name=$(echo "$model" | tr ':/' '_')
    echo "[WARMUP] Loading $model into memory..."
    curl -s http://localhost:11434/api/generate -d "{\"model\": \"$model\", \"prompt\": \"hi\", \"stream\": false}" > /dev/null 2>&1
    echo "[WARMUP] $model loaded."
done

for model in "${MODELS[@]}"; do
    safe_name=$(echo "$model" | tr ':/' '_')
    echo ""
    echo "=============================================="
    echo "  Testing: $model"
    echo "=============================================="

    # Unload other models to ensure clean GPU state
    echo "[PREP] Unloading all models..."
    for m in "${MODELS[@]}"; do
        curl -s http://localhost:11434/api/generate -d "{\"model\": \"$m\", \"keep_alive\": 0}" > /dev/null 2>&1
    done
    sleep 2

    # Pre-load this model
    echo "[PREP] Pre-loading $model..."
    curl -s http://localhost:11434/api/generate -d "{\"model\": \"$model\", \"prompt\": \"hi\", \"stream\": false}" > /dev/null 2>&1
    sleep 1

    for run in $(seq 1 $RUNS); do
        echo ""
        echo "--- Run $run/$RUNS ---"

        output_file="$OUTPUT_DIR/${safe_name}_run${run}.html"
        result_file="$RESULTS_DIR/${safe_name}_run${run}.json"

        # Call Ollama API and capture full response with metrics
        start_time=$(date +%s%N)

        response=$(curl -s http://localhost:11434/api/generate \
            -d "$(jq -n \
                --arg model "$model" \
                --arg prompt "$PROMPT" \
                '{
                    model: $model,
                    prompt: $prompt,
                    stream: false,
                    options: {
                        temperature: 0.7,
                        num_predict: 16384,
                        num_ctx: 16384
                    }
                }')" \
            --max-time 600)

        end_time=$(date +%s%N)

        # Parse response
        raw_response=$(echo "$response" | jq -r '.response // empty')
        total_duration=$(echo "$response" | jq -r '.total_duration // 0')
        load_duration=$(echo "$response" | jq -r '.load_duration // 0')
        prompt_eval_count=$(echo "$response" | jq -r '.prompt_eval_count // 0')
        prompt_eval_duration=$(echo "$response" | jq -r '.prompt_eval_duration // 0')
        eval_count=$(echo "$response" | jq -r '.eval_count // 0')
        eval_duration=$(echo "$response" | jq -r '.eval_duration // 0')

        # Calculate metrics
        total_sec=$(echo "scale=2; $total_duration / 1000000000" | bc)
        load_sec=$(echo "scale=2; $load_duration / 1000000000" | bc)
        prompt_eval_sec=$(echo "scale=3; $prompt_eval_duration / 1000000000" | bc)
        eval_sec=$(echo "scale=2; $eval_duration / 1000000000" | bc)

        if [ "$eval_duration" -gt 0 ]; then
            tokens_per_sec=$(echo "scale=2; $eval_count * 1000000000 / $eval_duration" | bc)
        else
            tokens_per_sec=0
        fi

        ttft_sec=$(echo "scale=3; ($load_duration + $prompt_eval_duration) / 1000000000" | bc)

        # Extract HTML from response (find <!DOCTYPE html> to </html>)
        echo "$raw_response" | sed -n '/<!DOCTYPE html>/I,/<\/html>/Ip' > "$output_file"

        # If that didn't work, try extracting from code blocks
        if [ ! -s "$output_file" ]; then
            echo "$raw_response" | sed -n '/```html/,/```/p' | sed '1d;$d' > "$output_file"
        fi

        # If still empty, just save raw response
        if [ ! -s "$output_file" ]; then
            echo "$raw_response" > "$output_file"
        fi

        html_size=$(wc -c < "$output_file")
        html_lines=$(wc -l < "$output_file")

        # Check if output is valid HTML
        has_doctype=$(grep -ci '<!DOCTYPE' "$output_file" || true)
        has_closing_html=$(grep -c '</html>' "$output_file" || true)
        has_canvas=$(grep -c '<canvas' "$output_file" || true)
        has_script=$(grep -c '<script' "$output_file" || true)

        # Save results JSON
        cat > "$result_file" <<EOJSON
{
    "model": "$model",
    "run": $run,
    "timestamp": "$(date -Iseconds)",
    "metrics": {
        "total_duration_sec": $total_sec,
        "model_load_sec": $load_sec,
        "prompt_eval_sec": $prompt_eval_sec,
        "generation_sec": $eval_sec,
        "ttft_sec": $ttft_sec,
        "tokens_generated": $eval_count,
        "tokens_per_sec": $tokens_per_sec,
        "prompt_tokens": $prompt_eval_count
    },
    "output": {
        "html_size_bytes": $html_size,
        "html_lines": $html_lines,
        "has_doctype": $has_doctype,
        "has_closing_html": $has_closing_html,
        "has_canvas": $has_canvas,
        "has_script": $has_script
    }
}
EOJSON

        echo "  Total time:     ${total_sec}s"
        echo "  Generation:     ${eval_sec}s"
        echo "  TTFT:           ${ttft_sec}s"
        echo "  Tokens:         ${eval_count}"
        echo "  Tokens/sec:     ${tokens_per_sec}"
        echo "  HTML size:      ${html_size} bytes (${html_lines} lines)"
        echo "  Valid HTML:     doctype=$has_doctype closing=$has_closing_html"
    done
done

echo ""
echo "=============================================="
echo "  Benchmark Complete!"
echo "=============================================="
echo "Results in: $RESULTS_DIR/"
echo "HTML outputs in: $OUTPUT_DIR/"
