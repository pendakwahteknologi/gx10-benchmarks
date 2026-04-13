#!/usr/bin/env python3
"""
Benchmark #07: Image & Video Generation Speed
Tests ComfyUI generation performance on the GX10 via the API.

Models tested:
  1. Z-Image-Turbo (12B bf16) — text-to-image, 4 steps
  2. Wan 2.2 T2V 14B (fp8) — text-to-video with LightX2V 4-step LoRA

Usage: python3 benchmark.py [--reps N] [--skip-video] [--skip-image]
"""

import json
import time
import uuid
import subprocess
import statistics
import argparse
import os
import glob
import csv
from urllib import request, parse, error

try:
    import websocket
    HAS_WS = True
except ImportError:
    HAS_WS = False

SERVER = "127.0.0.1:8188"
BENCHMARK_DIR = "/home/gx10/ai/benchmarks/07-efficiency-image-generation"
TIMESTAMP = time.strftime("%Y%m%d_%H%M%S")

# ============================================================================
# ComfyUI API helpers
# ============================================================================

def check_server():
    """Check if ComfyUI is running."""
    try:
        req = request.urlopen(f"http://{SERVER}/system_stats", timeout=5)
        data = json.loads(req.read())
        return data
    except Exception as e:
        return None


def queue_prompt(prompt_dict):
    """Submit a workflow to ComfyUI. Returns prompt_id."""
    prompt_id = str(uuid.uuid4())
    client_id = str(uuid.uuid4())
    payload = json.dumps({
        "prompt": prompt_dict,
        "client_id": client_id,
        "prompt_id": prompt_id,
    }).encode("utf-8")
    req = request.Request(f"http://{SERVER}/prompt", data=payload)
    req.add_header("Content-Type", "application/json")
    resp = request.urlopen(req)
    resp.read()
    return prompt_id, client_id


def wait_for_completion(prompt_id, client_id, timeout=1800):
    """Wait for a prompt to complete. Try WebSocket first, fall back to polling."""
    if HAS_WS:
        result = _wait_ws(prompt_id, client_id, timeout)
        if result is not None:
            return result
        # WebSocket failed/timed out — fall back to polling
        print("    WebSocket dropped, falling back to polling...")
    return _wait_poll(prompt_id, timeout)


def _wait_ws(prompt_id, client_id, timeout):
    """Wait via WebSocket. Returns True/False on completion, None if connection dropped."""
    try:
        ws = websocket.WebSocket()
        ws.settimeout(120)  # 2-min recv timeout — we'll loop and re-check
        ws.connect(f"ws://{SERVER}/ws?clientId={client_id}")
    except Exception as e:
        print(f"    WebSocket connect error: {e}")
        return None

    start = time.time()
    try:
        while time.time() - start < timeout:
            try:
                out = ws.recv()
            except websocket.WebSocketTimeoutException:
                # Recv timed out — check if still within total timeout
                continue
            except Exception:
                return None  # Connection lost

            if isinstance(out, str):
                msg = json.loads(out)
                if msg.get("type") == "executing":
                    data = msg["data"]
                    if data.get("node") is None and data.get("prompt_id") == prompt_id:
                        return True  # Done
                elif msg.get("type") == "execution_error":
                    print(f"    ERROR: {msg.get('data', {}).get('exception_message', 'unknown')}")
                    return False
    except Exception as e:
        print(f"    WebSocket error: {e}")
        return None
    finally:
        try:
            ws.close()
        except:
            pass

    return None  # Timeout reached


