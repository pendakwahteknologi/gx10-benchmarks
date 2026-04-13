#!/usr/bin/env python3
"""
Generate interactive HTML report for Benchmark #06: Embedding Throughput.
Usage: python3 generate_report.py results.csv summary.csv metadata.json report.html
"""

import sys
import csv
import json
import html as html_mod


def load_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def load_json(path):
    with open(path) as f:
        return json.load(f)


def esc(val):
    """HTML-escape a value."""
    return html_mod.escape(str(val))


def build_summary_table_rows(rows, best_cps):
    """Pre-render summary table rows server-side as safe HTML."""
    out = []
    for r in rows:
        mean_cps = float(r["mean_cps"])
        is_best = abs(mean_cps - best_cps) < 0.5
        cls = ' class="best-row"' if is_best else ''
        out.append(
            f'<tr{cls}>'
            f'<td>{esc(r["num_chunks"])}</td>'
            f'<td>{esc(r["batch_size"])}</td>'
            f'<td><strong>{mean_cps:.1f}</strong></td>'
            f'<td>{float(r["stddev_cps"]):.1f}</td>'
            f'<td>{float(r["min_cps"]):.1f}</td>'
            f'<td>{float(r["max_cps"]):.1f}</td>'
            f'<td>{float(r["mean_gpu_temp"]):.0f}</td>'
            f'<td>{float(r["mean_gpu_mem_mb"]):.0f}</td>'
            f'<td>{float(r["mean_gpu_power_w"]):.1f}</td>'
            f'</tr>'
        )
    return "\n".join(out)


def build_raw_table_rows(rows):
    """Pre-render raw data table rows server-side."""
    out = []
    for r in rows:
        device = r["device"]
        cls = "device-cuda" if device == "cuda" else "device-cpu"
        out.append(
            f'<tr>'
            f'<td>{esc(r["run"])}</td>'
            f'<td class="{cls}">{esc(device.upper())}</td>'
            f'<td>{esc(r["num_chunks"])}</td>'
            f'<td>{esc(r["batch_size"])}</td>'
            f'<td>{float(r["time_s"]):.4f}</td>'
            f'<td><strong>{float(r["chunks_per_sec"]):.1f}</strong></td>'
            f'<td>{esc(r["gpu_temp_c"])}</td>'
            f'<td>{esc(r["gpu_mem_used_mb"])}</td>'
            f'<td>{esc(r["gpu_power_w"])}</td>'
            f'</tr>'
        )
    return "\n".join(out)


def build_bar_chart_html(items, max_val):
    """Pre-render a horizontal bar chart as static HTML."""
    rows = []
    for item in items:
        pct = max((item["value"] / max_val) * 100, 3) if max_val > 0 else 3
        cls = item.get("type", "gpu")
        label = esc(item["label"])
        val_text = f'{item["value"]:.1f}'
        rows.append(
            f'<div class="bar-row">'
            f'  <div class="bar-label">{label}</div>'
            f'  <div class="bar-track">'
            f'    <div class="bar-fill {cls}" style="width:{pct:.1f}%">{val_text}</div>'
            f'  </div>'
            f'</div>'
        )
    return "\n".join(rows)


