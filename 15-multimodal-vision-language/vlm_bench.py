#!/usr/bin/env python3
"""
Vision-Language benchmark for Ollama-hosted VLMs on GX10.

Iterates over (model, image, prompt) triples and measures:
  - TTFT (prompt_eval_duration in ns)
  - Prefill tok/s (prompt_eval_count / prompt_eval_duration)
  - Decode tok/s (eval_count / eval_duration)
  - Wall time
  - Peak GPU memory (from nvidia-smi)

Output: CSV at results/vlm_<timestamp>.csv plus a JSON dump per run for raw replay.
"""

import argparse
import base64
import csv
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")

DEFAULT_MODELS = [
    "moondream:1.8b-v2",
    "llava:7b-v1.6",
    "llava:13b-v1.6",
    "llama3.2-vision:11b",
    "qwen2.5vl:7b",
    "qwen2.5vl:32b",
    "llama3.2-vision:90b",
]

DEFAULT_PROMPT_FILE = Path(__file__).parent / "prompts.txt"
DEFAULT_IMAGE_DIR = Path(__file__).parent / "test_images"


def load_prompts(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")]


def list_test_images(d: Path) -> list[Path]:
    if not d.exists():
        return []
    return sorted([p for p in d.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}])


def encode_image_b64(p: Path) -> str:
    return base64.b64encode(p.read_bytes()).decode("ascii")


def gpu_mem_mib() -> int:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            timeout=5,
        )
        return int(out.decode().strip().splitlines()[0])
    except Exception:
        return -1


def gpu_temp_c() -> int:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            timeout=5,
        )
        return int(out.decode().strip().splitlines()[0])
    except Exception:
        return -1


def model_present(model: str) -> bool:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        r.raise_for_status()
        tags = {m["name"] for m in r.json().get("models", [])}
        return model in tags
    except Exception:
        return False


def pull_model(model: str) -> None:
    print(f"  pulling {model} ...", flush=True)
    subprocess.run(["ollama", "pull", model], check=True)


def unload_model(model: str) -> None:
    try:
        requests.post(f"{OLLAMA_URL}/api/generate",
                      json={"model": model, "keep_alive": 0},
                      timeout=10)
    except Exception:
        pass


def remove_model(model: str) -> None:
    subprocess.run(["ollama", "rm", model], check=False)


def run_one(model: str, prompt: str, image_b64: str, num_predict: int) -> dict:
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
        "options": {
            "num_predict": num_predict,
            "temperature": 0,
            "seed": 42,
        },
    }
    mem_before = gpu_mem_mib()
    t0 = time.perf_counter()
    r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=600)
    wall = time.perf_counter() - t0
    r.raise_for_status()
    mem_after = gpu_mem_mib()
    j = r.json()

    p_eval = j.get("prompt_eval_count", 0) or 0
    p_dur = j.get("prompt_eval_duration", 0) or 0
    e_count = j.get("eval_count", 0) or 0
    e_dur = j.get("eval_duration", 0) or 0

    return {
        "wall_s": wall,
        "prompt_tokens": p_eval,
        "gen_tokens": e_count,
        "ttft_ms": (p_dur / 1e6) if p_dur else 0.0,
        "prefill_tok_s": (p_eval / (p_dur / 1e9)) if p_dur else 0.0,
        "decode_tok_s": (e_count / (e_dur / 1e9)) if e_dur else 0.0,
        "total_s": (p_dur + e_dur) / 1e9 if (p_dur or e_dur) else wall,
        "gpu_mem_before_mib": mem_before,
        "gpu_mem_after_mib": mem_after,
        "gpu_mem_delta_mib": (mem_after - mem_before) if mem_before >= 0 and mem_after >= 0 else -1,
        "response_text": (j.get("response") or "")[:400],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS),
                    help="Comma-separated list of Ollama model tags.")
    ap.add_argument("--prompts", default=str(DEFAULT_PROMPT_FILE),
                    help="Path to a text file with one prompt per line (# starts a comment).")
    ap.add_argument("--images-dir", default=str(DEFAULT_IMAGE_DIR),
                    help="Directory of test images.")
    ap.add_argument("--runs", type=int, default=3, help="Runs per (model,image,prompt) triple.")
    ap.add_argument("--num-predict", type=int, default=256)
    ap.add_argument("--no-pull", action="store_true", help="Skip pulling missing models (fail fast).")
    ap.add_argument("--no-cleanup", action="store_true", help="Do not unload/remove models between runs.")
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    prompts = load_prompts(Path(args.prompts))
    images = list_test_images(Path(args.images_dir))

    if not images:
        print(f"ERROR: no images found in {args.images_dir}. See README.md for the test_images/ spec.", file=sys.stderr)
        sys.exit(2)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    csv_path = out_dir / f"vlm_{ts}.csv"
    json_path = out_dir / f"vlm_{ts}.json"

    print(f"=== Vision-Language benchmark ===")
    print(f"Models : {models}")
    print(f"Images : {[p.name for p in images]}")
    print(f"Prompts: {len(prompts)}")
    print(f"Runs   : {args.runs}")
    print(f"CSV    : {csv_path}")

    fields = ["timestamp", "model", "image", "prompt_idx", "run",
              "prompt_tokens", "gen_tokens", "ttft_ms", "prefill_tok_s", "decode_tok_s",
              "total_s", "wall_s",
              "gpu_mem_before_mib", "gpu_mem_after_mib", "gpu_mem_delta_mib", "gpu_temp_c"]

    all_records = []
    with csv_path.open("w") as fh:
        w = csv.writer(fh)
        w.writerow(fields)

        for model in models:
            print(f"\n=== model: {model} ===", flush=True)
            if not model_present(model):
                if args.no_pull:
                    print(f"  not present and --no-pull set — skipping.", flush=True)
                    continue
                try:
                    pull_model(model)
                except subprocess.CalledProcessError as e:
                    print(f"  pull failed: {e} — skipping.", flush=True)
                    continue
            else:
                print(f"  already present", flush=True)

            # Warmup
            try:
                requests.post(f"{OLLAMA_URL}/api/generate",
                              json={"model": model, "prompt": "Hello.", "stream": False,
                                    "options": {"num_predict": 4}},
                              timeout=120)
            except Exception:
                pass

            for img_path in images:
                image_b64 = encode_image_b64(img_path)
                for pi, prompt in enumerate(prompts):
                    for run in range(1, args.runs + 1):
                        try:
                            m = run_one(model, prompt, image_b64, args.num_predict)
                        except Exception as e:
                            print(f"  ERR {img_path.name} prompt#{pi} run{run}: {e}", flush=True)
                            continue
                        rec = {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "model": model,
                            "image": img_path.name,
                            "prompt_idx": pi,
                            "run": run,
                            **m,
                            "gpu_temp_c": gpu_temp_c(),
                        }
                        all_records.append(rec)
                        w.writerow([rec.get(k, "") for k in fields])
                        fh.flush()
                        print(f"  {img_path.name} p#{pi} r{run}: "
                              f"prefill={m['prefill_tok_s']:.0f} decode={m['decode_tok_s']:.1f} "
                              f"ttft={m['ttft_ms']:.0f}ms mem={m['gpu_mem_after_mib']}MiB",
                              flush=True)

            if not args.no_cleanup:
                unload_model(model)
                time.sleep(2)
                remove_model(model)

    json_path.write_text(json.dumps(all_records, indent=2))
    print(f"\nWrote {len(all_records)} records.")
    print(f"CSV : {csv_path}")
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
