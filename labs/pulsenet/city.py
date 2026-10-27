import json
import math
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Literal

import prepare_city

HERE = Path(__file__).resolve().parent
TEMPLATE = prepare_city.DB
RUNBOOKS = HERE / "data" / "runbooks"
NOW = "2026-11-01T09:00"  # the clock is fixed so every run sees the same city

# settings PulseNet may change, and the values each one accepts
ALLOWED_SETTINGS = {
    "time_sync": ["ntp", "local_rtc"],
    "reconnect_strategy": ["exponential_jitter", "fixed_5s"],
    "network_access": ["normal", "quarantine"],
}


class ToolError(Exception):
    # a mistake the model should read and recover from (wrong ID, blocked action, bad value)
    pass


# ---------------------------------------------------------------- runbook search (the RAG part)
def load_runbooks():
    docs = []
    for path in sorted(RUNBOOKS.glob("*.md")):
        head, body = path.read_text(encoding="utf-8")[3:].split("---", 1)
        meta = dict(line.split(": ", 1) for line in head.strip().splitlines())
        docs.append({"id": meta["id"], "title": meta["title"], "keywords_ar": meta.get("keywords_ar", ""),
                     "text": body.strip()})
    return docs


def runbook_chunks():
    # one chunk per "## " section, so a search returns a short focused passage
    chunks = []
    for doc in load_runbooks():
        for section in re.split(r"\n(?=## )", doc["text"]):
            chunks.append({"runbook_id": doc["id"], "title": doc["title"], "text": section.strip(),
                           "search_text": f"{doc['title']} {doc['keywords_ar']} {section}"})
    return chunks


def words(text):
    return re.findall(r"\w+", text.lower())


def bm25_search(query, k=3):
    # BM25: a word scores higher when it is rare across chunks and frequent in this chunk
    chunks = runbook_chunks()
    docs = [words(c["search_text"]) for c in chunks]
    avg_len = sum(len(d) for d in docs) / len(docs)
    scores = []
    for chunk, doc in zip(chunks, docs):
        score = 0.0
        for w in set(words(query)):
            n_with_w = sum(1 for d in docs if w in d)
            if n_with_w == 0:
                continue
            idf = math.log(1 + (len(docs) - n_with_w + 0.5) / (n_with_w + 0.5))
            tf = doc.count(w)
            score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * len(doc) / avg_len))
        if score > 0:
            scores.append((score, chunk))
    scores.sort(key=lambda s: -s[0])
    return [c for _, c in scores[:k]]