def _wait_poll(prompt_id, timeout):
    """Fallback: poll /history and /queue endpoints."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            # Check history first — completed prompts appear here
            resp = request.urlopen(f"http://{SERVER}/history/{prompt_id}", timeout=5)
            data = json.loads(resp.read())
            if prompt_id in data:
                status = data[prompt_id].get("status", {})
                outputs = data[prompt_id].get("outputs", {})
                if status.get("completed", False) or status.get("status_str") == "success" or outputs:
                    return True
                if status.get("status_str") == "error":
                    return False
        except:
            pass

        try:
            # Check queue — if nothing running and not in history, it's done or failed
            resp = request.urlopen(f"http://{SERVER}/queue", timeout=5)
            qdata = json.loads(resp.read())
            running = qdata.get("queue_running", [])
            pending = qdata.get("queue_pending", [])
            if not running and not pending:
                # Queue empty — check history one more time
                try:
                    resp = request.urlopen(f"http://{SERVER}/history/{prompt_id}", timeout=5)
                    data = json.loads(resp.read())
                    if prompt_id in data:
                        return True
                except:
                    pass
        except:
            pass

        elapsed = time.time() - start
        if elapsed > 60:
            time.sleep(10)  # Poll less frequently for long runs
        else:
            time.sleep(3)
    return False


def get_history(prompt_id):
    """Get execution history for a prompt."""
    try:
        resp = request.urlopen(f"http://{SERVER}/history/{prompt_id}", timeout=10)
        return json.loads(resp.read())
    except:
        return {}


def free_memory():
    """Ask ComfyUI to free unused memory."""
    try:
        payload = json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8")
        req = request.Request(f"http://{SERVER}/free", data=payload)
        req.add_header("Content-Type", "application/json")
        request.urlopen(req, timeout=10).read()
    except:
        pass


def gpu_stats():
    """Get GPU temperature and power."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        parts = [p.strip() for p in r.stdout.strip().split(",")]
        temp = int(parts[0]) if parts[0] not in ("[N/A]", "N/A", "") else -1
        try:
            power = round(float(parts[1]), 1)
        except:
            power = -1.0
        return {"temp": temp, "power_w": power}
    except:
        return {"temp": -1, "power_w": -1.0}


# ============================================================================
# Workflow builders — flat API format extracted from blueprints
# ============================================================================

def build_z_image_turbo(prompt_text, width, height, seed=42, steps=4):
    """Build Z-Image-Turbo text-to-image workflow."""
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "z_image_turbo_bf16.safetensors",
                "weight_dtype": "default"
            }
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen_3_4b.safetensors",
                "type": "lumina2",
                "device": "default"
            }
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "ae.safetensors"
            }
        },
        "4": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {
                "model": ["1", 0],
                "shift": 3.0
            }
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["2", 0],
                "text": prompt_text
            }
        },
        "6": {
            "class_type": "ConditioningZeroOut",
            "inputs": {
                "conditioning": ["5", 0]
            }
        },
        "7": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1
            }
        },
        "8": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["4", 0],
                "positive": ["5", 0],
                "negative": ["6", 0],
                "latent_image": ["7", 0],
                "seed": seed,
                "steps": steps,
                "cfg": 1.0,
                "sampler_name": "res_multistep",
                "scheduler": "simple",
                "denoise": 1.0
            }
        },
        "9": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["8", 0],
                "vae": ["3", 0]
            }
        },
        "10": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["9", 0],
                "filename_prefix": f"bench07/z_turbo_{width}x{height}_s{steps}"
            }
        }
    }


def build_z_image_turbo_batch(prompt_text, width, height, seed=42, steps=4, batch_size=4):
    """Build Z-Image-Turbo workflow with batch_size > 1."""
    wf = build_z_image_turbo(prompt_text, width, height, seed, steps)
    wf["7"]["inputs"]["batch_size"] = batch_size
    wf["10"]["inputs"]["filename_prefix"] = f"bench07/z_turbo_{width}x{height}_b{batch_size}"
    return wf


