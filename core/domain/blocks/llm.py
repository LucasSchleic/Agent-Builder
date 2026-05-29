import os
from typing import Any

from core.domain.blocks.base import Block, _to_var_name
from core.domain.port import Port


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

    @staticmethod
    def _resolve(value: str) -> str:
        """Resolve a config value: if it looks like an env var name (no spaces, no '://'),
        return os.getenv(value) or the literal value as fallback."""
        if value and " " not in value and "://" not in value:
            resolved = os.getenv(value)
            if resolved:
                return resolved
        return value

    @staticmethod
    def _snippet_value(value: str) -> str:
        """Return a Python expression for a config value.

        If the value looks like an env var name, emit os.getenv(...) so the
        export service can resolve it to the actual value at export time.
        """
        if value and " " not in value and "://" not in value:
            return f"os.getenv({value!r})"
        return repr(value)

    def execute(self, context: dict) -> Any:
        """Instantiate and return a configured ChatOpenAI object."""
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            base_url=self._resolve(self.config["api_url"]),
            model=self._resolve(self.config["model_name"]),
            temperature=self.config["temperature"],
            api_key=os.getenv(self.config["api_key_env_var"]),
        )

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
