import unittest

from core.domain.block import LLMBlock, HTTPBlock
from core.domain.connection import Connection
from core.domain.workflow import Workflow, Subscriber


class MockSubscriber(Subscriber):
    """Test double that records how many times it was notified."""

    def __init__(self):
        self.update_count = 0
        self.last_workflow = None

    def update(self, workflow: Workflow) -> None:
        self.update_count += 1
        self.last_workflow = workflow


class TestWorkflowInit(unittest.TestCase):
    """Tests for Workflow instantiation."""

    def test_auto_generates_uuid(self):
        wf = Workflow(name="test")
        self.assertEqual(len(wf.id), 36)

    def test_uses_provided_id(self):
        wf = Workflow(name="test", workflow_id="my-id")
        self.assertEqual(wf.id, "my-id")

    def test_starts_empty(self):
        wf = Workflow(name="test")
        self.assertEqual(wf.blocks, [])
        self.assertEqual(wf.connections, [])


class TestWorkflowBlocks(unittest.TestCase):
    """Tests for add_block, remove_block, get_block."""

    def setUp(self):
        self.wf = Workflow(name="test")
        self.block = LLMBlock(name="LLM")

    def test_add_block(self):
        self.wf.add_block(self.block)
        self.assertIn(self.block, self.wf.blocks)

    def test_get_block_returns_correct_block(self):
        self.wf.add_block(self.block)
        found = self.wf.get_block(self.block.id)
        self.assertIs(found, self.block)

    def test_get_block_raises_for_unknown_id(self):
        with self.assertRaises(ValueError):
            self.wf.get_block("non-existent-id")

    def test_remove_block(self):
        self.wf.add_block(self.block)
        self.wf.remove_block(self.block.id)
        self.assertNotIn(self.block, self.wf.blocks)

    def test_remove_block_raises_for_unknown_id(self):
        with self.assertRaises(ValueError):
            self.wf.remove_block("non-existent-id")

    def test_remove_block_also_removes_its_connections(self):
        block_b = HTTPBlock(name="HTTP")
        self.wf.add_block(self.block)
        self.wf.add_block(block_b)
        conn = Connection(
            source_block_id=self.block.id,
            source_port_id=self.block.output_ports[0].id,
            target_block_id=block_b.id,
            target_port_id=block_b.input_ports[0].id,
        )
        self.wf.add_connection(conn)
        self.wf.remove_block(self.block.id)
        self.assertEqual(self.wf.connections, [])


class TestWorkflowConnections(unittest.TestCase):
    """Tests for add_connection and remove_connection."""

    def setUp(self):
        self.wf = Workflow(name="test")
        self.llm = LLMBlock(name="LLM")
        self.http = HTTPBlock(name="HTTP")
        self.wf.add_block(self.llm)
        self.wf.add_block(self.http)

    def _make_connection(self):
        return Connection(
            source_block_id=self.llm.id,
            source_port_id=self.llm.output_ports[0].id,
            target_block_id=self.http.id,
            target_port_id=self.http.input_ports[0].id,
        )

    def test_add_connection(self):
        conn = self._make_connection()
        self.wf.add_connection(conn)
        self.assertIn(conn, self.wf.connections)

    def test_add_connection_raises_if_source_block_missing(self):
        conn = Connection(
            source_block_id="ghost-id",
            source_port_id="p1",
            target_block_id=self.http.id,
            target_port_id="p2",
        )
        with self.assertRaises(ValueError):
            self.wf.add_connection(conn)

    def test_add_connection_raises_if_target_block_missing(self):
        conn = Connection(
            source_block_id=self.llm.id,
            source_port_id="p1",
            target_block_id="ghost-id",
            target_port_id="p2",
        )
        with self.assertRaises(ValueError):
            self.wf.add_connection(conn)

    def test_remove_connection(self):
        conn = self._make_connection()
        self.wf.add_connection(conn)
        self.wf.remove_connection(conn.id)
        self.assertNotIn(conn, self.wf.connections)

    def test_remove_connection_raises_for_unknown_id(self):
        with self.assertRaises(ValueError):
            self.wf.remove_connection("non-existent-id")


