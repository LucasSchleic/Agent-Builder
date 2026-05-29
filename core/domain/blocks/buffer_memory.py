from typing import Any

from core.domain.blocks.base import Block, _memory_savers, _to_var_name
from core.domain.port import Port


class BufferMemoryBlock(Block):
    """Provides a LangGraph MemorySaver checkpointer to a connected AgentBlock.

    Connect its output port to the memory_input port (bottom) of an AgentBlock
    to enable conversation memory for that agent.
    """

    def __init__(self, name: str = "Buffer Memory", config: dict = None, block_id: str = None):
        super().__init__(name, config, block_id)
        self.input_ports = []
        self.output_ports = [
            Port(name="memory_output", direction="output", data_type="memory"),
        ]

    def validate(self) -> bool:
        return True

    def execute(self, context: dict) -> Any:
        """Return the persistent MemorySaver for this block, creating it on first run."""
        from langgraph.checkpoint.memory import MemorySaver
        if self.id not in _memory_savers:
            _memory_savers[self.id] = MemorySaver()
        return _memory_savers[self.id]

    def generate_code_snippet(self) -> str:
        var = _to_var_name(self.name)
        return f"{var} = MemorySaver()"
