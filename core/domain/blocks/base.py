import uuid
from abc import ABC, abstractmethod
from typing import Any, List

from core.domain.port import Port


def _to_var_name(name: str) -> str:
    """Convert a block name to a valid Python snake_case variable name."""
    return name.lower().replace(" ", "_").replace("-", "_")


# Keeps MemorySaver instances alive across requests so conversation history
# persists between workflow runs for the lifetime of the Django process.
_memory_savers: dict = {}


class Block(ABC):
    """Abstract base class for all workflow blocks.

    Every concrete block must implement execute(), generate_code_snippet(),
    validate(), to_dict(), and from_dict().
    """

    def __init__(self, name: str, config: dict = None, block_id: str = None):
        """Initialize a Block.

        Args:
            name: Display name shown on the canvas.
            config: Dict of block-specific configuration values.
            block_id: Existing UUID string — generated if not provided.
        """
        self.id = block_id or str(uuid.uuid4())
        self.name = name
        self.config = config or {}
        self.input_ports: List[Port] = []
        self.output_ports: List[Port] = []

    @abstractmethod
    def execute(self, context: dict) -> Any:
        """Execute the block logic using values from context and return a result."""

    @abstractmethod
    def generate_code_snippet(self) -> str:
        """Return a Python code string for this block, used by ExportService."""

    def validate(self) -> bool:
        """Return True if the block has a non-empty name."""
        return bool(self.name)

    def get_dependencies(self) -> List[str]:
        """Return IDs of blocks this block depends on. Empty list by default."""
        return []

    def to_dict(self) -> dict:
        """Serialize the block to a dict for JSON persistence."""
        return {
            "id": self.id,
            "type": self.__class__.__name__,
            "name": self.name,
            "config": self.config,
            "input_ports": [p.to_dict() for p in self.input_ports],
            "output_ports": [p.to_dict() for p in self.output_ports],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Block":
        """Reconstruct the correct Block subclass from a serialized dict.

        Dispatches on data['type'] to instantiate the matching concrete class.
        Lazy imports inside the method body prevent circular import errors
        between sibling modules that all inherit from this base.
        """
        from core.domain.blocks.agent import AgentBlock
        from core.domain.blocks.buffer_memory import BufferMemoryBlock
        from core.domain.blocks.http import HTTPBlock
        from core.domain.blocks.llm import LLMBlock
        from core.domain.blocks.python_script import PythonScriptBlock

        mapping = {
            "LLMBlock": LLMBlock,
            "AgentBlock": AgentBlock,
            "HTTPBlock": HTTPBlock,
            "PythonScriptBlock": PythonScriptBlock,
            "BufferMemoryBlock": BufferMemoryBlock,
        }
        block_cls = mapping.get(data["type"])
        if block_cls is None:
            raise ValueError(f"Unknown block type: {data['type']}")

        block = block_cls(
            name=data["name"],
            config=data["config"],
            block_id=data["id"],
        )
        block.input_ports = [Port.from_dict(p) for p in data.get("input_ports", [])]
        block.output_ports = [Port.from_dict(p) for p in data.get("output_ports", [])]
        return block

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id[:8]!r}, name={self.name!r})"
