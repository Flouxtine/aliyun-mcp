"""Static resources for prompts and grounding."""

from .account_descriptions import register as register_account_descriptions
from .aliyun_metadata import register as register_aliyun_metadata
from .cost import register as register_cost
from .operations import register as register_operations
from .performance import register as register_performance
from .security import register as register_security


def register(mcp):
    register_aliyun_metadata(mcp)
    register_security(mcp)
    register_performance(mcp)
    register_cost(mcp)
    register_operations(mcp)
    register_account_descriptions(mcp)
