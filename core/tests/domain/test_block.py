import unittest

from core.domain.block import Block, LLMBlock, AgentBlock, HTTPBlock, PythonScriptBlock


class TestLLMBlock(unittest.TestCase):
    """Tests for LLMBlock."""

    def _make_valid(self):
        return LLMBlock(name="My LLM", config={
            "api_url": "https://api.example.com",
            "model_name": "gpt-4o",
            "temperature": 0.7,
            "api_key_env_var": "GENAI_API_KEY",
        })

    def test_has_no_input_ports(self):
        block = LLMBlock()
        self.assertEqual(len(block.input_ports), 0)

    def test_has_one_output_port(self):
        block = LLMBlock()
        self.assertEqual(len(block.output_ports), 1)
        self.assertEqual(block.output_ports[0].data_type, "llm")

    def test_validate_ok(self):
        self.assertTrue(self._make_valid().validate())

    def test_validate_fails_missing_api_url(self):
        block = self._make_valid()
        block.config["api_url"] = ""
        self.assertFalse(block.validate())

    def test_validate_fails_missing_model_name(self):
        block = self._make_valid()
        block.config["model_name"] = ""
        self.assertFalse(block.validate())

    def test_validate_fails_empty_name(self):
        block = self._make_valid()
        block.name = ""
        self.assertFalse(block.validate())

    def test_get_dependencies_is_empty(self):
        self.assertEqual(self._make_valid().get_dependencies(), [])

    def test_to_dict_includes_type(self):
        d = self._make_valid().to_dict()
        self.assertEqual(d["type"], "LLMBlock")

    def test_to_dict_includes_config(self):
        block = self._make_valid()
        d = block.to_dict()
        self.assertEqual(d["config"]["model_name"], "gpt-4o")

    def test_from_dict_roundtrip(self):
        block = self._make_valid()
        restored = Block.from_dict(block.to_dict())
        self.assertIsInstance(restored, LLMBlock)
        self.assertEqual(restored.name, block.name)
        self.assertEqual(restored.config["model_name"], "gpt-4o")

    def test_generate_code_snippet_contains_model_name(self):
        snippet = self._make_valid().generate_code_snippet()
        self.assertIn("gpt-4o", snippet)
        self.assertIn("ChatOpenAI", snippet)


class TestAgentBlock(unittest.TestCase):
    """Tests for AgentBlock."""

    def _make_valid(self):
        return AgentBlock(name="My Agent", config={
            "llm_block_id": "llm-uuid-123",
            "tool_block_ids": ["tool-uuid-456"],
            "user_prompt": "Do something",
            "memory_enabled": False,
        })

    def test_has_input_and_output_ports(self):
        block = AgentBlock()
        self.assertTrue(any(p.direction == "input" for p in block.input_ports))
        self.assertTrue(any(p.direction == "output" for p in block.output_ports))

    def test_validate_ok(self):
        self.assertTrue(self._make_valid().validate())

    def test_validate_fails_missing_llm_block_id(self):
        block = self._make_valid()
        block.config["llm_block_id"] = ""
        self.assertFalse(block.validate())

    def test_get_dependencies_includes_llm_and_tools(self):
        block = self._make_valid()
        deps = block.get_dependencies()
        self.assertIn("llm-uuid-123", deps)
        self.assertIn("tool-uuid-456", deps)

    def test_get_dependencies_no_tools(self):
        block = AgentBlock(name="A", config={"llm_block_id": "llm-id", "tool_block_ids": []})
        self.assertEqual(block.get_dependencies(), ["llm-id"])

    def test_from_dict_roundtrip(self):
        block = self._make_valid()
        restored = Block.from_dict(block.to_dict())
        self.assertIsInstance(restored, AgentBlock)
        self.assertEqual(restored.config["llm_block_id"], "llm-uuid-123")

    def test_generate_code_snippet_contains_agent_executor(self):
        snippet = self._make_valid().generate_code_snippet()
        self.assertIn("AgentExecutor", snippet)

    def test_generate_code_snippet_with_memory(self):
        block = self._make_valid()
        block.config["memory_enabled"] = True
        snippet = block.generate_code_snippet()
        self.assertIn("ConversationBufferMemory", snippet)

    def test_generate_code_snippet_without_memory(self):
        snippet = self._make_valid().generate_code_snippet()
        self.assertNotIn("ConversationBufferMemory", snippet)


