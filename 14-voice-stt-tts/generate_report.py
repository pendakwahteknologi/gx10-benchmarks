#!/usr/bin/env python3
"""Generate HTML report for Benchmark #08: Voice STT & TTS."""

import csv
import json
import sys
from pathlib import Path


def read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def generate_report(results_csv, summary_csv, metadata_json, output_html):
    results = read_csv(results_csv)
    summary = read_csv(summary_csv)
    metadata = json.loads(Path(metadata_json).read_text())

    tts_summary = [r for r in summary if r["type"] == "tts"]
    stt_summary = [r for r in summary if r["type"] == "stt"]
    tts_results = [r for r in results if r["type"] == "tts"]
    stt_results = [r for r in results if r["type"] == "stt"]

    sys_info = metadata["system"]
    gpu_info = metadata["gpu"]
    stt_model = metadata["models"]["stt"]
    tts_model = metadata["models"]["tts"]

    # Build TTS summary table rows
    tts_rows = ""
    for r in tts_summary:
        tts_rows += f"""<tr>
            <td>{r['test'].replace('tts_', '').replace('_', ' ').title()}</td>
            <td>{r.get('input_chars', '-')}</td>
            <td>{r.get('mean_audio_duration_s', '-')}s</td>
            <td>{r['mean_time_s']}s</td>
            <td>&plusmn;{r['stddev_time_s']}s</td>
            <td>{r.get('mean_chars_per_sec', '-')}</td>
            <td>{r.get('mean_rtf', '-')}</td>
            <td>{r.get('mean_gpu_power_w', '-')}W</td>
        </tr>"""

    # Build STT summary table rows
    stt_rows = ""
    for r in stt_summary:
        stt_rows += f"""<tr>
            <td>{r.get('input_duration_s', '-')}s</td>
            <td>{r['mean_time_s']}s</td>
            <td>&plusmn;{r['stddev_time_s']}s</td>
            <td>{r.get('mean_speed_x', '-')}x</td>
            <td>{r.get('mean_rtf', '-')}</td>
            <td>{r.get('mean_gpu_power_w', '-')}W</td>
        </tr>"""

    # Build TTS detail rows
    tts_detail_rows = ""
    for r in tts_results:
        tts_detail_rows += f"""<tr>
            <td>{r['test'].replace('tts_', '').replace('_', ' ').title()}</td>
            <td>{r['run']}</td>
            <td>{r.get('input_chars', '-')}</td>
            <td>{r.get('audio_duration_s', '-')}s</td>
            <td>{r['time_s']}s</td>
            <td>{r.get('chars_per_sec', '-')}</td>
            <td>{r.get('real_time_factor', '-')}</td>
            <td>{r['gpu_temp_before']}/{r['gpu_temp_after']}C</td>
            <td>{r.get('gpu_power_w', '-')}W</td>
        </tr>"""

    # Build STT detail rows
    stt_detail_rows = ""
    for r in stt_results:
        stt_detail_rows += f"""<tr>
            <td>{r.get('input_duration_s', '-')}s</td>
            <td>{r['run']}</td>
            <td>{r['time_s']}s</td>
            <td>{r.get('speed_x', '-')}x</td>
            <td>{r.get('real_time_factor', '-')}</td>
            <td>{r.get('output_chars', '-')}</td>
            <td>{r['gpu_temp_before']}/{r['gpu_temp_after']}C</td>
            <td>{r.get('gpu_power_w', '-')}W</td>
        </tr>"""

    # Chart data
    stt_chart_labels = json.dumps([r.get("input_duration_s", "?") + "s" for r in stt_summary])
    stt_chart_speed = json.dumps([float(r.get("mean_speed_x", 0)) for r in stt_summary])
    stt_chart_time = json.dumps([float(r["mean_time_s"]) for r in stt_summary])

    tts_chart_labels = json.dumps(
        [r["test"].replace("tts_", "").replace("_", " ").title() for r in tts_summary]
    )
    tts_chart_cps = json.dumps([float(r.get("mean_chars_per_sec", 0)) for r in tts_summary])
    tts_chart_time = json.dumps([float(r["mean_time_s"]) for r in tts_summary])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GX10 Benchmark #08: Voice STT & TTS</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root {{
    --bg: #0f172a; --surface: #1e293b; --border: #334155;
    --text: #e2e8f0; --text-dim: #94a3b8; --accent: #38bdf8;
    --accent2: #a78bfa; --green: #4ade80; --orange: #fb923c;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Inter', -apple-system, sans-serif;
    background: var(--bg); color: var(--text);
    line-height: 1.6; padding: 2rem;
  }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  h1 {{ font-size: 1.8rem; margin-bottom: 0.5rem; }}
  h2 {{
    font-size: 1.3rem; margin: 2rem 0 1rem;
    padding-bottom: 0.5rem; border-bottom: 1px solid var(--border);
  }}
  h3 {{ font-size: 1.1rem; margin: 1.5rem 0 0.8rem; color: var(--accent); }}
  .subtitle {{ color: var(--text-dim); margin-bottom: 2rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; margin: 1rem 0; }}
  .card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 1.2rem;
  }}
  .card-label {{ color: var(--text-dim); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .card-value {{ font-size: 1.5rem; font-weight: 700; margin-top: 0.3rem; }}
  .card-value.accent {{ color: var(--accent); }}
  .card-value.green {{ color: var(--green); }}
  .card-value.orange {{ color: var(--orange); }}
  .card-value.purple {{ color: var(--accent2); }}
  table {{
    width: 100%; border-collapse: collapse;
    background: var(--surface); border-radius: 8px; overflow: hidden;
    margin: 1rem 0;
  }}
  th, td {{ padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ background: rgba(56,189,248,0.1); color: var(--accent); font-weight: 600; font-size: 0.85rem; text-transform: uppercase; }}
  td {{ font-size: 0.9rem; }}
  tr:last-child td {{ border-bottom: none; }}
  .chart-container {{ background: var(--surface); border-radius: 8px; padding: 1.5rem; margin: 1rem 0; }}
  .info-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.5rem; }}
  .info-item {{ font-size: 0.9rem; }}
  .info-item span {{ color: var(--text-dim); }}
  details {{ margin: 1rem 0; }}
  summary {{
    cursor: pointer; font-weight: 600; color: var(--accent);
    padding: 0.5rem; background: var(--surface); border-radius: 4px;
  }}
  .footer {{ text-align: center; color: var(--text-dim); margin-top: 3rem; font-size: 0.85rem; }}
