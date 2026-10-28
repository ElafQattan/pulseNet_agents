# Downloads the public standards PulseNet searches, from the GSMA Open-Telco datasets on Hugging Face.
#   uv run python pulsenet/fetch_standards.py
# They are saved to data/knowledge/standards/ and are not committed (they belong to ITU and ETSI).

import re
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / "data" / "knowledge" / "standards"
BASE = "https://huggingface.co/datasets/GSMA/{}/resolve/main/{}"

STANDARDS = [
    ("ITU-T-Y.3173", "ITU-T Y.3173 Framework for evaluating intelligence levels of future networks", "itu",
     "marked/Y/T-REC-Y.3173-202002-I_PDF-E/raw.md"),
    ("ITU-T-Y.3177", "ITU-T Y.3177 AI-based network automation for resource and fault management", "itu",
     "marked/Y/T-REC-Y.3177-202102-I_PDF-E/raw.md"),
    ("ITU-T-Y.3172", "ITU-T Y.3172 Architectural framework for machine learning in future networks", "itu",
     "marked/Y/T-REC-Y.3172-201906-I_PDF-E/raw.md"),
    ("ETSI-ZSM-002", "ETSI GS ZSM 002 Zero-touch network and service management, reference architecture", "etsi",
     "marked/GS/gs_ZSM/gs_zsm002v010101p/raw.md"),
    ("ETSI-ZSM-009-1", "ETSI GS ZSM 009-1 Closed-loop automation, enablers", "etsi",
     "marked/GS/gs_ZSM/gs_zsm00901v010101p/raw.md"),
    ("ETSI-ZSM-009-2", "ETSI GS ZSM 009-2 Closed-loop automation, solutions for automation of E2E service and network management", "etsi",
     "marked/GS/gs_ZSM/gs_zsm00902v010101p/raw.md"),
]


def clean(text):
    # drop images, table-of-contents lines ("..... 12") and empty table rows
    lines = []
    for line in text.splitlines():
        if line.startswith("![") or re.search(r"\.{5,}", line) or re.fullmatch(r"[|\s-]*", line or "x"):
            continue
        lines.append(line)
    return "\n".join(lines)


def fetch():
    OUT.mkdir(parents=True, exist_ok=True)
    for doc_id, title, dataset, path in STANDARDS:
        url = BASE.format(dataset, urllib.parse.quote(path))
        text = urllib.request.urlopen(url, timeout=60).read().decode("utf-8")
        header = f"---\nid: {doc_id}\ntitle: {title}\nkeywords: standard, {dataset.upper()}\nsource: {url}\n---\n"
        (OUT / f"{doc_id}.md").write_text(header + clean(text), encoding="utf-8")
        print("saved", doc_id)


if __name__ == "__main__":
    fetch()
