import uuid


class Connection:
    """Represents a directed data link between an output port and an input port.

    A connection joins a source block/port pair to a target block/port pair,
    encoding the data flow edge in the workflow graph.
    """

    def __init__(
        self,
        source_block_id: str,
        source_port_id: str,
        target_block_id: str,
        target_port_id: str,
        connection_id: str = None,
    ):
        """Initialize a Connection.

        Args:
            source_block_id: UUID of the block the connection originates from.
            source_port_id: UUID of the output port on the source block.
            target_block_id: UUID of the block the connection leads to.
            target_port_id: UUID of the input port on the target block.
            connection_id: Existing UUID string — generated if not provided.
        """
        self.id = connection_id or str(uuid.uuid4())
        self.source_block_id = source_block_id
        self.source_port_id = source_port_id
        self.target_block_id = target_block_id
        self.target_port_id = target_port_id

    def validate(self) -> bool:
        """Return True if all four IDs are set and source and target blocks differ."""
        all_set = all([
            self.source_block_id,
            self.source_port_id,
            self.target_block_id,
            self.target_port_id,
        ])
        # A block connecting to itself would create a cycle that breaks topological sort.
        no_self_loop = self.source_block_id != self.target_block_id
        return all_set and no_self_loop

    def to_dict(self) -> dict:
        """Serialize the connection to a dict for JSON persistence."""
        return {
            "id": self.id,
            "source_block_id": self.source_block_id,
            "source_port_id": self.source_port_id,
            "target_block_id": self.target_block_id,
            "target_port_id": self.target_port_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Connection":
        """Reconstruct a Connection instance from a serialized dict."""
        return cls(
            source_block_id=data["source_block_id"],
            source_port_id=data["source_port_id"],
            target_block_id=data["target_block_id"],
            target_port_id=data["target_port_id"],
            connection_id=data["id"],
        )

    def __repr__(self) -> str:
        return (
            f"Connection({self.source_block_id[:8]}:{self.source_port_id[:8]}"
            f" -> {self.target_block_id[:8]}:{self.target_port_id[:8]})"
        )
