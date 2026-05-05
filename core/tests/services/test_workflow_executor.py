import unittest

from core.domain.block import PythonScriptBlock
from core.domain.connection import Connection
from core.domain.workflow import Workflow
from core.services.workflow_executor import WorkflowExecutor


def _script(block_id: str, name: str, code: str, function_name: str = "run") -> PythonScriptBlock:
    """Helper to build a PythonScriptBlock with auto-parsed ports."""
    return PythonScriptBlock(
        name=name,
        block_id=block_id,
        config={"script_code": code, "function_name": function_name},
    )


class TestTopologicalSort(unittest.TestCase):
    """Tests for WorkflowExecutor._topological_sort."""

    def setUp(self):
        self.executor = WorkflowExecutor()

    def test_single_block_returned(self):
        wf = Workflow(name="w")
        b = _script("b1", "A", "def run(): return 1")
        wf.add_block(b)
        result = self.executor.topological_sort(wf)
        self.assertEqual([b.id for b in result], ["b1"])

    def test_dependency_comes_first(self):
        wf = Workflow(name="w")
        b1 = _script("b1", "First", "def run(): return 1")
        b2 = _script("b2", "Second", "def run(x): return x", "run")
        wf.add_block(b1)
        wf.add_block(b2)
        conn = Connection(
            source_block_id="b1",
            source_port_id=b1.output_ports[0].id,
            target_block_id="b2",
            target_port_id=b2.input_ports[0].id,
            connection_id="c1",
        )
        wf.add_connection(conn)
        result = self.executor.topological_sort(wf)
        ids = [b.id for b in result]
        self.assertLess(ids.index("b1"), ids.index("b2"))

    def test_disconnected_blocks_all_returned(self):
        wf = Workflow(name="w")
        wf.add_block(_script("b1", "A", "def run(): return 1"))
        wf.add_block(_script("b2", "B", "def run(): return 2"))
        result = self.executor.topological_sort(wf)
        self.assertEqual(len(result), 2)

    def test_empty_workflow_returns_empty(self):
        wf = Workflow(name="w")
        result = self.executor.topological_sort(wf)
        self.assertEqual(result, [])

    def test_chain_of_three_blocks_ordered(self):
        wf = Workflow(name="w")
        b1 = _script("b1", "A", "def run(): return 1")
        b2 = _script("b2", "B", "def run(x): return x", "run")
        b3 = _script("b3", "C", "def run(x): return x", "run")
        wf.add_block(b1)
        wf.add_block(b2)
        wf.add_block(b3)
        wf.add_connection(Connection("b1", b1.output_ports[0].id, "b2", b2.input_ports[0].id, "c1"))
        wf.add_connection(Connection("b2", b2.output_ports[0].id, "b3", b3.input_ports[0].id, "c2"))
        result = self.executor.topological_sort(wf)
        ids = [b.id for b in result]
        self.assertLess(ids.index("b1"), ids.index("b2"))
        self.assertLess(ids.index("b2"), ids.index("b3"))


