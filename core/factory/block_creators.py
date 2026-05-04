from abc import ABC, abstractmethod

from core.domain.block import AgentBlock, Block, HTTPBlock, LLMBlock, PythonScriptBlock
from core.domain.workflow import Workflow


class BlockCreator(ABC):
    """Abstract creator in the Factory Method pattern.

    Defines the interface for creating Block objects and adding them to a
    Workflow. Concrete subclasses override _create_block() to produce the
    appropriate Block type.

    The Toolbox always goes through a BlockCreator — it never instantiates
    a Block directly. This keeps block construction logic in one place and
    makes adding new block types straightforward.
    """

    def add_block_to(self, workflow: Workflow) -> Block:
        """Create a new block and add it to the workflow.

        This is the public entry point used by the Toolbox. It delegates
        block construction to _create_block(), then adds the result to the
        workflow (which triggers Observer notifications to the Canvas).

        Args:
            workflow: The workflow instance to add the new block to.

        Returns:
            The newly created and added Block.
        """
        block = self._create_block()
        workflow.add_block(block)
        return block

    @abstractmethod
    def _create_block(self) -> Block:
        """Factory method — must be overridden by each concrete creator.

        Returns:
            A new Block instance of the appropriate type with default config.
        """


class LLMBlockCreator(BlockCreator):
    """Creates LLMBlock instances with default configuration."""

    def _create_block(self) -> LLMBlock:
        return LLMBlock()


class AgentBlockCreator(BlockCreator):
    """Creates AgentBlock instances with default configuration."""

    def _create_block(self) -> AgentBlock:
        return AgentBlock()


class HTTPBlockCreator(BlockCreator):
    """Creates HTTPBlock instances with default configuration."""

    def _create_block(self) -> HTTPBlock:
        return HTTPBlock()


class PythonScriptBlockCreator(BlockCreator):
    """Creates PythonScriptBlock instances with default configuration."""

    def _create_block(self) -> PythonScriptBlock:
        return PythonScriptBlock()
