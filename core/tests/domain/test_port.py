import unittest

from core.domain.port import Port, VALID_DIRECTIONS, VALID_DATA_TYPES


class TestPortInit(unittest.TestCase):
    """Tests for Port instantiation."""

    def test_auto_generates_uuid(self):
        port = Port(name="output", direction="output", data_type="str")
        self.assertIsNotNone(port.id)
        self.assertEqual(len(port.id), 36)  # standard UUID format

    def test_uses_provided_id(self):
        port = Port(name="output", direction="output", data_type="str", port_id="my-id")
        self.assertEqual(port.id, "my-id")

    def test_required_defaults_to_false(self):
        port = Port(name="output", direction="output", data_type="str")
        self.assertFalse(port.required)

    def test_required_can_be_set(self):
        port = Port(name="input", direction="input", data_type="llm", required=True)
        self.assertTrue(port.required)


class TestPortValidate(unittest.TestCase):
    """Tests for Port.validate()."""

    def test_valid_port(self):
        for direction in VALID_DIRECTIONS:
            for data_type in VALID_DATA_TYPES:
                port = Port(name="p", direction=direction, data_type=data_type)
                self.assertTrue(port.validate(), f"Expected valid: {direction}, {data_type}")

    def test_invalid_direction(self):
        port = Port(name="p", direction="sideways", data_type="str")
        self.assertFalse(port.validate())

    def test_invalid_data_type(self):
        port = Port(name="p", direction="input", data_type="banana")
        self.assertFalse(port.validate())

    def test_both_invalid(self):
        port = Port(name="p", direction="up", data_type="banana")
        self.assertFalse(port.validate())


class TestPortSerialization(unittest.TestCase):
    """Tests for Port.to_dict() and Port.from_dict()."""

    def _make_port(self):
        return Port(name="llm_output", direction="output", data_type="llm", required=False)

    def test_to_dict_keys(self):
        d = self._make_port().to_dict()
        self.assertIn("id", d)
        self.assertIn("name", d)
        self.assertIn("direction", d)
        self.assertIn("data_type", d)
        self.assertIn("required", d)

    def test_to_dict_values(self):
        port = self._make_port()
        d = port.to_dict()
        self.assertEqual(d["name"], "llm_output")
        self.assertEqual(d["direction"], "output")
        self.assertEqual(d["data_type"], "llm")
        self.assertFalse(d["required"])

    def test_from_dict_roundtrip(self):
        port = Port(name="in", direction="input", data_type="tool", required=True)
        restored = Port.from_dict(port.to_dict())
        self.assertEqual(restored.id, port.id)
        self.assertEqual(restored.name, port.name)
        self.assertEqual(restored.direction, port.direction)
        self.assertEqual(restored.data_type, port.data_type)
        self.assertEqual(restored.required, port.required)

    def test_from_dict_required_defaults_to_false(self):
        data = {"id": "abc", "name": "p", "direction": "input", "data_type": "str"}
        port = Port.from_dict(data)
        self.assertFalse(port.required)


if __name__ == "__main__":
    unittest.main()