class TestExecute(unittest.TestCase):
    """Tests for WorkflowExecutor.execute."""

    def setUp(self):
        self.executor = WorkflowExecutor()

    def test_returns_context_dict(self):
        wf = Workflow(name="w")
        wf.add_block(_script("b1", "A", "def run(): return 42"))
        result = self.executor.execute_workflow(wf)
        self.assertIsInstance(result, dict)

    def test_single_block_result_stored_in_context(self):
        wf = Workflow(name="w")
        wf.add_block(_script("b1", "A", "def run(): return 42"))
        context = self.executor.execute_workflow(wf)
        self.assertEqual(context["b1"], 42)

    def test_downstream_block_receives_upstream_result(self):
        # b1 returns 10, b2 doubles its input — result should be 20.
        wf = Workflow(name="w")
        b1 = _script("b1", "Producer", "def run(): return 10")
        b2 = _script("b2", "Doubler", "def run(x): return x * 2", "run")
        wf.add_block(b1)
        wf.add_block(b2)
        wf.add_connection(Connection("b1", b1.output_ports[0].id, "b2", b2.input_ports[0].id, "c1"))
        context = self.executor.execute_workflow(wf)
        self.assertEqual(context["b1"], 10)
        self.assertEqual(context["b2"], 20)

    def test_all_block_results_in_context(self):
        wf = Workflow(name="w")
        wf.add_block(_script("b1", "A", "def run(): return 1"))
        wf.add_block(_script("b2", "B", "def run(): return 2"))
        context = self.executor.execute_workflow(wf)
        self.assertIn("b1", context)
        self.assertIn("b2", context)

    def test_raises_on_invalid_workflow(self):
        # A block with empty name fails validate().
        from core.domain.block import LLMBlock
        wf = Workflow(name="w")
        # LLMBlock with empty api_url and model_name is invalid.
        wf.add_block(LLMBlock(name="LLM", block_id="b1", config={
            "api_url": "", "model_name": "", "temperature": 0.7,
        }))
        with self.assertRaises(ValueError):
            self.executor.execute_workflow(wf)

    def test_empty_workflow_returns_empty_context(self):
        wf = Workflow(name="w")
        context = self.executor.execute_workflow(wf)
        self.assertEqual(context, {})


class TestPrepareInputs(unittest.TestCase):
    """Tests for WorkflowExecutor.prepare_inputs."""

    def setUp(self):
        self.executor = WorkflowExecutor()

    def test_populates_context_with_port_name(self):
        wf = Workflow(name="w")
        b1 = _script("b1", "Producer", "def run(): return 99")
        b2 = _script("b2", "Consumer", "def run(x): return x", "run")
        wf.add_block(b1)
        wf.add_block(b2)
        conn = Connection("b1", b1.output_ports[0].id, "b2", b2.input_ports[0].id, "c1")
        wf.add_connection(conn)
        self.executor._workflow = wf
        context = {"b1": 99}
        self.executor.prepare_inputs(b2, context)
        # The port name 'x' should now be accessible in context.
        self.assertEqual(context["x"], 99)

    def test_returns_inputs_dict(self):
        wf = Workflow(name="w")
        b1 = _script("b1", "Producer", "def run(): return 7")
        b2 = _script("b2", "Consumer", "def run(x): return x", "run")
        wf.add_block(b1)
        wf.add_block(b2)
        wf.add_connection(Connection("b1", b1.output_ports[0].id, "b2", b2.input_ports[0].id, "c1"))
        self.executor._workflow = wf
        inputs = self.executor.prepare_inputs(b2, {"b1": 7})
        self.assertEqual(inputs, {"x": 7})

    def test_no_connections_returns_empty(self):
        wf = Workflow(name="w")
        b1 = _script("b1", "Alone", "def run(): return 1")
        wf.add_block(b1)
        self.executor._workflow = wf
        inputs = self.executor.prepare_inputs(b1, {})
        self.assertEqual(inputs, {})


class TestExecuteBlock(unittest.TestCase):
    """Tests for WorkflowExecutor.execute_block."""

    def setUp(self):
        self.executor = WorkflowExecutor()

    def test_returns_block_result(self):
        wf = Workflow(name="w")
        b = _script("b1", "A", "def run(): return 55")
        wf.add_block(b)
        self.executor._workflow = wf
        result = self.executor.execute_block(b, {})
        self.assertEqual(result, 55)

    def test_uses_prepared_inputs(self):
        wf = Workflow(name="w")
        b1 = _script("b1", "A", "def run(): return 3")
        b2 = _script("b2", "B", "def run(x): return x * 10", "run")
        wf.add_block(b1)
        wf.add_block(b2)
        wf.add_connection(Connection("b1", b1.output_ports[0].id, "b2", b2.input_ports[0].id, "c1"))
        self.executor._workflow = wf
        result = self.executor.execute_block(b2, {"b1": 3})
        self.assertEqual(result, 30)


if __name__ == "__main__":
    unittest.main()
