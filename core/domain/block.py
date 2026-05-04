import ast
import os
import uuid
from abc import ABC, abstractmethod
from typing import Any, List

from core.domain.port import Port


def _to_var_name(name: str) -> str:
    """Convert a block name to a valid Python snake_case variable name."""
    return name.lower().replace(" ", "_").replace("-", "_")


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

        Dispatches on data['type'] to instantiate the matching concrete class,
        then restores ports from the saved data.
        """
        mapping = {
            "LLMBlock": LLMBlock,
            "AgentBlock": AgentBlock,
            "HTTPBlock": HTTPBlock,
            "PythonScriptBlock": PythonScriptBlock,
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


# ---------------------------------------------------------------------------
# LLMBlock
# ---------------------------------------------------------------------------

class LLMBlock(Block):
    """Configures and instantiates a LangChain LLM (ChatOpenAI).

    Output: a ChatOpenAI object stored in context under this block's id,
    ready to be consumed by an AgentBlock.
    """

    def __init__(self, name: str = "LLM", config: dict = None, block_id: str = None):
        super().__init__(name, config, block_id)
        self.config.setdefault("api_url", "")
        self.config.setdefault("model_name", "")
        self.config.setdefault("temperature", 0.7)
        self.config.setdefault("api_key_env_var", "GENAI_API_KEY")
        self.output_ports = [
            Port(name="llm_output", direction="output", data_type="llm"),
        ]

    def validate(self) -> bool:
        return (
            super().validate()
            and bool(self.config.get("api_url"))
            and bool(self.config.get("model_name"))
            and bool(self.config.get("api_key_env_var"))
        )

    def execute(self, context: dict) -> Any:
        """Instantiate and return a configured ChatOpenAI object."""
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            base_url=self.config["api_url"],
            model=self.config["model_name"],
            temperature=self.config["temperature"],
            api_key=os.getenv(self.config["api_key_env_var"]),
        )

    def generate_code_snippet(self) -> str:
        var = _to_var_name(self.name)
        env_var = self.config["api_key_env_var"]
        return (
            f"{var} = ChatOpenAI(\n"
            f"    base_url=os.getenv('GENAI_API_URL'),\n"
            f"    model={self.config['model_name']!r},\n"
            f"    temperature={self.config['temperature']},\n"
            f"    api_key=os.getenv({env_var!r}),\n"
            f")"
        )


# ---------------------------------------------------------------------------
# AgentBlock
# ---------------------------------------------------------------------------

class AgentBlock(Block):
    """Represents a LangChain ReAct agent with optional memory and tools.

    Requires a connected LLMBlock (via llm_block_id) and zero or more
    HTTPBlocks used as tools (via tool_block_ids).
    """

    # Minimal local ReAct prompt — avoids hub.pull() to stay network-free.
    _REACT_PROMPT = (
        "Answer the following questions as best you can. "
        "You have access to the following tools:\n\n"
        "{tools}\n\n"
        "Use the following format:\n"
        "Question: the input question you must answer\n"
        "Thought: you should always think about what to do\n"
        "Action: the action to take, should be one of [{tool_names}]\n"
        "Action Input: the input to the action\n"
        "Observation: the result of the action\n"
        "... (this Thought/Action/Action Input/Observation can repeat N times)\n"
        "Thought: I now know the final answer\n"
        "Final Answer: the final answer to the original input question\n\n"
        "Begin!\n\n"
        "Question: {input}\n"
        "Thought:{agent_scratchpad}"
    )

    def __init__(self, name: str = "Agent", config: dict = None, block_id: str = None):
        super().__init__(name, config, block_id)
        self.config.setdefault("system_prompt", "")
        self.config.setdefault("user_prompt", "")
        self.config.setdefault("memory_enabled", False)
        self.config.setdefault("llm_block_id", "")
        self.config.setdefault("tool_block_ids", [])
        self.input_ports = [
            Port(name="llm_input", direction="input", data_type="llm", required=True),
            Port(name="tool_input", direction="input", data_type="tool", required=False),
        ]
        self.output_ports = [
            Port(name="agent_output", direction="output", data_type="str"),
        ]

    def validate(self) -> bool:
        return super().validate() and bool(self.config.get("llm_block_id"))

    def get_dependencies(self) -> List[str]:
        """Return the LLM block ID followed by all tool block IDs."""
        deps = []
        if self.config.get("llm_block_id"):
            deps.append(self.config["llm_block_id"])
        deps.extend(self.config.get("tool_block_ids", []))
        return deps

    def execute(self, context: dict) -> Any:
        """Build and invoke a LangChain ReAct AgentExecutor."""
        from langchain.agents import AgentExecutor, create_react_agent
        from langchain.memory import ConversationBufferMemory
        from langchain.tools import Tool
        from langchain_core.prompts import PromptTemplate

        llm = context[self.config["llm_block_id"]]

        tools = [
            Tool(
                name=tid[:8],
                func=lambda _, tid=tid: context[tid],
                description="HTTP tool",
            )
            for tid in self.config.get("tool_block_ids", [])
        ]

        prompt = PromptTemplate.from_template(self._REACT_PROMPT)
        agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)

        executor_kwargs: dict = {"agent": agent, "tools": tools, "verbose": True}
        if self.config.get("memory_enabled"):
            executor_kwargs["memory"] = ConversationBufferMemory()

        executor = AgentExecutor(**executor_kwargs)
        result = executor.invoke({"input": self.config["user_prompt"]})
        return result.get("output", result)

    def generate_code_snippet(self) -> str:
        var = _to_var_name(self.name)
        lines = []
        if self.config.get("memory_enabled"):
            lines.append(f"memory_{var} = ConversationBufferMemory()")
        lines.append(f"agent_{var} = AgentExecutor(")
        lines.append(f"    agent=create_react_agent(llm=llm, tools=tools, prompt=react_prompt),")
        lines.append(f"    tools=tools,")
        lines.append(f"    verbose=True,")
        if self.config.get("memory_enabled"):
            lines.append(f"    memory=memory_{var},")
        lines.append(f")")
        lines.append(
            f"result_{var} = agent_{var}.invoke({{\"input\": {self.config['user_prompt']!r}}})"
        )
        lines.append(f"print(result_{var})")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTTPBlock
# ---------------------------------------------------------------------------

class HTTPBlock(Block):
    """Performs an HTTP request and returns the parsed JSON response.

    Can be used standalone in a workflow or as a LangChain Tool inside an
    AgentBlock.
    """

    def __init__(self, name: str = "HTTP", config: dict = None, block_id: str = None):
        super().__init__(name, config, block_id)
        self.config.setdefault("method", "GET")
        self.config.setdefault("url", "")
        self.config.setdefault("headers", {})
        self.config.setdefault("body", {})
        self.input_ports = [
            Port(name="http_input", direction="input", data_type="any", required=False),
        ]
        self.output_ports = [
            Port(name="http_output", direction="output", data_type="dict"),
        ]

    def validate(self) -> bool:
        return (
            super().validate()
            and self.config.get("method") in ("GET", "POST", "PUT", "DELETE")
            and bool(self.config.get("url"))
        )

    def execute(self, context: dict) -> Any:
        """Send the configured HTTP request and return the JSON response body."""
        import requests

        response = requests.request(
            method=self.config["method"],
            url=self.config["url"],
            headers=self.config.get("headers") or {},
            json=self.config.get("body") or None,
        )
        return response.json()

    def generate_code_snippet(self) -> str:
        var = _to_var_name(self.name)
        method = self.config["method"]
        url = self.config["url"]
        headers = self.config.get("headers") or {}
        return (
            f"def block_{var}(input=None):\n"
            f"    response = requests.request(\n"
            f"        {method!r},\n"
            f"        {url!r},\n"
            f"        headers={headers!r},\n"
            f"    )\n"
            f"    return response.json()\n\n"
            f"{var}_tool = Tool(\n"
            f"    name={self.name!r},\n"
            f"    func=block_{var},\n"
            f"    description='HTTP {method} {url}',\n"
            f")"
        )


# ---------------------------------------------------------------------------
# PythonScriptBlock
# ---------------------------------------------------------------------------

class PythonScriptBlock(Block):
    """Executes a user-defined Python function as a workflow step.

    Input ports are derived automatically from the function signature via
    AST parsing whenever the script code is set.
    """

    def __init__(self, name: str = "Script", config: dict = None, block_id: str = None):
        super().__init__(name, config, block_id)
        self.config.setdefault("script_code", "")
        self.config.setdefault("function_name", "run")
        self.config.setdefault("detected_inputs", [])
        self.config.setdefault("detected_outputs", ["output"])

        if self.config["script_code"]:
            self.parse_signature()

    def parse_signature(self) -> None:
        """Infer input ports from the main function's parameters via AST.

        Updates detected_inputs in config and rebuilds input_ports and output_ports.
        """
        try:
            tree = ast.parse(self.config["script_code"])
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.FunctionDef)
                    and node.name == self.config["function_name"]
                ):
                    self.config["detected_inputs"] = [arg.arg for arg in node.args.args]
                    break
        except SyntaxError:
            pass

        self.input_ports = [
            Port(name=param, direction="input", data_type="any", required=True)
            for param in self.config["detected_inputs"]
        ]
        self.output_ports = [
            Port(name="output", direction="output", data_type="any"),
        ]

    def validate_script(self) -> bool:
        """Return True if the script code parses without a SyntaxError."""
        try:
            ast.parse(self.config["script_code"])
            return True
        except SyntaxError:
            return False

    def validate(self) -> bool:
        return (
            super().validate()
            and bool(self.config.get("script_code"))
            and bool(self.config.get("function_name"))
            and self.validate_script()
        )

    def execute(self, context: dict) -> Any:
        """Execute the user's script function with inputs pulled from context."""
        local_vars: dict = {}
        exec(self.config["script_code"], {}, local_vars)  # noqa: S102
        func = local_vars[self.config["function_name"]]
        inputs = {k: context[k] for k in self.config["detected_inputs"]}
        return func(**inputs)

    def generate_code_snippet(self) -> str:
        return self.config.get("script_code", "# no script defined")
