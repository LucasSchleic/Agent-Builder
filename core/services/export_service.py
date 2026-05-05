import os
from typing import List

from core.domain.block import AgentBlock, Block, HTTPBlock, LLMBlock, PythonScriptBlock
from core.domain.workflow import Workflow


def _to_var(name: str) -> str:
    """Convert a block name to a snake_case Python variable name."""
    return name.lower().replace(" ", "_").replace("-", "_")


class ExportService:
    """Generates a standalone Python script from a Workflow."""

    # Decorative separator line used in the script header.
    _HEADER = "# " + "=" * 60

    # ------------------------------------------------------------------
    # Topological sort (DFS postorder reversed)
    # ------------------------------------------------------------------

    def topological_sort(self, workflow: Workflow) -> List[Block]:
        """Return blocks ordered so every dependency comes before its dependents.

        Uses a DFS postorder traversal: each block is appended after all
        blocks reachable from it, then the list is reversed to get the
        correct dependency order.
        """
        visited: set = set()
        result: List[str] = []

        def dfs(block_id: str) -> None:
            # Mark as visited immediately to avoid infinite loops on cycles.
            visited.add(block_id)
            # Recurse into every block this one connects to (its dependents).
            for conn in workflow.connections:
                if conn.source_block_id == block_id and conn.target_block_id not in visited:
                    dfs(conn.target_block_id)
            # Append AFTER visiting all dependents — postorder.
            result.append(block_id)

        for block in workflow.blocks:
            # Skip blocks already reached via a previous DFS traversal.
            if block.id not in visited:
                dfs(block.id)

        # Reversing postorder gives dependency-first order:
        # dependencies end up before the blocks that need them.
        return [workflow.get_block(bid) for bid in reversed(result)]

    # ------------------------------------------------------------------
    # Import collection
    # ------------------------------------------------------------------

    def _collect_imports(self, blocks: List[Block]) -> List[str]:
        """Return the import lines needed based on which block types are present."""
        # os and load_dotenv are always required: env vars are used by every block type.
        imports = ["import os", "from dotenv import load_dotenv"]

        # LLMBlock uses ChatOpenAI from the langchain_openai package.
        if any(isinstance(b, LLMBlock) for b in blocks):
            imports.append("from langchain_openai import ChatOpenAI")

        # Both AgentBlock and HTTPBlock produce LangChain Tool objects.
        if any(isinstance(b, (AgentBlock, HTTPBlock)) for b in blocks):
            imports.append("from langchain.tools import Tool")

        if any(isinstance(b, AgentBlock) for b in blocks):
            imports.append("from langchain.agents import AgentExecutor, create_react_agent")
            # PromptTemplate is needed to build the ReAct prompt inline.
            imports.append("from langchain_core.prompts import PromptTemplate")
            # ConversationBufferMemory is only needed when at least one agent uses memory.
            if any(isinstance(b, AgentBlock) and b.config.get("memory_enabled") for b in blocks):
                imports.append("from langchain.memory import ConversationBufferMemory")

        # HTTPBlock uses the requests library to make HTTP calls.
        if any(isinstance(b, HTTPBlock) for b in blocks):
            imports.append("import requests")

        return imports

    # ------------------------------------------------------------------
    # AgentBlock glue code
    # ------------------------------------------------------------------

    def _agent_glue_lines(self, block: AgentBlock, workflow: Workflow) -> List[str]:
        """Return connector lines to inject before an AgentBlock snippet.

        AgentBlock.generate_code_snippet() references the variables `llm`,
        `tools`, and `react_prompt` as if they are already defined.  This
        method produces the assignments that make the exported script runnable.
        """
        lines = []

        # --- llm alias ---
        # LLMBlock.generate_code_snippet() names its variable after the block name,
        # e.g. "My Custom LLM" → my_custom_llm. But AgentBlock's snippet always
        # references `llm`, so we create an alias when the names differ.
        llm_id = block.config.get("llm_block_id")
        if llm_id:
            llm_var = _to_var(workflow.get_block(llm_id).name)
            if llm_var != "llm":
                # e.g. llm = my_custom_llm
                lines.append(f"llm = {llm_var}")

        # --- tools list ---
        # HTTPBlock.generate_code_snippet() produces `{var}_tool = Tool(...)`.
        # We collect those variable names here and build the list AgentBlock expects.
        tool_ids = block.config.get("tool_block_ids", [])
        tool_vars = []
        for tid in tool_ids:
            try:
                tool_block = workflow.get_block(tid)
                # Reconstruct the variable name that HTTPBlock's snippet produced.
                tool_vars.append(f"{_to_var(tool_block.name)}_tool")
            except ValueError:
                # Silently skip if a referenced tool block no longer exists.
                pass
        # e.g. tools = [search_tool, weather_tool]
        lines.append(f"tools = [{', '.join(tool_vars)}]")

        # --- react_prompt ---
        # Inline the ReAct prompt directly so the exported script is self-contained
        # and does not need a network call to hub.pull().
        lines.append("react_prompt = PromptTemplate.from_template(")
        lines.append(f"    {AgentBlock._REACT_PROMPT!r}")
        lines.append(")")

        return lines

    # ------------------------------------------------------------------
    # HTTPBlock standalone detection
    # ------------------------------------------------------------------

    def _is_tool_block(self, block_id: str, workflow: Workflow) -> bool:
        """Return True if the block is referenced as a tool by any AgentBlock.

        An HTTPBlock wired into an AgentBlock's tool_block_ids must be exported
        as a function + Tool object (generate_code_snippet).
        A standalone HTTPBlock must call the request directly (generate_standalone_snippet).
        """
        for block in workflow.blocks:
            if isinstance(block, AgentBlock) and block_id in block.config.get("tool_block_ids", []):
                return True
        return False

    # ------------------------------------------------------------------
    # Script generation
    # ------------------------------------------------------------------

    def generate_python(self, workflow: Workflow) -> str:
        """Generate a complete, standalone Python script from a workflow.

        Steps:
        1. Sort blocks topologically so dependencies are defined first.
        2. Collect the required imports from the block types present.
        3. Assemble the header, imports, load_dotenv(), then one section
           per block with its generated code snippet.
        """
        blocks = self.topological_sort(workflow)
        imports = self._collect_imports(blocks)

        # Start with the file header.
        lines: List[str] = [
            self._HEADER,
            "# Agent Builder — Export automatique",
            f"# Workflow : {workflow.name}",
            self._HEADER,
            "",
        ]

        # Add all imports, then load_dotenv() which reads the .env file at runtime.
        lines.extend(imports)
        lines.append("")
        lines.append("load_dotenv()")
        lines.append("")

        # One section per block, in dependency order.
        for block in blocks:
            # Section header comment identifies the block by name and type.
            lines.append(f"# --- Bloc : {block.name} ({block.__class__.__name__}) ---")
            # AgentBlock needs extra connector lines before its own snippet.
            if isinstance(block, AgentBlock):
                lines.extend(self._agent_glue_lines(block, workflow))
            # HTTPBlock has two export modes depending on whether it feeds an agent.
            if isinstance(block, HTTPBlock) and not self._is_tool_block(block.id, workflow):
                lines.append(block.generate_standalone_snippet())
            else:
                lines.append(block.generate_code_snippet())
            # Blank line between sections for readability.
            lines.append("")

        return "\n".join(lines)

    def export_to_file(self, workflow: Workflow, path: str) -> None:
        """Write the generated Python script to disk.

        Args:
            workflow: The workflow to export.
            path: Destination path for the .py file (extension included by caller).
        """
        code = self.generate_python(workflow)
        # Open in write mode — creates the file if it doesn't exist, overwrites if it does.
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
