"""Monitor tools."""
from .alerts import register as register_alerts


def register(mcp):
    register_alerts(mcp)
