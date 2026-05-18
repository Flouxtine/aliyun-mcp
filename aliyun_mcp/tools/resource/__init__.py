"""Resource-domain tools (ECS/SG/VPC/Tag read-only)."""
from .read import register as register_read


def register(mcp):
    register_read(mcp)