class TestWorkflowObserver(unittest.TestCase):
    """Tests for the Observer pattern (subscribe, unsubscribe, notify)."""

    def setUp(self):
        self.wf = Workflow(name="test")
        self.sub = MockSubscriber()

    def test_subscriber_notified_on_add_block(self):
        self.wf.subscribe(self.sub)
        self.wf.add_block(LLMBlock())
        self.assertEqual(self.sub.update_count, 1)

    def test_subscriber_notified_on_remove_block(self):
        block = LLMBlock()
        self.wf.add_block(block)
        self.wf.subscribe(self.sub)
        self.wf.remove_block(block.id)
        self.assertEqual(self.sub.update_count, 1)

    def test_subscriber_receives_workflow_reference(self):
        self.wf.subscribe(self.sub)
        self.wf.add_block(LLMBlock())
        self.assertIs(self.sub.last_workflow, self.wf)

    def test_no_duplicate_notifications_on_double_subscribe(self):
        self.wf.subscribe(self.sub)
        self.wf.subscribe(self.sub)  # subscribe twice
        self.wf.add_block(LLMBlock())
        self.assertEqual(self.sub.update_count, 1)  # notified only once

    def test_unsubscribe_stops_notifications(self):
        self.wf.subscribe(self.sub)
        self.wf.unsubscribe(self.sub)
        self.wf.add_block(LLMBlock())
        self.assertEqual(self.sub.update_count, 0)

    def test_unsubscribe_unknown_subscriber_does_not_crash(self):
        other = MockSubscriber()
        self.wf.unsubscribe(other)  # should not raise


class TestWorkflowValidate(unittest.TestCase):
    """Tests for Workflow.validate()."""

    def test_empty_workflow_is_valid(self):
        wf = Workflow(name="empty")
        self.assertTrue(wf.validate())

    def test_valid_workflow_with_blocks(self):
        wf = Workflow(name="test")
        wf.blocks.append(LLMBlock(name="LLM", config={
            "api_url": "http://x", "model_name": "gpt", "api_key_env_var": "K"
        }))
        self.assertTrue(wf.validate())

    def test_invalid_block_makes_workflow_invalid(self):
        wf = Workflow(name="test")
        bad_block = LLMBlock(name="LLM", config={"api_url": "", "model_name": ""})
        wf.blocks.append(bad_block)
        self.assertFalse(wf.validate())


class TestWorkflowSerialization(unittest.TestCase):
    """Tests for Workflow.to_dict() and Workflow.from_dict()."""

    def _make_workflow(self):
        wf = Workflow(name="my_workflow")
        wf.add_block(LLMBlock(name="LLM"))
        wf.add_block(HTTPBlock(name="HTTP"))
        return wf

    def test_to_dict_structure(self):
        d = self._make_workflow().to_dict()
        self.assertIn("id", d)
        self.assertIn("name", d)
        self.assertIn("blocks", d)
        self.assertIn("connections", d)

    def test_to_dict_excludes_subscribers(self):
        wf = self._make_workflow()
        wf.subscribe(MockSubscriber())
        d = wf.to_dict()
        self.assertNotIn("subscribers", d)
        self.assertNotIn("_subscribers", d)

    def test_from_dict_roundtrip(self):
        wf = self._make_workflow()
        restored = Workflow.from_dict(wf.to_dict())
        self.assertEqual(restored.id, wf.id)
        self.assertEqual(restored.name, wf.name)
        self.assertEqual(len(restored.blocks), 2)
        self.assertEqual(len(restored.connections), 0)

    def test_from_dict_restores_block_types(self):
        wf = self._make_workflow()
        restored = Workflow.from_dict(wf.to_dict())
        types = {type(b).__name__ for b in restored.blocks}
        self.assertIn("LLMBlock", types)
        self.assertIn("HTTPBlock", types)


if __name__ == "__main__":
    unittest.main()
