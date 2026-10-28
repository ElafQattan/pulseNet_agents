import json

# The harness controls, in one place. All of them are enforced in code: they hold even if the model is fooled.

CHANGE_TOOLS = ("update_config", "restart_asset")
CRITICAL = ("CORE-", "IGW-", "RAIL-", "TRAFFIC-", "EMERGENCY-")  # core, internet, railway, traffic, 911
YES_WORDS = ("y", "yes", "ok", "approve", "approved", "sure")


def targets(args):
    return [str(t).upper() for t in (args.get("asset_ids") or [args.get("asset_id", "")])]


def permission(name, args):
    # 1. deny list: critical assets can never be changed, whoever asks and whoever approves
    if name in CHANGE_TOOLS and any(t.startswith(CRITICAL) for t in targets(args)):
        return "deny"
    return "allow"


def needs_approval(approve):
    # 2. human approval: every change stops and asks the engineer; a "no" returns a clear message to the model
    def before_tool(name, args):
        if name in CHANGE_TOOLS and not approve(name, args):
            return json.dumps({"error": f"The engineer did not approve {name}. Nothing was changed. "
                                        "Do not retry it; ask what they would like to do instead."})
        return None
    return before_tool


def approve_in_terminal(name, args):
    print("\n" + "─" * 60)
    print(f"🛡️  PulseNet wants to run: {name}")
    print(f"    {json.dumps(args, ensure_ascii=False)}")
    answer = input("    Approve? [y/N] ").strip().lower()
    print("─" * 60)
    return bool(answer) and answer.split()[0] in YES_WORDS


def cap_and_audit(audit_file, max_chars):
    # 3. context budget and audit: every call is logged, long results are cut
    def after_tool(name, args, result):
        with audit_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"tool": name, "args": args, "chars": len(result)}, ensure_ascii=False) + "\n")
        if len(result) > max_chars:
            return result[:max_chars] + f"\n[... {len(result) - max_chars} characters cut, ask for less]"
        return None
    return after_tool

# 4. spotlighting (device text wrapped in <device_text> tags) lives in network.untrusted(), where the text is read.