def build_wan22_t2v(prompt_text, width=640, height=640, length=33, seed=42):
    """Build Wan 2.2 T2V workflow with LightX2V 4-step LoRA."""
    negative_prompt = (
        "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，"
        "整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，"
        "画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，"
        "静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走，裸露，NSFW"
    )
    return {
        # Model loaders
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors",
                "weight_dtype": "default"
            }
        },
        "2": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors",
                "weight_dtype": "default"
            }
        },
        "3": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                "type": "wan",
                "device": "default"
            }
        },
        "4": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "wan_2.1_vae.safetensors"
            }
        },
        # LoRA (4-step acceleration)
        "5": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["1", 0],
                "lora_name": "wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors",
                "strength_model": 1.0
            }
        },
        "6": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["2", 0],
                "lora_name": "wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors",
                "strength_model": 1.0
            }
        },
        # ModelSamplingSD3
        "7": {
            "class_type": "ModelSamplingSD3",
            "inputs": {
                "model": ["5", 0],
                "shift": 5.0
            }
        },
        "8": {
            "class_type": "ModelSamplingSD3",
            "inputs": {
                "model": ["6", 0],
                "shift": 5.0
            }
        },
        # Text encoding
        "9": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["3", 0],
                "text": prompt_text
            }
        },
        "10": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["3", 0],
                "text": negative_prompt
            }
        },
        # Latent video
        "11": {
            "class_type": "EmptyHunyuanLatentVideo",
            "inputs": {
                "width": width,
                "height": height,
                "length": length,
                "batch_size": 1
            }
        },
        # High noise sampler (steps 0-2)
        "12": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["7", 0],
                "positive": ["9", 0],
                "negative": ["10", 0],
                "latent_image": ["11", 0],
                "add_noise": "enable",
                "noise_seed": seed,
                "steps": 4,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "start_at_step": 0,
                "end_at_step": 2,
                "return_with_leftover_noise": "enable"
            }
        },
        # Low noise sampler (steps 2-4)
        "13": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["8", 0],
                "positive": ["9", 0],
                "negative": ["10", 0],
                "latent_image": ["12", 0],
                "add_noise": "disable",
                "noise_seed": seed,
                "steps": 4,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "start_at_step": 2,
                "end_at_step": 4,
                "return_with_leftover_noise": "disable"
            }
        },
        # Decode
        "14": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["13", 0],
                "vae": ["4", 0]
            }
        },
        # Save frames as images (for benchmarking we just need completion)
        "15": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["14", 0],
                "filename_prefix": f"bench07/wan22_{width}x{height}_f{length}"
            }
        }
    }


# ============================================================================
# Test configurations
# ============================================================================

IMAGE_PROMPTS = [
    "A majestic mountain landscape with a crystal clear lake reflecting the sunset, photorealistic",
    "A futuristic city skyline at night with neon lights and flying vehicles, cinematic lighting",
    "A serene Japanese garden with cherry blossoms falling over a stone path, soft natural light",
]

VIDEO_PROMPTS = [
    "A cat walking gracefully across a sunlit windowsill, smooth camera tracking, natural lighting",
    "Ocean waves gently crashing on a tropical beach at golden hour, cinematic slow motion",
]

IMAGE_TESTS = [
    # (name, width, height, steps)
    ("z_turbo_512x512_4steps", 512, 512, 4),
    ("z_turbo_768x768_4steps", 768, 768, 4),
    ("z_turbo_1024x1024_4steps", 1024, 1024, 4),
    ("z_turbo_1280x1280_4steps", 1280, 1280, 4),
    ("z_turbo_1024x1024_8steps", 1024, 1024, 8),
]

# Showcase: push resolution to the limit (122GB unified memory advantage)
IMAGE_SHOWCASE_TESTS = [
    ("z_turbo_2048x2048_4steps", 2048, 2048, 4),
    ("z_turbo_2560x2560_4steps", 2560, 2560, 4),
    ("z_turbo_3840x2160_4steps", 3840, 2160, 4),   # 4K landscape
]

# Showcase: batch generation (multiple images in one pass)
IMAGE_BATCH_TESTS = [
    # (name, width, height, steps, batch_size)
    ("z_turbo_1024x1024_batch4", 1024, 1024, 4, 4),
    ("z_turbo_1024x1024_batch8", 1024, 1024, 4, 8),
]

VIDEO_TESTS = [
    # (name, width, height, frames)
    ("wan22_480x480_17f", 480, 480, 17),
    ("wan22_640x640_33f", 640, 640, 33),
]

# Showcase: push frame count and resolution
VIDEO_SHOWCASE_TESTS = [
    ("wan22_640x640_81f", 640, 640, 81),
    ("wan22_640x640_129f", 640, 640, 129),
    ("wan22_832x832_33f", 832, 832, 33),
]


# ============================================================================
# Benchmark runner
# ============================================================================

