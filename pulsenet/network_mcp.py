# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=2.3"]
# ///
# The city's network management platform as an MCP server.
#   uv run pulsenet/network_mcp.py --workdir <folder>          (stdio, started by the agent)
#   uv run pulsenet/network_mcp.py --workdir <folder> --http 8766

import argparse
import functools
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402

import network  # noqa: E402


def readable_errors(fn):
    # turn our ToolError into MCP's ToolError so the model reads the message and can recover
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except network.ToolError as e:
            raise ToolError(str(e)) from e
    return wrapper


def build(workdir):
    net = network.Network(workdir, reset=False)  # the agent created this folder; keep its state
    server = MCPServer("pulsenet-network", title="Madinah city network management platform",
                       instructions="Assets, alarms, intents, paths, forecasts and changes for the city network "
                                    "(synthetic).", version="2.0.0", log_level="WARNING")
    for name in network.Network.MCP_TOOLS:
        fn = getattr(net, name)
        server.tool(name=name, description=inspect.getdoc(fn))(readable_errors(fn))
    return server


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True, help="folder holding this run's network.sqlite")
    ap.add_argument("--http", type=int, help="serve Streamable HTTP on this port instead of stdio")
    a = ap.parse_args()
    server = build(a.workdir)
    if a.http:
        server.run(transport="streamable-http", host="127.0.0.1", port=a.http)
    else:
        server.run()
