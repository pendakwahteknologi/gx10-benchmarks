# Test Images

Place exactly **5 images** in this directory before running `vlm_bench.py`. The runner will pick up any `.jpg`, `.jpeg`, `.png`, or `.webp` files alphabetically.

## Recommended set

To keep results comparable across runs and reproducible, use this fixed mix:

| Slot | Filename | Content | Why this content |
|------|----------|---------|------------------|
| 1 | `01_people_scene.jpg` | A photo with multiple people in a public setting (e.g., sports event, plaza) | Tests recognition + counting under occlusion |
| 2 | `02_product.jpg` | A clear product photo with visible packaging text | Tests fine detail + OCR on a structured layout |
| 3 | `03_document.png` | A page of printed text (scan of a magazine, paper, etc.) | Pure OCR difficulty, dense text |
| 4 | `04_landscape.jpg` | An outdoor nature scene with depth (mountains, ocean, forest) | Tests scene-level captioning, spatial reasoning |
| 5 | `05_chart.png` | A graph, infographic, or technical diagram | Tests structured-data understanding |

All images at native resolution (don't pre-resize). The benchmark will exercise resolution behaviour through the model's own image preprocessing.

## Sources

Use any source you have a clear right to redistribute (CC-BY, CC0, your own photos). Wikimedia Commons is a reliable bank for the first four; for the chart slot, a generated matplotlib figure or a screenshot of an open-data dashboard works.

This directory is **gitignored** by default — actual images don't ship with the repo. The benchmark JSON output captures the filenames so future readers can match outputs to images they place themselves.

## Image hashes

When the canonical 5-image set is finalised, SHA-256 hashes of each file go here so other runs can verify they used the same inputs.
