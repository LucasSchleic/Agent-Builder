import uuid
from abc import ABC, abstractmethod
from typing import List

from core.domain.block import Block
from core.domain.connection import Connection


class Subscriber(ABC):
    """Interface for components that react to Workflow state changes.

    Any UI component that needs to stay in sync with the workflow must
    implement this interface and subscribe via Workflow.subscribe().
    """

    @abstractmethod
    def update(self, workflow: "Workflow") -> None:
        """Called by the Workflow after every state change.

        Args:
            workflow: The workflow instance that was modified.
        """


class Workflow:
    """Represents a visual AI agent workflow as a directed graph of blocks.

    Acts as the Publisher in the Observer pattern: it notifies all registered
    Subscribers after every structural change (add/remove block or connection).
    Subscribers are runtime objects and are never serialized.
    """

    def __init__(self, name: str, workflow_id: str = None):
        """Initialize an empty Workflow.

        Args:
            name: Display name of the workflow.
            workflow_id: Existing UUID string — generated if not provided.
        """
        self.id = workflow_id or str(uuid.uuid4())
        self.name = name
        self.blocks: List[Block] = []
        self.connections: List[Connection] = []
        # Underscore prefix: subscribers are runtime UI objects, never serialized.
        self._subscribers: List[Subscriber] = []

    # ------------------------------------------------------------------
    # Block operations
    # ------------------------------------------------------------------

    def add_block(self, block: Block) -> None:
        """Append a block to the workflow and notify subscribers."""
        self.blocks.append(block)
        self.notify_subscribers()

    def remove_block(self, block_id: str) -> None:
        """Remove a block and all connections involving it, then notify.

        Args:
            block_id: UUID of the block to remove.
        Raises:
            ValueError: If no block with that ID exists.
        """
        block = self.get_block(block_id)
        self.blocks.remove(block)

        # Rebuild the list instead of mutating it while iterating — avoids skipped items.
        self.connections = [
            c for c in self.connections
            if c.source_block_id != block_id and c.target_block_id != block_id
        ]
        self.notify_subscribers()

    def get_block(self, block_id: str) -> Block:
        """Return the block with the given ID.

        Args:
            block_id: UUID of the block to retrieve.
        Raises:
            ValueError: If no block with that ID exists.
        """
        for block in self.blocks:
            if block.id == block_id:
                return block
        raise ValueError(f"No block with id '{block_id}' in workflow '{self.name}'.")

    # ------------------------------------------------------------------
    # Connection operations
    # ------------------------------------------------------------------

    def add_connection(self, connection: Connection) -> None:
        """Append a connection to the workflow and notify subscribers.

        Args:
            connection: The connection to add.
        Raises:
            ValueError: If the source or target block does not exist.
        """
        self.get_block(connection.source_block_id)
        self.get_block(connection.target_block_id)
        self.connections.append(connection)
        self.notify_subscribers()

    def remove_connection(self, connection_id: str) -> None:
        """Remove a connection by ID and notify subscribers.

        Args:
            connection_id: UUID of the connection to remove.
        Raises:
            ValueError: If no connection with that ID exists.
        """
        for connection in self.connections:
            if connection.id == connection_id:
                self.connections.remove(connection)
                self.notify_subscribers()
                return
        raise ValueError(f"No connection with id '{connection_id}' in workflow '{self.name}'.")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> bool:
        """Return True if all blocks and connections are individually valid
        and all connection endpoints reference existing blocks."""
        for block in self.blocks:
            if not block.validate():
                return False

        block_ids = {block.id for block in self.blocks}
        for connection in self.connections:
            if not connection.validate():
                return False
            if connection.source_block_id not in block_ids:
                return False
            if connection.target_block_id not in block_ids:
                return False

        return True

    # ------------------------------------------------------------------
    # Observer — Publisher side
    # ------------------------------------------------------------------

    def subscribe(self, subscriber: Subscriber) -> None:
        """Register a subscriber to receive state-change notifications."""
        # Guard against double-registration, which would trigger update() twice per change.
        if subscriber not in self._subscribers:
            self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber: Subscriber) -> None:
        """Remove a previously registered subscriber."""
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)

    def notify_subscribers(self) -> None:
        """Call update(self) on every registered subscriber."""
        for subscriber in self._subscribers:
            subscriber.update(self)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize the workflow to a dict for JSON persistence.

        Subscribers are runtime objects and are intentionally excluded.
        """
        return {
            "id": self.id,
            "name": self.name,
            "blocks": [block.to_dict() for block in self.blocks],
            "connections": [conn.to_dict() for conn in self.connections],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Workflow":
        """Reconstruct a Workflow instance from a serialized dict."""
        workflow = cls(name=data["name"], workflow_id=data["id"])
        workflow.blocks = [Block.from_dict(b) for b in data.get("blocks", [])]
        workflow.connections = [Connection.from_dict(c) for c in data.get("connections", [])]
        return workflow

    def __repr__(self) -> str:
        return (
            f"Workflow(name={self.name!r}, "
            f"blocks={len(self.blocks)}, "
            f"connections={len(self.connections)})"
        )
