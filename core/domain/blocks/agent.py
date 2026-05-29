from typing import Any, List

from core.domain.blocks.base import Block, _to_var_name
from core.domain.port import Port


class AgentBlock(Block):
    """Represents a LangChain ReAct agent with optional memory and tools.

    Requires a connected LLMBlock (via llm_block_id) and zero or more
    HTTPBlocks used as tools (via tool_block_ids).
    """

    def __init__(self, name: str = "Agent", config: dict = None, block_id: str = None):
        super().__init__(name, config, block_id)
        self.config.setdefault("system_prompt", "")
        self.config.setdefault("user_prompt", "")
        self.config.setdefault("llm_block_id", "")
        self.config.setdefault("tool_block_ids", [])
        self.config.setdefault("memory_block_id", "")
        self.input_ports = [
            Port(name="llm_input",    direction="input", data_type="llm",    required=True),
            Port(name="tool_input",   direction="input", data_type="tool",   required=False),
            Port(name="memory_input", direction="input", data_type="memory", required=False, position="bottom"),
        ]
        self.output_ports = [
            Port(name="agent_output", direction="output", data_type="str"),
        ]

    def validate(self) -> bool:
        return super().validate() and bool(self.config.get("llm_block_id"))

    def get_dependencies(self) -> List[str]:
        """Return the LLM block ID, tool block IDs, and optional memory block ID."""
        deps = []
        if self.config.get("llm_block_id"):
            deps.append(self.config["llm_block_id"])
        deps.extend(self.config.get("tool_block_ids", []))
        if self.config.get("memory_block_id"):
            deps.append(self.config["memory_block_id"])
        return deps

    def execute(self, context: dict) -> Any:
        """Build and invoke a LangChain agent using the create_agent API (v1.x)."""
        from langchain.agents import create_agent
        from langchain_core.tools import Tool

        llm = context[self.config["llm_block_id"]]

        tools = [
            Tool(
                name=tid[:8],
                func=lambda _, tid=tid: context[tid],
                description="HTTP tool",
            )
            for tid in self.config.get("tool_block_ids", [])
        ]

        agent_kwargs: dict = {
            "model": llm,
            "tools": tools or None,
        }
        if self.config.get("system_prompt"):
            agent_kwargs["system_prompt"] = self.config["system_prompt"]

        memory_block_id = self.config.get("memory_block_id", "")
        invoke_config = None
        if memory_block_id and memory_block_id in context:
            agent_kwargs["checkpointer"] = context[memory_block_id]
            invoke_config = {"configurable": {"thread_id": self.id}}

        agent = create_agent(**agent_kwargs)
        result = agent.invoke(
            {"messages": [{"role": "user", "content": self.config["user_prompt"]}]},
            config=invoke_config,
        )
        messages = result.get("messages", [])
        if messages:
            last = messages[-1]
            return last.content if hasattr(last, "content") else str(last)
        return str(result)

    def generate_code_snippet(self) -> str:
        var = _to_var_name(self.name)
        lines = []
        lines.append(f"agent_{var} = create_agent(")
        lines.append(f"    model=llm,")
        lines.append(f"    tools=tools or None,")
        if self.config.get("system_prompt"):
            lines.append(f"    system_prompt={self.config['system_prompt']!r},")
        if self.config.get("memory_block_id"):
            lines.append(f"    checkpointer=checkpointer,")
        lines.append(f")")

        if self.config.get("memory_block_id"):
            lines.append(f'print("Agent pret. Tapez vos messages (Ctrl+C pour quitter).")')
            lines.append(f'while True:')
            lines.append(f'    try:')
            lines.append(f'        user_input = input("Vous : ").strip()')
            lines.append(f'    except KeyboardInterrupt:')
            lines.append(f'        break')
            lines.append(f'    if not user_input:')
            lines.append(f'        continue')
            lines.append(f'    result_{var} = agent_{var}.invoke(')
            lines.append(f'        {{"messages": [{{"role": "user", "content": user_input}}]}},')
            lines.append(f'        config={{"configurable": {{"thread_id": "session_1"}}}},')
            lines.append(f'    )')
            lines.append(f'    print("Agent :", result_{var}["messages"][-1].content)')
        else:
            lines.append(
                f"result_{var} = agent_{var}.invoke({{\"messages\": [{{\"role\": \"user\", \"content\": {self.config['user_prompt']!r}}}]}})"
            )
            lines.append(f"print(result_{var}['messages'][-1].content)")

        return "\n".join(lines)