</style>
</head>
<body>
<div class="container">
  <h1>GX10 Benchmark #08: Voice STT & TTS</h1>
  <p class="subtitle">
    {sys_info.get('hostname', '')} &mdash; {gpu_info.get('name', '')} &mdash;
    {metadata.get('timestamp', '')}
  </p>

  <h2>System</h2>
  <div class="info-grid">
    <div class="info-item"><span>OS:</span> {sys_info.get('os', '')}</div>
    <div class="info-item"><span>Kernel:</span> {sys_info.get('kernel', '')}</div>
    <div class="info-item"><span>Arch:</span> {sys_info.get('arch', '')}</div>
    <div class="info-item"><span>CPU:</span> {sys_info.get('cpu_cores', '')} cores</div>
    <div class="info-item"><span>RAM:</span> {sys_info.get('ram_total_gb', '')} GB</div>
    <div class="info-item"><span>GPU:</span> {gpu_info.get('name', '')}</div>
    <div class="info-item"><span>Driver:</span> {gpu_info.get('driver', '')}</div>
    <div class="info-item"><span>CUDA:</span> {gpu_info.get('cuda_version', '')}</div>
  </div>

  <h2>Models</h2>
  <div class="grid">
    <div class="card">
      <div class="card-label">STT Model</div>
      <div class="card-value accent">{stt_model.get('name', '')}</div>
      <p style="margin-top:0.5rem;font-size:0.85rem;color:var(--text-dim)">
        Engine: {stt_model.get('engine', '')}<br>
        Compute: {stt_model.get('compute_type', '')}<br>
        Language: {stt_model.get('language', '')} | Beam: {stt_model.get('beam_size', '')}<br>
        Load time: {stt_model.get('load_time_s', '')}s
      </p>
    </div>
    <div class="card">
      <div class="card-label">TTS Model</div>
      <div class="card-value purple">{tts_model.get('name', '')}</div>
      <p style="margin-top:0.5rem;font-size:0.85rem;color:var(--text-dim)">
        Engine: {tts_model.get('engine', '')}<br>
        Sample rate: {tts_model.get('sample_rate', '')} Hz<br>
        Load time: {tts_model.get('load_time_s', '')}s
      </p>
    </div>
  </div>

  <!-- Key Metrics -->
  <h2>Key Metrics</h2>
  <div class="grid" id="key-metrics"></div>

  <!-- STT Results -->
  <h2>STT: Whisper large-v3 Transcription</h2>

  <div class="chart-container">
    <canvas id="sttSpeedChart" height="100"></canvas>
  </div>

  <h3>Summary</h3>
  <table>
    <tr>
      <th>Audio Duration</th><th>Mean Time</th><th>Std Dev</th>
      <th>Speed</th><th>RTF</th><th>Power</th>
    </tr>
    {stt_rows}
  </table>

  <details>
    <summary>All STT runs</summary>
    <table>
      <tr>
        <th>Audio</th><th>Run</th><th>Time</th><th>Speed</th>
        <th>RTF</th><th>Chars</th><th>Temp</th><th>Power</th>
      </tr>
      {stt_detail_rows}
    </table>
  </details>

  <!-- TTS Results -->
  <h2>TTS: MMS-TTS Malay Synthesis</h2>

  <div class="chart-container">
    <canvas id="ttsChart" height="100"></canvas>
  </div>

  <h3>Summary</h3>
  <table>
    <tr>
      <th>Text</th><th>Chars</th><th>Audio Out</th>
      <th>Mean Time</th><th>Std Dev</th><th>Chars/s</th><th>RTF</th><th>Power</th>
    </tr>
    {tts_rows}
  </table>

  <details>
    <summary>All TTS runs</summary>
    <table>
      <tr>
        <th>Text</th><th>Run</th><th>Chars</th><th>Audio</th>
        <th>Time</th><th>Chars/s</th><th>RTF</th><th>Temp</th><th>Power</th>
      </tr>
      {tts_detail_rows}
    </table>
  </details>

  <div class="footer">
    GX10 Benchmark Suite &mdash; Pendakwah Teknologi &mdash; Generated {metadata.get('timestamp', '')}
  </div>
