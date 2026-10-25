"""Synthetic structural tests for offline ComfyUI workflow validator."""
import importlib.util
import pathlib
import tempfile
import unittest

MODULE = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "validate-workflow-json.py"
SPEC = importlib.util.spec_from_file_location("validator", MODULE)
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class WorkflowValidatorTests(unittest.TestCase):
    def ui(self):
        return {"nodes": [
            {"id": 1, "type": "Loader", "inputs": [], "outputs": [{"links": [1]}]},
            {"id": 2, "type": "Saver", "inputs": [{"link": 1}], "outputs": []}
        ], "links": [[1, 1, 0, 2, 0, "IMAGE"]]}

    def test_valid_ui(self):
        self.assertEqual(validator.validate(self.ui()), ([], "ui"))

    def test_missing_node(self):
        doc = self.ui()
        doc["links"][0][3] = 99
        self.assertTrue(validator.validate(doc)[0])

    def test_bad_slot_and_negative_slot(self):
        for value in (2, -1):
            doc = self.ui()
            doc["links"][0][2] = value
            self.assertTrue(validator.validate(doc)[0])

    def test_duplicate_link(self):
        doc = self.ui()
        doc["links"].append(doc["links"][0][:])
        self.assertIn("duplicate link", " ".join(validator.validate(doc)[0]))

    def test_orphaned_input(self):
        doc = self.ui()
        doc["links"] = []
        self.assertTrue(validator.validate(doc)[0])

    def test_valid_api(self):
        doc = {"1": {"class_type": "Loader", "inputs": {}},
               "2": {"class_type": "Saver", "inputs": {"image": ["1", 0]}}}
        self.assertEqual(validator.validate(doc), ([], "api"))

    def test_bad_api_input_reference(self):
        doc = {"1": {"class_type": "Saver", "inputs": {"image": ["99", 0]}}}
        self.assertIn("missing upstream", " ".join(validator.validate(doc)[0]))

    def test_reject_malformed(self):
        for data in ([], {}, {"nodes": [], "links": "broken"}, {"foo": 1}):
            self.assertTrue(validator.validate(data)[0])

    def test_not_a_json_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "graph.json"
            path.write_text("{invalid")
            self.assertFalse(validator.check_file(path)["ok"])


if __name__ == "__main__":
    unittest.main()
