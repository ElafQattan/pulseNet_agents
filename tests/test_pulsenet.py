# Offline tests: no model is called. Run with  uv run --with pytest pytest -q
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pulsenet"))

import guards  # noqa: E402
import knowledge  # noqa: E402
import memory  # noqa: E402
from network import Network, ToolError  # noqa: E402


@pytest.fixture
def net(tmp_path):
    return Network(tmp_path)  # a fresh copy of the 09:30 network


# ---------------------------------------------------------------- the network and its tools
def test_one_cut_explains_several_alarms(net):
    alarmed = {a["asset_id"] for a in net.alarms()}
    assert {"FIBER-AZIZIYAH-QUBA", "SPUR-AZIZIYAH-02", "SITE-AZIZIYAH-02", "AGG-AZIZIYAH"} <= alarmed
    assert net.get_asset("SPUR-AZIZIYAH-02")["metrics"]["duct"] == "D-114"
    assert net.get_asset("FIBER-AZIZIYAH-QUBA")["metrics"]["duct"] == "D-114"


def test_all_intents_violated_at_start(net):
    assert all(not i["met"] for i in net.check_intents())


def test_backup_wavelength_restores_protection_and_peak(net):
    assert net.forecast("FIBER-KHALIDIYAH-UYUN")["utilisation_pct"] > 100
    net.update_config(["BACKUP-WAVE-1"], "state", "enabled")
    intents = {i["id"]: i["met"] for i in net.check_intents()}
    assert intents["INT-2"] and intents["INT-5"]
    assert net.forecast("FIBER-KHALIDIYAH-UYUN")["utilisation_pct"] <= 70


def test_trace_path_finds_the_cut_spur(net):
    hops = net.trace_path("SITE-AZIZIYAH-02")
    assert hops[1]["asset_id"] == "SPUR-AZIZIYAH-02" and hops[1]["status"] == "down"


def test_sleeping_cell_fixed_by_restart(net):
    net.restart_asset("SITE-UYUN-03")
    assert 0 not in net.get_asset("SITE-UYUN-03")["metrics"]["sectors"].values()


@pytest.mark.parametrize("call", [
    lambda n: n.restart_asset("CORE-R1"),
    lambda n: n.update_config(["TRAFFIC-CTRL"], "state", "enabled"),
    lambda n: n.restart_asset("SITE-SULTANAH-02"),             # on battery
    lambda n: n.update_config(["SITE-QUBA-01"], "state", "x"),  # value not allowed
    lambda n: n.get_asset("NO-SUCH-ASSET"),
])
def test_tools_refuse_unsafe_or_wrong_calls(net, call):
    with pytest.raises(ToolError):
        call(net)


def test_device_text_is_wrapped_as_data(net):
    text = net.get_asset("IOT-GW-KHALIDIYAH")["description"]
    assert text.startswith("<device_text>") and "AI OPERATOR" in text


# ---------------------------------------------------------------- harness guards
def test_critical_assets_are_denied_even_with_approval():
    assert guards.permission("restart_asset", {"asset_id": "CORE-R1"}) == "deny"
    assert guards.permission("update_config", {"asset_ids": ["SITE-QUBA-01", "TRAFFIC-CTRL"]}) == "deny"
    assert guards.permission("get_asset", {"asset_id": "CORE-R1"}) == "allow"  # reading is fine


def test_changes_wait_for_the_engineer():
    refuse = guards.needs_approval(lambda name, args: False)
    accept = guards.needs_approval(lambda name, args: True)
    assert "did not approve" in json.loads(refuse("restart_asset", {"asset_id": "SITE-UYUN-03"}))["error"]
    assert accept("restart_asset", {"asset_id": "SITE-UYUN-03"}) is None
    assert refuse("get_overview", {}) is None  # reads never ask


# ---------------------------------------------------------------- knowledge (RAG) and memory
@pytest.mark.parametrize("query, expected", [
    ("fiber cut roadworks shared duct", {"RB-01", "INC-2024-09"}),
    ("site on battery power cut", {"RB-04", "INC-2025-06"}),
    ("sector with zero users and no alarm", {"RB-05", "INC-2024-12"}),
    ("closed loop automation in ZSM", {"ETSI-ZSM-009-1", "ETSI-ZSM-009-2", "ETSI-ZSM-002"}),
])
def test_keyword_search_finds_the_right_document(query, expected):
    if not (knowledge.KNOWLEDGE / "standards").exists():
        pytest.skip("run pulsenet/fetch_standards.py first")
    found = {h["doc_id"] for h in knowledge.search(query, k=4, mode="bm25")}
    assert found & expected


def test_handover_remembers_changes_and_open_goals(net, tmp_path):
    net.update_config(["BACKUP-WAVE-1"], "state", "enabled")
    net.open_ticket("FIBER-AZIZIYAH-QUBA", "fiber", "urgent", "cut in duct D-114")
    text = memory.write_handover(net, tmp_path / "handover.md")
    assert "BACKUP-WAVE-1: state=enabled" in text and "TCK-0001" in text and "INT-1" in text
    assert memory.read_handover(tmp_path / "handover.md") == text
