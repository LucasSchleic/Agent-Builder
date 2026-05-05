import json
import os
import tempfile
import unittest

from core.domain.block import LLMBlock, HTTPBlock
from core.domain.connection import Connection
from core.domain.workflow import Workflow
from core.services.workflow_service import WorkflowService


def _make_workflow() -> Workflow:
    """Build a minimal workflow with one block for reuse across tests."""
    wf = Workflow(name="test_wf", workflow_id="wf-001")
    block = LLMBlock(
        name="My LLM",
        block_id="b-001",
        config={"api_url": "http://example.com", "model_name": "gpt-4o", "temperature": 0.7},
    )
    wf.add_block(block)
    return wf


class TestWorkflowServiceCreate(unittest.TestCase):
    """Tests for WorkflowService.create_workflow."""

    def setUp(self):
        self.service = WorkflowService()

    def test_returns_workflow_instance(self):
        wf = self.service.create_workflow("my_wf")
        self.assertIsInstance(wf, Workflow)

    def test_sets_name(self):
        wf = self.service.create_workflow("my_wf")
        self.assertEqual(wf.name, "my_wf")

    def test_starts_empty(self):
        wf = self.service.create_workflow("my_wf")
        self.assertEqual(wf.blocks, [])
        self.assertEqual(wf.connections, [])

    def test_generates_unique_ids(self):
        wf1 = self.service.create_workflow("a")
        wf2 = self.service.create_workflow("b")
        self.assertNotEqual(wf1.id, wf2.id)


class TestWorkflowServiceSaveAs(unittest.TestCase):
    """Tests for WorkflowService.save_as_workflow."""

    def setUp(self):
        self.service = WorkflowService()
        self.tmp_dir = tempfile.mkdtemp()

    def test_creates_file_at_new_path(self):
        wf = _make_workflow()
        path = os.path.join(self.tmp_dir, "copy.json")
        self.service.save_as_workflow(wf, path)
        self.assertTrue(os.path.isfile(path))

    def test_saved_content_matches_original(self):
        wf = _make_workflow()
        path = os.path.join(self.tmp_dir, "copy.json")
        self.service.save_as_workflow(wf, path)
        loaded = self.service.load_workflow(path)
        self.assertEqual(loaded.id, wf.id)
        self.assertEqual(loaded.name, wf.name)


class TestWorkflowServiceSave(unittest.TestCase):
    """Tests for WorkflowService.save_workflow."""

    def setUp(self):
        self.service = WorkflowService()
        self.tmp_dir = tempfile.mkdtemp()

    def _path(self, filename: str) -> str:
        return os.path.join(self.tmp_dir, filename)

    def test_creates_json_file(self):
        wf = _make_workflow()
        path = self._path("wf.json")
        self.service.save_workflow(wf, path)
        self.assertTrue(os.path.isfile(path))

    def test_file_is_valid_json(self):
        wf = _make_workflow()
        path = self._path("wf.json")
        self.service.save_workflow(wf, path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("id", data)
        self.assertIn("name", data)
        self.assertIn("blocks", data)
        self.assertIn("connections", data)

    def test_saves_correct_name(self):
        wf = _make_workflow()
        path = self._path("wf.json")
        self.service.save_workflow(wf, path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["name"], "test_wf")

    def test_overwrites_existing_file(self):
        wf = _make_workflow()
        path = self._path("wf.json")
        self.service.save_workflow(wf, path)
        wf.name = "updated_name"
        self.service.save_workflow(wf, path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["name"], "updated_name")


class TestWorkflowServiceLoad(unittest.TestCase):
    """Tests for WorkflowService.load_workflow."""

    def setUp(self):
        self.service = WorkflowService()
        self.tmp_dir = tempfile.mkdtemp()

    def _save(self, wf: Workflow, filename: str = "wf.json") -> str:
        path = os.path.join(self.tmp_dir, filename)
        self.service.save_workflow(wf, path)
        return path

    def test_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            self.service.load_workflow("/nonexistent/path/wf.json")

    def test_returns_workflow_instance(self):
        path = self._save(_make_workflow())
        result = self.service.load_workflow(path)
        self.assertIsInstance(result, Workflow)

    def test_roundtrip_id_and_name(self):
        wf = _make_workflow()
        path = self._save(wf)
        loaded = self.service.load_workflow(path)
        self.assertEqual(loaded.id, wf.id)
        self.assertEqual(loaded.name, wf.name)

    def test_roundtrip_blocks(self):
        wf = _make_workflow()
        path = self._save(wf)
        loaded = self.service.load_workflow(path)
        self.assertEqual(len(loaded.blocks), 1)
        self.assertEqual(loaded.blocks[0].id, "b-001")
        self.assertEqual(loaded.blocks[0].name, "My LLM")

    def test_roundtrip_connections(self):
        wf = Workflow(name="conn_wf", workflow_id="wf-002")
        b1 = LLMBlock(name="LLM", block_id="b1", config={})
        b2 = HTTPBlock(name="HTTP", block_id="b2", config={})
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
        path = self._save(wf, "conn_wf.json")
        loaded = self.service.load_workflow(path)
        self.assertEqual(len(loaded.connections), 1)
        self.assertEqual(loaded.connections[0].id, "c1")

    def test_subscribers_not_restored(self):
        """Subscribers are runtime-only and must not appear after load."""
        path = self._save(_make_workflow())
        loaded = self.service.load_workflow(path)
        self.assertEqual(loaded._subscribers, [])


class TestWorkflowServiceList(unittest.TestCase):
    """Tests for WorkflowService.list_workflows."""

    def setUp(self):
        self.service = WorkflowService()
        self.tmp_dir = tempfile.mkdtemp()

    def _touch(self, filename: str) -> None:
        open(os.path.join(self.tmp_dir, filename), "w").close()

    def test_returns_empty_list_when_no_json(self):
        result = self.service.list_workflows(self.tmp_dir)
        self.assertEqual(result, [])

    def test_returns_json_files(self):
        self._touch("wf1.json")
        self._touch("wf2.json")
        result = self.service.list_workflows(self.tmp_dir)
        self.assertIn("wf1.json", result)
        self.assertIn("wf2.json", result)
        self.assertEqual(len(result), 2)

    def test_excludes_non_json_files(self):
        self._touch("wf.json")
        self._touch("wf.py")
        self._touch("notes.txt")
        result = self.service.list_workflows(self.tmp_dir)
        self.assertEqual(result, ["wf.json"])


if __name__ == "__main__":
    unittest.main()
