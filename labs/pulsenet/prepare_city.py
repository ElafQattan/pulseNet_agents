import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DB = DATA / "city.sqlite"

# the tables the agent's tools read from and write to
SCHEMA = """
CREATE TABLE devices (device_id TEXT PRIMARY KEY, type TEXT, district TEXT, connectivity TEXT, gateway_id TEXT,
                      status TEXT, last_seen TEXT, battery_pct INTEGER, firmware TEXT, critical INTEGER,
                      signal TEXT, metrics TEXT, description TEXT);
CREATE TABLE config (device_id TEXT, setting TEXT, value TEXT, PRIMARY KEY (device_id, setting));
CREATE TABLE logs (ts TEXT, device_id TEXT, level TEXT, message TEXT);
CREATE TABLE tickets (ticket_id TEXT PRIMARY KEY, created TEXT, device_id TEXT, team TEXT, priority TEXT,
                      summary TEXT, status TEXT, created_by TEXT);
CREATE TABLE audit_log (ts TEXT, actor TEXT, action TEXT, detail TEXT);
"""


def read_logs(path):
    # each line looks like: 2026-11-01T06:42:10 GW-NKH-01 ERROR heartbeat to network server missed
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            ts, device, level, message = line.split(" ", 3)
            rows.append((ts, device, level, message))
    return rows


def build(db=DB):
    devices = json.loads((DATA / "devices.json").read_text(encoding="utf-8"))["devices"]
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)

    for d in devices:
        con.execute("INSERT INTO devices VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (d["device_id"], d["type"], d["district"], d["connectivity"], d["gateway_id"], d["status"],
                     d["last_seen"], d["battery_pct"], d["firmware"], int(d["critical"]),
                     json.dumps(d["signal"]), json.dumps(d["metrics"]), d["description"]))
        for setting, value in d["config"].items():
            con.execute("INSERT INTO config VALUES (?,?,?)", (d["device_id"], setting, value))

    con.executemany("INSERT INTO logs VALUES (?,?,?,?)", read_logs(DATA / "logs.txt"))
    con.commit()
    con.close()
    print("wrote", db, "with", len(devices), "devices")
    return db


if __name__ == "__main__":
    build()
