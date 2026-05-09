# Benchmark #08: Voice STT & TTS Performance

Measures speech-to-text and text-to-speech performance on the GX10.

## Models

| Task | Model | Engine | Precision |
|------|-------|--------|-----------|
| STT | Whisper large-v3 | faster-whisper (CTranslate2) | float16 |
| TTS | MMS-TTS Malay (facebook/mms-tts-zlm) | HuggingFace VITS | GPU |

## Test Matrix

### TTS (Text-to-Speech)
- 4 text lengths: short (25 chars), medium (~200 chars), long (~500 chars), very long (~1000 chars)
- 3 repetitions each
- Metrics: synthesis time, audio duration, chars/sec, real-time factor

### STT (Speech-to-Text)
- 6 audio durations: 5s, 15s, 30s, 60s, 120s, 300s
- Test audio generated via TTS (Malay sentences)
- 3 repetitions each
- Metrics: transcription time, speed (x realtime), real-time factor

## Usage

```bash
./run.sh
```

## Output

- `results_*.csv` — raw per-run data
- `summary_*.csv` — aggregated statistics
- `metadata_*.json` — system and model info
- `log_*.txt` — full console log
- `report_*.html` — visual HTML report with charts
- `samples/` — generated audio files
