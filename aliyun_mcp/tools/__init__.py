"""Register all MCP tools."""
from .resource import register as register_resource
from .cost import register as register_cost
from .monitor import register as register_monitor
from .compliance import register as register_compliance


def register_all(mcp):
    register_resource(mcp)
    register_cost(mcp)
    register_monitor(mcp)
    register_compliance(mcp)
