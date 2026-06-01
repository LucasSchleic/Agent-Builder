import json
from typing import Any, Generator, List

from core.domain.block import Block
from core.domain.workflow import Workflow


class WorkflowExecutor:
    """Executes a Workflow by running each block in dependency order.

    Uses a DFS postorder traversal to determine execution order.
    Each block's result is stored in a shared context dict keyed by block ID,
    making it available to all downstream blocks.

    Public interface (matches UML):
        execute_workflow(workflow)  — main entry point
        execute_block(block, context) — executes a single block
        prepare_inputs(block, context) — resolves port-name mappings in context
        topological_sort(workflow) — returns blocks in dependency order
    """

    def __init__(self):
        """Initialize the executor with no active workflow."""
        # Stored during execute_workflow so prepare_inputs can access connections
        # without needing workflow passed as an extra argument.
        self._workflow: Workflow = None

    # ------------------------------------------------------------------
    # Topological sort — DFS postorder reversed
    # ------------------------------------------------------------------

    def topological_sort(self, workflow: Workflow) -> List[Block]:
        """Return blocks in execution order using DFS postorder traversal.

        Each block is appended after all blocks reachable from it,
        then the list is reversed to get dependency-first order.
        """
        visited: set = set()
        result: List[str] = []

        def dfs(block_id: str) -> None:
            # Mark as visited immediately to avoid revisiting on cycles.
            visited.add(block_id)
            # Recurse into every block this one connects to.
            for conn in workflow.connections:
                if conn.source_block_id == block_id and conn.target_block_id not in visited:
                    dfs(conn.target_block_id)
            # Append after visiting all dependents — postorder.
            result.append(block_id)

        for block in workflow.blocks:
            # Skip blocks already reached via a previous DFS traversal.
            if block.id not in visited:
                dfs(block.id)

        # Reversing postorder gives dependency-first order.
        return [workflow.get_block(bid) for bid in reversed(result)]

    # ------------------------------------------------------------------
    # Input preparation
    # ------------------------------------------------------------------

    def prepare_inputs(self, block: Block, context: dict) -> dict:
        """Resolve port-name mappings and inject them into context.

        AgentBlock accesses context by block ID directly (e.g. context[llm_block_id]).
        PythonScriptBlock accesses context by parameter name (e.g. context['x']).
        This method bridges the two by adding context[port.name] = context[source_block_id]
        for every connection that feeds into this block.

        Args:
            block: The block about to be executed.
            context: The shared execution context, modified in place.

        Returns:
            A dict of the port-name → value pairs that were added to context.
        """
        inputs = {}
        for conn in self._workflow.connections:
            if conn.target_block_id == block.id and conn.source_block_id in context:
                # Find the target port to get its name (= parameter name for PythonScriptBlock).
                target_port = next(
                    (p for p in block.input_ports if p.id == conn.target_port_id),
                    None,
                )
                if target_port:
                    value = context[conn.source_block_id]
                    # Expose the upstream result under the port name so blocks
                    # that look up inputs by name can find it.
                    context[target_port.name] = value
                    inputs[target_port.name] = value
        return inputs

    # ------------------------------------------------------------------
    # Block execution
    # ------------------------------------------------------------------

    def execute_block(self, block: Block, context: dict) -> Any:
        """Prepare inputs for a block and execute it.

        Args:
            block: The block to execute.
            context: The shared execution context.

        Returns:
            The result produced by the block.
        """
        # Populate port-name keys in context before the block reads from it.
        self.prepare_inputs(block, context)
        return block.execute(context)

    # ------------------------------------------------------------------
    # Streaming execution (SSE)
    # ------------------------------------------------------------------

    @staticmethod
    def _sse(data: dict) -> str:
        """Format a dict as a single SSE message."""
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    def execute_workflow_stream(self, workflow: Workflow) -> Generator[str, None, None]:
        """Execute blocks one by one and yield SSE progress events.

        Each yielded string is a complete SSE message ready to be written
        to a StreamingHttpResponse.  The frontend reads these events and
        updates the console panel in real time.

        Event types:
            start       — workflow started, includes total block count
            block_start — a block has begun executing
            block_done  — a block finished, includes its output
            block_error — a block raised an exception (stream stops)
            done        — all blocks finished successfully
            error       — workflow-level error (validation failure)
        """
        if not workflow.validate():
            yield self._sse({"type": "error", "error": f"Workflow '{workflow.name}' is invalid — check block configurations."})
            return

        self._workflow = workflow
        blocks = self.topological_sort(workflow)

        yield self._sse({"type": "start", "workflow": workflow.name, "total": len(blocks)})

        _serializable = (str, int, float, bool, list, dict, type(None))
        context: dict = {}

        for block in blocks:
            yield self._sse({
                "type": "block_start",
                "block_id": block.id,
                "block_name": block.name,
                "block_type": block.__class__.__name__,
            })
            try:
                self.prepare_inputs(block, context)
                result = block.execute(context)
                context[block.id] = result
                safe = result if isinstance(result, _serializable) else str(result)
                yield self._sse({
                    "type": "block_done",
                    "block_id": block.id,
                    "block_name": block.name,
                    "output": safe,
                })
            except Exception as exc:
                yield self._sse({
                    "type": "block_error",
                    "block_id": block.id,
                    "block_name": block.name,
                    "error": str(exc),
                })
                return

        safe_context = {k: v if isinstance(v, _serializable) else str(v) for k, v in context.items()}
        yield self._sse({"type": "done", "context": safe_context})

    # ------------------------------------------------------------------
    # Workflow execution
    # ------------------------------------------------------------------

    def execute_workflow(self, workflow: Workflow) -> dict:
        """Execute all blocks in topological order and return the context.

        The context maps each block's ID to its result, allowing callers
        to retrieve any block's output after execution.

        Args:
            workflow: The workflow to execute.

        Returns:
            The final context dict: {block_id: result, ...}

        Raises:
            ValueError: If the workflow is invalid.
        """
        # Validate before executing to catch misconfigured blocks early.
        if not workflow.validate():
            raise ValueError(
                f"Workflow '{workflow.name}' is invalid — check block configurations."
            )

        # Store workflow on self so prepare_inputs can access connections.
        self._workflow = workflow

        blocks = self.topological_sort(workflow)

        # Shared execution context: each block writes its result here so that
        # downstream blocks can read it by referencing context[upstream_block_id].
        context: dict = {}

        for block in blocks:
            result = self.execute_block(block, context)
            # Store result under block ID for downstream blocks that reference by ID.
            context[block.id] = result

        return context
