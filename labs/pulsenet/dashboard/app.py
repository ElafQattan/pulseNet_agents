# /// script
# requires-python = ">=3.11"
# dependencies = ["fastapi>=0.150", "uvicorn>=0.40", "openai>=3.30", "pydantic>=2.12", "python-dotenv>=1.1",
#                 "pandas>=2.2", "mcp>=2.3"]
# ///
# PulseNet control-center dashboard: run from labs/ and open http://127.0.0.1:8000
#   uv run pulsenet/dashboard/app.py

import json
import sys
import threading
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(PROJECT.parent))  # agentkit (course library)
sys.path.insert(0, str(PROJECT))         # agent, city

import uvicorn  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import agent  # noqa: E402
import agentkit as K  # noqa: E402
from city import City  # noqa: E402

app = FastAPI(title="PulseNet")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

# one technician, one city, one conversation at a time
world = {"city": None, "mcp": None, "history": []}
jobs = {}
busy = threading.Lock()


def start_city():
    if world["mcp"]:
        world["mcp"].close()
    workdir = K.lab_dir("pulsenet/dashboard", reset=True)  # always start from the same broken city
    world["city"] = City(workdir)
    world["mcp"] = K.MCPBridge(agent.mcp_server(workdir)).open()
    world["history"] = []


# ---------------------------------------------------------------- one agent run, followed live by the page
class Job:
    def __init__(self, message):
        self.id = uuid.uuid4().hex[:8]
        self.message = message
        self.events = []
        self.pending = None  # an approval waiting for the technician
        self.final = None
        self.done = False
        self._answer = threading.Event()
        self._approved = False

    def on_event(self, e):
        text = e.text if len(e.text) < 600 else e.text[:600] + " …"
        self.events.append({"kind": e.kind, "text": text})

    def approve(self, name, args):
        # called by the agent loop before a change; waits for the button on the page (5 minutes at most)
        self.pending = {"tool": name, "args": args}
        self._answer.wait(timeout=300)
        self.pending = None
        self._answer.clear()
        approved, self._approved = self._approved, False
        self.events.append({"kind": "approval", "text": "approved" if approved else "rejected"})
        return approved

    def answer(self, approved):
        self._approved = approved
        self._answer.set()

    def run(self):
        K.print_event = self.on_event  # the course loop prints each step; we collect them for the page
        try:
            result = agent.run(self.message, world["city"], world["mcp"], history=agent.compact(world["history"]),
                               approve=self.approve)
            self.final = result.final or f"(stopped: {result.stopped})"
            world["history"] = result.state[1:]
        except Exception as e:  # noqa: BLE001 - show the problem in the chat instead of failing silently
            self.final = f"Something went wrong: {type(e).__name__}: {str(e)[:300]}"
        finally:
            self.done = True
            busy.release()


# ---------------------------------------------------------------- API
class ChatIn(BaseModel):
    message: str


class ApprovalIn(BaseModel):
    approve: bool


@app.get("/")
def index():
    return FileResponse(HERE / "static" / "index.html")


@app.get("/api/state")
def state():
    c = world["city"]
    devices = c.sql("SELECT device_id, name, kind, district, status, last_seen, battery_pct FROM devices "
                    "ORDER BY district, device_id")
    weather = json.loads(c.sql("SELECT metrics FROM devices WHERE device_id = 'CENTER-WEATHER'")[0]["metrics"])
    return {"time": "Sunday 1 November 2026 · 09:00", "weather": weather, "devices": devices,
            "alerts": c.alerts(), "tickets": c.sql("SELECT * FROM tickets ORDER BY ticket_id DESC"),
            "logs": c.sql("SELECT * FROM logs ORDER BY rowid DESC LIMIT 25")}


@app.get("/api/devices/{device_id}")
def device(device_id: str):
    try:
        return world["city"].get_device_status(device_id)
    except Exception as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/chat")
def chat(body: ChatIn):
    if not busy.acquire(blocking=False):
        raise HTTPException(409, "PulseNet is still working on the previous message.")
    job = Job(body.message.strip())
    jobs[job.id] = job
    threading.Thread(target=job.run, daemon=True).start()
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = jobs.get(job_id) or {}
    if not job:
        raise HTTPException(404, "unknown job")
    return {"events": job.events, "pending": job.pending, "final": job.final, "done": job.done}


@app.post("/api/jobs/{job_id}/approval")
def approval(job_id: str, body: ApprovalIn):
    job = jobs.get(job_id)
    if not job or not job.pending:
        raise HTTPException(409, "nothing is waiting for approval")
    job.answer(body.approve)
    return {"ok": True}


@app.post("/api/reset")
def reset():
    if not busy.acquire(blocking=False):
        raise HTTPException(409, "Wait until PulseNet finishes.")
    try:
        start_city()
    finally:
        busy.release()
    return {"ok": True}


if __name__ == "__main__":
    start_city()
    print("PulseNet dashboard on http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
