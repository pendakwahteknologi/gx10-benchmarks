#!/usr/bin/env python3
"""Generate benchmark charts for 09-coding-llm-webpage.
Style matches the aitopatom-benchmarks matplotlib theme:
- White background, light grid
- Bold titles with em dash
- Blue/green/orange palette
- Bold value labels on bars
- 1480x730 resolution
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os

# Output directory
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'charts')
os.makedirs(OUT_DIR, exist_ok=True)

# Data (median of 3 runs)
models = ['Qwen3-Coder\n30B', 'DeepCoder\n14B', 'Devstral\n24B']
models_short = ['Qwen3-Coder 30B', 'DeepCoder 14B', 'Devstral 24B']
colors = ['#4A90D9', '#4CAF50', '#FF9800']  # blue, green, orange

tok_per_sec = [71.08, 22.43, 14.01]
gen_time = [61.33, 129.39, 212.64]
tokens_generated = [4360, 2903, 2978]
output_size_kb = [18.2, 8.8, 10.4]
vram_gb = [18, 9, 14]
ttft_warm_ms = [85, 153, 209]

# Common style setup
def setup_style():
    plt.rcParams.update({
        'figure.facecolor': 'white',
        'axes.facecolor': 'white',
        'axes.grid': True,
        'grid.alpha': 0.3,
        'grid.color': '#cccccc',
        'axes.edgecolor': '#cccccc',
        'font.family': 'sans-serif',
        'font.size': 14,
        'axes.titlesize': 20,
        'axes.titleweight': 'bold',
        'axes.labelsize': 14,
        'xtick.labelsize': 13,
        'ytick.labelsize': 12,
    })

setup_style()

# --- Chart 1: Generation Speed (tok/s) ---
fig, ax = plt.subplots(figsize=(14.8, 7.3))
bars = ax.bar(models, tok_per_sec, color=colors, width=0.5, edgecolor='white', linewidth=1.5)
for bar, val in zip(bars, tok_per_sec):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5,
            f'{val:.1f} tok/s', ha='center', va='bottom', fontsize=16, fontweight='bold')
ax.set_ylabel('Tokens per Second')
ax.set_title('Generation Speed \u2014 Coding LLM Benchmark')
ax.set_ylim(0, max(tok_per_sec) * 1.2)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, 'generation_speed.png'), dpi=100, bbox_inches='tight')
plt.close()
print('Saved generation_speed.png')

# --- Chart 2: Generation Time ---
fig, ax = plt.subplots(figsize=(14.8, 7.3))
bars = ax.bar(models, gen_time, color=colors, width=0.5, edgecolor='white', linewidth=1.5)
for bar, val in zip(bars, gen_time):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 3,
            f'{val:.0f}s', ha='center', va='bottom', fontsize=16, fontweight='bold')
ax.set_ylabel('Time (seconds)')
ax.set_title('Generation Time \u2014 Coding LLM Benchmark')
ax.set_ylim(0, max(gen_time) * 1.2)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, 'generation_time.png'), dpi=100, bbox_inches='tight')
plt.close()
print('Saved generation_time.png')

# --- Chart 3: VRAM Usage with 128GB reference line ---
fig, ax = plt.subplots(figsize=(14.8, 7.3))
bars = ax.bar(models, vram_gb, color=colors, width=0.5, edgecolor='white', linewidth=1.5)
ax.axhline(y=128, color='#FF4444', linestyle='--', linewidth=2, label='Total GPU Memory (128 GB)')
for bar, val in zip(bars, vram_gb):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
            f'{val} GB', ha='center', va='bottom', fontsize=16, fontweight='bold')
ax.set_ylabel('GPU Memory (GB)')
ax.set_title('VRAM Usage \u2014 Coding LLM Benchmark')
ax.set_ylim(0, 145)
ax.legend(loc='upper left', fontsize=13)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, 'vram_usage.png'), dpi=100, bbox_inches='tight')
plt.close()
print('Saved vram_usage.png')

# --- Chart 4: Output Size ---
fig, ax = plt.subplots(figsize=(14.8, 7.3))
bars = ax.bar(models, output_size_kb, color=colors, width=0.5, edgecolor='white', linewidth=1.5)
for bar, val in zip(bars, output_size_kb):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.4,
            f'{val} KB', ha='center', va='bottom', fontsize=16, fontweight='bold')
ax.set_ylabel('HTML Output Size (KB)')
ax.set_title('Output Size \u2014 Coding LLM Benchmark')
ax.set_ylim(0, max(output_size_kb) * 1.3)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, 'output_size.png'), dpi=100, bbox_inches='tight')
plt.close()
print('Saved output_size.png')

# --- Chart 5: Tokens Generated ---
fig, ax = plt.subplots(figsize=(14.8, 7.3))
bars = ax.bar(models, tokens_generated, color=colors, width=0.5, edgecolor='white', linewidth=1.5)
for bar, val in zip(bars, tokens_generated):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 50,
            f'{val:,}', ha='center', va='bottom', fontsize=16, fontweight='bold')
ax.set_ylabel('Tokens Generated')
ax.set_title('Tokens Generated \u2014 Coding LLM Benchmark')
ax.set_ylim(0, max(tokens_generated) * 1.2)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, 'tokens_generated.png'), dpi=100, bbox_inches='tight')
plt.close()
print('Saved tokens_generated.png')

print(f'\nAll charts saved to {OUT_DIR}/')
