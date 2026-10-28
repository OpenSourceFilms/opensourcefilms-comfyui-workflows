"""Fail-closed source-only contracts for selected API graph topology."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "osf_api_topology", ROOT / "scripts" / "audit_selected_api_topology.py"
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def graph():
    return {
        "1": {"class_type": "Generate", "inputs": {"seed": 10}},
        "2": {"class_type": "Transform", "inputs": {"input": ["1", 0]}},
        "3": {"class_type": "Save", "inputs": {"frame": ["2", 1]}},
    }


class ApiTopologyContracts(unittest.TestCase):
    def test_valid_dag_counts_links_and_retains_negative_runtime_flags(self):
        report = audit.audit_api_graph(graph())
        self.assertEqual(report["node_count"], 3)
        self.assertEqual(report["link_input_count"], 2)
        self.assertEqual(report["maximum_dependency_depth"], 2)
        self.assertEqual(report["root_node_count"], 1)
        self.assertTrue(report["topology_verified"])
        self.assertFalse(report["output_slot_schema_verified"])
        self.assertFalse(report["executable_prompt_qualified"])

    def test_missing_upstream_and_invalid_output_slot_rejected(self):
        for value, expected in (
            (["999", 0], "missing upstream"),
            (["1", -1], "negative output slot"),
            (["1", True], "Boolean API output slot"),
        ):
            with self.subTest(value=value):
                candidate = graph()
                candidate["2"]["inputs"]["input"] = value
                with self.assertRaisesRegex(ValueError, expected):
                    audit.audit_api_graph(candidate)

    def test_self_link_and_multinode_cycles_rejected(self):
        candidate = graph()
        candidate["2"]["inputs"]["input"] = ["2", 0]
        with self.assertRaisesRegex(ValueError, "own output"):
            audit.audit_api_graph(candidate)
        candidate = graph()
        candidate["1"]["inputs"]["feedback"] = ["3", 0]
        with self.assertRaisesRegex(ValueError, "dependency cycle"):
            audit.audit_api_graph(candidate)

    def test_malformed_ids_or_node_shapes_rejected(self):
        for key in ("0", "01", "-1", "bad/name", "", "00"):
            with self.subTest(key=key):
                candidate = graph()
                candidate[key] = candidate.pop("3")
                with self.assertRaisesRegex(ValueError, "invalid node keys"):
                    audit.audit_api_graph(candidate)
        for bad in (
            {"class_type": "", "inputs": {}},
            {"class_type": "Valid", "inputs": []},
            {"inputs": {}},
        ):
            candidate = graph()
            candidate["3"] = bad
            with self.assertRaisesRegex(ValueError, "Malformed API"):
                audit.audit_api_graph(candidate)

    def test_nested_data_is_not_fabricated_as_an_api_edge(self):
        candidate = graph()
        candidate["1"]["inputs"]["real_literal"] = [0, 0]
        candidate["1"]["inputs"]["more_literal"] = {"nested": ["1", 0]}
        result = audit.audit_api_graph(candidate)
        self.assertEqual(result["link_input_count"], 2)

    def test_canonical_four_api_workflows_have_expected_source_topology(self):
        report = audit.audit_selected_api()
        self.assertEqual(report["schema"], "osf-selected-four-api-topology-v1")
        self.assertEqual(report["approved_selected_workflows"], 11)
        self.assertEqual(report["api_workflows_audited"], 4)
        self.assertEqual(report["ui_workflows_not_executed"], 7)
        self.assertEqual(report["total_api_nodes"], 60)
        self.assertEqual(report["total_api_link_inputs"], 82)
        names = {Path(name).stem for name in report["workflows"]}
        self.assertEqual(names, audit.API_FILES)
        self.assertTrue(all(
            item["topology_verified"]
            and not item["executable_prompt_qualified"]
            and len(item["source_sha256"]) == 64
            for item in report["workflows"].values()
        ))
        self.assertFalse(report["full_eleven_workflows_qualified"])
        self.assertFalse(report["model_or_gpu_inference_qualified"])

    def test_duplicate_edge_inputs_still_count_as_two_references(self):
        candidate = graph()
        candidate["2"]["inputs"]["another_link"] = ["1", 0]
        report = audit.audit_api_graph(candidate)
        self.assertEqual(report["link_input_count"], 3)
        self.assertEqual(report["directed_dependency_pairs"], 2)


if __name__ == "__main__":
    unittest.main()