def collect_metadata():
    """Collect system and software metadata."""
    import platform

    def cmd(c):
        try:
            return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=10).stdout.strip()
        except:
            return "N/A"

    sys_stats = check_server() or {}

    meta = {
        "benchmark": "07-efficiency-image-generation",
        "title": "Image & Video Generation Speed",
        "timestamp": TIMESTAMP,
        "system": {
            "hostname": platform.node(),
            "os": cmd("lsb_release -ds 2>/dev/null || head -1 /etc/os-release"),
            "kernel": platform.release(),
            "arch": platform.machine(),
            "cpu_model": cmd("lscpu | grep 'Model name' | head -1 | sed 's/.*: *//'"),
            "cpu_cores": int(cmd("nproc")),
            "ram_total_gb": round(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / (1024**3), 1),
        },
        "gpu": {
            "name": cmd("nvidia-smi --query-gpu=name --format=csv,noheader"),
            "driver": cmd("nvidia-smi --query-gpu=driver_version --format=csv,noheader"),
            "cuda_version": cmd("nvidia-smi --query-gpu=compute_cap --format=csv,noheader"),
        },
        "comfyui": {
            "version": sys_stats.get("system", {}).get("comfyui_version", "N/A"),
            "python": sys_stats.get("system", {}).get("python_version", "N/A"),
            "pytorch": sys_stats.get("system", {}).get("pytorch_version", "N/A"),
        },
        "models": {
            "image": {
                "name": "Z-Image-Turbo",
                "file": "z_image_turbo_bf16.safetensors",
                "precision": "bf16",
                "text_encoder": "qwen_3_4b.safetensors",
                "vae": "ae.safetensors",
                "sampler": "res_multistep",
                "default_steps": 4,
            },
            "video": {
                "name": "Wan 2.2 T2V 14B",
                "files": [
                    "wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors",
                    "wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors",
                ],
                "precision": "fp8",
                "lora": "LightX2V 4-step (v1.1)",
                "text_encoder": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                "vae": "wan_2.1_vae.safetensors",
                "sampler": "euler",
                "total_steps": 4,
            },
        },
        "prompts": {
            "image": IMAGE_PROMPTS,
            "video": VIDEO_PROMPTS,
        },
        "image_tests": [{"name": t[0], "width": t[1], "height": t[2], "steps": t[3]} for t in IMAGE_TESTS],
        "video_tests": [{"name": t[0], "width": t[1], "height": t[2], "frames": t[3]} for t in VIDEO_TESTS],
    }
    return meta


def run_test(test_name, build_fn, build_kwargs, n_reps, prompt_texts):
    """Run a single test configuration N times and return results."""
    results = []

    for rep in range(1, n_reps + 1):
        # Pick prompt (rotate through available prompts)
        prompt_text = prompt_texts[(rep - 1) % len(prompt_texts)]
        seed = 42 + rep  # Deterministic but different per rep

        workflow = build_fn(prompt_text=prompt_text, seed=seed, **build_kwargs)

        stats_before = gpu_stats()

        t0 = time.time()
        prompt_id, client_id = queue_prompt(workflow)
        success = wait_for_completion(prompt_id, client_id, timeout=1800)
        elapsed = time.time() - t0

        stats_after = gpu_stats()

        if not success:
            print(f"    Run {rep}/{n_reps}: FAILED")
            continue

        result = {
            "test": test_name,
            "run": rep,
            "prompt": prompt_text,
            "seed": seed,
            "time_s": round(elapsed, 2),
            "gpu_temp_before": stats_before["temp"],
            "gpu_temp_after": stats_after["temp"],
            "gpu_power_w": stats_after["power_w"],
            "prompt_id": prompt_id,
        }
        results.append(result)

        print(f"    Run {rep}/{n_reps}: {elapsed:.2f}s | GPU: {stats_after['temp']}C, {stats_after['power_w']}W")

    return results