class TestHTTPBlock(unittest.TestCase):
    """Tests for HTTPBlock."""

    def _make_valid(self):
        return HTTPBlock(name="My HTTP", config={
            "method": "GET",
            "url": "https://api.example.com/data",
            "headers": {},
            "body": {},
        })

    def test_has_input_and_output_ports(self):
        block = HTTPBlock()
        self.assertEqual(len(block.input_ports), 1)
        self.assertEqual(len(block.output_ports), 1)

    def test_validate_ok(self):
        self.assertTrue(self._make_valid().validate())

    def test_validate_fails_missing_url(self):
        block = self._make_valid()
        block.config["url"] = ""
        self.assertFalse(block.validate())

    def test_validate_fails_invalid_method(self):
        block = self._make_valid()
        block.config["method"] = "PATCH"
        self.assertFalse(block.validate())

    def test_validate_all_methods(self):
        for method in ("GET", "POST", "PUT", "DELETE"):
            block = self._make_valid()
            block.config["method"] = method
            self.assertTrue(block.validate(), f"Expected valid method: {method}")

    def test_from_dict_roundtrip(self):
        block = self._make_valid()
        restored = Block.from_dict(block.to_dict())
        self.assertIsInstance(restored, HTTPBlock)
        self.assertEqual(restored.config["url"], "https://api.example.com/data")

    def test_generate_code_snippet_contains_requests(self):
        snippet = self._make_valid().generate_code_snippet()
        self.assertIn("requests.request", snippet)
        self.assertIn("Tool", snippet)


class TestPythonScriptBlock(unittest.TestCase):
    """Tests for PythonScriptBlock."""

    SCRIPT = "def run(x, y):\n    return x + y"

    def _make_block(self, script=None):
        return PythonScriptBlock(name="Script", config={
            "script_code": script or self.SCRIPT,
            "function_name": "run",
        })

    def test_parse_signature_detects_inputs(self):
        block = self._make_block()
        self.assertEqual(block.config["detected_inputs"], ["x", "y"])

    def test_parse_signature_creates_input_ports(self):
        block = self._make_block()
        port_names = [p.name for p in block.input_ports]
        self.assertIn("x", port_names)
        self.assertIn("y", port_names)

    def test_parse_signature_creates_output_port(self):
        block = self._make_block()
        self.assertEqual(len(block.output_ports), 1)
        self.assertEqual(block.output_ports[0].name, "output")

    def test_validate_script_valid(self):
        self.assertTrue(self._make_block().validate_script())

    def test_validate_script_invalid_syntax(self):
        block = self._make_block(script="def run(x:\n    return x")
        self.assertFalse(block.validate_script())

    def test_validate_ok(self):
        self.assertTrue(self._make_block().validate())

    def test_validate_fails_empty_script(self):
        block = PythonScriptBlock(name="S", config={"script_code": "", "function_name": "run"})
        self.assertFalse(block.validate())

    def test_execute_runs_script(self):
        block = self._make_block()
        result = block.execute({"x": 3, "y": 4})
        self.assertEqual(result, 7)

    def test_generate_code_snippet_returns_script(self):
        block = self._make_block()
        self.assertEqual(block.generate_code_snippet(), self.SCRIPT)

    def test_from_dict_roundtrip(self):
        block = self._make_block()
        restored = Block.from_dict(block.to_dict())
        self.assertIsInstance(restored, PythonScriptBlock)
        self.assertEqual(restored.config["script_code"], self.SCRIPT)


class TestBlockFromDict(unittest.TestCase):
    """Tests for the Block.from_dict() dispatch mechanism."""

    def test_dispatches_to_llm_block(self):
        block = LLMBlock(name="L")
        self.assertIsInstance(Block.from_dict(block.to_dict()), LLMBlock)

    def test_dispatches_to_agent_block(self):
        block = AgentBlock(name="A")
        self.assertIsInstance(Block.from_dict(block.to_dict()), AgentBlock)

    def test_dispatches_to_http_block(self):
        block = HTTPBlock(name="H")
        self.assertIsInstance(Block.from_dict(block.to_dict()), HTTPBlock)

    def test_dispatches_to_python_script_block(self):
        block = PythonScriptBlock(name="P")
        self.assertIsInstance(Block.from_dict(block.to_dict()), PythonScriptBlock)

    def test_unknown_type_raises_value_error(self):
        with self.assertRaises(ValueError):
            Block.from_dict({"type": "UnknownBlock", "id": "x", "name": "x", "config": {}})


if __name__ == "__main__":
    unittest.main()
