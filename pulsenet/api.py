# /// script
# requires-python = ">=3.11"
# dependencies = ["fastapi>=0.150", "uvicorn>=0.40", "openai>=3.30", "pydantic>=2.12", "python-dotenv>=1.1",
#                 "pandas>=2.2", "mcp>=2.3", "bm25s>=0.3", "model2vec>=0.10", "numpy>=2.0"]
# ///
# PulseNet as an HTTP service, so a NOC dashboard or another system can use it.
#   PULSENET_API_KEYS=dev-key-1 uv run pulsenet/api.py --port 8800
#
#   curl -s localhost:8800/v1/chat -H "X-API-Key: dev-key-1" -H "Content-Type: application/json" \
#        -d '{"message": "What is wrong with the network?"}'          -> {"job_id": ...}
#   curl -s localhost:8800/v1/jobs/<job_id> -H "X-API-Key: dev-key-1"   -> steps, pending approval, answer
#   curl -s localhost:8800/v1/jobs/<job_id>/approval -H "X-API-Key: dev-key-1" -H "Content-Type: application/json" \
#        -d '{"approve": true}'

import argparse
import json
import os
import sys
import threading
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import uvicorn  # noqa: E402
from fastapi import Depends, FastAPI, Header, HTTPException  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import agent  # noqa: E402
import agentkit as K  # noqa: E402
import memory  # noqa: E402
from network import Network  # noqa: E402

API_KEYS = {k.strip() for k in os.getenv("PULSENET_API_KEYS", "dev-key-1").split(",") if k.strip()}
TRACES = K.lab_dir("pulsenet") / "traces.jsonl"
APPROVAL_TIMEOUT_S = 300  # an approval nobody answers counts as "no"

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
        self.id, self.message = uuid.uuid4().hex[:8], message
        self.steps, self.pending, self.final, self.done = [], None, None, False
        self._answered, self._approved = threading.Event(), False

    def on_event(self, e):
        self.steps.append({"kind": e.kind, "text": e.text[:500]})

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
    return {"steps": job.steps, "pending_approval": job.pending, "answer": job.final, "done": job.done}


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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8800)
    args = ap.parse_args()
    workdir = K.lab_dir("pulsenet/api", reset=True)
    state["net"] = Network(workdir)
    state["mcp"] = K.MCPBridge(agent.mcp_server(workdir)).open()
    print(f"PulseNet API on http://127.0.0.1:{args.port}  (docs: /docs)")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
