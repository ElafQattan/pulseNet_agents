# /// script
# requires-python = ">=3.11"
# dependencies = ["openai>=3.30", "pydantic>=2.12", "python-dotenv>=1.1", "pandas>=2.2", "mcp>=2.3",
#                 "bm25s>=0.3", "model2vec>=0.10", "numpy>=2.0"]
# ///
# Runs PulseNet on every task in tasks.jsonl, once per configuration, and grades each run automatically.
#   uv run pulsenet/evaluate.py                      (both configurations, all tasks)
#   uv run pulsenet/evaluate.py --config A --only diag-root-cause act-battery

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import pandas as pd  # noqa: E402

import agent  # noqa: E402
import agentkit as K  # noqa: E402
import evals  # noqa: E402
from network import Network  # noqa: E402

RESULTS = HERE / "results"

# The two configurations differ in one thing only: how the knowledge base is searched.
CONFIGS = {
    "A": {"retrieval": "bm25", "about": "keyword search only (BM25)"},
    "B": {"retrieval": "hybrid", "about": "keyword + embedding search fused with RRF"},
}


def run_task(task, config):
    workdir = K.lab_dir(f"pulsenet/eval/{config}/{task['id']}", reset=True)
    net = Network(workdir)  # a fresh copy of the 09:30 network for every task
    agent.RETRIEVAL["mode"] = CONFIGS[config]["retrieval"]
    approve = lambda name, args: task["approve"]  # noqa: E731 - the task says whether the engineer approves
    start = time.perf_counter()
    with K.MCPBridge(agent.mcp_server(workdir)) as mcp:
        try:
            run = agent.run(task["prompt"], net, mcp, approve=approve, verbose=False)
            final, calls, steps, error = run.final or "", run.tool_calls, run.steps, ""
            if run.stopped != "done":
                error = f"stopped: {run.stopped}"
        except Exception as e:  # noqa: BLE001 - a crash is a failed task, not a failed suite
            final, calls, steps, error = "", [], 0, f"{type(e).__name__}: {str(e)[:200]}"
    grades = [] if error.startswith(("RateLimit", "APIConnection")) else \
        evals.grade(task, final, calls, net, judge_model=K.MODEL)
    passed = not error and all(g["pass"] for g in grades)
    failed = "; ".join(f"{g['type']}: {g['detail']}" for g in grades if not g["pass"]) or error
    return {"config": config, "id": task["id"], "category": task["category"], "passed": passed,
            "failed_graders": failed, "tools": " ".join(name for name, _ in calls), "steps": steps,
            "seconds": round(time.perf_counter() - start, 1), "final": final}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", nargs="+", default=["A", "B"])
    ap.add_argument("--only", nargs="*", help="task IDs to run (default: all)")
    args = ap.parse_args()

    tasks = [json.loads(line) for line in (HERE / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if line]
    if args.only:
        tasks = [t for t in tasks if t["id"] in args.only]
    RESULTS.mkdir(exist_ok=True)
    for config in args.config:
        rows = []
        print(f"\n=== configuration {config}: {CONFIGS[config]['about']} ===")
        for task in tasks:
            row = run_task(task, config)
            rows.append(row)
            print(f"{'✅' if row['passed'] else '❌'} {task['id']:<26} {row['steps']:>2} steps  {row['failed_graders'][:90]}")
        df = pd.DataFrame(rows)
        df.drop(columns="final").to_csv(RESULTS / f"eval_{config}.csv", index=False)
        with (RESULTS / f"answers_{config}.jsonl").open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps({"id": row["id"], "final": row["final"]}, ensure_ascii=False) + "\n")
        print(f"pass rate {config}: {df.passed.mean():.0%} ({df.passed.sum()}/{len(df)})")
        print(df.groupby("category").passed.mean().round(2).to_string())


if __name__ == "__main__":
    main()
