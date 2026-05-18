"""Prompt templates registration."""

from .compliance import register as register_compliance
from .cost_optimization import register as register_cost
from .inspection import register as register_inspection
from .inventory import register as register_inventory
from .monitoring import register as register_monitoring
from .troubleshooting import register as register_troubleshooting


def register_all(mcp):
    register_inventory(mcp)
    register_cost(mcp)
    register_monitoring(mcp)
    register_compliance(mcp)
    register_troubleshooting(mcp)
    register_inspection(mcp)