</div>

<script>
// STT Speed chart
const sttCtx = document.getElementById('sttSpeedChart').getContext('2d');
new Chart(sttCtx, {{
  type: 'bar',
  data: {{
    labels: {stt_chart_labels},
    datasets: [
      {{
        label: 'Speed (x realtime)',
        data: {stt_chart_speed},
        backgroundColor: 'rgba(56,189,248,0.7)',
        borderColor: '#38bdf8',
        borderWidth: 1,
        yAxisID: 'y',
      }},
      {{
        label: 'Time (s)',
        data: {stt_chart_time},
        type: 'line',
        borderColor: '#fb923c',
        backgroundColor: 'rgba(251,146,60,0.2)',
        yAxisID: 'y1',
        tension: 0.3,
        pointRadius: 5,
      }}
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{
      title: {{ display: true, text: 'STT: Transcription Speed vs Audio Duration', color: '#e2e8f0' }},
      legend: {{ labels: {{ color: '#94a3b8' }} }}
    }},
    scales: {{
      x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#334155' }} }},
      y: {{
        position: 'left',
        title: {{ display: true, text: 'Speed (x realtime)', color: '#38bdf8' }},
        ticks: {{ color: '#38bdf8' }}, grid: {{ color: '#334155' }}
      }},
      y1: {{
        position: 'right',
        title: {{ display: true, text: 'Time (seconds)', color: '#fb923c' }},
        ticks: {{ color: '#fb923c' }}, grid: {{ drawOnChartArea: false }}
      }}
    }}
  }}
}});

