"""Cost tools."""
from .billing import register as register_billing


def register(mcp):
    register_billing(mcp)
