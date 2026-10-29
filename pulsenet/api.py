# /// script
# requires-python = ">=3.11"
# dependencies = ["fastapi>=0.150", "uvicorn>=0.40", "openai>=3.30", "pydantic>=2.12", "python-dotenv>=1.1",
#                 "pandas>=2.2", "mcp>=2.3", "bm25s>=0.3", "model2vec>=0.10", "numpy>=2.0"]
# ///
# PulseNet as an HTTP service, so a NOC dashboard or another system can use it.
#   PULSENET_API_KEYS=dev-key-1 uv run pulsenet/api.py --port 8800
#   the operations dashboard (pulsenet/ui/) is not in this repository; it runs on the Hugging Face Space
#
#   curl -s localhost:8800/v1/chat -H "X-API-Key: dev-key-1" -H "Content-Type: application/json" \
#        -d '{"message": "What is wrong with the network?"}'          -> {"job_id": ...}
#   curl -s localhost:8800/v1/jobs/<job_id> -H "X-API-Key: dev-key-1"   -> steps, pending approval, answer
#   curl -s localhost:8800/v1/jobs/<job_id>/approval -H "X-API-Key: dev-key-1" -H "Content-Type: application/json" \
#        -d '{"approve": true}'

import argparse
import json
import math
import os
import sys
import threading
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import uvicorn  # noqa: E402
from fastapi import Depends, FastAPI, Header, HTTPException  # noqa: E402
from fastapi.responses import RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import agent  # noqa: E402
import agentkit as K  # noqa: E402
import guards  # noqa: E402
import memory  # noqa: E402
from network import Network  # noqa: E402

API_KEYS = {k.strip() for k in os.getenv("PULSENET_API_KEYS", "dev-key-1").split(",") if k.strip()}
TRACES = K.lab_dir("pulsenet") / "traces.jsonl"
APPROVAL_TIMEOUT_S = 300  # an approval nobody answers counts as "no"
# small moving noise on the readings the dashboard shows, so it looks like live telemetry (never stored)
NOISE = {"utilisation_pct": 1.5, "prb_dl_pct": 2, "inlet_temp_c": 0.15, "uplink_mbps": 1.2, "used_gbps": 4,
         "cpu_pct": 3}

app = FastAPI(title="PulseNet API", version="1.0.0")
state = {"net": None, "mcp": None, "history": []}
jobs = {}
one_at_a_time = threading.Lock()


def check_key(x_api_key: str = Header(default="")):
    if x_api_key not in API_KEYS:
        raise HTTPException(401, "missing or wrong X-API-Key")


class Job:
    # one request to the agent, run in the background so the caller can approve changes while it waits
    def __init__(self, message):
        self.id, self.message, self.started = uuid.uuid4().hex[:8], message, time.time()
        self.steps, self.pending, self.final, self.done = [], None, None, False
        self._answered, self._approved = threading.Event(), False

    def on_event(self, e):
        self.steps.append({"kind": e.kind, "text": e.text[:500], "tool": e.data.get("name")})

    def approve(self, name, args):
        self.pending = {"tool": name, "args": args}
        self._answered.wait(APPROVAL_TIMEOUT_S)
        approved, self.pending, self._approved = self._approved, None, False
        self._answered.clear()
        self.steps.append({"kind": "approval", "text": f"{name}: {'approved' if approved else 'rejected'}"})
        return approved

    def answer(self, approved):
        self._approved = approved
        self._answered.set()

    def run(self):
        K.print_event = self.on_event  # the course loop prints every step; we keep them for the caller
        try:
            result = agent.run(self.message, state["net"], state["mcp"], history=agent.compact(state["history"]),
                               approve=self.approve)
            self.final = result.final or f"(stopped: {result.stopped})"
            state["history"] = result.state[1:]
            memory.write_handover(state["net"])
        except Exception as e:  # noqa: BLE001 - report the problem to the caller
            self.final = f"error: {type(e).__name__}: {str(e)[:300]}"
        finally:
            with TRACES.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"job": self.id, "message": self.message, "steps": self.steps,
                                    "final": self.final}, ensure_ascii=False) + "\n")
            self.done = True
            one_at_a_time.release()


class ChatIn(BaseModel):
    message: str


class ApprovalIn(BaseModel):
    approve: bool


@app.get("/health")
def health():
    return {"ok": True, "model": K.MODEL}


