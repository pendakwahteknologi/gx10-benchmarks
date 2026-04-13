#!/usr/bin/env python3
"""
Benchmark #08: Voice STT & TTS Performance
Tests Whisper large-v3 (STT) and MMS-TTS Malay (TTS) on the GX10.

STT test matrix:
  - Generate synthetic Malay speech at various durations (5s, 15s, 30s, 60s, 120s, 300s)
  - Transcribe each with faster-whisper large-v3 on GPU
  - Measure: load time, transcription time, real-time factor, GPU temp/power

TTS test matrix:
  - Synthesize Malay text at various lengths (short/medium/long/very long)
  - Measure: synthesis time, audio duration produced, chars/sec, GPU temp/power
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import torch

# ---------------------------------------------------------------------------
# GPU monitoring helpers
# ---------------------------------------------------------------------------

def gpu_temp():
    """Get GPU temperature in Celsius."""
    try:
        import subprocess
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            text=True,
        )
        return int(out.strip().split("\n")[0])
    except Exception:
        return -1


def gpu_power():
    """Get GPU power draw in watts."""
    try:
        import subprocess
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
            text=True,
        )
        return float(out.strip().split("\n")[0])
    except Exception:
        return -1.0


# ---------------------------------------------------------------------------
# TTS: generate synthetic audio for STT benchmarking
# ---------------------------------------------------------------------------

MALAY_SENTENCES = [
    "Selamat pagi, apa khabar hari ini.",
    "Saya ingin bertanya tentang perkhidmatan yang disediakan.",
    "Terima kasih kerana sudi membantu kami dalam projek ini.",
    "Cuaca hari ini sangat panas dan terik.",
    "Kami akan mengadakan mesyuarat pada pukul sepuluh pagi.",
    "Pendidikan adalah kunci kejayaan masa depan.",
    "Makanan di restoran itu sangat sedap dan berpatutan.",
    "Sila pastikan semua dokumen telah lengkap sebelum menghantar.",
    "Teknologi kecerdasan buatan semakin berkembang pesat.",
    "Malaysia adalah sebuah negara yang kaya dengan budaya.",
    "Kami berharap dapat bekerjasama dengan pihak tuan pada masa hadapan.",
    "Program latihan ini bertujuan meningkatkan kemahiran pekerja.",
    "Perpustakaan negara mempunyai koleksi buku yang sangat banyak.",
    "Industri pelancongan memainkan peranan penting dalam ekonomi negara.",
    "Pelajar universiti perlu belajar dengan tekun untuk berjaya.",
    "Kerajaan telah melancarkan pelbagai inisiatif untuk membantu rakyat.",
    "Projek pembangunan infrastruktur sedang berjalan dengan lancar.",
    "Sistem pengangkutan awam perlu ditambah baik untuk keselesaan pengguna.",
    "Kajian saintifik menunjukkan keputusan yang sangat menggalakkan.",
    "Festival kebudayaan tahunan akan diadakan pada bulan hadapan.",
]


def generate_test_audio_tts(tts_model, tts_tokenizer, target_duration_s, sample_rate=16000):
    """Generate test audio by synthesizing repeated Malay sentences until target duration."""
    device = next(tts_model.parameters()).device
    chunks = []
    total_samples = 0
    target_samples = target_duration_s * sample_rate
    idx = 0

    while total_samples < target_samples:
        text = MALAY_SENTENCES[idx % len(MALAY_SENTENCES)]
        inputs = tts_tokenizer(text, return_tensors="pt").to(device)
        with torch.no_grad():
            output = tts_model(**inputs).waveform
        waveform = output.squeeze().cpu().numpy()
        chunks.append(waveform)
        total_samples += len(waveform)
        # Add a small silence gap between sentences
        gap = np.zeros(int(0.3 * sample_rate), dtype=np.float32)
        chunks.append(gap)
        total_samples += len(gap)
        idx += 1

    audio = np.concatenate(chunks)
    # Trim to target duration
    audio = audio[: int(target_samples)]
    return audio


def save_wav(audio, path, sample_rate=16000):
    """Save numpy audio array as 16-bit PCM WAV."""
    import struct

    pcm = (audio * 32767).astype(np.int16)
    n_samples = len(pcm)
    data_size = n_samples * 2
    file_size = 36 + data_size

    with open(path, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", file_size))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))  # chunk size
        f.write(struct.pack("<H", 1))  # PCM
        f.write(struct.pack("<H", 1))  # mono
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", sample_rate * 2))  # byte rate
        f.write(struct.pack("<H", 2))  # block align
        f.write(struct.pack("<H", 16))  # bits per sample
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(pcm.tobytes())


# ---------------------------------------------------------------------------
# TTS benchmark texts
# ---------------------------------------------------------------------------

TTS_TEXTS = {
    "short": "Selamat pagi, apa khabar.",
    "medium": (
        "Teknologi kecerdasan buatan telah mengubah cara kita bekerja dan berkomunikasi. "
        "Sistem ini mampu memproses data dengan pantas dan memberikan jawapan yang tepat. "
        "Malaysia sedang giat membangunkan ekosistem teknologi untuk masa hadapan."
    ),
    "long": (
        "Pendidikan merupakan asas pembangunan negara yang mampan. Dalam era digital ini, "
        "pelajar perlu dilengkapkan dengan kemahiran teknologi maklumat yang kukuh. Kerajaan "
        "telah melancarkan pelbagai inisiatif termasuk program latihan kemahiran digital, "
        "pembangunan pusat data, dan kerjasama dengan syarikat teknologi antarabangsa. "
        "Matlamat utama adalah untuk memastikan rakyat Malaysia bersedia menghadapi cabaran "
        "Revolusi Perindustrian Keempat. Selain itu, penekanan juga diberikan kepada "
        "pembangunan infrastruktur jalur lebar berkelajuan tinggi di seluruh negara."
    ),
    "very_long": (
        "Industri kecerdasan buatan di Malaysia sedang mengalami pertumbuhan yang pesat. "
        "Pelbagai syarikat tempatan dan antarabangsa telah mula melabur dalam teknologi ini "
        "untuk meningkatkan kecekapan operasi dan memberikan perkhidmatan yang lebih baik "
        "kepada pelanggan. Dalam sektor kesihatan, sistem AI digunakan untuk mendiagnosis "
        "penyakit dengan lebih tepat dan cepat. Dalam sektor pendidikan, platform pembelajaran "
        "pintar membantu pelajar belajar mengikut kadar masing-masing. Sektor pertanian juga "
        "tidak ketinggalan dengan penggunaan dron dan sensor pintar untuk memantau tanaman. "
        "Kerajaan telah memperuntukkan bajet yang besar untuk penyelidikan dan pembangunan "
        "dalam bidang ini. Universiti tempatan juga telah menawarkan program pengajian khusus "
        "dalam bidang sains data dan kecerdasan buatan. Kerjasama antara industri dan akademia "
        "amat penting untuk memastikan graduan yang dihasilkan memenuhi keperluan pasaran. "
        "Cabaran utama yang dihadapi termasuk kekurangan tenaga mahir, kos infrastruktur yang "
        "tinggi, dan keperluan untuk membangunkan rangka kerja etika AI yang komprehensif. "
        "Namun begitu, potensi teknologi ini untuk mentransformasi ekonomi negara adalah sangat "
        "besar dan tidak boleh diabaikan."
    ),
}


# ---------------------------------------------------------------------------
# Main benchmark
# ---------------------------------------------------------------------------

def run_benchmark(n_reps=3, output_dir="."):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(output_dir)
    samples_dir = output_dir / "samples"
    samples_dir.mkdir(exist_ok=True)

    results_file = output_dir / f"results_{timestamp}.csv"
    summary_file = output_dir / f"summary_{timestamp}.csv"
    metadata_file = output_dir / f"metadata_{timestamp}.json"
    log_file = output_dir / f"log_{timestamp}.txt"

    import subprocess

    def log(msg):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        print(line)
        with open(log_file, "a") as f:
            f.write(line + "\n")

    log("=" * 60)
    log("  GX10 Benchmark #08: Voice STT & TTS")
    log(f"  Reps per config: {n_reps}")
    log("=" * 60)

    # ---- Collect system info ----
    import platform

    hostname = platform.node()
    os_info = ""
    try:
        os_info = subprocess.check_output(["lsb_release", "-d", "-s"], text=True).strip()
    except Exception:
        os_info = platform.platform()

    gpu_name = ""
    driver = ""
    cuda_ver = ""
    try:
        gpu_name = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], text=True
        ).strip()
        driver = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"], text=True
        ).strip()
    except Exception:
        pass
    cuda_ver = torch.version.cuda or ""

    # ---- Load TTS model first (needed for generating STT test audio) ----
    log("")
    log("[Phase 0] Loading TTS model (facebook/mms-tts-zlm)...")
    from transformers import VitsModel, AutoTokenizer

    tts_model_name = "facebook/mms-tts-zlm"
    hf_cache = os.environ.get("HF_HOME", None)

    t0 = time.perf_counter()
    tts_tokenizer = AutoTokenizer.from_pretrained(tts_model_name, cache_dir=hf_cache)
    tts_model = VitsModel.from_pretrained(tts_model_name, cache_dir=hf_cache).to("cuda")
    tts_load_time = time.perf_counter() - t0
    log(f"  TTS model loaded in {tts_load_time:.2f}s")

    # ---- Load STT model ----
    log("[Phase 0] Loading Whisper large-v3...")
    from faster_whisper import WhisperModel

    # CTranslate2 on aarch64 doesn't ship CUDA wheels -- use CPU with int8
    stt_device = "cuda"
    stt_compute = "float16"
    try:
        import ctranslate2
        ctranslate2.get_supported_compute_types("cuda")
    except ValueError:
        log("  Note: CTranslate2 has no CUDA support, using CPU (int8)")
        stt_device = "cpu"
        stt_compute = "int8"

    t0 = time.perf_counter()
    whisper_model = WhisperModel("large-v3", device=stt_device, compute_type=stt_compute)
    stt_load_time = time.perf_counter() - t0
    log(f"  Whisper loaded in {stt_load_time:.2f}s")

    results = []

    # ==================================================================
    # Phase 1: TTS Benchmark
    # ==================================================================
    log("")
    log("=" * 60)
    log("[Phase 1] TTS Benchmark — MMS-TTS Malay")
    log("=" * 60)

    for label, text in TTS_TEXTS.items():
        n_chars = len(text)
        log(f"\n  Test: tts_{label} ({n_chars} chars)")

        for run in range(1, n_reps + 1):
            temp_before = gpu_temp()
            power_before = gpu_power()

            device = next(tts_model.parameters()).device
            inputs = tts_tokenizer(text, return_tensors="pt").to(device)

            torch.cuda.synchronize()
            t0 = time.perf_counter()
            with torch.no_grad():
                output = tts_model(**inputs).waveform
            torch.cuda.synchronize()
            elapsed = time.perf_counter() - t0

            waveform = output.squeeze().cpu().numpy()
            audio_duration = len(waveform) / 16000.0

            temp_after = gpu_temp()
            power_after = gpu_power()
            avg_power = (power_before + power_after) / 2

            chars_per_sec = n_chars / elapsed if elapsed > 0 else 0
            rtf = elapsed / audio_duration if audio_duration > 0 else 0

            log(f"    Run {run}: {elapsed:.3f}s → {audio_duration:.2f}s audio "
                f"({chars_per_sec:.0f} chars/s, RTF={rtf:.3f})")

            results.append({
                "test": f"tts_{label}",
                "model": "mms-tts-zlm",
                "type": "tts",
                "run": run,
                "input_chars": n_chars,
                "audio_duration_s": round(audio_duration, 3),
                "time_s": round(elapsed, 4),
                "chars_per_sec": round(chars_per_sec, 1),
                "real_time_factor": round(rtf, 4),
                "gpu_temp_before": temp_before,
                "gpu_temp_after": temp_after,
                "gpu_power_w": round(avg_power, 1),
            })

            # Save first run sample
            if run == 1:
                sample_path = samples_dir / f"tts_{label}.wav"
                save_wav(waveform, sample_path)

    # ==================================================================
    # Phase 2: STT Benchmark
    # ==================================================================
    log("")
    log("=" * 60)
    log("[Phase 2] STT Benchmark — Whisper large-v3")
    log("=" * 60)

    stt_durations = [5, 15, 30, 60, 120, 300]

    for target_dur in stt_durations:
        test_name = f"stt_{target_dur}s"
        log(f"\n  Generating {target_dur}s test audio...")

        audio = generate_test_audio_tts(tts_model, tts_tokenizer, target_dur)
        actual_dur = len(audio) / 22050.0
        wav_path = samples_dir / f"stt_input_{target_dur}s.wav"
        save_wav(audio, wav_path)
        log(f"    Generated {actual_dur:.1f}s audio → {wav_path.name}")

        for run in range(1, n_reps + 1):
            temp_before = gpu_temp()
            power_before = gpu_power()

            if stt_device == "cuda":
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            segments, info = whisper_model.transcribe(
                str(wav_path), language="ms", beam_size=5
            )
            # Consume the generator to force full transcription
            text_out = " ".join(seg.text.strip() for seg in segments)
            if stt_device == "cuda":
                torch.cuda.synchronize()
            elapsed = time.perf_counter() - t0

            temp_after = gpu_temp()
            power_after = gpu_power()
            avg_power = (power_before + power_after) / 2

            rtf = elapsed / actual_dur if actual_dur > 0 else 0
            speed_x = actual_dur / elapsed if elapsed > 0 else 0

            log(f"    Run {run}: {elapsed:.2f}s for {actual_dur:.1f}s audio "
                f"(RTF={rtf:.3f}, {speed_x:.1f}x realtime)")

            results.append({
                "test": test_name,
                "model": "whisper-large-v3",
                "type": "stt",
                "run": run,
                "input_duration_s": round(actual_dur, 2),
                "time_s": round(elapsed, 4),
                "real_time_factor": round(rtf, 4),
                "speed_x": round(speed_x, 2),
                "output_chars": len(text_out),
                "gpu_temp_before": temp_before,
                "gpu_temp_after": temp_after,
                "gpu_power_w": round(avg_power, 1),
            })

    # ==================================================================
    # Write results
    # ==================================================================
    log("")
    log("=" * 60)
    log("[Phase 3] Writing results...")
    log("=" * 60)

    # Raw results CSV
    fieldnames = [
        "test", "model", "type", "run",
        "input_chars", "input_duration_s", "audio_duration_s",
        "time_s", "chars_per_sec", "real_time_factor", "speed_x",
        "output_chars",
        "gpu_temp_before", "gpu_temp_after", "gpu_power_w",
    ]
    with open(results_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    log(f"  Results: {results_file}")

    # Summary CSV (aggregated)
    from collections import defaultdict

    groups = defaultdict(list)
    for r in results:
        groups[r["test"]].append(r)

    summary_rows = []
    for test_name, runs in groups.items():
        times = [r["time_s"] for r in runs]
        row = {
            "test": test_name,
            "model": runs[0]["model"],
            "type": runs[0]["type"],
            "n_runs": len(runs),
            "mean_time_s": round(np.mean(times), 4),
            "stddev_time_s": round(np.std(times), 4),
            "min_time_s": round(min(times), 4),
            "max_time_s": round(max(times), 4),
        }

        if runs[0]["type"] == "tts":
            row["input_chars"] = runs[0]["input_chars"]
            row["mean_audio_duration_s"] = round(
                np.mean([r["audio_duration_s"] for r in runs]), 3
            )
            row["mean_chars_per_sec"] = round(
                np.mean([r["chars_per_sec"] for r in runs]), 1
            )
            row["mean_rtf"] = round(np.mean([r["real_time_factor"] for r in runs]), 4)
        else:
            row["input_duration_s"] = runs[0]["input_duration_s"]
            row["mean_rtf"] = round(np.mean([r["real_time_factor"] for r in runs]), 4)
            row["mean_speed_x"] = round(
                np.mean([r["speed_x"] for r in runs]), 2
            )

        row["mean_gpu_power_w"] = round(
            np.mean([r["gpu_power_w"] for r in runs]), 1
        )
        summary_rows.append(row)

    summary_fields = [
        "test", "model", "type", "n_runs",
        "input_chars", "input_duration_s",
        "mean_time_s", "stddev_time_s", "min_time_s", "max_time_s",
        "mean_audio_duration_s", "mean_chars_per_sec",
        "mean_rtf", "mean_speed_x", "mean_gpu_power_w",
    ]
    with open(summary_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summary_rows)
    log(f"  Summary: {summary_file}")

    # Metadata JSON
    metadata = {
        "benchmark": "08-voice-stt-tts",
        "title": "Voice STT & TTS Performance",
        "timestamp": timestamp,
        "system": {
            "hostname": hostname,
            "os": os_info,
            "kernel": platform.release(),
            "arch": platform.machine(),
            "cpu_cores": os.cpu_count(),
            "ram_total_gb": round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1024**3), 1),
        },
        "gpu": {
            "name": gpu_name,
            "driver": driver,
            "cuda_version": cuda_ver,
        },
        "models": {
            "stt": {
                "name": "Whisper large-v3",
                "engine": "faster-whisper (CTranslate2)",
                "device": stt_device,
                "compute_type": stt_compute,
                "language": "ms",
                "beam_size": 5,
                "load_time_s": round(stt_load_time, 2),
            },
            "tts": {
                "name": "MMS-TTS Malay (facebook/mms-tts-zlm)",
                "engine": "HuggingFace Transformers (VitsModel)",
                "sample_rate": 16000,
                "load_time_s": round(tts_load_time, 2),
            },
        },
        "stt_tests": [{"name": f"stt_{d}s", "duration_s": d} for d in stt_durations],
        "tts_tests": [
            {"name": f"tts_{k}", "chars": len(v)} for k, v in TTS_TEXTS.items()
        ],
        "n_reps": n_reps,
    }
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
    log(f"  Metadata: {metadata_file}")

    log("")
    log("Benchmark complete!")
    return str(results_file), str(summary_file), str(metadata_file), timestamp


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark #08: Voice STT & TTS")
    parser.add_argument("--reps", type=int, default=3, help="Repetitions per config")
    parser.add_argument("--output-dir", type=str, default=".", help="Output directory")
    args = parser.parse_args()

    run_benchmark(n_reps=args.reps, output_dir=args.output_dir)