def generate_html(raw_rows, summary_rows, metadata):
    gpu_summaries = [r for r in summary_rows if r["device"] == "cuda"]
    cpu_summaries = [r for r in summary_rows if r["device"] == "cpu"]

    best_gpu = max(gpu_summaries, key=lambda r: float(r["mean_cps"])) if gpu_summaries else None
    best_cpu = max(cpu_summaries, key=lambda r: float(r["mean_cps"])) if cpu_summaries else None

    best_gpu_cps = float(best_gpu["mean_cps"]) if best_gpu else 0
    best_cpu_cps = float(best_cpu["mean_cps"]) if best_cpu else 0
    speedup = round(best_gpu_cps / best_cpu_cps, 1) if best_cpu_cps > 0 else 0

    gpu_raw = [r for r in raw_rows if r["device"] == "cuda"]
    gpu_temps = [int(r["gpu_temp_c"]) for r in gpu_raw if int(r["gpu_temp_c"]) > 0]
    temp_min = min(gpu_temps) if gpu_temps else 0
    temp_max = max(gpu_temps) if gpu_temps else 0

    n_reps = metadata.get("n_reps", 3)
    total_runs = len(raw_rows)

    # Pre-render all tables
    gpu_table_rows = build_summary_table_rows(gpu_summaries, best_gpu_cps)
    cpu_table_rows = build_summary_table_rows(cpu_summaries, best_cpu_cps)
    raw_table_rows = build_raw_table_rows(raw_rows)

    # Pre-render charts

    # Overview: batch size at 5000 chunks
    rows_5k = [r for r in gpu_summaries if r["num_chunks"] == "5000"]
    max_5k = max(float(r["mean_cps"]) for r in rows_5k) * 1.1 if rows_5k else 1
    overview_chart = build_bar_chart_html(
        [{"label": f'batch={r["batch_size"]}', "value": float(r["mean_cps"]), "type": "gpu"} for r in rows_5k],
        max_5k
    )

    # GPU vs CPU at 1000 chunks, batch=64
    gpu_1k = next((r for r in gpu_summaries if r["num_chunks"] == "1000" and r["batch_size"] == "64"), None)
    cpu_1k = next((r for r in cpu_summaries if r["num_chunks"] == "1000" and r["batch_size"] == "64"), None)
    if gpu_1k and cpu_1k:
        comp_max = float(gpu_1k["mean_cps"]) * 1.15
        comparison_chart = build_bar_chart_html([
            {"label": "GPU (CUDA)", "value": float(gpu_1k["mean_cps"]), "type": "gpu"},
            {"label": "CPU (ARM)", "value": float(cpu_1k["mean_cps"]), "type": "cpu"},
        ], comp_max)
    else:
        comparison_chart = "<p>No matching data for this comparison.</p>"

    # All GPU configs chart
    all_gpu_max = best_gpu_cps * 1.1 if best_gpu_cps > 0 else 1
    all_gpu_chart = build_bar_chart_html(
        [{"label": f'{r["num_chunks"]}ch b={r["batch_size"]}', "value": float(r["mean_cps"]), "type": "gpu"}
         for r in gpu_summaries],
        all_gpu_max
    )

    # Batch size average chart
    batch_groups = {}
    for r in gpu_summaries:
        bs = r["batch_size"]
        batch_groups.setdefault(bs, []).append(float(r["mean_cps"]))
    batch_avg_chart = build_bar_chart_html(
        [{"label": f'batch={bs} (avg)', "value": sum(vals)/len(vals), "type": "gpu"}
         for bs, vals in sorted(batch_groups.items())],
        all_gpu_max
    )

    # Temperature chart
    temp_items = [{"label": f'{r["num_chunks"]}ch b={r["batch_size"]}', "value": float(r["mean_gpu_temp"]), "type": "gpu"}
                  for r in gpu_summaries]
    temp_max_val = max(i["value"] for i in temp_items) * 1.3 if temp_items else 1
    temp_chart = build_bar_chart_html(temp_items, temp_max_val)

    # Power chart
    power_items = [{"label": f'{r["num_chunks"]}ch b={r["batch_size"]}', "value": float(r["mean_gpu_power_w"]), "type": "gpu"}
                   for r in gpu_summaries]
    power_max_val = max(i["value"] for i in power_items) * 1.2 if power_items else 1
    power_chart = build_bar_chart_html(power_items, power_max_val)

    # System info helpers
    gpu_info = metadata.get("gpu", {})
    sys_info = metadata.get("system", {})
    model_info = metadata.get("model", {})
    sw_info = metadata.get("software", {})
    tp_info = metadata.get("test_params", {})

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GX10 Benchmark #06: Embedding Throughput</title>
<style>
:root {{
    --primary: #1a73e8;
    --primary-light: #4a90d9;
    --accent: #34a853;
    --warn: #ea4335;
    --orange: #f9ab00;
    --bg: #0d1117;
    --surface: #161b22;
    --surface2: #1c2333;
    --border: #30363d;
    --text: #e6edf3;
    --text-dim: #8b949e;
    --gpu-color: #58a6ff;
    --cpu-color: #f97583;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    font-size: 14px;
}}
.header {{
    background: linear-gradient(135deg, #1a1f35 0%, #0d1117 100%);
    border-bottom: 1px solid var(--border);
    padding: 2rem;
    text-align: center;
}}
.header h1 {{ font-size: 1.8rem; font-weight: 700; margin-bottom: 0.25rem; }}
.header .subtitle {{ color: var(--text-dim); font-size: 0.85rem; }}
.header .timestamp {{ color: var(--text-dim); font-size: 0.75rem; margin-top: 0.5rem; }}
.container {{ max-width: 1200px; margin: 0 auto; padding: 1.5rem; }}
.nav {{
    display: flex; gap: 0.5rem; margin-bottom: 1.5rem;
    border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; flex-wrap: wrap;
}}
.nav button {{
    background: transparent; border: none; color: var(--text-dim);
    padding: 0.5rem 1rem; cursor: pointer; font-family: inherit;
    font-size: 0.85rem; border-radius: 6px 6px 0 0; transition: all 0.2s;
}}
.nav button:hover {{ color: var(--text); background: var(--surface); }}
.nav button.active {{
    color: var(--primary-light); border-bottom: 2px solid var(--primary);
    background: var(--surface);
}}
.panel {{ display: none; }}
.panel.active {{ display: block; }}
.stat-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem; margin-bottom: 1.5rem;
}}
.stat-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 1.25rem;
}}
.stat-label {{ color: var(--text-dim); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
.stat-value {{ font-size: 1.8rem; font-weight: 700; margin: 0.25rem 0; }}
.stat-unit {{ color: var(--text-dim); font-size: 0.8rem; }}
.stat-value.gpu {{ color: var(--gpu-color); }}
.stat-value.cpu {{ color: var(--cpu-color); }}
.stat-value.green {{ color: var(--accent); }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 1.5rem; font-size: 0.85rem; }}
th, td {{ padding: 0.6rem 0.8rem; text-align: right; border-bottom: 1px solid var(--border); }}
th {{
    color: var(--text-dim); font-weight: 600; text-transform: uppercase;
    font-size: 0.7rem; letter-spacing: 0.05em; background: var(--surface);
    position: sticky; top: 0;
}}
th:first-child, td:first-child {{ text-align: left; }}
tr:hover td {{ background: var(--surface2); }}
.device-cuda {{ color: var(--gpu-color); font-weight: 600; }}
.device-cpu {{ color: var(--cpu-color); font-weight: 600; }}
.best-row {{ background: rgba(52, 168, 83, 0.08); }}
.best-row td {{ border-left: 3px solid var(--accent); }}
.chart-container {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem;
}}
.chart-title {{ font-size: 1rem; font-weight: 600; margin-bottom: 1rem; }}
.chart-subtitle {{ color: var(--text-dim); font-size: 0.75rem; margin-bottom: 1rem; }}
.bar-row {{ display: flex; align-items: center; margin-bottom: 0.5rem; gap: 0.5rem; }}
.bar-label {{ width: 160px; font-size: 0.8rem; text-align: right; flex-shrink: 0; color: var(--text-dim); }}
.bar-track {{ flex: 1; height: 28px; background: var(--surface2); border-radius: 4px; overflow: hidden; position: relative; }}
.bar-fill {{
    height: 100%; border-radius: 4px; display: flex; align-items: center;
    padding: 0 8px; font-size: 0.75rem; font-weight: 600; color: #fff;
    white-space: nowrap; min-width: fit-content; transition: width 0.3s;
}}
.bar-fill.gpu {{ background: linear-gradient(90deg, #1a73e8, #58a6ff); }}
.bar-fill.cpu {{ background: linear-gradient(90deg, #b33a3a, #f97583); }}
.info-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1rem; margin-bottom: 1.5rem;
}}
.info-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 1.25rem;
}}
.info-card h3 {{ font-size: 0.85rem; color: var(--primary-light); margin-bottom: 0.75rem; }}
.info-row {{
    display: flex; justify-content: space-between; padding: 0.3rem 0;
    border-bottom: 1px solid var(--border); font-size: 0.8rem;
}}
.info-row:last-child {{ border-bottom: none; }}
.info-key {{ color: var(--text-dim); }}
.info-val {{ font-weight: 600; }}
.legend {{ display: flex; gap: 1.5rem; margin-bottom: 1rem; font-size: 0.8rem; }}
.legend-item {{ display: flex; align-items: center; gap: 0.4rem; }}
.legend-dot {{ width: 12px; height: 12px; border-radius: 3px; }}
.legend-dot.gpu {{ background: var(--gpu-color); }}
.legend-dot.cpu {{ background: var(--cpu-color); }}
.footer {{
    text-align: center; padding: 2rem; color: var(--text-dim);
    font-size: 0.75rem; border-top: 1px solid var(--border); margin-top: 2rem;
}}
@media (max-width: 768px) {{
    .stat-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .info-grid {{ grid-template-columns: 1fr; }}
    .bar-label {{ width: 100px; font-size: 0.7rem; }}
    .nav {{ overflow-x: auto; flex-wrap: nowrap; }}
}}
</style>
</head>
<body>

<div class="header">
    <h1>GX10 Benchmark #06</h1>
    <div class="subtitle">Embedding Throughput &mdash; Mesolitica Mistral-Embedding 191M</div>
    <div class="timestamp">{esc(metadata.get("timestamp", ""))} &bull; {n_reps} reps/config &bull; {total_runs} total runs</div>
</div>

<div class="container">

<div class="nav">
    <button class="active" onclick="switchTab(this, 'overview')">Overview</button>
    <button onclick="switchTab(this, 'gpu')">GPU Results</button>
    <button onclick="switchTab(this, 'cpu')">CPU Results</button>
    <button onclick="switchTab(this, 'charts')">Charts</button>
    <button onclick="switchTab(this, 'raw')">Raw Data</button>
    <button onclick="switchTab(this, 'system')">System Info</button>
</div>

<!-- OVERVIEW -->
<div id="panel-overview" class="panel active">
    <div class="stat-grid">
        <div class="stat-card">
            <div class="stat-label">Peak GPU Throughput (mean)</div>
            <div class="stat-value gpu">{best_gpu_cps:,.1f}</div>
            <div class="stat-unit">chunks/sec (batch={esc(best_gpu["batch_size"] if best_gpu else "?")}, n={esc(best_gpu["num_chunks"] if best_gpu else "?")})</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Peak CPU Throughput (mean)</div>
            <div class="stat-value cpu">{best_cpu_cps:,.1f}</div>
            <div class="stat-unit">chunks/sec (batch={esc(best_cpu["batch_size"] if best_cpu else "?")}, n={esc(best_cpu["num_chunks"] if best_cpu else "?")})</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">GPU Speedup</div>
            <div class="stat-value green">{speedup}x</div>
            <div class="stat-unit">over CPU</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">GPU Temperature</div>
            <div class="stat-value">{temp_min}&ndash;{temp_max}</div>
            <div class="stat-unit">&deg;C during test</div>
        </div>
    </div>

    <div class="chart-container">
        <div class="chart-title">Throughput by Batch Size (GPU, 5000 chunks)</div>
        <div class="chart-subtitle">Mean chunks/sec &mdash; {n_reps} repetitions per config</div>
        <div class="legend"><div class="legend-item"><div class="legend-dot gpu"></div> GPU (CUDA)</div></div>
        {overview_chart}
    </div>

    <div class="chart-container">
        <div class="chart-title">GPU vs CPU Comparison (1000 chunks, batch=64)</div>
        <div class="chart-subtitle">Mean chunks/sec &mdash; showing relative performance gap</div>
        <div class="legend">
            <div class="legend-item"><div class="legend-dot gpu"></div> GPU</div>
            <div class="legend-item"><div class="legend-dot cpu"></div> CPU</div>
        </div>
        {comparison_chart}
    </div>
</div>

<!-- GPU RESULTS -->
<div id="panel-gpu" class="panel">
    <h2 style="margin-bottom:1rem; font-size:1.1rem;">GPU (CUDA) &mdash; Aggregated Results</h2>
    <table>
        <thead><tr>
            <th>Chunks</th><th>Batch</th><th>Mean CPS</th><th>StdDev</th>
            <th>Min</th><th>Max</th><th>Temp &deg;C</th><th>Mem MB</th><th>Power W</th>
        </tr></thead>
        <tbody>{gpu_table_rows}</tbody>
    </table>
</div>

<!-- CPU RESULTS -->
<div id="panel-cpu" class="panel">
    <h2 style="margin-bottom:1rem; font-size:1.1rem;">CPU (ARM) &mdash; Aggregated Results</h2>
    <table>
        <thead><tr>
            <th>Chunks</th><th>Batch</th><th>Mean CPS</th><th>StdDev</th>
            <th>Min</th><th>Max</th><th>Temp &deg;C</th><th>Mem MB</th><th>Power W</th>
        </tr></thead>
        <tbody>{cpu_table_rows}</tbody>
    </table>
</div>

<!-- CHARTS -->
<div id="panel-charts" class="panel">
    <div class="chart-container">
        <div class="chart-title">GPU: Throughput by Configuration</div>
        <div class="chart-subtitle">Mean chunks/sec &mdash; higher is better</div>
        {all_gpu_chart}
    </div>
    <div class="chart-container">
        <div class="chart-title">GPU: Average Throughput by Batch Size</div>
        <div class="chart-subtitle">Mean across all chunk counts &mdash; higher is better</div>
        {batch_avg_chart}
    </div>
    <div class="chart-container">
        <div class="chart-title">GPU Temperature Profile</div>
        <div class="chart-subtitle">Mean temperature per configuration (&deg;C)</div>
        {temp_chart}
    </div>
    <div class="chart-container">
        <div class="chart-title">GPU Power Draw</div>
        <div class="chart-subtitle">Mean power per configuration (Watts)</div>
        {power_chart}
    </div>
</div>

<!-- RAW DATA -->
<div id="panel-raw" class="panel">
    <h2 style="margin-bottom:1rem; font-size:1.1rem;">All Individual Runs ({total_runs} rows)</h2>
    <table>
        <thead><tr>
            <th>Run</th><th>Device</th><th>Chunks</th><th>Batch</th>
            <th>Time (s)</th><th>Chunks/s</th><th>Temp &deg;C</th><th>Mem MB</th><th>Power W</th>
        </tr></thead>
        <tbody>{raw_table_rows}</tbody>
    </table>
</div>

<!-- SYSTEM INFO -->
<div id="panel-system" class="panel">
    <div class="info-grid">
        <div class="info-card">
            <h3>GPU</h3>
            <div class="info-row"><span class="info-key">Name</span><span class="info-val">{esc(gpu_info.get("name", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Driver</span><span class="info-val">{esc(gpu_info.get("driver", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">CUDA</span><span class="info-val">{esc(gpu_info.get("cuda_version", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Compute</span><span class="info-val">SM {esc(gpu_info.get("compute_capability", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">VRAM</span><span class="info-val">{esc(gpu_info.get("memory_total_mb", 0))} MB</span></div>
        </div>
        <div class="info-card">
            <h3>CPU / System</h3>
            <div class="info-row"><span class="info-key">CPU</span><span class="info-val">{esc(sys_info.get("cpu_model", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Cores</span><span class="info-val">{esc(sys_info.get("cpu_cores", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">RAM</span><span class="info-val">{esc(sys_info.get("ram_total_gb", "N/A"))} GB</span></div>
            <div class="info-row"><span class="info-key">OS</span><span class="info-val">{esc(sys_info.get("os", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Kernel</span><span class="info-val">{esc(sys_info.get("kernel", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Arch</span><span class="info-val">{esc(sys_info.get("arch", "N/A"))}</span></div>
        </div>
        <div class="info-card">
            <h3>Model</h3>
            <div class="info-row"><span class="info-key">Name</span><span class="info-val">{esc(model_info.get("name", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Parameters</span><span class="info-val">{esc(model_info.get("parameters", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Embedding Dim</span><span class="info-val">{esc(model_info.get("embedding_dim", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Max Seq Length</span><span class="info-val">{esc(model_info.get("max_seq_length", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Language</span><span class="info-val">{esc(model_info.get("language", "N/A"))}</span></div>
        </div>
        <div class="info-card">
            <h3>Software</h3>
            <div class="info-row"><span class="info-key">Python</span><span class="info-val">{esc(sw_info.get("python", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">PyTorch</span><span class="info-val">{esc(sw_info.get("torch", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Sentence Transformers</span><span class="info-val">{esc(sw_info.get("sentence_transformers", "N/A"))}</span></div>
        </div>
    </div>
    <div class="info-card" style="margin-bottom:1.5rem;">
        <h3>Test Parameters</h3>
        <div class="info-row"><span class="info-key">Repetitions</span><span class="info-val">{n_reps} per configuration</span></div>
        <div class="info-row"><span class="info-key">Chunk Counts</span><span class="info-val">{esc(tp_info.get("chunk_counts", []))}</span></div>
        <div class="info-row"><span class="info-key">Batch Sizes</span><span class="info-val">{esc(tp_info.get("batch_sizes", []))}</span></div>
        <div class="info-row"><span class="info-key">Devices</span><span class="info-val">CUDA (GPU), CPU (ARM)</span></div>
        <div class="info-row"><span class="info-key">CPU Max Chunks</span><span class="info-val">{esc(tp_info.get("cpu_max_chunks", "N/A"))}</span></div>
        <div class="info-row"><span class="info-key">Warmup</span><span class="info-val">5 progressive rounds (16, 32, 64, 128, 256 chunks)</span></div>
    </div>
</div>

</div>

<div class="footer">
    GX10 Benchmark #06: Embedding Throughput &bull; Pendakwah Teknologi &bull; Generated {esc(metadata.get("timestamp", ""))}
</div>

<script>
function switchTab(btn, name) {{
    document.querySelectorAll('.panel').forEach(function(p) {{ p.classList.remove('active'); }});
    document.querySelectorAll('.nav button').forEach(function(b) {{ b.classList.remove('active'); }});
    document.getElementById('panel-' + name).classList.add('active');
    btn.classList.add('active');
}}
</script>
</body>
</html>"""
    return html


def main():
    if len(sys.argv) != 5:
        print(f"Usage: {sys.argv[0]} results.csv summary.csv metadata.json report.html")
        sys.exit(1)

    raw_rows = load_csv(sys.argv[1])
    summary_rows = load_csv(sys.argv[2])
    metadata = load_json(sys.argv[3])

    html = generate_html(raw_rows, summary_rows, metadata)

    with open(sys.argv[4], "w") as f:
        f.write(html)

    print(f"Report generated: {sys.argv[4]}")
    print(f"  Raw rows: {len(raw_rows)}")
    print(f"  Summary configs: {len(summary_rows)}")


if __name__ == "__main__":
    main()
