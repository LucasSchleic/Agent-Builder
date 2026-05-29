from typing import Any

from core.domain.blocks.base import Block, _to_var_name
from core.domain.port import Port


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
        """Generate the Tool-wrapped snippet — used when connected to an AgentBlock."""
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
            f"    name={var!r},\n"
            f"    func=block_{var},\n"
            f"    description='HTTP {method} {url}',\n"
            f")"
        )

    def generate_standalone_snippet(self) -> str:
        """Generate a direct HTTP call snippet — used when not connected to any AgentBlock."""
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
