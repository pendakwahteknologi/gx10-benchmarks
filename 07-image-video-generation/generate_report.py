#!/usr/bin/env python3
"""
Generate interactive HTML report for Benchmark #07: Image & Video Generation.
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
    return html_mod.escape(str(val))


def build_bar_chart(items, max_val, unit=""):
    rows = []
    for item in items:
        pct = max((item["value"] / max_val) * 100, 3) if max_val > 0 else 3
        cls = item.get("type", "image")
        label = esc(item["label"])
        val_text = f'{item["value"]:.2f}{unit}'
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
    img_summaries = [r for r in summary_rows if r["type"] == "image"]
    vid_summaries = [r for r in summary_rows if r["type"] == "video"]

    # Best image config
    best_img = min(img_summaries, key=lambda r: float(r["mean_time_s"])) if img_summaries else None
    best_vid = None
    best_vid_fps = 0
    if vid_summaries:
        for v in vid_summaries:
            fps = float(v["frames_per_sec"])
            if fps > best_vid_fps:
                best_vid_fps = fps
                best_vid = v

    n_reps_img = metadata.get("n_reps_image", metadata.get("n_reps", 3))
    n_reps_vid = metadata.get("n_reps_video", 2)
    n_reps = f"{n_reps_img} img / {n_reps_vid} vid"
    total_runs = len(raw_rows)
    timestamp = metadata.get("timestamp", "")

    # GPU stats
    all_temps = [int(r["gpu_temp_after"]) for r in raw_rows if int(r["gpu_temp_after"]) > 0]
    temp_min = min(all_temps) if all_temps else 0
    temp_max = max(all_temps) if all_temps else 0

    # Build tables
    img_table = build_summary_table(img_summaries, "image")
    vid_table = build_summary_table(vid_summaries, "video")
    raw_table = build_raw_table(raw_rows)

    # Charts - Image generation time
    if img_summaries:
        img_max = max(float(r["mean_time_s"]) for r in img_summaries) * 1.2
        img_time_chart = build_bar_chart(
            [{"label": r["test"].replace("z_turbo_", ""), "value": float(r["mean_time_s"]), "type": "image"}
             for r in img_summaries],
            img_max, "s"
        )
        img_rate_max = max(float(r["images_per_min"]) for r in img_summaries) * 1.2
        img_rate_chart = build_bar_chart(
            [{"label": r["test"].replace("z_turbo_", ""), "value": float(r["images_per_min"]), "type": "image"}
             for r in img_summaries],
            img_rate_max, " img/min"
        )
    else:
        img_time_chart = "<p>No image tests run.</p>"
        img_rate_chart = ""

    # Charts - Video generation
    if vid_summaries:
        vid_max = max(float(r["mean_time_s"]) for r in vid_summaries) * 1.2
        vid_time_chart = build_bar_chart(
            [{"label": r["test"].replace("wan22_", ""), "value": float(r["mean_time_s"]), "type": "video"}
             for r in vid_summaries],
            vid_max, "s"
        )
        vid_fps_max = max(float(r["frames_per_sec"]) for r in vid_summaries) * 1.2
        vid_fps_chart = build_bar_chart(
            [{"label": r["test"].replace("wan22_", ""), "value": float(r["frames_per_sec"]), "type": "video"}
             for r in vid_summaries],
            vid_fps_max, " fps"
        )
    else:
        vid_time_chart = "<p>No video tests run.</p>"
        vid_fps_chart = ""

    # Power chart
    all_summaries = img_summaries + vid_summaries
    if all_summaries:
        power_items = [{"label": r["test"], "value": float(r["mean_gpu_power_w"]),
                        "type": r["type"]} for r in all_summaries if float(r["mean_gpu_power_w"]) > 0]
        power_max = max(i["value"] for i in power_items) * 1.2 if power_items else 1
        power_chart = build_bar_chart(power_items, power_max, "W")
    else:
        power_chart = ""

    # System info
    gpu_info = metadata.get("gpu", {})
    sys_info = metadata.get("system", {})
    comfy_info = metadata.get("comfyui", {})
    img_model = metadata.get("models", {}).get("image", {})
    vid_model = metadata.get("models", {}).get("video", {})

    # Overview stats
    best_img_time = f'{float(best_img["mean_time_s"]):.2f}' if best_img else "N/A"
    best_img_label = best_img["test"].replace("z_turbo_", "") if best_img else ""
    best_img_rate = f'{float(best_img["images_per_min"]):.1f}' if best_img else "N/A"
    best_vid_time_str = f'{float(best_vid["mean_time_s"]):.1f}' if best_vid else "N/A"
    best_vid_label = best_vid["test"].replace("wan22_", "") if best_vid else ""
    best_vid_fps_str = f'{best_vid_fps:.2f}' if best_vid else "N/A"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GX10 Benchmark #07: Image &amp; Video Generation</title>
<style>
:root {{
    --primary: #1a73e8; --primary-light: #4a90d9;
    --accent: #34a853; --warn: #ea4335;
    --bg: #0d1117; --surface: #161b22; --surface2: #1c2333;
    --border: #30363d; --text: #e6edf3; --text-dim: #8b949e;
    --img-color: #c084fc; --vid-color: #f97583;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
    background: var(--bg); color: var(--text); line-height: 1.6; font-size: 14px;
}}
.header {{
    background: linear-gradient(135deg, #1a1f35 0%, #0d1117 100%);
    border-bottom: 1px solid var(--border); padding: 2rem; text-align: center;
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
    color: var(--primary-light); border-bottom: 2px solid var(--primary); background: var(--surface);
}}
.panel {{ display: none; }}
.panel.active {{ display: block; }}
.stat-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem; margin-bottom: 1.5rem;
}}
.stat-card {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.25rem;
}}
.stat-label {{ color: var(--text-dim); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
.stat-value {{ font-size: 1.8rem; font-weight: 700; margin: 0.25rem 0; }}
.stat-unit {{ color: var(--text-dim); font-size: 0.8rem; }}
.stat-value.img {{ color: var(--img-color); }}
.stat-value.vid {{ color: var(--vid-color); }}
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
.best-row {{ background: rgba(52, 168, 83, 0.08); }}
.best-row td {{ border-left: 3px solid var(--accent); }}
.type-image {{ color: var(--img-color); font-weight: 600; }}
.type-video {{ color: var(--vid-color); font-weight: 600; }}
.chart-container {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem;
}}
.chart-title {{ font-size: 1rem; font-weight: 600; margin-bottom: 1rem; }}
.chart-subtitle {{ color: var(--text-dim); font-size: 0.75rem; margin-bottom: 1rem; }}
.bar-row {{ display: flex; align-items: center; margin-bottom: 0.5rem; gap: 0.5rem; }}
.bar-label {{ width: 200px; font-size: 0.8rem; text-align: right; flex-shrink: 0; color: var(--text-dim); }}
.bar-track {{ flex: 1; height: 28px; background: var(--surface2); border-radius: 4px; overflow: hidden; }}
.bar-fill {{
    height: 100%; border-radius: 4px; display: flex; align-items: center;
    padding: 0 8px; font-size: 0.75rem; font-weight: 600; color: #fff;
    white-space: nowrap; min-width: fit-content; transition: width 0.3s;
}}
.bar-fill.image {{ background: linear-gradient(90deg, #7c3aed, #c084fc); }}
.bar-fill.video {{ background: linear-gradient(90deg, #b33a3a, #f97583); }}
.info-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1rem; margin-bottom: 1.5rem;
}}
.info-card {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.25rem;
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
.legend-dot.image {{ background: var(--img-color); }}
.legend-dot.video {{ background: var(--vid-color); }}
.section-title {{ font-size: 1.1rem; margin-bottom: 1rem; }}
.footer {{
    text-align: center; padding: 2rem; color: var(--text-dim);
    font-size: 0.75rem; border-top: 1px solid var(--border); margin-top: 2rem;
}}
@media (max-width: 768px) {{
    .stat-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .info-grid {{ grid-template-columns: 1fr; }}
    .bar-label {{ width: 120px; font-size: 0.7rem; }}
}}
</style>
</head>
<body>

<div class="header">
    <h1>GX10 Benchmark #07</h1>
    <div class="subtitle">Image &amp; Video Generation Speed</div>
    <div class="timestamp">{esc(timestamp)} &bull; {n_reps} reps/config &bull; {total_runs} total runs</div>
</div>

<div class="container">

<div class="nav">
    <button class="active" onclick="switchTab(this,'overview')">Overview</button>
    <button onclick="switchTab(this,'image')">Image (Z-Turbo)</button>
    <button onclick="switchTab(this,'video')">Video (Wan 2.2)</button>
    <button onclick="switchTab(this,'charts')">Charts</button>
    <button onclick="switchTab(this,'raw')">Raw Data</button>
    <button onclick="switchTab(this,'system')">System Info</button>
</div>

<!-- OVERVIEW -->
<div id="panel-overview" class="panel active">
    <div class="stat-grid">
        <div class="stat-card">
            <div class="stat-label">Fastest Image</div>
            <div class="stat-value img">{best_img_time}s</div>
            <div class="stat-unit">{esc(best_img_label)} ({best_img_rate} img/min)</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Best Video FPS</div>
            <div class="stat-value vid">{best_vid_fps_str}</div>
            <div class="stat-unit">frames/sec ({esc(best_vid_label)})</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Fastest Video</div>
            <div class="stat-value vid">{best_vid_time_str}s</div>
            <div class="stat-unit">{esc(best_vid_label)}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">GPU Temperature</div>
            <div class="stat-value">{temp_min}&ndash;{temp_max}</div>
            <div class="stat-unit">&deg;C during tests</div>
        </div>
    </div>

    <div class="chart-container">
        <div class="chart-title">Image Generation Time (Z-Image-Turbo)</div>
        <div class="chart-subtitle">Mean seconds per image &mdash; lower is better</div>
        <div class="legend"><div class="legend-item"><div class="legend-dot image"></div> Image</div></div>
        {img_time_chart}
    </div>

    <div class="chart-container">
        <div class="chart-title">Video Generation Time (Wan 2.2 T2V 14B)</div>
        <div class="chart-subtitle">Mean seconds per video &mdash; lower is better</div>
        <div class="legend"><div class="legend-item"><div class="legend-dot video"></div> Video</div></div>
        {vid_time_chart}
    </div>
</div>

<!-- IMAGE RESULTS -->
<div id="panel-image" class="panel">
    <h2 class="section-title">Z-Image-Turbo &mdash; Aggregated Results</h2>
    <table>
        <thead><tr>
            <th>Test</th><th>Resolution</th><th>Steps</th>
            <th>Mean (s)</th><th>StdDev</th><th>Min</th><th>Max</th>
            <th>Img/min</th><th>GPU &deg;C</th><th>Power W</th>
        </tr></thead>
        <tbody>{img_table}</tbody>
    </table>
</div>

<!-- VIDEO RESULTS -->
<div id="panel-video" class="panel">
    <h2 class="section-title">Wan 2.2 T2V 14B &mdash; Aggregated Results</h2>
    <table>
        <thead><tr>
            <th>Test</th><th>Resolution</th><th>Frames</th>
            <th>Mean (s)</th><th>StdDev</th><th>Min</th><th>Max</th>
            <th>FPS</th><th>GPU &deg;C</th><th>Power W</th>
        </tr></thead>
        <tbody>{vid_table}</tbody>
    </table>
</div>

<!-- CHARTS -->
<div id="panel-charts" class="panel">
    <div class="chart-container">
        <div class="chart-title">Image: Generation Rate</div>
        <div class="chart-subtitle">Images per minute &mdash; higher is better</div>
        {img_rate_chart}
    </div>
    <div class="chart-container">
        <div class="chart-title">Video: Frames per Second</div>
        <div class="chart-subtitle">Effective FPS including all overhead &mdash; higher is better</div>
        {vid_fps_chart}
    </div>
    <div class="chart-container">
        <div class="chart-title">GPU Power Draw</div>
        <div class="chart-subtitle">Mean watts per configuration</div>
        <div class="legend">
            <div class="legend-item"><div class="legend-dot image"></div> Image</div>
            <div class="legend-item"><div class="legend-dot video"></div> Video</div>
        </div>
        {power_chart}
    </div>
</div>

<!-- RAW DATA -->
<div id="panel-raw" class="panel">
    <h2 class="section-title">All Individual Runs ({total_runs} rows)</h2>
    <table>
        <thead><tr>
            <th>Test</th><th>Type</th><th>Run</th><th>Resolution</th>
            <th>Time (s)</th><th>Temp &deg;C</th><th>Power W</th>
        </tr></thead>
        <tbody>{raw_table}</tbody>
    </table>
</div>

<!-- SYSTEM INFO -->
<div id="panel-system" class="panel">
    <div class="info-grid">
        <div class="info-card">
            <h3>GPU / System</h3>
            <div class="info-row"><span class="info-key">GPU</span><span class="info-val">{esc(gpu_info.get("name", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Driver</span><span class="info-val">{esc(gpu_info.get("driver", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">CPU</span><span class="info-val">{esc(sys_info.get("cpu_model", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Cores</span><span class="info-val">{esc(sys_info.get("cpu_cores", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">RAM</span><span class="info-val">{esc(sys_info.get("ram_total_gb", "N/A"))} GB</span></div>
            <div class="info-row"><span class="info-key">OS</span><span class="info-val">{esc(sys_info.get("os", "N/A"))}</span></div>
        </div>
        <div class="info-card">
            <h3>ComfyUI</h3>
            <div class="info-row"><span class="info-key">Version</span><span class="info-val">{esc(comfy_info.get("version", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Python</span><span class="info-val">{esc(comfy_info.get("python", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">PyTorch</span><span class="info-val">{esc(comfy_info.get("pytorch", "N/A"))}</span></div>
        </div>
        <div class="info-card">
            <h3>Image Model: Z-Image-Turbo</h3>
            <div class="info-row"><span class="info-key">UNet</span><span class="info-val">{esc(img_model.get("file", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Precision</span><span class="info-val">{esc(img_model.get("precision", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Text Encoder</span><span class="info-val">{esc(img_model.get("text_encoder", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">VAE</span><span class="info-val">{esc(img_model.get("vae", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Sampler</span><span class="info-val">{esc(img_model.get("sampler", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Steps</span><span class="info-val">{esc(img_model.get("default_steps", "N/A"))}</span></div>
        </div>
        <div class="info-card">
            <h3>Video Model: Wan 2.2 T2V 14B</h3>
            <div class="info-row"><span class="info-key">Precision</span><span class="info-val">{esc(vid_model.get("precision", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">LoRA</span><span class="info-val">{esc(vid_model.get("lora", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Text Encoder</span><span class="info-val">{esc(vid_model.get("text_encoder", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">VAE</span><span class="info-val">{esc(vid_model.get("vae", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Sampler</span><span class="info-val">{esc(vid_model.get("sampler", "N/A"))}</span></div>
            <div class="info-row"><span class="info-key">Steps</span><span class="info-val">{esc(vid_model.get("total_steps", "N/A"))}</span></div>
        </div>
    </div>
</div>

</div>

<div class="footer">
    GX10 Benchmark #07: Image &amp; Video Generation &bull; Pendakwah Teknologi &bull; Generated {esc(timestamp)}
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


def build_summary_table(rows, test_type):
    if not rows:
        return "<tr><td colspan='10'>No data</td></tr>"
    if test_type == "image":
        best_val = min(float(r["mean_time_s"]) for r in rows)
    else:
        best_val = max(float(r["frames_per_sec"]) for r in rows) if rows else 0

    out = []
    for r in rows:
        mean_t = float(r["mean_time_s"])
        if test_type == "image":
            is_best = abs(mean_t - best_val) < 0.01
        else:
            is_best = abs(float(r["frames_per_sec"]) - best_val) < 0.01
        cls = ' class="best-row"' if is_best else ''
        res = f'{r["width"]}x{r["height"]}'
        rate_col = f'{float(r["images_per_min"]):.1f}' if test_type == "image" else f'{float(r["frames_per_sec"]):.2f}'
        third_col = r["steps"] if test_type == "image" else r["frames"]
        out.append(
            f'<tr{cls}>'
            f'<td>{esc(r["test"])}</td>'
            f'<td>{esc(res)}</td>'
            f'<td>{esc(third_col)}</td>'
            f'<td><strong>{mean_t:.2f}</strong></td>'
            f'<td>{float(r["stddev_time_s"]):.2f}</td>'
            f'<td>{float(r["min_time_s"]):.2f}</td>'
            f'<td>{float(r["max_time_s"]):.2f}</td>'
            f'<td><strong>{rate_col}</strong></td>'
            f'<td>{float(r["mean_gpu_temp"]):.0f}</td>'
            f'<td>{float(r["mean_gpu_power_w"]):.1f}</td>'
            f'</tr>'
        )
    return "\n".join(out)


def build_raw_table(rows):
    out = []
    for r in rows:
        t = r["type"]
        cls = "type-image" if t == "image" else "type-video"
        res = f'{r["width"]}x{r["height"]}'
        if t == "video":
            res += f'x{r["frames"]}f'
        out.append(
            f'<tr>'
            f'<td>{esc(r["test"])}</td>'
            f'<td class="{cls}">{esc(t.upper())}</td>'
            f'<td>{esc(r["run"])}</td>'
            f'<td>{esc(res)}</td>'
            f'<td><strong>{float(r["time_s"]):.2f}</strong></td>'
            f'<td>{esc(r["gpu_temp_after"])}</td>'
            f'<td>{esc(r["gpu_power_w"])}</td>'
            f'</tr>'
        )
    return "\n".join(out)


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