# ---------------------------------------------------------------- the city and its tools
class City:
    def __init__(self, workdir=None, reset=True):
        # every run works on its own copy of the database, so changes never touch the template
        if not TEMPLATE.exists():
            prepare_city.build()
        if workdir is None:
            self.db = TEMPLATE
        else:
            Path(workdir).mkdir(parents=True, exist_ok=True)
            self.db = Path(workdir) / "city.sqlite"
            if reset or not self.db.exists():
                shutil.copy(TEMPLATE, self.db)

    def sql(self, query, params=()):
        con = sqlite3.connect(self.db)
        con.row_factory = sqlite3.Row
        try:
            rows = [dict(r) for r in con.execute(query, params)]
            con.commit()
            return rows
        finally:
            con.close()

    def _device(self, device_id):
        rows = self.sql("SELECT * FROM devices WHERE device_id = ?", (device_id.strip().upper(),))
        if not rows:
            raise ToolError(f"No device {device_id!r}. IDs look like GW-NKH-01 or PK-WAH-03. Use list_devices.")
        d = rows[0]
        d["signal"], d["metrics"] = json.loads(d["signal"]), json.loads(d["metrics"])
        d["critical"] = bool(d["critical"])
        d["config"] = {r["setting"]: r["value"] for r in
                       self.sql("SELECT setting, value FROM config WHERE device_id = ?", (d["device_id"],))}
        return d

    def _set(self, device_id, **fields):
        for name, value in fields.items():
            if name in ("signal", "metrics"):
                value = json.dumps(value)
            self.sql(f"UPDATE devices SET {name} = ? WHERE device_id = ?", (value, device_id))

    def _log(self, device_id, level, message):
        self.sql("INSERT INTO logs VALUES (?,?,?,?)", (NOW, device_id, level, message))

    def _audit(self, action, detail):
        self.sql("INSERT INTO audit_log VALUES (?,?,?,?)", (NOW, "pulsenet", action, json.dumps(detail)))

    def _refuse_critical(self, d):
        if d["critical"]:
            raise ToolError(f"{d['device_id']} is a critical system ({d['type']}). PulseNet never changes it "
                            "(RB-06). Hand over with open_ticket instead.")

    # ================================================================ read tools
    def list_devices(self, district: Literal["NKH", "WAH", "RWD", "CC"] | None = None,
                     type: Literal["mqtt_broker", "lorawan_gateway", "streetlight", "parking_sensor", "water_meter",
                                   "camera", "traffic_controller"] | None = None,
                     status: Literal["online", "offline", "degraded", "quarantined"] | None = None) -> list[dict]:
        """List devices, optionally filtered. Returns ID, type, district, status and last_seen for each.

        Args:
            district: NKH (Al-Nakheel), WAH (Al-Waha), RWD (Al-Rawdah) or CC (Control Center).
            type: device type.
            status: online, offline, degraded or quarantined.
        """
        query, params = "SELECT device_id, type, district, status, last_seen FROM devices WHERE 1=1", []
        for column, value in (("district", district), ("type", type), ("status", status)):
            if value:
                query += f" AND {column} = ?"
                params.append(value)
        return self.sql(query + " ORDER BY device_id", params)

    def get_device_status(self, device_id: str) -> dict:
        """Full status of one device: status, last_seen, battery, signal, firmware, metrics, config and the
        description the device reports about itself.

        Args:
            device_id: e.g. "GW-NKH-01".
        """
        return self._device(device_id)

    def search_logs(self, query: str = "", device_id: str | None = None,
                    level: Literal["INFO", "WARN", "ERROR"] | None = None, limit: int = 20) -> list[dict]:
        """Search today's device logs, newest last.

        Args:
            query: words to look for in the message, e.g. "out of memory" (empty = any).
            device_id: only this device.
            level: only this level.
            limit: maximum lines (1-50).
        """
        sql, params = "SELECT ts, device_id, level, message FROM logs WHERE 1=1", []
        if device_id:
            sql += " AND device_id = ?"
            params.append(device_id.strip().upper())
        if level:
            sql += " AND level = ?"
            params.append(level)
        for w in query.split():
            sql += " AND (message LIKE ? OR device_id LIKE ?)"
            params += [f"%{w}%", f"%{w}%"]
        rows = self.sql(sql + " ORDER BY ts", params)
        return rows[-max(1, min(int(limit), 50)):] or [{"note": "No log line matched. Try fewer words."}]

    def search_runbooks(self, query: str) -> list[dict]:
        """Search the operations runbooks and the GSMA TS.34 guideline. Returns the best passages with their ID
        (cite it, e.g. RB-05). Works with English or Arabic.

        Args:
            query: the symptom or topic, e.g. "gateway offline" or "عاصفة إعادة الاتصال".
        """
        hits = bm25_search(query, k=3)
        if not hits:
            return [{"note": "No passage matched. Try other words, e.g. the device type and the symptom."}]
        return [{"runbook_id": h["runbook_id"], "title": h["title"], "text": h["text"]} for h in hits]

    # ================================================================ change tools
    def reboot_device(self, device_id: str) -> dict:
        """Restart one device or gateway. Devices behind a gateway are offline for about 3 minutes during its
        reboot. Never used on critical systems.

        Args:
            device_id: e.g. "GW-NKH-01".
        """
        d = self._device(device_id)
        self._refuse_critical(d)
        result = {"device_id": d["device_id"], "rebooted": True}

        if d["type"] == "lorawan_gateway":
            behind = self.sql("SELECT device_id FROM devices WHERE gateway_id = ?", (d["device_id"],))
            for row in behind:
                if self._device(row["device_id"])["status"] == "offline":
                    self._set(row["device_id"], status="online", last_seen=NOW)
            d["metrics"]["connected_devices"] = d["metrics"]["expected_devices"]
            self._set(d["device_id"], status="online", last_seen=NOW, metrics=d["metrics"])
            result["now"] = f"online, {len(behind)} of {len(behind)} devices connected"
        elif d["config"].get("time_sync") == "local_rtc":
            result["now"] = "online, but the clock reset again because time_sync is local_rtc"
        elif d["config"].get("reconnect_strategy") == "fixed_5s":
            result["now"] = "online, still retrying on a fixed 5 s timer"
        else:
            result["now"] = d["status"]

        self._log(d["device_id"], "INFO", "rebooted by PulseNet")
        self._audit("reboot_device", result)
        return result

    def update_config(self, device_ids: list[str],
                      setting: Literal["time_sync", "reconnect_strategy", "network_access"],
                      value: str) -> dict:
        """Change one setting on one or more devices.

        Args:
            device_ids: e.g. ["SL-WAH-03"] or ["PK-WAH-01", "PK-WAH-02"].
            setting: time_sync (ntp | local_rtc), reconnect_strategy (exponential_jitter | fixed_5s) or
                network_access (normal | quarantine).
            value: the new value, one of those listed for the setting.
        """
        if value not in ALLOWED_SETTINGS[setting]:
            raise ToolError(f"{setting} accepts only {ALLOWED_SETTINGS[setting]}, not {value!r}.")
        devices = [self._device(i) for i in device_ids]
        for d in devices:
            self._refuse_critical(d)
            if setting not in d["config"]:
                raise ToolError(f"{d['device_id']} ({d['type']}) has no setting {setting!r}. "
                                f"Its settings: {list(d['config'])}.")

        for d in devices:
            self.sql("UPDATE config SET value = ? WHERE device_id = ? AND setting = ?", (value, d["device_id"], setting))
            if setting == "time_sync" and value == "ntp":
                d["metrics"].update(device_clock=NOW, lamp="off")
                self._set(d["device_id"], metrics=d["metrics"])
            if setting == "reconnect_strategy" and value == "exponential_jitter":
                d["metrics"]["reconnects_last_hour"] = 1
                self._set(d["device_id"], status="online", metrics=d["metrics"])
            if setting == "network_access" and value == "quarantine":
                d["metrics"].update(uplink_mbps=0, external_connections=[])
                self._set(d["device_id"], status="quarantined", metrics=d["metrics"])
            self._log(d["device_id"], "INFO", f"config {setting}={value} set by PulseNet")

        # the broker recovers once no device is left on the fixed retry timer
        still_fixed = self.sql("SELECT count(*) AS n FROM config WHERE setting = 'reconnect_strategy' "
                               "AND value = 'fixed_5s'")[0]["n"]
        if setting == "reconnect_strategy" and still_fixed == 0:
            broker = self._device("BROKER-01")
            broker["metrics"].update(connect_attempts_per_min=45, cpu_pct=22)
            self._set("BROKER-01", status="online", metrics=broker["metrics"])

        result = {"changed": [d["device_id"] for d in devices], "setting": setting, "value": value}
        self._audit("update_config", result)
        return result

    def open_ticket(self, device_id: str, team: Literal["maintenance", "network", "security", "traffic"],
                    priority: Literal["low", "normal", "high", "urgent"], summary: str) -> dict:
        """Open a ticket for a field or specialist team. It changes nothing on the network.

        Args:
            device_id: the device the ticket is about.
            team: maintenance (batteries, antennas, hardware), network (gateways, backhaul), security
                (compromised devices, camera firmware) or traffic (anything on a traffic controller).
            priority: low, normal, high or urgent (see RB-08).
            summary: what is wrong, the evidence, and what the team should do.
        """
        d = self._device(device_id)
        n = self.sql("SELECT count(*) AS n FROM tickets")[0]["n"]
        ticket_id = f"TCK-{n + 1:04d}"
        self.sql("INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?)",
                 (ticket_id, NOW, d["device_id"], team, priority, summary, "open", "pulsenet"))
        self._audit("open_ticket", {"ticket_id": ticket_id, "device_id": d["device_id"], "team": team})
        return {"ticket_id": ticket_id, "device_id": d["device_id"], "team": team, "priority": priority,
                "status": "open"}

    MCP_TOOLS = ("list_devices", "get_device_status", "search_logs", "reboot_device", "update_config")
    LOCAL_TOOLS = ("search_runbooks", "open_ticket")
    CHANGE_TOOLS = ("reboot_device", "update_config")
