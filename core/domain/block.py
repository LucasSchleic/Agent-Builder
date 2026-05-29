# Backward-compatible re-export.
# All existing imports of the form `from core.domain.block import X` continue
# to work unchanged — the actual implementations live in core/domain/blocks/.
from core.domain.blocks import (  # noqa: F401
    AgentBlock,
    Block,
    BufferMemoryBlock,
    HTTPBlock,
    LLMBlock,
    PythonScriptBlock,
    _memory_savers,
    _to_var_name,
)

__all__ = [
    "Block",
    "LLMBlock",
    "AgentBlock",
    "HTTPBlock",
    "PythonScriptBlock",
    "BufferMemoryBlock",
    "_to_var_name",
    "_memory_savers",
]
