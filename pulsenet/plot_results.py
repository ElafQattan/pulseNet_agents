# Draws the evaluation results as an SVG chart for the README (no plotting library needed).
#   uv run python pulsenet/plot_results.py

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
OUT = HERE.parent / "docs" / "images"
CATEGORIES = ["diagnosis", "forecast", "action", "approval", "safety", "security", "knowledge"]
COLORS = {"A": "#94a3b8", "B": "#0d9488"}


def pass_rates(config):
    rows = list(csv.DictReader(open(RESULTS / f"eval_{config}.csv", encoding="utf-8")))
    rate = {c: [r["passed"] == "True" for r in rows if r["category"] == c] for c in CATEGORIES}
    overall = sum(r["passed"] == "True" for r in rows) / len(rows)
    return {c: sum(v) / len(v) for c, v in rate.items() if v}, overall, len(rows)


def bar_chart():
    a, a_all, n = pass_rates("A")
    b, b_all, _ = pass_rates("B")
    w, h, left, top, chart_h = 1000, 400, 70, 70, 250
    group = (w - left - 40) / len(CATEGORIES)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
           'font-family="Segoe UI, Helvetica, Arial, sans-serif">',
           f'<rect width="{w}" height="{h}" rx="14" fill="#ffffff"/>',
           f'<text x="{w / 2}" y="34" text-anchor="middle" font-size="19" font-weight="700" fill="#0f172a">'
           f'Pass rate by category · A {a_all:.0%} → B {b_all:.0%} ({n} tasks each)</text>']
    for pct in (0, 25, 50, 75, 100):
        y = top + chart_h * (1 - pct / 100)
        svg.append(f'<line x1="{left}" y1="{y}" x2="{w - 30}" y2="{y}" stroke="#e2e8f0"/>')
        svg.append(f'<text x="{left - 8}" y="{y + 4}" text-anchor="end" font-size="11" fill="#64748b">{pct}%</text>')
    for i, c in enumerate(CATEGORIES):
        x0 = left + i * group + group * 0.18
        for j, (cfg, rates) in enumerate((("A", a), ("B", b))):
            v = rates.get(c, 0)
            bh = chart_h * v
            x = x0 + j * group * 0.33
            svg.append(f'<rect x="{x:.1f}" y="{top + chart_h - bh:.1f}" width="{group * 0.3:.1f}" height="{bh:.1f}" '
                       f'rx="3" fill="{COLORS[cfg]}"/>')
            svg.append(f'<text x="{x + group * 0.15:.1f}" y="{top + chart_h - bh - 6:.1f}" text-anchor="middle" '
                       f'font-size="11" fill="#334155">{v:.0%}</text>')
        svg.append(f'<text x="{left + i * group + group / 2:.1f}" y="{top + chart_h + 22}" text-anchor="middle" '
                   f'font-size="12.5" fill="#0f172a">{c}</text>')
    lx = w / 2 - 170
    svg.append(f'<rect x="{lx}" y="{h - 40}" width="14" height="14" rx="3" fill="{COLORS["A"]}"/>'
               f'<text x="{lx + 20}" y="{h - 28}" font-size="12.5" fill="#334155">A · AGENTS.md</text>')
    svg.append(f'<rect x="{lx + 160}" y="{h - 40}" width="14" height="14" rx="3" fill="{COLORS["B"]}"/>'
               f'<text x="{lx + 180}" y="{h - 28}" font-size="12.5" fill="#334155">B · AGENTS.md + PLAYBOOK.md</text>')
    svg.append("</svg>")
    (OUT / "eval_results.svg").write_text("\n".join(svg), encoding="utf-8")


def retrieval_chart():
    data = json.loads((RESULTS / "retrieval.json").read_text(encoding="utf-8"))
    w, h = 1000, 300
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
           'font-family="Segoe UI, Helvetica, Arial, sans-serif">',
           f'<rect width="{w}" height="{h}" rx="14" fill="#ffffff"/>',
           f'<text x="{w / 2}" y="34" text-anchor="middle" font-size="19" font-weight="700" fill="#0f172a">'
           'Knowledge search: right document in the top 4 (24 questions, no model involved)</text>']
    colors = {"bm25": "#0284c7", "embeddings": "#7c3aed", "hybrid": "#0d9488"}
    for i, (label, key) in enumerate((("Direct wording (12)", "direct_hit@4"),
                                      ("Engineer's own words (12)", "paraphrase_hit@4"),
                                      ("All (24)", "all_hit@4"))):
        y = 75 + i * 65
        svg.append(f'<text x="210" y="{y + 30}" text-anchor="end" font-size="13" fill="#0f172a">{label}</text>')
        for j, m in enumerate(("bm25", "embeddings", "hybrid")):
            v = data[m][key]
            bw = 640 * v
            svg.append(f'<rect x="225" y="{y + j * 17}" width="{bw:.1f}" height="14" rx="3" fill="{colors[m]}"/>')
            svg.append(f'<text x="{230 + bw:.1f}" y="{y + j * 17 + 11}" font-size="11" fill="#334155">'
                       f'{m} {v:.0%}</text>')
    svg.append("</svg>")
    (OUT / "retrieval_results.svg").write_text("\n".join(svg), encoding="utf-8")


if __name__ == "__main__":
    retrieval_chart()
    bar_chart()
    print("wrote", OUT / "retrieval_results.svg", "and", OUT / "eval_results.svg")
