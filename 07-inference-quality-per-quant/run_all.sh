#!/bin/bash
# Quality-per-quant orchestrator: Qwen2.5 3B/7B/14B × Q4_K_M/Q5_K_M/Q8_0
# Pulls each model, runs HumanEval-164 + GSM8K-200, unloads, deletes, moves on.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
LOG=$ROOT/run_all.log
mkdir -p $ROOT/results

MODELS=(
  "qwen2.5:3b-instruct-q4_K_M"
  "qwen2.5:3b-instruct-q5_K_M"
  "qwen2.5:3b-instruct-q8_0"
  "qwen2.5:7b-instruct-q4_K_M"
  "qwen2.5:7b-instruct-q5_K_M"
  "qwen2.5:7b-instruct-q8_0"
  "qwen2.5:14b-instruct-q4_K_M"
  "qwen2.5:14b-instruct-q5_K_M"
  "qwen2.5:14b-instruct-q8_0"
)

echo "=== Quality-per-quant pipeline started $(date) ===" | tee -a $LOG

for model in "${MODELS[@]}"; do
  safe="${model//:/_}"
  out="$ROOT/results/${safe}.json"
  if [ -f "$out" ]; then
    echo "[$(date)] SKIP $model (already done)" | tee -a $LOG
    continue
  fi
  echo "" | tee -a $LOG
  echo "=== [$(date)] $model ===" | tee -a $LOG
  echo "  pulling..." | tee -a $LOG
  ollama pull "$model" 2>&1 | tail -3 | tee -a $LOG
  echo "  evaluating..." | tee -a $LOG
  python3 $ROOT/scripts/quality_eval.py --model "$model" --humaneval-n 164 --gsm8k-n 200 --out "$out" 2>&1 | tee -a $LOG
  # Unload model (zero keep-alive request) then delete from disk
  curl -s http://localhost:11434/api/generate -d "{\"model\":\"$model\",\"keep_alive\":0}" > /dev/null 2>&1
  sleep 3
  echo "  removing model file" | tee -a $LOG
  ollama rm "$model" 2>&1 | tee -a $LOG
  sync
  sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null || true
  free -h | head -2 | tee -a $LOG
done

echo "" | tee -a $LOG
echo "=== Quality-per-quant pipeline complete $(date) ===" | tee -a $LOG
