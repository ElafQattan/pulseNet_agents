import json
from pathlib import Path

# Shift memory: what one session leaves for the next one.
# At the end of a session the harness writes a short handover from the network's audit log, tickets and intents.
# At the start of the next session the handover is added to the system prompt, so PulseNet knows what was
# already done, what is still open, and does not repeat a change or open the same ticket twice.

MEMORY_FILE = Path(__file__).resolve().parents[1] / "artifacts" / "pulsenet" / "shift_memory.md"
MAX_CHARS = 2000  # the handover is a summary, never a full transcript (context budget)


def write_handover(net, path=MEMORY_FILE):
    changes = net.sql("SELECT ts, action, detail FROM audit_log ORDER BY ts")
    tickets = net.sql("SELECT ticket_id, asset_id, team, priority FROM tickets WHERE status = 'open'")
    open_goals = [i for i in net.check_intents() if not i["met"]]

    lines = ["## Handover from the previous session"]
    lines.append("Changes applied: " + (", ".join(_describe(c) for c in changes if c["action"] != "open_ticket")
                                        or "none"))
    lines.append("Open tickets: " + (", ".join(f"{t['ticket_id']} {t['asset_id']} ({t['team']}, {t['priority']})"
                                               for t in tickets) or "none"))
    lines.append("Intents still violated: " + (", ".join(f"{i['id']} by {', '.join(i['violated_by'])}"
                                                         for i in open_goals) or "none"))
    text = "\n".join(lines)[:MAX_CHARS]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def read_handover(path=MEMORY_FILE):
    return path.read_text(encoding="utf-8")[:MAX_CHARS] if path.exists() else ""


def clear(path=MEMORY_FILE):
    path.unlink(missing_ok=True)


def _describe(change):
    d = json.loads(change["detail"])
    if change["action"] == "update_config":
        return f"{', '.join(d['changed'])}: {d['setting']}={d['value']}"
    return f"{change['action']} {d.get('asset_id', '')}".strip()
