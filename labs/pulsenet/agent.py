# /// script
# requires-python = ">=3.11"
# dependencies = ["openai>=3.30", "pydantic>=2.12", "python-dotenv>=1.1", "pandas>=2.2", "mcp>=2.3",
#                 "bm25s>=0.3", "model2vec>=0.10", "numpy>=2.0"]
# ///
# PulseNet: run from labs/
#   uv run pulsenet/agent.py ask "Good morning, what is wrong with the network?"
#   uv run pulsenet/agent.py chat

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LABS = HERE.parent
sys.path.insert(0, str(LABS))  # the course library: agentkit
sys.path.insert(0, str(HERE))  # our project: network, knowledge

from mcp import StdioServerParameters  # noqa: E402

import agentkit as K  # noqa: E402
import knowledge  # noqa: E402
from network import Network  # noqa: E402

OUT = K.lab_dir("pulsenet")

# ---------------------------------------------------------------- context: the spec and the budgets
SPEC = (HERE / "AGENTS.md").read_text(encoding="utf-8")
MAX_STEPS = 14              # tool rounds before the harness stops the agent
MAX_COST = 0.05             # dollars per request (free models cost 0, so the step limit is what bites)
MAX_RESULT_CHARS = 6000     # longer tool results are cut so they don't fill the context window
MAX_HISTORY_MESSAGES = 24   # chat mode keeps only the last messages (compaction rule)
CRITICAL = ("CORE-", "IGW-", "RAIL-", "TRAFFIC-", "EMERGENCY-")  # never changed, whatever anyone approves
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


# ---------------------------------------------------------------- harness: permissions, approvals, audit
YES_WORDS = ("y", "yes", "ok", "approve", "approved", "sure")


def targets(args):
    return [str(t).upper() for t in (args.get("asset_ids") or [args.get("asset_id", "")])]


def permission(name, args):
    # critical assets are blocked in code, whatever the model or the engineer says
    if name in Network.CHANGE_TOOLS and any(t.startswith(CRITICAL) for t in targets(args)):
        return "deny"
    return "allow"


def approve_cli(name, args):
    print("\n" + "─" * 60)
    print(f"🛡️  PulseNet wants to run: {name}")
    print(f"    {json.dumps(args, ensure_ascii=False)}")
    answer = input("    Approve? [y/N] ").strip().lower()
    print("─" * 60)
    return bool(answer) and answer.split()[0] in YES_WORDS


def needs_approval(approve):
    # before every change, stop and ask the engineer; a "no" blocks the call with a clear message
    def before_tool(name, args):
        if name in Network.CHANGE_TOOLS and not approve(name, args):
            return json.dumps({"error": f"The engineer did not approve {name}. Nothing was changed. "
                                        "Do not retry it; ask what they would like to do instead."})
        return None
    return before_tool


def after_tool(name, args, result):
    with (OUT / "audit.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"tool": name, "args": args, "chars": len(result)}, ensure_ascii=False) + "\n")
    if len(result) > MAX_RESULT_CHARS:
        return result[:MAX_RESULT_CHARS] + f"\n[... {len(result) - MAX_RESULT_CHARS} characters cut, ask for less]"
    return None


def compact(history):
    # keep the last messages, and never start on a tool result whose call was cut off
    if len(history) <= MAX_HISTORY_MESSAGES:
        return history
    tail = history[-MAX_HISTORY_MESSAGES:]
    while tail and tail[0].get("role") != "user":
        tail = tail[1:]
    return tail


# ---------------------------------------------------------------- the agent
def run(prompt, net, mcp, system=SPEC, model=None, history=None, approve=approve_cli, verbose=True, **kw):
    return K.run_agent(prompt, all_tools(net, mcp), system=system, model=model, history=history,
                       max_steps=MAX_STEPS, max_cost=MAX_COST, permission=permission,
                       before_tool=needs_approval(approve), after_tool=after_tool, verbose=verbose, **kw)


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
    sub.add_parser("chat")
    args = ap.parse_args()

    workdir = K.lab_dir("pulsenet/live", reset=True)  # every session starts from the same 09:30 network
    net = Network(workdir)
    with K.MCPBridge(mcp_server(workdir)) as mcp:
        if args.cmd == "ask":
            result = run(args.question, net, mcp)
            print("\n" + (result.final or f"(stopped: {result.stopped})"))
        else:
            print("PulseNet chat. Empty line to quit.")
            history = []
            while (msg := read_line("\n👷 ")):
                result = run(msg, net, mcp, history=compact(history))
                print("\n🤖", result.final or f"(stopped: {result.stopped})")
                history = result.state[1:]


if __name__ == "__main__":
    main()
