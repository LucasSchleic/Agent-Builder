import unittest

from core.domain.connection import Connection


class TestConnectionInit(unittest.TestCase):
    """Tests for Connection instantiation."""

    def _make_connection(self, **kwargs):
        defaults = dict(
            source_block_id="block-A",
            source_port_id="port-1",
            target_block_id="block-B",
            target_port_id="port-2",
        )
        defaults.update(kwargs)
        return Connection(**defaults)

    def test_auto_generates_uuid(self):
        conn = self._make_connection()
        self.assertIsNotNone(conn.id)
        self.assertEqual(len(conn.id), 36)

    def test_uses_provided_id(self):
        conn = self._make_connection(connection_id="my-conn-id")
        self.assertEqual(conn.id, "my-conn-id")

    def test_stores_all_ids(self):
        conn = self._make_connection()
        self.assertEqual(conn.source_block_id, "block-A")
        self.assertEqual(conn.source_port_id, "port-1")
        self.assertEqual(conn.target_block_id, "block-B")
        self.assertEqual(conn.target_port_id, "port-2")


class TestConnectionValidate(unittest.TestCase):
    """Tests for Connection.validate()."""

    def _make_connection(self, **kwargs):
        defaults = dict(
            source_block_id="block-A",
            source_port_id="port-1",
            target_block_id="block-B",
            target_port_id="port-2",
        )
        defaults.update(kwargs)
        return Connection(**defaults)

    def test_valid_connection(self):
        self.assertTrue(self._make_connection().validate())

    def test_self_loop_is_invalid(self):
        conn = self._make_connection(source_block_id="block-A", target_block_id="block-A")
        self.assertFalse(conn.validate())

    def test_empty_source_block_id_is_invalid(self):
        conn = self._make_connection(source_block_id="")
        self.assertFalse(conn.validate())

    def test_empty_target_block_id_is_invalid(self):
        conn = self._make_connection(target_block_id="")
        self.assertFalse(conn.validate())

    def test_empty_source_port_id_is_invalid(self):
        conn = self._make_connection(source_port_id="")
        self.assertFalse(conn.validate())

    def test_empty_target_port_id_is_invalid(self):
        conn = self._make_connection(target_port_id="")
        self.assertFalse(conn.validate())


class TestConnectionSerialization(unittest.TestCase):
    """Tests for Connection.to_dict() and Connection.from_dict()."""

    def _make_connection(self):
        return Connection(
            source_block_id="block-A",
            source_port_id="port-1",
            target_block_id="block-B",
            target_port_id="port-2",
        )

    def test_to_dict_uses_id_key_not_connection_id(self):
        d = self._make_connection().to_dict()
        self.assertIn("id", d)
        self.assertNotIn("connection_id", d)

    def test_to_dict_values(self):
        conn = self._make_connection()
        d = conn.to_dict()
        self.assertEqual(d["source_block_id"], "block-A")
        self.assertEqual(d["source_port_id"], "port-1")
        self.assertEqual(d["target_block_id"], "block-B")
        self.assertEqual(d["target_port_id"], "port-2")

    def test_from_dict_roundtrip(self):
        conn = self._make_connection()
        restored = Connection.from_dict(conn.to_dict())
        self.assertEqual(restored.id, conn.id)
        self.assertEqual(restored.source_block_id, conn.source_block_id)
        self.assertEqual(restored.source_port_id, conn.source_port_id)
        self.assertEqual(restored.target_block_id, conn.target_block_id)
        self.assertEqual(restored.target_port_id, conn.target_port_id)


if __name__ == "__main__":
    unittest.main()
