import ast
from typing import Any

from core.domain.blocks.base import Block, _to_var_name
from core.domain.port import Port


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
        self.config.setdefault("function_name", "run")
        self.config.setdefault("detected_inputs", [])
        self.config.setdefault("detected_outputs", ["output"])
        self.config.setdefault("detected_config", {})

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
                                "value":   existing.get("value", default),
                            }
                    self.config["detected_config"] = detected_config
                    break
        except SyntaxError:
            pass

        old_inputs = {p.name: p.id for p in self.input_ports}
        self.input_ports = [
            Port(name=param, direction="input", data_type="any", required=True,
                 port_id=old_inputs.get(param))
            for param in self.config["detected_inputs"]
        ]
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

        dc = self.config.get("detected_config", {})
        if dc:
            overrides = {k: v["value"] for k, v in dc.items()}
            try:
                tree = self._ConfigInjector(overrides).visit(ast.parse(script))
                ast.fix_missing_locations(tree)
                script = ast.unparse(tree)
            except Exception:
                pass

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