def run_benchmark(n_reps=3, video_reps=2, skip_image=False, skip_video=False,
                   showcase=False, showcase_only=False):
    """Run all benchmark tests."""
    print(f"\n{'='*70}")
    print(f"  GX10 Benchmark #07: Image & Video Generation Speed")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Reps per config: {n_reps}")
    print(f"{'='*70}")

    # Check server
    print("\n[Phase 1] Checking ComfyUI server...")
    sys_stats = check_server()
    if not sys_stats:
        print("  ERROR: ComfyUI is not running at http://127.0.0.1:8188")
        print("  Start it with: sudo systemctl start comfyui")
        return None, None

    print(f"  ComfyUI v{sys_stats.get('system', {}).get('comfyui_version', '?')} is running")
    print(f"  WebSocket support: {'yes' if HAS_WS else 'no (using polling fallback)'}")

    # Create output dir for generated images
    os.makedirs("/home/gx10/ai/ComfyUI/output/bench07", exist_ok=True)

    # Collect metadata
    print("\n[Phase 2] Collecting metadata...")
    metadata = collect_metadata()
    metadata["n_reps_image"] = n_reps
    metadata["n_reps_video"] = video_reps

    meta_file = os.path.join(BENCHMARK_DIR, f"metadata_{TIMESTAMP}.json")
    with open(meta_file, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  Saved to {meta_file}")

    all_results = []

    run_standard = not showcase_only

    # ---- Image tests (Z-Image-Turbo) ----
    if not skip_image and (run_standard or showcase or showcase_only):
        print(f"\n{'='*70}")
        print("  MODEL: Z-Image-Turbo (text-to-image)")
        print(f"{'='*70}")

        # Warmup
        print("\n  Warmup (512x512, 1 image)...")
        wf = build_z_image_turbo("warmup test image", 512, 512, seed=1, steps=4)
        pid, cid = queue_prompt(wf)
        wait_for_completion(pid, cid)
        print("  Warmup complete.")

        # Standard image tests
        if run_standard:
            for test_name, width, height, steps in IMAGE_TESTS:
                print(f"\n  Test: {test_name} ({width}x{height}, {steps} steps)")
                results = run_test(
                    test_name=test_name,
                    build_fn=build_z_image_turbo,
                    build_kwargs={"width": width, "height": height, "steps": steps},
                    n_reps=n_reps,
                    prompt_texts=IMAGE_PROMPTS,
                )
                if results:
                    times = [r["time_s"] for r in results]
                    mean_t = statistics.mean(times)
                    std_t = statistics.stdev(times) if len(times) > 1 else 0
                    print(f"    => Mean: {mean_t:.2f}s (stddev: {std_t:.2f}s)")

                for r in results:
                    r["model"] = "z-image-turbo"
                    r["type"] = "image"
                    r["width"] = width
                    r["height"] = height
                    r["steps"] = steps
                    r["frames"] = 1
                    r["megapixels"] = round(width * height / 1e6, 2)
                all_results.extend(results)

        # Showcase: ultra-high resolution
        if showcase or showcase_only:
            print(f"\n  --- SHOWCASE: Ultra-High Resolution (122GB Memory Advantage) ---")
            for test_name, width, height, steps in IMAGE_SHOWCASE_TESTS:
                mp = round(width * height / 1e6, 1)
                print(f"\n  Test: {test_name} ({width}x{height}, {mp}MP)")
                results = run_test(
                    test_name=test_name,
                    build_fn=build_z_image_turbo,
                    build_kwargs={"width": width, "height": height, "steps": steps},
                    n_reps=n_reps,
                    prompt_texts=IMAGE_PROMPTS,
                )
                if results:
                    times = [r["time_s"] for r in results]
                    mean_t = statistics.mean(times)
                    std_t = statistics.stdev(times) if len(times) > 1 else 0
                    print(f"    => Mean: {mean_t:.2f}s (stddev: {std_t:.2f}s)")

                for r in results:
                    r["model"] = "z-image-turbo"
                    r["type"] = "image"
                    r["width"] = width
                    r["height"] = height
                    r["steps"] = steps
                    r["frames"] = 1
                    r["megapixels"] = round(width * height / 1e6, 2)
                all_results.extend(results)

            # Showcase: batch generation
            print(f"\n  --- SHOWCASE: Batch Generation (Multiple Images Per Pass) ---")
            for test_name, width, height, steps, batch_size in IMAGE_BATCH_TESTS:
                print(f"\n  Test: {test_name} ({width}x{height}, batch={batch_size})")
                results = run_test(
                    test_name=test_name,
                    build_fn=build_z_image_turbo_batch,
                    build_kwargs={"width": width, "height": height, "steps": steps, "batch_size": batch_size},
                    n_reps=n_reps,
                    prompt_texts=IMAGE_PROMPTS,
                )
                if results:
                    times = [r["time_s"] for r in results]
                    mean_t = statistics.mean(times)
                    std_t = statistics.stdev(times) if len(times) > 1 else 0
                    ips = batch_size / mean_t * 60
                    print(f"    => Mean: {mean_t:.2f}s for {batch_size} images ({ips:.1f} img/min)")

                for r in results:
                    r["model"] = "z-image-turbo"
                    r["type"] = "batch"
                    r["width"] = width
                    r["height"] = height
                    r["steps"] = steps
                    r["frames"] = batch_size
                    r["megapixels"] = round(width * height * batch_size / 1e6, 2)
                all_results.extend(results)

        # Free memory before video tests
        print("\n  Freeing GPU memory...")
        free_memory()
        time.sleep(5)

    # ---- Video tests (Wan 2.2 T2V) ----
    if not skip_video and (run_standard or showcase or showcase_only):
        print(f"\n{'='*70}")
        print("  MODEL: Wan 2.2 T2V 14B + LightX2V 4-step LoRA")
        print(f"{'='*70}")

        # Warmup
        print("\n  Warmup (480x480, 17 frames)...")
        wf = build_wan22_t2v("warmup test video of a ball bouncing", 480, 480, 17, seed=1)
        pid, cid = queue_prompt(wf)
        wait_for_completion(pid, cid, timeout=600)
        print("  Warmup complete.")

        # Standard video tests
        if run_standard:
            for test_name, width, height, frames in VIDEO_TESTS:
                print(f"\n  Test: {test_name} ({width}x{height}, {frames} frames)")
                results = run_test(
                    test_name=test_name,
                    build_fn=build_wan22_t2v,
                    build_kwargs={"width": width, "height": height, "length": frames},
                    n_reps=video_reps,
                    prompt_texts=VIDEO_PROMPTS,
                )
                if results:
                    times = [r["time_s"] for r in results]
                    mean_t = statistics.mean(times)
                    std_t = statistics.stdev(times) if len(times) > 1 else 0
                    fps = frames / mean_t
                    print(f"    => Mean: {mean_t:.2f}s (stddev: {std_t:.2f}s, {fps:.2f} frames/s)")

                for r in results:
                    r["model"] = "wan22-t2v-14b"
                    r["type"] = "video"
                    r["width"] = width
                    r["height"] = height
                    r["steps"] = 4
                    r["frames"] = frames
                    r["megapixels"] = round(width * height * frames / 1e6, 2)
                all_results.extend(results)

        # Showcase: push frame count and resolution
        if showcase or showcase_only:
            print(f"\n  --- SHOWCASE: Extended Video (Frame & Resolution Scaling) ---")
            for test_name, width, height, frames in VIDEO_SHOWCASE_TESTS:
                mp = round(width * height * frames / 1e6, 1)
                print(f"\n  Test: {test_name} ({width}x{height}, {frames} frames, {mp}MP total)")
                results = run_test(
                    test_name=test_name,
                    build_fn=build_wan22_t2v,
                    build_kwargs={"width": width, "height": height, "length": frames},
                    n_reps=video_reps,
                    prompt_texts=VIDEO_PROMPTS,
                )
                if results:
                    times = [r["time_s"] for r in results]
                    mean_t = statistics.mean(times)
                    std_t = statistics.stdev(times) if len(times) > 1 else 0
                    fps = frames / mean_t
                    print(f"    => Mean: {mean_t:.2f}s (stddev: {std_t:.2f}s, {fps:.2f} frames/s)")

                for r in results:
                    r["model"] = "wan22-t2v-14b"
                    r["type"] = "video"
                    r["width"] = width
                    r["height"] = height
                    r["steps"] = 4
                    r["frames"] = frames
                    r["megapixels"] = round(width * height * frames / 1e6, 2)
                all_results.extend(results)

    if not all_results:
        print("\nNo results collected!")
        return metadata, []

    # ---- Write raw CSV ----
    print(f"\n{'='*70}")
    print("  Writing results...")
    print(f"{'='*70}")

    results_file = os.path.join(BENCHMARK_DIR, f"results_{TIMESTAMP}.csv")
    fieldnames = ["test", "model", "type", "run", "width", "height", "steps", "frames",
                  "megapixels", "prompt", "seed", "time_s", "gpu_temp_before", "gpu_temp_after", "gpu_power_w"]
    with open(results_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_results)
    print(f"  Raw results: {results_file} ({len(all_results)} rows)")

    # ---- Write summary CSV ----
    summary_file = os.path.join(BENCHMARK_DIR, f"summary_{TIMESTAMP}.csv")
    summary_rows = compute_summary(all_results)
    summary_fields = ["test", "model", "type", "width", "height", "steps", "frames",
                      "megapixels", "n_runs",
                      "mean_time_s", "stddev_time_s", "min_time_s", "max_time_s",
                      "images_per_min", "frames_per_sec",
                      "mean_gpu_temp", "mean_gpu_power_w"]
    with open(summary_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"  Summary: {summary_file} ({len(summary_rows)} configs)")

    # ---- Print summary table ----
    print(f"\n{'='*100}")
    print(f"{'Test':<30} {'Type':<6} {'Res':<12} {'Mean(s)':<10} {'StdDev':<10} {'Rate':<18} {'GPU C':<7} {'Watts'}")
    print("-" * 100)
    for s in summary_rows:
        res = f"{s['width']}x{s['height']}"
        if s['type'] == 'video':
            res += f"x{s['frames']}f"
            rate = f"{s['frames_per_sec']:.2f} fps"
        else:
            rate = f"{s['images_per_min']:.1f} img/min"
        print(f"{s['test']:<30} {s['type']:<6} {res:<12} {s['mean_time_s']:<10.2f} "
              f"{s['stddev_time_s']:<10.2f} {rate:<18} {s['mean_gpu_temp']:<7.0f} {s['mean_gpu_power_w']:.1f}")

    return metadata, summary_rows


def compute_summary(all_results):
    """Compute per-config summary statistics."""
    configs = {}
    for r in all_results:
        key = r["test"]
        configs.setdefault(key, []).append(r)

    summaries = []
    for test_name, runs in configs.items():
        times = [r["time_s"] for r in runs]
        temps = [r["gpu_temp_after"] for r in runs if r["gpu_temp_after"] > 0]
        powers = [r["gpu_power_w"] for r in runs if r["gpu_power_w"] > 0]
        r0 = runs[0]
        n = len(times)

        mean_t = statistics.mean(times)
        frames = r0["frames"]

        summaries.append({
            "test": test_name,
            "model": r0["model"],
            "type": r0["type"],
            "width": r0["width"],
            "height": r0["height"],
            "steps": r0["steps"],
            "frames": frames,
            "megapixels": r0["megapixels"],
            "n_runs": n,
            "mean_time_s": round(mean_t, 2),
            "stddev_time_s": round(statistics.stdev(times), 2) if n > 1 else 0,
            "min_time_s": round(min(times), 2),
            "max_time_s": round(max(times), 2),
            "images_per_min": round(frames * 60 / mean_t, 1) if r0["type"] in ("image", "batch") else 0,
            "frames_per_sec": round(frames / mean_t, 2) if r0["type"] == "video" else 0,
            "mean_gpu_temp": round(statistics.mean(temps), 0) if temps else -1,
            "mean_gpu_power_w": round(statistics.mean(powers), 1) if powers else -1,
        })

    return summaries


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark #07: Image & Video Generation")
    parser.add_argument("--reps", type=int, default=3, help="Repetitions per image config (default: 3)")
    parser.add_argument("--video-reps", type=int, default=2, help="Repetitions per video config (default: 2)")
    parser.add_argument("--skip-video", action="store_true", help="Skip video generation tests")
    parser.add_argument("--skip-image", action="store_true", help="Skip image generation tests")
    parser.add_argument("--showcase", action="store_true", help="Run showcase tests (ultra-high res, long video, batch)")
    parser.add_argument("--showcase-only", action="store_true", help="Run ONLY showcase tests (skip standard tests)")
    args = parser.parse_args()

    metadata, summary = run_benchmark(
        n_reps=args.reps,
        video_reps=args.video_reps,
        skip_image=args.skip_image,
        skip_video=args.skip_video,
        showcase=args.showcase,
        showcase_only=args.showcase_only,
    )

    if metadata and summary:
        print(f"\n{'='*70}")
        print("  Benchmark Complete!")
        print(f"{'='*70}")
    else:
        print("\nBenchmark failed or produced no results.")
