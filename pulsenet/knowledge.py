import hashlib
import os
import re
from pathlib import Path

import bm25s
import numpy as np

KNOWLEDGE = Path(__file__).resolve().parent / "data" / "knowledge"
CACHE = Path(__file__).resolve().parents[1] / "artifacts" / "pulsenet"
EMBED_MODEL = "minishlab/potion-retrieval-32M"  # small static embedding model tuned for search (129 MB)
MAX_CHARS = 1200

# A = keywords only (BM25), B = keywords + meaning (hybrid). Set by the eval configurations.
MODE = os.getenv("PULSENET_RETRIEVAL", "hybrid")


# ---------------------------------------------------------------- read and split the documents
def read_doc(path):
    head, body = path.read_text(encoding="utf-8")[3:].split("---", 1)
    meta = dict(line.split(": ", 1) for line in head.strip().splitlines() if ": " in line)
    return meta, body


def split_long(text):
    # a long section is cut at paragraph breaks into pieces of about MAX_CHARS
    pieces, buf = [], ""
    for para in text.split("\n\n"):
        if buf and len(buf) + len(para) > MAX_CHARS:
            pieces.append(buf)
            buf = ""
        buf += para + "\n\n"
    if buf.strip():
        pieces.append(buf)
    return [p[:MAX_CHARS * 2] for p in pieces]


def load_chunks():
    chunks = []
    for kind in ("runbooks", "incidents", "standards"):
        for path in sorted((KNOWLEDGE / kind).glob("*.md")):
            meta, body = read_doc(path)
            for section in re.split(r"\n(?=#{1,4} )", body):
                heading = section.strip().splitlines()[0].strip("# *") if section.strip() else ""
                for piece in split_long(section.strip()):
                    if len(piece) < 120:
                        continue
                    chunks.append({"doc_id": meta["id"], "title": meta["title"], "kind": kind[:-1],
                                   "section": heading[:100], "text": piece.strip(),
                                   "search_text": f"{meta['title']} {meta.get('keywords', '')} {piece}"})
    return chunks


# ---------------------------------------------------------------- the index (built once per process)
_index = {}


def index():
    if _index:
        return _index
    chunks = load_chunks()
    texts = [c["search_text"] for c in chunks]
    bm25 = bm25s.BM25()
    bm25.index(bm25s.tokenize(texts, stopwords="en", show_progress=False), show_progress=False)
    _index.update(chunks=chunks, texts=texts, bm25=bm25)
    return _index


def embeddings():
    # load the model and embed every chunk once; the vectors are cached on disk
    ix = index()
    if "vectors" in ix:
        return ix["model"], ix["vectors"]
    from model2vec import StaticModel

    model = StaticModel.from_pretrained(EMBED_MODEL)
    key = hashlib.sha1("".join(ix["texts"]).encode()).hexdigest()[:12]
    path = CACHE / f"embeddings-{key}.npy"
    if path.exists():
        vectors = np.load(path)
    else:
        vectors = model.encode(ix["texts"])
        vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
        CACHE.mkdir(parents=True, exist_ok=True)
        np.save(path, vectors)
    ix.update(model=model, vectors=vectors)
    return model, vectors


def bm25_ranking(query, depth):
    ix = index()
    ids, _ = ix["bm25"].retrieve(bm25s.tokenize([query], stopwords="en", show_progress=False),
                                 k=min(depth, len(ix["chunks"])), show_progress=False)
    return [int(i) for i in ids[0]]


def embedding_ranking(query, depth):
    model, vectors = embeddings()
    v = model.encode([query])[0]
    scores = vectors @ (v / np.linalg.norm(v))
    return [int(i) for i in np.argsort(-scores)[:depth]]


def search(query, k=4, mode=None):
    mode = mode or MODE
    if mode == "bm25":
        ranked = bm25_ranking(query, k)
    else:
        # reciprocal rank fusion: a chunk ranked high by either method comes first
        fused = {}
        for ranking in (bm25_ranking(query, 20), embedding_ranking(query, 20)):
            for rank, i in enumerate(ranking):
                fused[i] = fused.get(i, 0.0) + 1 / (60 + rank)
        ranked = sorted(fused, key=fused.get, reverse=True)[:k]
    chunks = index()["chunks"]
    return [{key: chunks[i][key] for key in ("doc_id", "title", "kind", "section", "text")} for i in ranked]
