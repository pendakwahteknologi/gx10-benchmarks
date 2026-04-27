# Benchmark #07: Image & Video Generation Speed

Tests how fast the GX10 can generate images and videos using ComfyUI,
measuring end-to-end generation time including model loading, encoding,
sampling, and decoding.

## Hardware

- **GPU:** NVIDIA GB10 (Blackwell, SM 12.1)
- **CPU:** 20 ARM cores (Cortex-X925 + A725)
- **Memory:** 122GB unified (shared CPU/GPU)
- **CUDA:** 13.0, Driver 580.142
- **OS:** Ubuntu 24.04 aarch64

## Models Tested

### 1. Z-Image-Turbo (Text-to-Image)

| Component | File | Size |
|-----------|------|------|
| UNet | z_image_turbo_bf16.safetensors | 12G |
| Text Encoder | qwen_3_4b.safetensors | 7.5G |
| VAE | ae.safetensors | 320M |

- Precision: bf16
- Sampler: res_multistep
- Default steps: 4 (turbo mode)
- CFG: 1.0

### 2. Wan 2.2 T2V 14B (Text-to-Video)

| Component | File | Size |
|-----------|------|------|
| High-noise model | wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors | 14G |
| Low-noise model | wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors | 14G |
| LoRA (high) | wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors | 1.2G |
| LoRA (low) | wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors | 1.2G |
| Text Encoder | umt5_xxl_fp8_e4m3fn_scaled.safetensors | 6.3G |
| VAE | wan_2.1_vae.safetensors | 243M |

- Precision: fp8
- Sampler: euler (dual-stage: high-noise 0-2 steps, low-noise 2-4 steps)
- Total steps: 4 (with LightX2V LoRA acceleration)
- CFG: 1.0

## Test Matrix

### Image Tests (Z-Image-Turbo)

| Test | Resolution | Steps | Reps |
|------|-----------|-------|------|
| z_turbo_512x512_4steps | 512x512 | 4 | 3 |
| z_turbo_768x768_4steps | 768x768 | 4 | 3 |
| z_turbo_1024x1024_4steps | 1024x1024 | 4 | 3 |
| z_turbo_1280x1280_4steps | 1280x1280 | 4 | 3 |
| z_turbo_1024x1024_8steps | 1024x1024 | 8 | 3 |

### Video Tests (Wan 2.2 T2V)

| Test | Resolution | Frames | Reps |
|------|-----------|--------|------|
| wan22_640x640_33f | 640x640 | 33 | 3 |
| wan22_640x640_49f | 640x640 | 49 | 3 |
| wan22_640x640_81f | 640x640 | 81 | 3 |
| wan22_480x480_33f | 480x480 | 33 | 3 |

**Total: 27 individual runs** (9 configs x 3 reps)

## Methodology

- **API-driven:** All tests submitted via ComfyUI REST API (POST /prompt)
- **WebSocket tracking:** Completion detected via WebSocket for accurate timing
- **Warmup:** 1 warmup generation per model before measurement
- **Memory management:** GPU memory freed between model switches
- **Timing:** End-to-end wall-clock (queue to completion)
- **GPU metrics:** Temperature and power draw per run
- **Statistics:** Mean, stddev, min, max per config (3 reps)

## Metrics

| Metric | Description |
|--------|-------------|
| time_s | Total generation time (seconds) |
| images_per_min | Images generated per minute (image tests) |
| frames_per_sec | Effective FPS (video tests) |
| gpu_temp | GPU temperature after each run |
| gpu_power_w | GPU power draw (watts) |

## Output Files

| File | Description |
|------|-------------|
| `results_*.csv` | Raw per-run measurements |
| `summary_*.csv` | Aggregated statistics per config |
| `metadata_*.json` | System info, model details, test parameters |
| `log_*.txt` | Full console output |
| `report_*.html` | Interactive HTML report with charts |

## How to Run

```bash
cd ~/ai/benchmarks/07-efficiency-image-generation
bash run.sh
```

The script automatically:
1. Starts ComfyUI if not running
2. Stops non-essential services
3. Runs all tests (image + video)
4. Generates the HTML report
5. Restarts services

**Estimated time:** ~30-60 minutes (video tests dominate)

To skip video tests (image only): edit benchmark.py --skip-video
To skip image tests (video only): edit benchmark.py --skip-image

## Created by

Pendakwah Teknologi
