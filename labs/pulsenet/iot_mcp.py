# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=2.3"]
# ///
# PulseNet's device-management platform as an MCP server.
#   uv run pulsenet/iot_mcp.py --workdir <folder>          (stdio, launched by the agent)
#   uv run pulsenet/iot_mcp.py --workdir <folder> --http 8766

import argparse
import functools
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402

import city  # noqa: E402


def readable_errors(fn):
    # turn our ToolError into MCP's ToolError so the model reads the message and can recover
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except city.ToolError as e:
            raise ToolError(str(e)) from e
    return wrapper


def build(workdir):
    c = city.City(workdir, reset=False)  # the agent created this folder; keep its state
    server = MCPServer("pulsenet-iot", title="City IoT device management",
                       instructions="Devices, logs and remote actions for the city's IoT network (synthetic).",
                       version="1.0.0", log_level="WARNING")
    for name in city.City.MCP_TOOLS:
        fn = getattr(c, name)
        server.tool(name=name, description=inspect.getdoc(fn))(readable_errors(fn))
    return server


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True, help="folder holding this run's city.sqlite")
    ap.add_argument("--http", type=int, help="serve Streamable HTTP on this port instead of stdio")
    a = ap.parse_args()
    server = build(a.workdir)
    if a.http:
        server.run(transport="streamable-http", host="127.0.0.1", port=a.http)
    else:
        server.run()
