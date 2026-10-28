# /// script
# requires-python = ">=3.11"
# dependencies = ["openai>=3.30", "pydantic>=2.12", "python-dotenv>=1.1", "pandas>=2.2", "mcp>=2.3",
#                 "bm25s>=0.3", "model2vec>=0.10", "numpy>=2.0"]
# ///
# PulseNet: run from the repository root
#   uv run pulsenet/agent.py ask "Good morning, what is wrong with the network?"
#   uv run pulsenet/agent.py chat            (keeps a shift handover between sessions)
#   uv run pulsenet/agent.py chat --forget   (start without the handover)

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # agentkit: the agent loop and MCP bridge from the course
sys.path.insert(0, str(HERE))         # our modules

from mcp import StdioServerParameters  # noqa: E402

import agentkit as K  # noqa: E402
import guards  # noqa: E402
import knowledge  # noqa: E402
import memory  # noqa: E402
from network import Network  # noqa: E402

OUT = K.lab_dir("pulsenet")

# ---------------------------------------------------------------- context: the spec and the budgets
BASE_SPEC = (HERE / "AGENTS.md").read_text(encoding="utf-8")
PLAYBOOK = (HERE / "PLAYBOOK.md").read_text(encoding="utf-8")  # added after the error analysis (config B)
SPEC = BASE_SPEC + "\n\n" + PLAYBOOK
MAX_STEPS = 14              # tool rounds before the harness stops the agent
MAX_COST = 0.05             # dollars per request (free models cost 0, so the step limit is what bites)
MAX_RESULT_CHARS = 6000     # longer tool results are cut so they don't fill the context window
MAX_HISTORY_MESSAGES = 24   # chat keeps only the last messages (compaction rule)
RETRIEVAL = {"mode": knowledge.MODE}  # "bm25" or "hybrid"; the eval switches it between configurations A and B


# ---------------------------------------------------------------- tools
def mcp_server(workdir):
    # the network management platform, started as a separate process that speaks MCP
    return StdioServerParameters(command="uv", args=["run", "--quiet", str(HERE / "network_mcp.py"),
                                                     "--workdir", str(workdir)])


def search_knowledge(query: str) -> list[dict]:
    """Search the knowledge base: operations runbooks (RB-…), past incident reports (INC-…) and the public
    standards on autonomous networks (ITU-T Y.3172, Y.3173, Y.3177; ETSI ZSM 002, 009-1, 009-2). Returns the best
    passages with their document ID; cite it.

    Args:
        query: the symptom, question or topic, e.g. "fiber cut shared duct" or "intelligence level L3".
    """
    return knowledge.search(query, k=4, mode=RETRIEVAL["mode"])


def all_tools(net, mcp):
    local = [search_knowledge, net.open_ticket, net.list_tickets]
    return local + mcp.agent_tools()


def compact(history):
    # keep the last messages, and never start on a tool result whose call was cut off
    if len(history) <= MAX_HISTORY_MESSAGES:
        return history
    tail = history[-MAX_HISTORY_MESSAGES:]
    while tail and tail[0].get("role") != "user":
        tail = tail[1:]
    return tail


# ---------------------------------------------------------------- the agent
def run(prompt, net, mcp, system=SPEC, model=None, history=None, approve=guards.approve_in_terminal,
        handover="", verbose=True, **kw):
    if handover:
        system = system + "\n\n" + handover  # memory from the previous session
    return K.run_agent(prompt, all_tools(net, mcp), system=system, model=model, history=history,
                       max_steps=MAX_STEPS, max_cost=MAX_COST, permission=guards.permission,
                       before_tool=guards.needs_approval(approve),
                       after_tool=guards.cap_and_audit(OUT / "audit.jsonl", MAX_RESULT_CHARS),
                       verbose=verbose, **kw)


def read_line(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def main():
    # Windows terminals don't always use UTF-8
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ask").add_argument("question")
    sub.add_parser("chat").add_argument("--forget", action="store_true", help="start without the shift handover")
    args = ap.parse_args()

    if args.cmd == "ask" or args.forget:
        memory.clear()
    handover = memory.read_handover()
    # the network continues from the last session when there is a handover; otherwise it starts at 09:30
    workdir = K.lab_dir("pulsenet/live", reset=not handover)
    net = Network(workdir, reset=not handover)
    with K.MCPBridge(mcp_server(workdir)) as mcp:
        if args.cmd == "ask":
            result = run(args.question, net, mcp)
            print("\n" + (result.final or f"(stopped: {result.stopped})"))
            return
        print("PulseNet chat. Empty line to quit." + (" (handover from the last session loaded)" if handover else ""))
        history = []
        while (msg := read_line("\n👷 ")):
            result = run(msg, net, mcp, history=compact(history), handover=handover)
            print("\n🤖", result.final or f"(stopped: {result.stopped})")
            history = result.state[1:]
            memory.write_handover(net)  # saved after every turn, so a crash loses nothing


if __name__ == "__main__":
    main()
