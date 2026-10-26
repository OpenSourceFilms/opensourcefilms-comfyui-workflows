"""Malformed ComfyUI graph regressions. Validation must report errors, not crash."""
import copy
import importlib.util
from pathlib import Path
import unittest

P = Path(__file__).resolve().parents[1] / "scripts" / "validate-workflow-json.py"
spec = importlib.util.spec_from_file_location("offline_workflow_validator", P)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def graph():
    return {"nodes": [
        {"id": 1, "type": "A", "inputs": [], "outputs": [{"links": [1]}]},
        {"id": 2, "type": "B", "inputs": [{"link": 1}], "outputs": []}],
        "links": [[1,1,0,2,0,"IMAGE"]]}


class MalformedInputs(unittest.TestCase):
    def reject(self, value):
        errors, kind = validator.validate(value)
        self.assertEqual(kind, "ui")
        self.assertTrue(errors, "malformed graph unexpectedly accepted")

    def test_valid_baseline(self):
        self.assertEqual(validator.validate(graph()), ([], "ui"))

    def test_null_node_output_port_array(self):
        item = graph()
        item["nodes"][0]["outputs"] = None
        self.reject(item)

    def test_null_node_input_port_array(self):
        item = graph()
        item["nodes"][1]["inputs"] = None
        self.reject(item)

    def test_unhashable_input_link(self):
        item = graph()
        item["nodes"][1]["inputs"][0]["link"] = [1,2]
        self.reject(item)

    def test_unhashable_output_link(self):
        item = graph()
        item["nodes"][0]["outputs"][0]["links"] = [[1,2]]
        self.reject(item)

    def test_unhashable_link_id(self):
        item = graph()
        item["links"][0][0] = [1]
        self.reject(item)

    def test_bool_link_id_is_not_integer(self):
        item = graph()
        item["links"][0][0] = True
        self.reject(item)

    def test_bool_node_id_is_not_integer(self):
        item = graph()
        item["nodes"][0]["id"] = True
        self.reject(item)

    def test_bool_slot_is_not_integer(self):
        item = graph()
        item["links"][0][2] = True
        self.reject(item)

    def test_malformed_link_endpoint_does_not_crash(self):
        item = graph()
        item["links"][0][3] = []
        self.reject(item)

    def test_null_output_ports_without_link_are_valid(self):
        item = {"nodes": [{"id":1,"type":"Terminal","inputs":[],"outputs":None}], "links":[]}
        errors, kind = validator.validate(item)
        self.assertEqual(kind,"ui")
        self.assertTrue(errors)  # Null ports are malformed even if not linked.

    def test_api_bool_source_slot_is_invalid(self):
        item = {"1":{"class_type":"Source","inputs":{}},
                "2":{"class_type":"Sink","inputs":{"image":["1",True]}}}
        errors, kind = validator.validate(item)
        self.assertEqual(kind,"api")
        self.assertTrue(errors)

    def test_api_valid_baseline(self):
        item = {"1":{"class_type":"Source","inputs":{}},
                "2":{"class_type":"Sink","inputs":{"image":["1",0]}}}
        self.assertEqual(validator.validate(item),([],"api"))


if __name__ == "__main__":
    unittest.main()
