import uuid

VALID_DIRECTIONS = ("input", "output")
VALID_DATA_TYPES = ("llm", "tool", "memory", "str", "dict", "any")


class Port:
    """Represents a typed connection point on a Block.

    A port has a direction (input or output) and a data type that constrains
    which ports can be connected together.
    """

    def __init__(
        self,
        name: str,
        direction: str,
        data_type: str,
        required: bool = False,
        port_id: str = None,
        position: str = None,
    ):
        """Initialize a Port.

        Args:
            name: Display name of the port.
            direction: 'input' or 'output'.
            data_type: Type of data flowing through this port.
            required: Whether a connection on this port is mandatory for execution.
            port_id: Existing UUID string — generated if not provided.
            position: Optional visual hint — 'bottom' renders the port on the bottom edge.
        """
        self.id = port_id or str(uuid.uuid4())
        self.name = name
        self.direction = direction
        self.data_type = data_type
        self.required = required
        self.position = position  # None = auto (left/right), 'bottom' = bottom edge

    def validate(self) -> bool:
        """Return True if direction and data_type hold valid values."""
        return self.direction in VALID_DIRECTIONS and self.data_type in VALID_DATA_TYPES

    def to_dict(self) -> dict:
        """Serialize the port to a dict for JSON persistence."""
        d = {
            "id": self.id,
            "name": self.name,
            "direction": self.direction,
            "data_type": self.data_type,
            "required": self.required,
        }
        if self.position:
            d["position"] = self.position
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Port":
        """Reconstruct a Port instance from a serialized dict."""
        return cls(
            name=data["name"],
            direction=data["direction"],
            data_type=data["data_type"],
            required=data.get("required", False),
            port_id=data["id"],
            position=data.get("position"),
        )

    def __repr__(self) -> str:
        return f"Port(name={self.name!r}, direction={self.direction!r}, data_type={self.data_type!r})"