// TTS chart
const ttsCtx = document.getElementById('ttsChart').getContext('2d');
new Chart(ttsCtx, {{
  type: 'bar',
  data: {{
    labels: {tts_chart_labels},
    datasets: [
      {{
        label: 'Chars/sec',
        data: {tts_chart_cps},
        backgroundColor: 'rgba(167,139,250,0.7)',
        borderColor: '#a78bfa',
        borderWidth: 1,
        yAxisID: 'y',
      }},
      {{
        label: 'Time (s)',
        data: {tts_chart_time},
        type: 'line',
        borderColor: '#4ade80',
        backgroundColor: 'rgba(74,222,128,0.2)',
        yAxisID: 'y1',
        tension: 0.3,
        pointRadius: 5,
      }}
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{
      title: {{ display: true, text: 'TTS: Synthesis Speed vs Text Length', color: '#e2e8f0' }},
      legend: {{ labels: {{ color: '#94a3b8' }} }}
    }},
    scales: {{
      x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#334155' }} }},
      y: {{
        position: 'left',
        title: {{ display: true, text: 'Chars/sec', color: '#a78bfa' }},
        ticks: {{ color: '#a78bfa' }}, grid: {{ color: '#334155' }}
      }},
      y1: {{
        position: 'right',
        title: {{ display: true, text: 'Time (seconds)', color: '#4ade80' }},
        ticks: {{ color: '#4ade80' }}, grid: {{ drawOnChartArea: false }}
      }}
    }}
  }}
}});

// Key metrics cards
const sttData = {json.dumps([dict(r) for r in stt_summary])};
const ttsData = {json.dumps([dict(r) for r in tts_summary])};

const metricsDiv = document.getElementById('key-metrics');
const bestSTT = sttData.reduce((a, b) => parseFloat(a.mean_speed_x||0) > parseFloat(b.mean_speed_x||0) ? a : b, {{}});
const bestTTS = ttsData.reduce((a, b) => parseFloat(a.mean_chars_per_sec||0) > parseFloat(b.mean_chars_per_sec||0) ? a : b, {{}});

const metrics = [
  {{ label: 'Best STT Speed', value: (bestSTT.mean_speed_x || '?') + 'x', cls: 'accent', sub: 'realtime (' + (bestSTT.input_duration_s||'?') + 's audio)' }},
  {{ label: 'Best TTS Speed', value: (bestTTS.mean_chars_per_sec || '?') + ' c/s', cls: 'purple', sub: bestTTS.test ? bestTTS.test.replace('tts_','').replace('_',' ') : '' }},
  {{ label: 'STT Load Time', value: '{stt_model.get("load_time_s", "?")}s', cls: 'green', sub: 'Whisper large-v3' }},
  {{ label: 'TTS Load Time', value: '{tts_model.get("load_time_s", "?")}s', cls: 'orange', sub: 'MMS-TTS Malay' }},
];

metrics.forEach(m => {{
  metricsDiv.innerHTML += `
    <div class="card">
      <div class="card-label">${{m.label}}</div>
      <div class="card-value ${{m.cls}}">${{m.value}}</div>
      <div style="font-size:0.8rem;color:var(--text-dim);margin-top:0.3rem">${{m.sub}}</div>
    </div>`;
}});
</script>
</body>
</html>"""

    Path(output_html).write_text(html)
    print(f"  Report generated: {output_html}")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(f"Usage: {sys.argv[0]} <results.csv> <summary.csv> <metadata.json> <output.html>")
        sys.exit(1)
    generate_report(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
