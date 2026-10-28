import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DB = DATA / "network.sqlite"

# the tables the agent's tools read from and write to
SCHEMA = """
CREATE TABLE assets (asset_id TEXT PRIMARY KEY, name TEXT, kind TEXT, district TEXT, uplink TEXT, status TEXT,
                     critical INTEGER, metrics TEXT, config TEXT, description TEXT);
CREATE TABLE logs (ts TEXT, asset_id TEXT, level TEXT, message TEXT);
CREATE TABLE tickets (ticket_id TEXT PRIMARY KEY, created TEXT, asset_id TEXT, team TEXT, priority TEXT,
                      summary TEXT, status TEXT, created_by TEXT);
CREATE TABLE audit_log (ts TEXT, actor TEXT, action TEXT, detail TEXT);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""


def read_logs(path):
    # each line looks like: 2026-11-02T08:47:02 SPUR-AZIZIYAH-02 ERROR loss of signal (duct D-114)
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            ts, asset, level, message = line.split(" ", 3)
            rows.append((ts, asset, level, message))
    return rows


def build(db=DB):
    data = json.loads((DATA / "network.json").read_text(encoding="utf-8"))
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    for a in data["assets"]:
        con.execute("INSERT INTO assets VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (a["asset_id"], a["name"], a["kind"], a["district"], a["uplink"], a["status"], int(a["critical"]),
                     json.dumps(a["metrics"]), json.dumps(a["config"]), a["description"]))
    con.executemany("INSERT INTO logs VALUES (?,?,?,?)", read_logs(DATA / "logs.txt"))
    for key in ("intents", "traffic_profile", "districts"):
        con.execute("INSERT INTO meta VALUES (?,?)", (key, json.dumps(data[key])))
    con.commit()
    con.close()
    print("wrote", db, "with", len(data["assets"]), "assets")
    return db


if __name__ == "__main__":
    build()
