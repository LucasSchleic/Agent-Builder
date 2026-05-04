import unittest

from core.domain.block import AgentBlock, HTTPBlock, LLMBlock, PythonScriptBlock
from core.domain.workflow import Workflow
from core.factory.block_creators import (
    AgentBlockCreator,
    BlockCreator,
    HTTPBlockCreator,
    LLMBlockCreator,
    PythonScriptBlockCreator,
)


class TestBlockCreatorIsAbstract(unittest.TestCase):
    """BlockCreator cannot be instantiated directly."""

    def test_cannot_instantiate_abstract_creator(self):
        with self.assertRaises(TypeError):
            BlockCreator()


class TestLLMBlockCreator(unittest.TestCase):

    def setUp(self):
        self.workflow = Workflow(name="test")
        self.creator = LLMBlockCreator()

    def test_creates_llm_block(self):
        block = self.creator.add_block_to(self.workflow)
        self.assertIsInstance(block, LLMBlock)

    def test_block_is_added_to_workflow(self):
        block = self.creator.add_block_to(self.workflow)
        self.assertIn(block, self.workflow.blocks)

    def test_returns_same_block_that_was_added(self):
        block = self.creator.add_block_to(self.workflow)
        self.assertIs(self.workflow.blocks[0], block)

    def test_each_call_creates_a_distinct_block(self):
        block_a = self.creator.add_block_to(self.workflow)
        block_b = self.creator.add_block_to(self.workflow)
        self.assertNotEqual(block_a.id, block_b.id)


class TestAgentBlockCreator(unittest.TestCase):

    def setUp(self):
        self.workflow = Workflow(name="test")
        self.creator = AgentBlockCreator()

    def test_creates_agent_block(self):
        block = self.creator.add_block_to(self.workflow)
        self.assertIsInstance(block, AgentBlock)

    def test_block_is_added_to_workflow(self):
        block = self.creator.add_block_to(self.workflow)
        self.assertIn(block, self.workflow.blocks)


class TestHTTPBlockCreator(unittest.TestCase):

    def setUp(self):
        self.workflow = Workflow(name="test")
        self.creator = HTTPBlockCreator()

    def test_creates_http_block(self):
        block = self.creator.add_block_to(self.workflow)
        self.assertIsInstance(block, HTTPBlock)

    def test_block_is_added_to_workflow(self):
        block = self.creator.add_block_to(self.workflow)
        self.assertIn(block, self.workflow.blocks)


class TestPythonScriptBlockCreator(unittest.TestCase):

    def setUp(self):
        self.workflow = Workflow(name="test")
        self.creator = PythonScriptBlockCreator()

    def test_creates_python_script_block(self):
        block = self.creator.add_block_to(self.workflow)
        self.assertIsInstance(block, PythonScriptBlock)

    def test_block_is_added_to_workflow(self):
        block = self.creator.add_block_to(self.workflow)
        self.assertIn(block, self.workflow.blocks)


class TestAddBlockToNotifiesObserver(unittest.TestCase):
    """add_block_to must trigger Observer notifications via workflow.add_block()."""

    def test_observer_notified_after_creation(self):
        from core.domain.workflow import Subscriber

        class Counter(Subscriber):
            def __init__(self):
                self.count = 0
            def update(self, workflow):
                self.count += 1

        wf = Workflow(name="test")
        counter = Counter()
        wf.subscribe(counter)

        LLMBlockCreator().add_block_to(wf)
        self.assertEqual(counter.count, 1)


class TestMultipleCreatorsOnSameWorkflow(unittest.TestCase):
    """Different creators can add blocks to the same workflow independently."""

    def test_four_creators_produce_four_blocks(self):
        wf = Workflow(name="test")
        LLMBlockCreator().add_block_to(wf)
        AgentBlockCreator().add_block_to(wf)
        HTTPBlockCreator().add_block_to(wf)
        PythonScriptBlockCreator().add_block_to(wf)
        self.assertEqual(len(wf.blocks), 4)

    def test_block_types_are_all_distinct(self):
        wf = Workflow(name="test")
        LLMBlockCreator().add_block_to(wf)
        AgentBlockCreator().add_block_to(wf)
        HTTPBlockCreator().add_block_to(wf)
        PythonScriptBlockCreator().add_block_to(wf)
        types = {type(b).__name__ for b in wf.blocks}
        self.assertEqual(types, {"LLMBlock", "AgentBlock", "HTTPBlock", "PythonScriptBlock"})


if __name__ == "__main__":
    unittest.main()
