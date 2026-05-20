"""Integration tests: workflow execution (in-app) and export (generated Python script).

Tests are grouped by workflow:
  - TestWorkflowLoading   : all JSONs in workflows/ load and parse without error
  - TestPurePythonChain   : calcul_chaine — deterministic, no external deps
  - TestHTTPWorkflow      : http_test — requests.request mocked, no network needed
"""
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.domain.workflow import Workflow
from core.services.export_service import ExportService
from core.services.workflow_executor import WorkflowExecutor
from core.services.workflow_service import WorkflowService

WORKFLOWS_DIR = Path(__file__).parents[3] / "workflows"


def _load(name: str) -> Workflow:
    """Load a workflow JSON by filename (without extension)."""
    return WorkflowService().load_workflow(str(WORKFLOWS_DIR / f"{name}.json"))


# ---------------------------------------------------------------------------
# Structural: every JSON must load correctly
# ---------------------------------------------------------------------------

class TestWorkflowLoading(unittest.TestCase):
    """Every .json file in workflows/ must deserialize without error."""

    def test_all_workflows_load(self):
        json_files = list(WORKFLOWS_DIR.glob("*.json"))
        self.assertGreater(len(json_files), 0, "No workflow JSON files found.")
        service = WorkflowService()
        for path in json_files:
            with self.subTest(workflow=path.name):
                wf = service.load_workflow(str(path))
                self.assertIsInstance(wf, Workflow)
                self.assertTrue(wf.name, f"{path.name} has no name.")
                self.assertGreater(len(wf.blocks), 0, f"{path.name} has no blocks.")

    def test_calcul_chaine_structure(self):
        wf = _load("calcul_chaine")
        self.assertEqual(len(wf.blocks), 3)
        self.assertEqual(len(wf.connections), 2)
        block_names = [b.name for b in wf.blocks]
        self.assertIn("Generer Donnees", block_names)
        self.assertIn("Doubler Valeurs", block_names)
        self.assertIn("Rapport", block_names)


# ---------------------------------------------------------------------------
# calcul_chaine — pure PythonScriptBlock chain, fully deterministic
# ---------------------------------------------------------------------------

class TestPurePythonChain(unittest.TestCase):
    """In-app execution and export of calcul_chaine (no external dependencies)."""

    def setUp(self):
        self.wf = _load("calcul_chaine")
        self.executor = WorkflowExecutor()
        self.export = ExportService()

    def _sorted_blocks(self):
        return self.executor.topological_sort(self.wf)

    # --- In-app execution ---

    def test_executor_returns_context_for_all_blocks(self):
        context = self.executor.execute_workflow(self.wf)
        # context also holds port-name entries added by prepare_inputs, so
        # we only assert that every block ID is present, not check the total count.
        for block in self.wf.blocks:
            self.assertIn(block.id, context)

    def test_first_block_generates_initial_list(self):
        context = self.executor.execute_workflow(self.wf)
        first_id = self._sorted_blocks()[0].id
        self.assertEqual(context[first_id], [1, 2, 3, 4, 5])

    def test_second_block_doubles_values(self):
        context = self.executor.execute_workflow(self.wf)
        second_id = self._sorted_blocks()[1].id
        self.assertEqual(context[second_id], [2, 4, 6, 8, 10])

    def test_final_block_produces_correct_summary(self):
        context = self.executor.execute_workflow(self.wf)
        last_id = self._sorted_blocks()[-1].id
        self.assertEqual(context[last_id], "Somme: 30 | Max: 10")

    def test_execution_order_follows_connections(self):
        """Blocks must execute in dependency order: Generer → Doubler → Rapport."""
        blocks = self._sorted_blocks()
        names = [b.name for b in blocks]
        self.assertLess(names.index("Generer Donnees"), names.index("Doubler Valeurs"))
        self.assertLess(names.index("Doubler Valeurs"), names.index("Rapport"))

    # --- Export ---

    def test_exported_script_contains_block_comments(self):
        script = self.export.generate_python(self.wf)
        for block in self.wf.blocks:
            self.assertIn(f"# --- Bloc : {block.name}", script)

    def test_exported_script_defines_all_functions(self):
        script = self.export.generate_python(self.wf)
        self.assertIn("def run_generer_donnees(", script)
        self.assertIn("def run_doubler_valeurs(", script)
        self.assertIn("def run_rapport(", script)

    def test_exported_script_calls_in_dependency_order(self):
        script = self.export.generate_python(self.wf)
        pos = {name: script.index(name) for name in
               ("run_generer_donnees", "run_doubler_valeurs", "run_rapport")}
        self.assertLess(pos["run_generer_donnees"], pos["run_doubler_valeurs"])
        self.assertLess(pos["run_doubler_valeurs"], pos["run_rapport"])

    def test_exported_script_produces_correct_result_when_executed(self):
        """exec() the generated script and verify the final variable value."""
        script = self.export.generate_python(self.wf)
        ns: dict = {}
        exec(script, ns)  # noqa: S102
        self.assertEqual(ns["result_rapport"], "Somme: 30 | Max: 10")

    def test_exported_script_passes_intermediate_values(self):
        """Intermediate results must be threaded correctly between renamed functions."""
        script = self.export.generate_python(self.wf)
        ns: dict = {}
        exec(script, ns)  # noqa: S102
        self.assertEqual(ns["result_generer_donnees"], [1, 2, 3, 4, 5])
        self.assertEqual(ns["result_doubler_valeurs"], [2, 4, 6, 8, 10])


