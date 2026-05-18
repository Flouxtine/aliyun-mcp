"""Compliance / audit tools."""
from .audit import register as register_audit


def register(mcp):
    register_audit(mcp)
