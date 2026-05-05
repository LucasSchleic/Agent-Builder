import os
import tempfile
import unittest

from core.domain.block import AgentBlock, HTTPBlock, LLMBlock, PythonScriptBlock
from core.domain.connection import Connection
from core.domain.workflow import Workflow
from core.services.export_service import ExportService


def _llm(block_id="llm-1", name="LLM") -> LLMBlock:
    return LLMBlock(name=name, block_id=block_id, config={
        "api_url": "http://example.com", "model_name": "gpt-4o",
        "temperature": 0.7, "api_key_env_var": "GENAI_API_KEY",
    })


def _http(block_id="http-1", name="HTTP Tool") -> HTTPBlock:
    return HTTPBlock(name=name, block_id=block_id, config={
        "method": "GET", "url": "https://api.example.com/data",
    })


def _agent(block_id="agent-1", llm_id="llm-1", tool_ids=None) -> AgentBlock:
    return AgentBlock(name="My Agent", block_id=block_id, config={
        "llm_block_id": llm_id,
        "tool_block_ids": tool_ids or [],
        "user_prompt": "Hello",
        "memory_enabled": False,
    })


def _script(block_id="script-1") -> PythonScriptBlock:
    return PythonScriptBlock(name="My Script", block_id=block_id, config={
        "script_code": "def run(x):\n    return x * 2",
        "function_name": "run",
    })


class TestTopologicalSort(unittest.TestCase):
    """Tests for ExportService.topological_sort."""

    def setUp(self):
        self.service = ExportService()

    def test_single_block_returns_it(self):
        wf = Workflow(name="w")
        wf.add_block(_llm())
        result = self.service.topological_sort(wf)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "llm-1")

    def test_dependency_comes_before_dependent(self):
        wf = Workflow(name="w")
        llm = _llm()
        agent = _agent(llm_id="llm-1")
        wf.add_block(llm)
        wf.add_block(agent)
        conn = Connection(
            source_block_id="llm-1",
            source_port_id=llm.output_ports[0].id,
            target_block_id="agent-1",
            target_port_id=agent.input_ports[0].id,
            connection_id="c1",
        )
        wf.add_connection(conn)
        result = self.service.topological_sort(wf)
        ids = [b.id for b in result]
        self.assertLess(ids.index("llm-1"), ids.index("agent-1"))

    def test_disconnected_blocks_all_returned(self):
        wf = Workflow(name="w")
        wf.add_block(_llm())
        wf.add_block(_http())
        result = self.service.topological_sort(wf)
        self.assertEqual(len(result), 2)

    def test_empty_workflow_returns_empty(self):
        wf = Workflow(name="w")
        result = self.service.topological_sort(wf)
        self.assertEqual(result, [])


class TestCollectImports(unittest.TestCase):
    """Tests for ExportService._collect_imports."""

    def setUp(self):
        self.service = ExportService()

    def test_always_includes_os_and_dotenv(self):
        imports = self.service._collect_imports([])
        self.assertIn("import os", imports)
        self.assertIn("from dotenv import load_dotenv", imports)

    def test_llm_block_adds_chatOpenAI(self):
        imports = self.service._collect_imports([_llm()])
        self.assertTrue(any("ChatOpenAI" in i for i in imports))

    def test_http_block_adds_requests(self):
        imports = self.service._collect_imports([_http()])
        self.assertIn("import requests", imports)

    def test_agent_block_adds_langchain_agents(self):
        imports = self.service._collect_imports([_agent()])
        self.assertTrue(any("AgentExecutor" in i for i in imports))
        self.assertTrue(any("PromptTemplate" in i for i in imports))

    def test_memory_enabled_adds_memory_import(self):
        agent = AgentBlock(name="A", block_id="a1", config={
            "llm_block_id": "llm-1", "memory_enabled": True,
        })
        imports = self.service._collect_imports([agent])
        self.assertTrue(any("ConversationBufferMemory" in i for i in imports))

    def test_memory_disabled_no_memory_import(self):
        imports = self.service._collect_imports([_agent()])
        self.assertFalse(any("ConversationBufferMemory" in i for i in imports))

    def test_no_duplicate_tool_import(self):
        imports = self.service._collect_imports([_http(), _agent()])
        tool_imports = [i for i in imports if "Tool" in i and "from langchain.tools" in i]
        self.assertEqual(len(tool_imports), 1)


