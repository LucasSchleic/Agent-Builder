import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "agent_builder.settings")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-not-for-production")

try:
    import django
    django.setup()
    from django.test import RequestFactory
    from core.api import views
    DJANGO_AVAILABLE = True
except Exception:
    DJANGO_AVAILABLE = False

from core.domain.block import HTTPBlock, LLMBlock, PythonScriptBlock
from core.domain.connection import Connection
from core.domain.workflow import Workflow

skip_no_django = unittest.skipUnless(DJANGO_AVAILABLE, "Django not installed")


def _post(factory, url: str, payload: dict):
    """Helper: build a POST request with a JSON body."""
    return factory.post(url, data=json.dumps(payload).encode(), content_type="application/json")


# ---------------------------------------------------------------------------
# list_workflows
# ---------------------------------------------------------------------------

@skip_no_django
class TestListWorkflows(unittest.TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_returns_200(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(views, "WORKFLOWS_DIR", Path(tmpdir)):
                resp = views.list_workflows(self.factory.get("/api/workflows/"))
        self.assertEqual(resp.status_code, 200)

    def test_empty_directory_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(views, "WORKFLOWS_DIR", Path(tmpdir)):
                resp = views.list_workflows(self.factory.get("/api/workflows/"))
        self.assertEqual(json.loads(resp.content)["workflows"], [])

    def test_returns_json_filenames(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "wf1.json").write_text("{}")
            (tmp / "wf2.json").write_text("{}")
            with patch.object(views, "WORKFLOWS_DIR", tmp):
                resp = views.list_workflows(self.factory.get("/api/workflows/"))
        names = json.loads(resp.content)["workflows"]
        self.assertIn("wf1.json", names)
        self.assertIn("wf2.json", names)

    def test_excludes_non_json_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "notes.txt").write_text("hello")
            (tmp / "wf.json").write_text("{}")
            with patch.object(views, "WORKFLOWS_DIR", tmp):
                resp = views.list_workflows(self.factory.get("/api/workflows/"))
        names = json.loads(resp.content)["workflows"]
        self.assertNotIn("notes.txt", names)


# ---------------------------------------------------------------------------
# new_workflow
# ---------------------------------------------------------------------------

@skip_no_django
class TestNewWorkflow(unittest.TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_returns_workflow_with_given_name(self):
        resp = views.new_workflow(_post(self.factory, "/api/workflow/new/", {"name": "my_wf"}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content)["workflow"]["name"], "my_wf")

    def test_defaults_name_to_new_workflow(self):
        resp = views.new_workflow(_post(self.factory, "/api/workflow/new/", {}))
        self.assertEqual(json.loads(resp.content)["workflow"]["name"], "new_workflow")

    def test_workflow_starts_empty(self):
        resp = views.new_workflow(_post(self.factory, "/api/workflow/new/", {"name": "t"}))
        data = json.loads(resp.content)["workflow"]
        self.assertEqual(data["blocks"], [])
        self.assertEqual(data["connections"], [])

    def test_response_contains_id(self):
        resp = views.new_workflow(_post(self.factory, "/api/workflow/new/", {"name": "t"}))
        self.assertIn("id", json.loads(resp.content)["workflow"])


# ---------------------------------------------------------------------------
# load_workflow
# ---------------------------------------------------------------------------

@skip_no_django
class TestLoadWorkflow(unittest.TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_returns_404_for_unknown_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(views, "WORKFLOWS_DIR", Path(tmpdir)):
                resp = views.load_workflow(self.factory.get("/"), name="ghost.json")
        self.assertEqual(resp.status_code, 404)

    def test_loads_saved_workflow(self):
        wf = Workflow(name="saved_wf")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "saved_wf.json").write_text(json.dumps(wf.to_dict()))
            with patch.object(views, "WORKFLOWS_DIR", tmp):
                resp = views.load_workflow(self.factory.get("/"), name="saved_wf.json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content)["workflow"]["name"], "saved_wf")

    def test_restores_workflow_id(self):
        wf = Workflow(name="wf", workflow_id="fixed-id")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "wf.json").write_text(json.dumps(wf.to_dict()))
            with patch.object(views, "WORKFLOWS_DIR", tmp):
                resp = views.load_workflow(self.factory.get("/"), name="wf.json")
        self.assertEqual(json.loads(resp.content)["workflow"]["id"], "fixed-id")


# ---------------------------------------------------------------------------
# save_workflow
# ---------------------------------------------------------------------------

@skip_no_django
class TestSaveWorkflow(unittest.TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_returns_status_ok(self):
        wf = Workflow(name="to_save")
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(views, "WORKFLOWS_DIR", Path(tmpdir)):
                resp = views.save_workflow(_post(self.factory, "/api/workflow/save/", {"workflow": wf.to_dict()}))
        self.assertEqual(json.loads(resp.content)["status"], "ok")

    def test_creates_json_file_on_disk(self):
        wf = Workflow(name="to_save")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            with patch.object(views, "WORKFLOWS_DIR", tmp):
                views.save_workflow(_post(self.factory, "/api/workflow/save/", {"workflow": wf.to_dict()}))
            self.assertTrue((tmp / "to_save.json").exists())

    def test_response_contains_path(self):
        wf = Workflow(name="to_save")
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(views, "WORKFLOWS_DIR", Path(tmpdir)):
                resp = views.save_workflow(_post(self.factory, "/api/workflow/save/", {"workflow": wf.to_dict()}))
        self.assertIn("path", json.loads(resp.content))


# ---------------------------------------------------------------------------
# add_block
# ---------------------------------------------------------------------------

@skip_no_django
class TestAddBlock(unittest.TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.wf = Workflow(name="test")

    def _req(self, block_type):
        return _post(self.factory, "/api/workflow/block/add/", {
            "workflow": self.wf.to_dict(),
            "block_type": block_type,
        })

    def test_adds_llm_block(self):
        resp = views.add_block(self._req("LLMBlock"))
        data = json.loads(resp.content)["workflow"]
        self.assertEqual(len(data["blocks"]), 1)
        self.assertEqual(data["blocks"][0]["type"], "LLMBlock")

    def test_adds_agent_block(self):
        resp = views.add_block(self._req("AgentBlock"))
        self.assertEqual(json.loads(resp.content)["workflow"]["blocks"][0]["type"], "AgentBlock")

    def test_adds_http_block(self):
        resp = views.add_block(self._req("HTTPBlock"))
        self.assertEqual(json.loads(resp.content)["workflow"]["blocks"][0]["type"], "HTTPBlock")

    def test_adds_python_script_block(self):
        resp = views.add_block(self._req("PythonScriptBlock"))
        self.assertEqual(json.loads(resp.content)["workflow"]["blocks"][0]["type"], "PythonScriptBlock")

    def test_unknown_block_type_returns_400(self):
        resp = views.add_block(self._req("UnknownBlock"))
        self.assertEqual(resp.status_code, 400)

    def test_missing_block_type_returns_400(self):
        req = _post(self.factory, "/api/workflow/block/add/", {"workflow": self.wf.to_dict()})
        resp = views.add_block(req)
        self.assertEqual(resp.status_code, 400)

    def test_returns_200_on_success(self):
        resp = views.add_block(self._req("LLMBlock"))
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# remove_block
# ---------------------------------------------------------------------------

@skip_no_django
class TestRemoveBlock(unittest.TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.wf = Workflow(name="test")
        self.block = LLMBlock(name="LLM")
        self.wf.add_block(self.block)

    def test_removes_block(self):
        req = _post(self.factory, "/api/workflow/block/remove/", {
            "workflow": self.wf.to_dict(),
            "block_id": self.block.id,
        })
        resp = views.remove_block(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content)["workflow"]["blocks"], [])

    def test_unknown_block_id_returns_404(self):
        req = _post(self.factory, "/api/workflow/block/remove/", {
            "workflow": self.wf.to_dict(),
            "block_id": "non-existent",
        })
        self.assertEqual(views.remove_block(req).status_code, 404)

    def test_also_removes_connections(self):
        http = HTTPBlock(name="HTTP")
        self.wf.add_block(http)
        conn = Connection(
            source_block_id=self.block.id,
            source_port_id=self.block.output_ports[0].id,
            target_block_id=http.id,
            target_port_id=http.input_ports[0].id,
        )
        self.wf.add_connection(conn)
        req = _post(self.factory, "/api/workflow/block/remove/", {
            "workflow": self.wf.to_dict(),
            "block_id": self.block.id,
        })
        data = json.loads(views.remove_block(req).content)["workflow"]
        self.assertEqual(data["connections"], [])


# ---------------------------------------------------------------------------
# update_block
# ---------------------------------------------------------------------------

@skip_no_django
class TestUpdateBlock(unittest.TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.wf = Workflow(name="test")
        self.block = LLMBlock(name="LLM")
        self.wf.add_block(self.block)

    def test_updates_config_field(self):
        req = _post(self.factory, "/api/workflow/block/update/", {
            "workflow": self.wf.to_dict(),
            "block_id": self.block.id,
            "config": {"model_name": "gpt-4o"},
        })
        resp = views.update_block(req)
        self.assertEqual(resp.status_code, 200)
        updated = next(b for b in json.loads(resp.content)["workflow"]["blocks"] if b["id"] == self.block.id)
        self.assertEqual(updated["config"]["model_name"], "gpt-4o")

    def test_unknown_block_returns_404(self):
        req = _post(self.factory, "/api/workflow/block/update/", {
            "workflow": self.wf.to_dict(),
            "block_id": "ghost",
            "config": {},
        })
        self.assertEqual(views.update_block(req).status_code, 404)

    def test_python_script_reruns_parse_signature_on_code_change(self):
        wf = Workflow(name="test")
        block = PythonScriptBlock(name="S", config={
            "script_code": "def run(x): return x",
            "function_name": "run",
        })
        wf.add_block(block)
        req = _post(self.factory, "/api/workflow/block/update/", {
            "workflow": wf.to_dict(),
            "block_id": block.id,
            "config": {"script_code": "def run(x, y): return x + y", "function_name": "run"},
        })
        resp = views.update_block(req)
        updated = next(b for b in json.loads(resp.content)["workflow"]["blocks"] if b["id"] == block.id)
        input_names = [p["name"] for p in updated["input_ports"]]
        self.assertIn("x", input_names)
        self.assertIn("y", input_names)


# ---------------------------------------------------------------------------
# add_connection
# ---------------------------------------------------------------------------

@skip_no_django
class TestAddConnection(unittest.TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.wf = Workflow(name="test")
        self.llm = LLMBlock(name="LLM")
        self.http = HTTPBlock(name="HTTP")
        self.wf.add_block(self.llm)
        self.wf.add_block(self.http)

    def test_adds_connection(self):
        req = _post(self.factory, "/api/workflow/connection/add/", {
            "workflow": self.wf.to_dict(),
            "source_block_id": self.llm.id,
            "source_port_id": self.llm.output_ports[0].id,
            "target_block_id": self.http.id,
            "target_port_id": self.http.input_ports[0].id,
        })
        resp = views.add_connection(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(json.loads(resp.content)["workflow"]["connections"]), 1)

    def test_missing_source_block_returns_400(self):
        req = _post(self.factory, "/api/workflow/connection/add/", {
            "workflow": self.wf.to_dict(),
            "source_block_id": "ghost",
            "source_port_id": "p1",
            "target_block_id": self.http.id,
            "target_port_id": "p2",
        })
        self.assertEqual(views.add_connection(req).status_code, 400)

    def test_missing_target_block_returns_400(self):
        req = _post(self.factory, "/api/workflow/connection/add/", {
            "workflow": self.wf.to_dict(),
            "source_block_id": self.llm.id,
            "source_port_id": self.llm.output_ports[0].id,
            "target_block_id": "ghost",
            "target_port_id": "p2",
        })
        self.assertEqual(views.add_connection(req).status_code, 400)


# ---------------------------------------------------------------------------
# remove_connection
# ---------------------------------------------------------------------------

@skip_no_django
class TestRemoveConnection(unittest.TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.wf = Workflow(name="test")
        llm = LLMBlock(name="LLM")
        http = HTTPBlock(name="HTTP")
        self.wf.add_block(llm)
        self.wf.add_block(http)
        conn = Connection(
            source_block_id=llm.id,
            source_port_id=llm.output_ports[0].id,
            target_block_id=http.id,
            target_port_id=http.input_ports[0].id,
        )
        self.wf.add_connection(conn)
        self.conn_id = conn.id

    def test_removes_connection(self):
        req = _post(self.factory, "/api/workflow/connection/remove/", {
            "workflow": self.wf.to_dict(),
            "connection_id": self.conn_id,
        })
        resp = views.remove_connection(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content)["workflow"]["connections"], [])

    def test_unknown_connection_returns_404(self):
        req = _post(self.factory, "/api/workflow/connection/remove/", {
            "workflow": self.wf.to_dict(),
            "connection_id": "ghost",
        })
        self.assertEqual(views.remove_connection(req).status_code, 404)


# ---------------------------------------------------------------------------
# export_workflow
# ---------------------------------------------------------------------------

@skip_no_django
class TestExportWorkflow(unittest.TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def _make_valid_wf(self):
        wf = Workflow(name="export_test")
        wf.add_block(LLMBlock(name="LLM", config={
            "api_url": "http://x", "model_name": "gpt-4o", "api_key_env_var": "K"
        }))
        return wf

    def test_returns_script_and_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(views, "WORKFLOWS_DIR", Path(tmpdir)):
                req = _post(self.factory, "/api/workflow/export/", {"workflow": self._make_valid_wf().to_dict()})
                resp = views.export_workflow(req)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertIn("script", data)
        self.assertIn("path", data)

    def test_script_contains_workflow_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(views, "WORKFLOWS_DIR", Path(tmpdir)):
                req = _post(self.factory, "/api/workflow/export/", {"workflow": self._make_valid_wf().to_dict()})
                resp = views.export_workflow(req)
        self.assertIn("export_test", json.loads(resp.content)["script"])

    def test_creates_py_file_on_disk(self):
        wf = self._make_valid_wf()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            with patch.object(views, "WORKFLOWS_DIR", tmp):
                req = _post(self.factory, "/api/workflow/export/", {"workflow": wf.to_dict()})
                views.export_workflow(req)
            self.assertTrue((tmp / f"{wf.name}_export.py").exists())


# ---------------------------------------------------------------------------
# run_workflow
# ---------------------------------------------------------------------------

@skip_no_django
class TestRunWorkflow(unittest.TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_invalid_workflow_returns_400(self):
        wf = Workflow(name="test")
        bad = LLMBlock(name="LLM", config={"api_url": "", "model_name": ""})
        wf.blocks.append(bad)
        req = _post(self.factory, "/api/workflow/run/", {"workflow": wf.to_dict()})
        self.assertEqual(views.run_workflow(req).status_code, 400)

    def test_returns_context_on_success(self):
        wf = Workflow(name="test")
        with patch.object(views._executor, "execute_workflow", return_value={"b1": "result"}):
            req = _post(self.factory, "/api/workflow/run/", {"workflow": wf.to_dict()})
            resp = views.run_workflow(req)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertIn("context", data)
        self.assertEqual(data["context"]["b1"], "result")

    def test_non_serializable_result_becomes_string(self):
        wf = Workflow(name="test")
        with patch.object(views._executor, "execute_workflow", return_value={"b": object()}):
            req = _post(self.factory, "/api/workflow/run/", {"workflow": wf.to_dict()})
            resp = views.run_workflow(req)
        self.assertIsInstance(json.loads(resp.content)["context"]["b"], str)

    def test_returns_empty_context_for_empty_workflow(self):
        wf = Workflow(name="test")
        with patch.object(views._executor, "execute_workflow", return_value={}):
            req = _post(self.factory, "/api/workflow/run/", {"workflow": wf.to_dict()})
            resp = views.run_workflow(req)
        self.assertEqual(json.loads(resp.content)["context"], {})


if __name__ == "__main__":
    unittest.main()