# ---------------------------------------------------------------------------
# http_test — HTTPBlock + PythonScriptBlock, requests mocked
# ---------------------------------------------------------------------------

class TestHTTPWorkflow(unittest.TestCase):
    """In-app execution and export of http_test, with requests.request mocked."""

    MOCK_JOKE = {
        "id": 1,
        "type": "general",
        "setup": "Why did the chicken cross the road?",
        "punchline": "To get to the other side!",
    }

    def setUp(self):
        self.wf = _load("http_test")
        self.executor = WorkflowExecutor()
        self.export = ExportService()

    def _mock_response(self) -> MagicMock:
        resp = MagicMock()
        resp.json.return_value = self.MOCK_JOKE
        resp.status_code = 200
        return resp

    # --- In-app execution ---

    def test_executor_calls_http_and_formats_output(self):
        with patch("requests.request", return_value=self._mock_response()):
            context = self.executor.execute_workflow(self.wf)

        last_id = self.executor.topological_sort(self.wf)[-1].id
        result = context[last_id]
        self.assertIn("Why did the chicken cross the road?", result)
        self.assertIn("To get to the other side!", result)

    def test_executor_output_starts_with_q_and_a(self):
        with patch("requests.request", return_value=self._mock_response()):
            context = self.executor.execute_workflow(self.wf)
        last_id = self.executor.topological_sort(self.wf)[-1].id
        result = context[last_id]
        self.assertTrue(result.startswith("Q:"), f"Expected 'Q:' prefix, got: {result!r}")
        self.assertIn("\nA:", result)

    def test_http_block_receives_get_request(self):
        with patch("requests.request", return_value=self._mock_response()) as mock_req:
            self.executor.execute_workflow(self.wf)
        mock_req.assert_called_once()
        # execute() uses keyword arguments: method=, url=, headers=, json=
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs["method"].upper(), "GET")

    # --- Export ---

    def test_exported_script_contains_requests_import(self):
        script = self.export.generate_python(self.wf)
        self.assertIn("import requests", script)

    def test_exported_script_produces_correct_output_when_executed(self):
        script = self.export.generate_python(self.wf)
        ns: dict = {}
        with patch("requests.request", return_value=self._mock_response()):
            exec(script, ns)  # noqa: S102
        self.assertIn("Why did the chicken cross the road?", ns["result_formateur"])
        self.assertIn("To get to the other side!", ns["result_formateur"])

    def test_exported_script_url_matches_workflow_config(self):
        script = self.export.generate_python(self.wf)
        http_block = next(b for b in self.wf.blocks if b.__class__.__name__ == "HTTPBlock")
        self.assertIn(http_block.config["url"], script)


if __name__ == "__main__":
    unittest.main()