class TestGeneratePython(unittest.TestCase):
    """Tests for ExportService.generate_python."""

    def setUp(self):
        self.service = ExportService()

    def test_contains_header_with_workflow_name(self):
        wf = Workflow(name="my_workflow")
        wf.add_block(_llm())
        script = self.service.generate_python(wf)
        self.assertIn("my_workflow", script)

    def test_contains_load_dotenv(self):
        wf = Workflow(name="w")
        wf.add_block(_llm())
        script = self.service.generate_python(wf)
        self.assertIn("load_dotenv()", script)

    def test_block_comment_present(self):
        wf = Workflow(name="w")
        wf.add_block(_llm(name="My LLM"))
        script = self.service.generate_python(wf)
        self.assertIn("# --- Bloc : My LLM (LLMBlock) ---", script)

    def test_llm_snippet_present(self):
        wf = Workflow(name="w")
        wf.add_block(_llm())
        script = self.service.generate_python(wf)
        self.assertIn("ChatOpenAI", script)

    def test_http_standalone_uses_direct_call(self):
        wf = Workflow(name="w")
        wf.add_block(_http())
        script = self.service.generate_python(wf)
        # Standalone HTTPBlock must call the request directly, not wrap it in a Tool.
        self.assertIn("result_", script)
        self.assertIn("requests.request", script)
        self.assertNotIn("Tool(", script)

    def test_http_as_tool_uses_tool_wrapper(self):
        wf = Workflow(name="w")
        llm = _llm()
        http = _http()
        agent = _agent(llm_id="llm-1", tool_ids=["http-1"])
        wf.add_block(llm)
        wf.add_block(http)
        wf.add_block(agent)
        script = self.service.generate_python(wf)
        # HTTPBlock wired to an agent must produce a Tool object.
        self.assertIn("Tool(", script)
        self.assertIn("def block_", script)

    def test_agent_glue_injects_tools_and_prompt(self):
        wf = Workflow(name="w")
        llm = _llm()
        agent = _agent(llm_id="llm-1", tool_ids=[])
        wf.add_block(llm)
        wf.add_block(agent)
        script = self.service.generate_python(wf)
        self.assertIn("tools = []", script)
        self.assertIn("react_prompt", script)

    def test_agent_glue_injects_llm_alias_when_needed(self):
        wf = Workflow(name="w")
        llm = _llm(name="Custom LLM Name")
        agent = _agent(llm_id="llm-1")
        wf.add_block(llm)
        wf.add_block(agent)
        script = self.service.generate_python(wf)
        self.assertIn("llm = custom_llm_name", script)

    def test_agent_no_llm_alias_when_already_named_llm(self):
        wf = Workflow(name="w")
        llm = _llm(name="LLM")
        agent = _agent(llm_id="llm-1")
        wf.add_block(llm)
        wf.add_block(agent)
        script = self.service.generate_python(wf)
        self.assertNotIn("llm = llm", script)

    def test_python_script_snippet_present(self):
        wf = Workflow(name="w")
        wf.add_block(_script())
        script = self.service.generate_python(wf)
        self.assertIn("def run(x):", script)

    def test_dependency_order_in_output(self):
        wf = Workflow(name="w")
        llm = _llm()
        agent = _agent(llm_id="llm-1")
        wf.add_block(llm)
        wf.add_block(agent)
        conn = Connection(
            source_block_id="llm-1",
            source_port_id=llm.output_ports[0].id,
            target_block_id="agent-1",
            target_port_id=agent.input_ports[0].id,
            connection_id="c1",
        )
        wf.add_connection(conn)
        script = self.service.generate_python(wf)
        self.assertLess(script.index("LLMBlock"), script.index("AgentBlock"))


class TestExportToFile(unittest.TestCase):
    """Tests for ExportService.export_to_file."""

    def setUp(self):
        self.service = ExportService()
        self.tmp_dir = tempfile.mkdtemp()

    def test_creates_py_file(self):
        wf = Workflow(name="w")
        wf.add_block(_llm())
        path = os.path.join(self.tmp_dir, "export.py")
        self.service.export_to_file(wf, path)
        self.assertTrue(os.path.isfile(path))

    def test_file_content_matches_generate_python(self):
        wf = Workflow(name="w")
        wf.add_block(_llm())
        path = os.path.join(self.tmp_dir, "export.py")
        self.service.export_to_file(wf, path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertEqual(content, self.service.generate_python(wf))


if __name__ == "__main__":
    unittest.main()