@app.post("/v1/chat", dependencies=[Depends(check_key)])
def chat(body: ChatIn):
    if not one_at_a_time.acquire(blocking=False):
        raise HTTPException(409, "PulseNet is still working on the previous request")
    job = Job(body.message)
    jobs[job.id] = job
    threading.Thread(target=job.run, daemon=True).start()
    return {"job_id": job.id}


@app.get("/v1/jobs/{job_id}", dependencies=[Depends(check_key)])
def job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "unknown job")
    return {"id": job.id, "message": job.message, "steps": job.steps, "pending_approval": job.pending,
            "answer": job.final, "done": job.done}


@app.get("/v1/jobs", dependencies=[Depends(check_key)])
def recent_jobs():
    # newest first, so the controller page can show a change waiting for approval from any client
    latest = sorted(jobs.values(), key=lambda j: j.started, reverse=True)[:10]
    return [job_status(j.id) for j in latest]


@app.post("/v1/jobs/{job_id}/approval", dependencies=[Depends(check_key)])
def approval(job_id: str, body: ApprovalIn):
    job = jobs.get(job_id)
    if not job or not job.pending:
        raise HTTPException(409, "nothing is waiting for approval")
    job.answer(body.approve)
    return {"ok": True}


@app.get("/v1/alarms", dependencies=[Depends(check_key)])
def alarms():
    return state["net"].get_overview()


@app.get("/v1/intents", dependencies=[Depends(check_key)])
def intents():
    return state["net"].check_intents()


@app.get("/v1/audit", dependencies=[Depends(check_key)])
def audit():
    return state["net"].sql("SELECT * FROM audit_log ORDER BY ts")


def live(a, now):
    # the stored reading plus a little noise; down or quarantined assets stay flat
    if a["status"] in ("down", "quarantined"):
        return a
    seed = sum(map(ord, a["asset_id"]))
    for key, size in NOISE.items():
        value = a["metrics"].get(key)
        if isinstance(value, (int, float)) and value > 0:
            wobble = size * math.sin(now / 7 + seed) * math.cos(now / 13 + seed / 3)
            a["metrics"][key] = round(max(0, value + wobble), 1)
    return a


@app.get("/v1/assets", dependencies=[Depends(check_key)])
def assets():
    now = time.time()
    rows = [live(a, now) for a in state["net"]._all()]
    for a in rows:
        a.pop("description", None)  # device text is for the agent's tools, not the dashboard
    return rows


@app.get("/v1/logs", dependencies=[Depends(check_key)])
def logs():
    return state["net"].sql("SELECT ts, asset_id, level, message FROM logs ORDER BY ts")


@app.get("/v1/tickets", dependencies=[Depends(check_key)])
def tickets():
    return state["net"].sql("SELECT * FROM tickets ORDER BY ticket_id")


@app.get("/v1/meta", dependencies=[Depends(check_key)])
def meta():
    rows = {r["key"]: json.loads(r["value"]) for r in state["net"].sql("SELECT key, value FROM meta")}
    return {"now": "2026-11-02T09:30", "model": K.MODEL, "districts": rows.get("districts", {}),
            "traffic_profile": rows.get("traffic_profile", {}), "max_steps": agent.MAX_STEPS,
            "max_cost": agent.MAX_COST, "critical_prefixes": list(guards.CRITICAL)}


@app.post("/v1/reset", dependencies=[Depends(check_key)])
def reset():
    # back to Monday 09:30, for a fresh demo
    if not one_at_a_time.acquire(blocking=False):
        raise HTTPException(409, "PulseNet is still working on a request")
    try:
        state["net"] = Network(state["workdir"], reset=True)
        state["history"] = []
        memory.clear()
    finally:
        one_at_a_time.release()
    return {"ok": True}


UI = HERE / "ui"  # the dashboard, when it is installed next to the API (as on the Hugging Face Space)
if UI.exists():
    app.mount("/ui", StaticFiles(directory=UI, html=True), name="ui")


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/ui/" if UI.exists() else "/docs")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.getenv("PORT", 8800)))
    ap.add_argument("--host", default="127.0.0.1", help="0.0.0.0 inside a container")
    args = ap.parse_args()
    workdir = K.lab_dir("pulsenet/api", reset=True)
    state["workdir"], state["net"] = workdir, Network(workdir)
    state["mcp"] = K.MCPBridge(agent.mcp_server(workdir)).open()
    print(f"PulseNet API on http://{args.host}:{args.port}  (docs: /docs)")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
