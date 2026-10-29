# `pulsenet/`: the code, file by file

This folder holds the whole agent. The [main README](../README.md) explains the design and the results. This page
covers the details: what each file does, the full tool list, the memory format, the guards and the API.

## Files

| File | Role |
|---|---|
| [`agent.py`](agent.py) | the harness: builds the prompt, connects the tools, guards, budgets and memory; terminal chat (`ask`, `chat`, `chat --forget`) |
| [`AGENTS.md`](AGENTS.md) | the system prompt: role, autonomy level L3, network map, closed-loop method, answer shape, rules |
| [`PLAYBOOK.md`](PLAYBOOK.md) | fault → exact action rules, added after the error analysis (configuration B) |
| [`guards.py`](guards.py) | deny list, approval hook, result cap and audit log |
| [`memory.py`](memory.py) | shift handover written after every turn, read at the start of the next session |
| [`network.py`](network.py) | the simulated network (SQLite) and its 12 tools |
| [`network_mcp.py`](network_mcp.py) | MCP server that exposes 10 of the network tools |
| [`knowledge.py`](knowledge.py) | RAG: BM25, embeddings (`potion-retrieval-32M`) and hybrid search with reciprocal rank fusion |
| [`fetch_standards.py`](fetch_standards.py) | downloads 6 ITU-T / ETSI standards from the GSMA datasets on Hugging Face and cleans the text |
| [`prepare_data.py`](prepare_data.py) | builds `data/network.sqlite` from `network.json` and `logs.txt` |
| [`api.py`](api.py) | HTTP API (FastAPI) with API keys, approvals and traces |
| [`evaluate.py`](evaluate.py) · [`tasks.jsonl`](tasks.jsonl) | the 21-task evaluation and its graders |
| [`eval_retrieval.py`](eval_retrieval.py) | the 24-question retrieval test, with no model involved |
| [`attack.py`](attack.py) | the prompt-injection experiment, run without and with the defences |
| [`plot_results.py`](plot_results.py) | draws the charts in `docs/images/` |
| `data/` | `network.json` (40 assets, intents, traffic profile), `logs.txt` (the morning timeline), `knowledge/` (12 runbooks, 8 incident reports; the standards are downloaded) |
| `results/` | evaluation, retrieval and attack outputs, described in [results/README.md](results/README.md) |

## All tools

| Tool | What it does | Type | Over MCP | Approval |
|---|---|---|---|---|
| `get_overview` | alarms sorted by severity, counts per district | read | ✅ | |
| `check_intents` | which goals are violated, and by which assets | read | ✅ | |
| `list_assets` · `get_asset` | inventory and full status of one asset | read | ✅ | |
| `trace_path` | hop-by-hop path from an asset to the core | read | ✅ | |
| `impact_of` | blast radius: everything that depends on an asset | read | ✅ | |
| `search_logs` | today's logs | read | ✅ | |
| `forecast` | state later today (traffic profile, battery and temperature trends) | read | ✅ | |
| `update_config` | `second_carrier`, `energy_saving`, `state` (backup link), `migrate_to` (workloads), `network_access` (quarantine) | **change** | ✅ | ✅ |
| `restart_asset` | restart a cell site or IoT gateway | **change** | ✅ | ✅ |
| `search_knowledge` | RAG over runbooks, incidents and standards | read | | |
| `open_ticket` · `list_tickets` | hand work to a field team; avoid duplicates | ticket | | |

The MCP server runs as its own process over stdio (`uv run network_mcp.py --workdir ...`), the way a real
network-management platform would expose an API. `--http` serves it over HTTP instead.

## Memory format

`memory.py` builds the handover from the network's own records (not from the chat), caps it at 2,000 characters and
saves it to `artifacts/pulsenet/shift_memory.md`:

```
## Handover from the previous session
Changes applied: BACKUP-WAVE-1: state=enabled
Open tickets: TCK-0001 FIBER-AZIZIYAH-QUBA (fiber, urgent)
Intents still violated: INT-1 by SITE-AZIZIYAH-02, SITE-UYUN-03; INT-3 by EDGE-DC-UYUN; INT-4 by SITE-SULTANAH-02
```

`chat` continues from it; `chat --forget` clears it and resets the network.

## Guards and budgets

| Guard | Where | Rule |
|---|---|---|
| Deny list | `guards.permission` + the tool itself | assets starting with `CORE-`, `IGW-`, `RAIL-`, `TRAFFIC-`, `EMERGENCY-` can never be changed |
| Approval | `guards.needs_approval` (`before_tool` hook) | every `update_config` and `restart_asset` asks the engineer; a "no" goes back to the model as an error message |
| Result cap | `guards.cap_and_audit` | tool results over 6,000 characters are cut |
| Audit | `guards.cap_and_audit` | every call goes to `artifacts/pulsenet/audit.jsonl` |
| Spotlighting | `network.untrusted` | text written by devices is wrapped in `<device_text>` tags |
| Budgets | `agent.py` | 14 tool rounds, $0.05 per request, chat history kept to the last 24 messages |

## API

```bash
uv run pulsenet/api.py        # http://127.0.0.1:8800, interactive docs at /docs
```

Every request needs an `X-API-Key` header (keys from `PULSENET_API_KEYS`).

| Endpoint | Purpose |
|---|---|
| `GET /health` | liveness check |
| `POST /v1/chat` | send a message; returns a job ID |
| `GET /v1/jobs/{id}` | steps so far, a pending approval if any, and the answer |
| `POST /v1/jobs/{id}/approval` | approve or reject the pending change (times out after 300 s) |
| `GET /v1/alarms` · `/v1/intents` · `/v1/audit` | network state and the audit log |

Each job is saved as a trace in `artifacts/pulsenet/traces.jsonl`.
