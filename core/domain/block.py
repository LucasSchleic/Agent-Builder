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
        # Guard against a caller passing None explicitly instead of omitting the argument.
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
            # The class name is saved so from_dict() knows which subclass to recreate.
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
        # Mapping from the saved type string to the actual Python class.
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
        # Ports are restored from saved data instead of relying on __init__ defaults,
        # so that any user-edited port IDs are preserved across save/load cycles.
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
        # setdefault only sets the value if the key is not already present,
        # so a config passed at construction time is never overwritten.
        self.config.setdefault("api_url", "")
        self.config.setdefault("model_name", "")
        self.config.setdefault("temperature", 0.7)
        self.config.setdefault("api_key_env_var", "GENAI_API_KEY")
        self.output_ports = [
            Port(name="llm_output", direction="output", data_type="llm"),
        ]

    def validate(self) -> bool:
        # All three fields must be non-empty: without them the ChatOpenAI call would fail.
        return (
            super().validate()
            and bool(self.config.get("api_url"))
            and bool(self.config.get("model_name"))
            and bool(self.config.get("api_key_env_var"))
        )

    @staticmethod
    def _resolve(value: str) -> str:
        """Resolve a config value: if it looks like an env var name (no spaces, no '://'),
        return os.getenv(value) or the literal value as fallback."""
        if value and " " not in value and "://" not in value:
            resolved = os.getenv(value)
            if resolved:
                return resolved
        return value

    def execute(self, context: dict) -> Any:
        """Instantiate and return a configured ChatOpenAI object."""
        # Lazy import: keeps the domain importable even if langchain is not installed yet.
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            base_url=self._resolve(self.config["api_url"]),
            model=self._resolve(self.config["model_name"]),
            temperature=self.config["temperature"],
            # Read the API key from the environment at runtime — never hardcoded.
            api_key=os.getenv(self.config["api_key_env_var"]),
        )

    @staticmethod
    def _snippet_value(value: str) -> str:
        """Return a Python expression for a config value.

        If the value looks like an env var name, emit os.getenv(...) so the
        export service can resolve it to the actual value at export time.
        """
        if value and " " not in value and "://" not in value:
            return f"os.getenv({value!r})"
        return repr(value)

    def generate_code_snippet(self) -> str:
        var = _to_var_name(self.name)
        env_var = self.config["api_key_env_var"]
        return (
            f"{var} = ChatOpenAI(\n"
            f"    base_url={self._snippet_value(self.config['api_url'])},\n"
            f"    model={self._snippet_value(self.config['model_name'])},\n"
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
    # Placeholders {tools}, {tool_names}, {input}, {agent_scratchpad} are
    # filled in automatically by LangChain's AgentExecutor at runtime.
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
        # llm_block_id and tool_block_ids are set by the user when wiring the canvas.
        self.config.setdefault("llm_block_id", "")
        self.config.setdefault("tool_block_ids", [])
        self.input_ports = [
            # llm_input is required: the agent cannot run without an LLM.
            Port(name="llm_input", direction="input", data_type="llm", required=True),
            # tool_input is optional: the agent can run with zero tools.
            Port(name="tool_input", direction="input", data_type="tool", required=False),
        ]
        self.output_ports = [
            Port(name="agent_output", direction="output", data_type="str"),
        ]

    def validate(self) -> bool:
        # An agent without an LLM reference is not executable.
        return super().validate() and bool(self.config.get("llm_block_id"))

    def get_dependencies(self) -> List[str]:
        """Return the LLM block ID followed by all tool block IDs."""
        deps = []
        if self.config.get("llm_block_id"):
            deps.append(self.config["llm_block_id"])
        deps.extend(self.config.get("tool_block_ids", []))
        return deps

    def execute(self, context: dict) -> Any:
        """Build and invoke a LangChain agent using the create_agent API (v1.x)."""
        # Lazy imports — defer until actually needed.
        from langchain.agents import create_agent
        from langchain_core.tools import Tool

        # Retrieve the ChatOpenAI object produced by the upstream LLMBlock.
        llm = context[self.config["llm_block_id"]]

        tools = [
            Tool(
                name=tid[:8],
                # tid=tid captures the current loop value to avoid the late-binding closure trap.
                func=lambda _, tid=tid: context[tid],
                description="HTTP tool",
            )
            for tid in self.config.get("tool_block_ids", [])
        ]

        agent_kwargs: dict = {
            "model": llm,
            "tools": tools or None,
        }
        # Pass the system prompt if one is configured.
        if self.config.get("system_prompt"):
            agent_kwargs["system_prompt"] = self.config["system_prompt"]
        # Memory is implemented via a LangGraph MemorySaver checkpointer.
        if self.config.get("memory_enabled"):
            from langgraph.checkpoint.memory import MemorySaver
            agent_kwargs["checkpointer"] = MemorySaver()

        agent = create_agent(**agent_kwargs)
        result = agent.invoke({
            "messages": [{"role": "user", "content": self.config["user_prompt"]}]
        })
        # create_agent returns a state dict with a 'messages' list.
        # The last message is the AI's final response.
        messages = result.get("messages", [])
        if messages:
            last = messages[-1]
            return last.content if hasattr(last, "content") else str(last)
        return str(result)

    def generate_code_snippet(self) -> str:
        var = _to_var_name(self.name)
        lines = []
        # llm and tools are injected by ExportService before this snippet.
        lines.append(f"agent_{var} = create_agent(")
        lines.append(f"    model=llm,")
        lines.append(f"    tools=tools or None,")
        if self.config.get("system_prompt"):
            lines.append(f"    system_prompt={self.config['system_prompt']!r},")
        if self.config.get("memory_enabled"):
            lines.append(f"    checkpointer=MemorySaver(),")
        lines.append(f")")
        # Double braces {{ }} produce literal { } in the f-string output.
        lines.append(
            f"result_{var} = agent_{var}.invoke({{\"messages\": [{{\"role\": \"user\", \"content\": {self.config['user_prompt']!r}}}]}})"
        )
        lines.append(f"print(result_{var}['messages'][-1].content)")
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
        # body is only sent for POST/PUT requests; ignored for GET/DELETE.
        self.config.setdefault("body", {})
        self.input_ports = [
            # input is optional: HTTPBlock can be the first block in a workflow.
            Port(name="http_input", direction="input", data_type="any", required=False),
        ]
        self.output_ports = [
            Port(name="http_output", direction="output", data_type="dict"),
        ]

    def validate(self) -> bool:
        # Only standard HTTP methods are accepted to prevent misconfiguration.
        return (
            super().validate()
            and self.config.get("method") in ("GET", "POST", "PUT", "DELETE")
            and bool(self.config.get("url"))
        )

    def execute(self, context: dict) -> Any:
        """Send the configured HTTP request and return the JSON response body."""
        # Lazy import: avoids requiring requests at domain import time.
        import requests

        response = requests.request(
            method=self.config["method"],
            url=self.config["url"],
            # `or {}` converts None (if the key exists but was set to None) to an empty dict.
            headers=self.config.get("headers") or {},
            # Pass body as JSON only when it has content; None disables the request body.
            json=self.config.get("body") or None,
        )
        return response.json()

    def generate_code_snippet(self) -> str:
        """Generate the Tool-wrapped snippet — used when connected to an AgentBlock."""
        var = _to_var_name(self.name)
        method = self.config["method"]
        url = self.config["url"]
        headers = self.config.get("headers") or {}
        # The HTTP call is wrapped in a function so it can be passed as a LangChain Tool.
        return (
            f"def block_{var}(input=None):\n"
            f"    response = requests.request(\n"
            f"        {method!r},\n"
            f"        {url!r},\n"
            f"        headers={headers!r},\n"
            f"    )\n"
            f"    return response.json()\n\n"
            f"{var}_tool = Tool(\n"
            f"    name={var!r},\n"
            f"    func=block_{var},\n"
            f"    description='HTTP {method} {url}',\n"
            f")"
        )

    def generate_standalone_snippet(self) -> str:
        """Generate a direct HTTP call snippet — used when not connected to any AgentBlock.

        Unlike generate_code_snippet(), this does not wrap the call in a function
        or create a Tool object. It simply executes the request and prints the result.
        """
        var = _to_var_name(self.name)
        method = self.config["method"]
        url = self.config["url"]
        headers = self.config.get("headers") or {}
        body = self.config.get("body") or None
        lines = (
            f"result_{var} = requests.request(\n"
            f"    {method!r},\n"
            f"    {url!r},\n"
            f"    headers={headers!r},\n"
        )
        if body:
            lines += f"    json={body!r},\n"
        lines += f")\nprint(result_{var}.json())"
        return lines


# ---------------------------------------------------------------------------
# PythonScriptBlock
# ---------------------------------------------------------------------------

class PythonScriptBlock(Block):
    """Executes a user-defined Python function as a workflow step.

    Input ports are derived automatically from the function signature via
    AST parsing whenever the script code is set.
    """

    _DEFAULT_SCRIPT = (
        "def run(input):\n"
        "    \n"
        "    # Modify this function to process your data.\n"
        "    # Parameters become input ports (connected to other blocks).\n"
        "    # ALL_CAPS variables will become configurable fields (coming soon).\n"
        "    \n"
        "    OUTPUT_DIR = 'output'\n"
        "    result = str(input)\n"
        "    return result\n"
    )

    def __init__(self, name: str = "Script", config: dict = None, block_id: str = None):
        super().__init__(name, config, block_id)
        self.config.setdefault("script_code", self._DEFAULT_SCRIPT)
        # function_name identifies which function inside the script to call.
        self.config.setdefault("function_name", "run")
        self.config.setdefault("detected_inputs", [])
        self.config.setdefault("detected_outputs", ["output"])
        # detected_config: ALL_CAPS variables detected in the script body.
        # Each entry: {"key": "OUTPUT_DIR", "label": "Output Dir", "default": "output", "value": "output"}
        # Reserved for configurable fields feature (IMPROVEMENTS.md #3).
        self.config.setdefault("detected_config", {})

        # If the block is loaded from saved data, the script is already set —
        # parse it immediately so ports reflect the actual function signature.
        if self.config["script_code"]:
            self.parse_signature()

    def parse_signature(self) -> None:
        """Infer input ports from the main function's parameters via AST.

        Updates detected_inputs in config and rebuilds input_ports and output_ports.
        """
        try:
            # Parse the script source code into an AST without executing it.
            tree = ast.parse(self.config["script_code"])
            for node in ast.walk(tree):
                # Find the function whose name matches function_name.
                if (
                    isinstance(node, ast.FunctionDef)
                    and node.name == self.config["function_name"]
                ):
                    # Extract parameter names from the function definition.
                    self.config["detected_inputs"] = [arg.arg for arg in node.args.args]

                    # Detect ALL_CAPS assignments as future configurable fields.
                    # Stored now, used by the configurable-fields feature (IMPROVEMENTS.md #3).
                    detected_config = {}
                    for stmt in node.body:
                        if (
                            isinstance(stmt, ast.Assign)
                            and len(stmt.targets) == 1
                            and isinstance(stmt.targets[0], ast.Name)
                            and stmt.targets[0].id.isupper()
                            and isinstance(stmt.value, (ast.Constant,))
                        ):
                            key = stmt.targets[0].id
                            default = stmt.value.value
                            label = key.replace("_", " ").title()
                            existing = self.config.get("detected_config", {}).get(key, {})
                            detected_config[key] = {
                                "label":   label,
                                "default": default,
                                # Preserve user-edited value if already set.
                                "value":   existing.get("value", default),
                            }
                    self.config["detected_config"] = detected_config
                    break
        except SyntaxError:
            # If the script has a syntax error, keep whatever inputs were detected before.
            pass

        # Rebuild input ports, preserving existing port IDs by name so that
        # connections referencing those IDs are not invalidated on each save.
        old_inputs = {p.name: p.id for p in self.input_ports}
        self.input_ports = [
            Port(name=param, direction="input", data_type="any", required=True,
                 port_id=old_inputs.get(param))
            for param in self.config["detected_inputs"]
        ]
        # Preserve the output port ID the same way.
        old_output_id = self.output_ports[0].id if self.output_ports else None
        self.output_ports = [
            Port(name="output", direction="output", data_type="any",
                 port_id=old_output_id),
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

    class _ConfigInjector(ast.NodeTransformer):
        """Rewrites ALL_CAPS constant assignments with user-configured values."""
        def __init__(self, values: dict):
            self.values = values

        def visit_Assign(self, node):
            if (
                len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in self.values
                and isinstance(node.value, ast.Constant)
            ):
                node.value = ast.Constant(value=self.values[node.targets[0].id])
            return node

    def execute(self, context: dict) -> Any:
        """Execute the user's script function with inputs pulled from context."""
        script = self.config["script_code"]

        # If the user configured ALL_CAPS fields, rewrite their values in the AST
        # before executing so the script uses the configured values, not the defaults.
        dc = self.config.get("detected_config", {})
        if dc:
            overrides = {k: v["value"] for k, v in dc.items()}
            try:
                tree = self._ConfigInjector(overrides).visit(ast.parse(script))
                ast.fix_missing_locations(tree)
                script = ast.unparse(tree)
            except Exception:
                pass  # Fall back to the original script on any AST error.

        local_vars: dict = {}
        exec(script, {}, local_vars)  # noqa: S102
        func = local_vars[self.config["function_name"]]
        inputs = {k: context[k] for k in self.config["detected_inputs"]}
        return func(**inputs)

    def generate_code_snippet(self) -> str:
        script = self.config.get("script_code", "# no script defined")
        dc = self.config.get("detected_config", {})
        if dc:
            overrides = {k: v["value"] for k, v in dc.items()}
            try:
                tree = self._ConfigInjector(overrides).visit(ast.parse(script))
                ast.fix_missing_locations(tree)
                script = ast.unparse(tree)
            except Exception:
                pass
        return script
