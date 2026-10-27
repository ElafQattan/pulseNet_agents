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

District = Literal["QUBA", "AZIZIYAH", "SULTANAH", "UYUN", "CENTER"]
Kind = Literal["gateway", "light", "cabinet", "parking", "water", "drain", "pump", "tunnel", "camera", "traffic",
               "mqtt", "weather"]
Team = Literal["network", "maintenance", "electrical", "drainage", "traffic", "security"]
Priority = Literal["low", "normal", "high", "urgent"]

CRITICAL_KINDS = ("traffic", "tunnel", "mqtt")  # never changed by PulseNet (RB-06)

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
        docs.append({"id": meta["id"], "title": meta["title"], "keywords": meta.get("keywords", ""),
                     "text": body.strip()})
    return docs


def runbook_chunks():
    # one chunk per "## " section, so a search returns a short focused passage
    chunks = []
    for doc in load_runbooks():
        for section in re.split(r"\n(?=## )", doc["text"]):
            chunks.append({"runbook_id": doc["id"], "title": doc["title"], "text": section.strip(),
                           "search_text": f"{doc['title']} {doc['keywords']} {section}"})
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
            raise ToolError(f"No device {device_id!r}. IDs look like QUBA-GATEWAY or UYUN-PARKING-03. "
                            "Use list_devices.")
        d = rows[0]
        d["signal"], d["metrics"] = json.loads(d["signal"]), json.loads(d["metrics"])
        d["critical"] = bool(d["critical"])
        d["config"] = {r["setting"]: r["value"] for r in
                       self.sql("SELECT setting, value FROM config WHERE device_id = ?", (d["device_id"],))}
        return d

    def _set(self, device_id, **fields):
        for name, value in fields.items():
            if name in ("signal", "metrics"):
                value = json.dumps(value, ensure_ascii=False)
            self.sql(f"UPDATE devices SET {name} = ? WHERE device_id = ?", (value, device_id))

    def _log(self, device_id, level, message):
        self.sql("INSERT INTO logs VALUES (?,?,?,?)", (NOW, device_id, level, message))

    def _audit(self, action, detail):
        self.sql("INSERT INTO audit_log VALUES (?,?,?,?)", (NOW, "pulsenet", action,
                                                            json.dumps(detail, ensure_ascii=False)))

    def _refuse_critical(self, d):
        if d["critical"]:
            raise ToolError(f"{d['device_id']} is a critical system ({d['kind']}). PulseNet never changes it "
                            "(RB-06). Hand over with open_ticket instead.")

    def alerts(self):
        # the monitoring rules a control-center dashboard would run; the agent still has to find the cause
        out = []

        def alert(severity, d, text):
            out.append({"severity": severity, "device_id": d["device_id"], "name": d["name"],
                        "district": d["district"], "alert": text})

        all_devices = [self._device(r["device_id"]) for r in self.sql("SELECT device_id FROM devices")]
        flooded = {d["district"] for d in all_devices
                   if d["kind"] == "tunnel" and d["metrics"]["water_level_cm"] >= d["metrics"]["warning_cm"]}
        for d in all_devices:
            m, kind = d["metrics"], d["kind"]
            if kind == "tunnel" and m["water_level_cm"] >= m["close_tunnel_cm"]:
                alert("urgent", d, f"water {m['water_level_cm']} cm, above close-tunnel level "
                                   f"{m['close_tunnel_cm']} cm, {m['trend']}")
            elif kind == "tunnel" and m["water_level_cm"] >= m["warning_cm"]:
                alert("high", d, f"water {m['water_level_cm']} cm, above warning level, {m['trend']}")
            if kind == "pump" and not m["running"]:
                alert("urgent" if d["district"] in flooded else "high", d, f"pump stopped ({m['trip_reason']})")
            if kind == "cabinet" and m["breaker"] == "open":
                alert("urgent" if m.get("trip_reason") == "earth_leakage" else "high", d,
                      f"breaker open ({m.get('trip_reason')}), {m.get('lights_powered', 0)} lights powered")
            if kind == "traffic" and m["mode"] != "normal_cycle":
                alert("urgent", d, f"signal in {m['mode']} since {m.get('since', '?')}")
            if kind == "traffic" and d["firmware"] < "tcx 2.3.0":
                alert("urgent", d, f"firmware {d['firmware']} matches advisory PN-SA-2026-014")
            if kind == "camera" and (m["external_connections"] or m["uplink_mbps"] > 5 * m["normal_uplink_mbps"]):
                alert("urgent", d, f"uplink {m['uplink_mbps']} Mbps (normal {m['normal_uplink_mbps']}), "
                                   f"external connections {m['external_connections']}")
            if kind == "gateway" and d["status"] == "offline":
                alert("high", d, f"gateway offline since {d['last_seen']}, "
                                 f"{m['expected_devices'] - m['connected_devices']} devices not reporting")
            if kind == "mqtt" and m["connect_attempts_per_min"] > 10 * m["normal_connect_attempts_per_min"]:
                alert("high", d, f"{m['connect_attempts_per_min']} connect attempts/min "
                                 f"(normal {m['normal_connect_attempts_per_min']}), cpu {m['cpu_pct']} %")
            if kind == "drain" and m["fill_pct"] >= 70:
                alert("high", d, f"storm drain {m['fill_pct']} % full, {m['trend']}")
            if kind == "light" and m.get("lamp") == "on":
                alert("normal", d, "lamp on during the day")
            if kind == "parking" and m.get("reconnects_last_hour", 0) > 100:
                alert("high", d, f"{m['reconnects_last_hour']} reconnects in the last hour")
            if d["battery_pct"] is not None and d["battery_pct"] < 10:
                alert("high" if d["battery_pct"] < 5 else "normal", d, f"battery {d['battery_pct']} %")
            if d["signal"] and d["signal"].get("coverage_class") == "CE2":
                alert("normal", d, f"weak NB-IoT signal (RSRP {d['signal']['rsrp_dbm']} dBm, CE2)")
        order = {"urgent": 0, "high": 1, "normal": 2}
        return sorted(out, key=lambda a: (order[a["severity"]], a["device_id"]))

    # ================================================================ read tools
    def get_overview(self) -> dict:
        """The situation right now: active alerts sorted by severity (urgent first), device counts per district
        and status, the weather, and how many tickets are open. Start here for general questions.
        """
        rows = self.sql("SELECT district, status, count(*) AS n FROM devices GROUP BY district, status")
        counts = {}
        for r in rows:
            counts.setdefault(r["district"], {})[r["status"]] = r["n"]
        weather = json.loads(self.sql("SELECT metrics FROM devices WHERE device_id = 'CENTER-WEATHER'")[0]["metrics"])
        open_tickets = self.sql("SELECT count(*) AS n FROM tickets WHERE status = 'open'")[0]["n"]
        return {"time": NOW, "alerts": self.alerts(), "counts_by_district": counts, "weather": weather,
                "open_tickets": open_tickets,
                "note": "alerts show symptoms, not causes; offline devices behind an offline gateway or a tripped "
                        "cabinet are covered by that one alert"}

    def list_devices(self, district: District | None = None, kind: Kind | None = None,
                     status: Literal["online", "offline", "degraded", "stopped", "tripped", "quarantined"] | None = None
                     ) -> list[dict]:
        """List devices, optionally filtered. Returns ID, name, kind, district, status and last_seen.

        Args:
            district: QUBA, AZIZIYAH, SULTANAH, UYUN or CENTER (control center).
            kind: gateway, light (streetlight), cabinet (streetlight power cabinet), parking, water (meter),
                drain (storm drain), pump (tunnel pump), tunnel (tunnel water level), camera, traffic, mqtt, weather.
            status: online, offline, degraded, stopped, tripped or quarantined.
        """
        query, params = "SELECT device_id, name, kind, district, status, last_seen FROM devices WHERE 1=1", []
        for column, value in (("district", district), ("kind", kind), ("status", status)):
            if value:
                query += f" AND {column} = ?"
                params.append(value)
        return self.sql(query + " ORDER BY device_id", params)

    def get_device_status(self, device_id: str) -> dict:
        """Full status of one device: status, last_seen, battery, signal, firmware, readings (metrics), settings
        (config), its gateway or power cabinet, and the description the device reports about itself.

        Args:
            device_id: e.g. "QUBA-GATEWAY" or "QUBA-PUMP-01".
        """
        return self._device(device_id)

    def search_logs(self, query: str = "", device_id: str | None = None,
                    level: Literal["INFO", "WARN", "ERROR"] | None = None, limit: int = 20) -> list[dict]:
        """Search today's device logs, oldest first.

        Args:
            query: words to look for in the message or device ID, e.g. "out of memory" or "QUBA" (empty = any).
            device_id: only this device.
            level: only this level.
            limit: maximum lines, the most recent ones (1-50).
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
        (cite it, e.g. RB-09).

        Args:
            query: the symptom or topic, e.g. "pump stopped tunnel" or "breaker tripped after rain".
        """
        hits = bm25_search(query, k=3)
        if not hits:
            return [{"note": "No passage matched. Try other words, e.g. the device kind and the symptom."}]
        return [{"runbook_id": h["runbook_id"], "title": h["title"], "text": h["text"]} for h in hits]

    def list_tickets(self, status: Literal["open", "closed"] | None = "open") -> list[dict]:
        """Tickets already opened today, so you don't open the same one twice.

        Args:
            status: open or closed (default open).
        """
        rows = self.sql("SELECT * FROM tickets WHERE ? IS NULL OR status = ? ORDER BY ticket_id", (status, status))
        return rows or [{"note": f"No {status or ''} tickets."}]

    # ================================================================ change tools
    def reboot_device(self, device_id: str) -> dict:
        """Restart or reset one device: a gateway, a sensor, a streetlight controller, a pump controller after a
        trip, or a power cabinet after an overload trip. Devices behind a gateway are offline for about
        3 minutes during its reboot. Never used on critical systems.

        Args:
            device_id: e.g. "QUBA-GATEWAY" or "QUBA-PUMP-01".
        """
        d = self._device(device_id)
        self._refuse_critical(d)
        m, result = d["metrics"], {"device_id": d["device_id"], "rebooted": True}

        if d["kind"] == "cabinet" and m.get("trip_reason") == "earth_leakage":
            raise ToolError(f"{d['device_id']} tripped on earth leakage ({m['earth_leakage_ma_at_trip']} mA). "
                            "Resetting it remotely can electrify the poles (RB-11). Electricians must test it on site: "
                            "open_ticket, team electrical, priority urgent.")
        if d["kind"] == "pump" and m.get("trip_reason") in ("overcurrent", "motor_overheat"):
            raise ToolError(f"{d['device_id']} tripped on {m['trip_reason']}. Do not reset remotely (RB-09): "
                            "open_ticket, team drainage, priority urgent.")

        if d["kind"] == "gateway":
            behind = self.sql("SELECT device_id FROM devices WHERE gateway_id = ? AND status = 'offline' "
                              "AND (cabinet_id IS NULL OR cabinet_id NOT IN "
                              "(SELECT device_id FROM devices WHERE status = 'tripped'))", (d["device_id"],))
            for row in behind:
                self._set(row["device_id"], status="online", last_seen=NOW)
            m["connected_devices"] = m["expected_devices"] - self.sql(
                "SELECT count(*) AS n FROM devices WHERE gateway_id = ? AND status = 'offline'", (d["device_id"],))[0]["n"]
            self._set(d["device_id"], status="online", last_seen=NOW, metrics=m)
            result["now"] = f"online, {m['connected_devices']} of {m['expected_devices']} devices connected"
        elif d["kind"] == "pump" and m.get("trip_reason") == "undervoltage":
            m.update(running=True, trip_reason=None, flow_l_s=55)
            self._set(d["device_id"], status="online", metrics=m)
            tunnel = self._device(d["device_id"].replace("PUMP-01", "TUNNEL-01").replace("PUMP-02", "TUNNEL-01"))
            tunnel["metrics"].update(trend="falling", expected_below_20cm_in_min=35)
            self._set(tunnel["device_id"], metrics=tunnel["metrics"])
            result["now"] = "pump running at 55 l/s; with both pumps the tunnel level is now falling"
        elif d["kind"] == "cabinet" and m.get("trip_reason") == "overload":
            m.update(breaker="closed", trip_reason=None)
            self._set(d["device_id"], status="online", metrics=m)
            result["now"] = "breaker closed"
        elif d["config"].get("time_sync") == "local_rtc":
            result["now"] = "online, but the clock reset again because time_sync is local_rtc"
        elif d["config"].get("reconnect_strategy") == "fixed_5s":
            result["now"] = "online, still retrying on a fixed 5 s timer"
        else:
            result["now"] = d["status"]

        self._log(d["device_id"], "INFO", "restarted by PulseNet")
        self._audit("reboot_device", result)
        return result

    def update_config(self, device_ids: list[str],
                      setting: Literal["time_sync", "reconnect_strategy", "network_access"],
                      value: str) -> dict:
        """Change one setting on one or more devices.

        Args:
            device_ids: e.g. ["UYUN-LIGHT-03"] or ["UYUN-PARKING-01", "UYUN-PARKING-02"].
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
                raise ToolError(f"{d['device_id']} ({d['kind']}) has no setting {setting!r}. "
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

        # the central platform recovers once no device is left on the fixed retry timer
        still_fixed = self.sql("SELECT count(*) AS n FROM config WHERE setting = 'reconnect_strategy' "
                               "AND value = 'fixed_5s'")[0]["n"]
        if setting == "reconnect_strategy" and still_fixed == 0:
            mqtt = self._device("CENTER-MQTT")
            mqtt["metrics"].update(connect_attempts_per_min=45, cpu_pct=22)
            self._set("CENTER-MQTT", status="online", metrics=mqtt["metrics"])

        result = {"changed": [d["device_id"] for d in devices], "setting": setting, "value": value}
        self._audit("update_config", result)
        return result

    def open_ticket(self, device_id: str, team: Team, priority: Priority, summary: str) -> dict:
        """Open a ticket for a field or specialist team. It changes nothing on the network.

        Args:
            device_id: the device the ticket is about.
            team: network (gateways, platform), maintenance (batteries, antennas, sensors), electrical (power
                cabinets, earth faults), drainage (storm drains, tunnel pumps), traffic (signals, closing roads and
                tunnels) or security (compromised devices, camera firmware).
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

    MCP_TOOLS = ("get_overview", "list_devices", "get_device_status", "search_logs", "reboot_device", "update_config")
    LOCAL_TOOLS = ("search_runbooks", "open_ticket", "list_tickets")
    CHANGE_TOOLS = ("reboot_device", "update_config")
