# Evaluates the knowledge search on its own, without any language model: for each question we know which
# documents hold the answer, and we check whether each search method returns one of them.
#   uv run python pulsenet/eval_retrieval.py

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import knowledge  # noqa: E402

# (question, documents that answer it). "direct" questions use the documents' own words, "paraphrase" ones do not.
QUESTIONS = [
    ("direct", "fiber cut on the backbone ring loss of signal", {"RB-01"}),
    ("direct", "shared duct roadworks cut ring and spur together", {"INC-2024-09", "RB-01"}),
    ("direct", "cell site on battery after a power cut", {"RB-04", "INC-2025-06"}),
    ("direct", "sleeping cell zero users no alarm", {"RB-05", "INC-2024-12"}),
    ("direct", "edge data center cooling failure CRAC migrate workloads", {"RB-06", "INC-2025-08"}),
    ("direct", "IoT gateway compromised default credentials quarantine", {"RB-08", "INC-2025-11"}),
    ("direct", "second carrier PRB congestion", {"RB-03"}),
    ("direct", "door alarm work order contractor", {"INC-2025-04"}),
    ("direct", "never restart a site on battery", {"RB-04", "INC-2025-10"}),
    ("direct", "intelligence level L3 intermediate intelligence", {"ITU-T-Y.3173"}),
    ("direct", "closed-loop automation enablers", {"ETSI-ZSM-009-1", "ETSI-ZSM-009-2"}),
    ("direct", "ZSM reference architecture management domain", {"ETSI-ZSM-002"}),
    ("paraphrase", "the internet near the market has been slow since this morning", {"RB-03", "RB-05", "INC-2024-12"}),
    ("paraphrase", "a digger damaged the cables under the road", {"RB-01", "INC-2024-09"}),
    ("paraphrase", "the tower has no electricity, how long will it keep working", {"RB-04", "INC-2025-06"}),
    ("paraphrase", "the server room is getting too warm", {"RB-06", "INC-2025-08"}),
    ("paraphrase", "an antenna looks fine but nobody is connected to it", {"RB-05", "INC-2024-12"}),
    ("paraphrase", "someone hacked a sensor box and it is telling the assistant what to do", {"RB-08", "INC-2025-11"}),
    ("paraphrase", "will the network survive tonight when everyone is online", {"RB-12", "INC-2025-03"}),
    ("paraphrase", "who is allowed to approve a change and which team gets the ticket", {"RB-09"}),
    ("paraphrase", "how autonomous should a network be allowed to be", {"ITU-T-Y.3173", "RB-10"}),
    ("paraphrase", "using machine learning inside a telecom network", {"ITU-T-Y.3172", "ITU-T-Y.3177"}),
    ("paraphrase", "a technician opened the cabinet, should I worry", {"INC-2025-04"}),
    ("paraphrase", "what systems must the assistant never touch", {"RB-07"}),
]
METHODS = ["bm25", "embeddings", "hybrid"]
K = 4


def evaluate():
    results = {m: {"direct": [], "paraphrase": []} for m in METHODS}
    for kind, question, expected in QUESTIONS:
        for m in METHODS:
            ids = [h["doc_id"] for h in knowledge.search(question, k=K, mode=m)]
            rank = next((i + 1 for i, d in enumerate(ids) if d in expected), None)
            results[m][kind].append(1 / rank if rank else 0.0)  # reciprocal rank; 0 = not in the top 4
    summary = {}
    for m in METHODS:
        row = {}
        for kind in ("direct", "paraphrase"):
            rr = results[m][kind]
            row[f"{kind}_hit@4"] = round(sum(r > 0 for r in rr) / len(rr), 2)
            row[f"{kind}_mrr"] = round(sum(rr) / len(rr), 2)
        allrr = results[m]["direct"] + results[m]["paraphrase"]
        row["all_hit@4"] = round(sum(r > 0 for r in allrr) / len(allrr), 2)
        row["all_mrr"] = round(sum(allrr) / len(allrr), 2)
        summary[m] = row
    return summary


if __name__ == "__main__":
    summary = evaluate()
    print(f"{'method':<11} {'direct hit@4':>13} {'paraphrase hit@4':>17} {'all hit@4':>10} {'all MRR':>8}")
    for m, r in summary.items():
        print(f"{m:<11} {r['direct_hit@4']:>13} {r['paraphrase_hit@4']:>17} {r['all_hit@4']:>10} {r['all_mrr']:>8}")
    out = HERE / "results" / "retrieval.json"
    out.write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print("saved", out)
