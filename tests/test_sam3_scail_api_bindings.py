"""Offline SAM3/SCAIL pinned-public-core API input binding contracts."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "audit_sam3_scail_api_bindings.py"
spec = importlib.util.spec_from_file_location("osf_sam3_scail_bindings", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def graph(name="step6_animation_mode"):
    return json.loads(
        (ROOT / "workflows" / "commercial-compatible" / (name + ".json"))
        .read_text(encoding="utf-8")
    )


class NativeBindingsTests(unittest.TestCase):
    def test_all_three_published_graphs_match_exact_pinned_source_schema(self):
        report = mod.audit()
        self.assertEqual(report["api_workflows_checked"], 3)
        self.assertEqual(report["native_node_instances_checked"], 12)
        self.assertTrue(report["source_schema_snapshot_only"])
        self.assertFalse(report["full_graph_or_gpu_inference_qualified"])
        self.assertEqual(len(mod.NATIVE), 5)
        self.assertEqual([item["native_node_instances"]
                          for item in report["workflows"]], [4, 4, 4])
        self.assertGreater(sum(item["checked_native_to_native_output_types"]
                               for item in report["workflows"]), 0)
        for item in report["workflows"]:
            self.assertFalse(item["model_weights_or_inference_tested"])
            self.assertFalse(item["all_other_workflow_nodes_qualified"])

    def test_unknown_native_input_fails(self):
        source = graph()
        source["4"]["inputs"]["not_an_upstream_input"] = 1
        with self.assertRaisesRegex(ValueError, "unknown input"):
            mod.check_api_bindings(source)

    def test_missing_required_model_fails(self):
        source = graph()
        del source["4"]["inputs"]["model"]
        with self.assertRaisesRegex(ValueError, "required input missing"):
            mod.check_api_bindings(source)

    def test_wrong_integer_boolean_or_enum_fails(self):
        for target, field, value in (
            ("4", "max_objects", True),
            ("6", "threshold", "0.5"),
            ("7", "replacement_mode", 1),
            ("7", "sort_by", "random"),
            ("20", "height", 768.5),
        ):
            with self.subTest(target=target, field=field):
                source = graph()
                source[target]["inputs"][field] = value
                with self.assertRaisesRegex(ValueError, "scalar input type mismatch"):
                    mod.check_api_bindings(source)

    def test_sam3_forced_input_coordinate_sockets_reject_literals(self):
        # Public pinned nodes_sam3.py specifies force_input=True for all
        # three optional prompt sockets. Omission is permitted.
        self.assertEqual(mod.check_api_bindings(graph())["native_node_instances"], 4)
        self.assertEqual(mod.FORCE_LINK_FIELDS, {
            "SAM3_Detect.bboxes",
            "SAM3_Detect.positive_coords",
            "SAM3_Detect.negative_coords",
        })
        for field, value in (
            ("positive_coords", "[]"),
            ("negative_coords", "[]"),
            ("positive_coords", ""),
            ("negative_coords", 1),
            ("bboxes", []),
            ("bboxes", None),
        ):
            with self.subTest(field=field, value=value):
                source = graph()
                source["6"]["inputs"][field] = value
                with self.assertRaisesRegex(ValueError, "force_input socket requires a link"):
                    mod.check_api_bindings(source)

    def test_missing_reference_and_malformed_link_fail(self):
        source = graph()
        source["7"]["inputs"]["driving_track_data"] = ["missing", 0]
        with self.assertRaisesRegex(ValueError, "absent node"):
            mod.check_api_bindings(source)
        for bad in ("4", ["4", -1], ["4", True], ["4", "0"], ["4"]):
            with self.subTest(bad=bad):
                source = graph()
                source["7"]["inputs"]["driving_track_data"] = bad
                with self.assertRaisesRegex(ValueError, "lacks a valid link"):
                    mod.check_api_bindings(source)

    def test_out_of_range_native_output_slot_fails(self):
        source = graph()
        source["7"]["inputs"]["driving_track_data"] = ["4", 1]
        with self.assertRaisesRegex(ValueError, "absent output slot"):
            mod.check_api_bindings(source)

    def test_wrong_native_output_type_fails(self):
        source = graph()
        source["7"]["inputs"]["driving_track_data"] = ["6", 0]
        with self.assertRaisesRegex(ValueError, "output type mismatch"):
            mod.check_api_bindings(source)

    def test_detect_mask_is_allowed_as_scail_reference_mask(self):
        source = graph()
        source["7"]["inputs"]["ref_track_data"] = ["6", 0]
        self.assertEqual(mod.check_api_bindings(source)["native_node_instances"], 4)

    def test_zero_output_trackpreview_cannot_be_used_as_image(self):
        source = graph("step4_5_sam3_mask")
        source["7"]["inputs"]["ref_track_data"] = ["10", 0]
        with self.assertRaisesRegex(ValueError, "absent output slot"):
            mod.check_api_bindings(source)

    def test_malformed_graph_and_missing_native_nodes_fail(self):
        for value in (None, [], {}, {"1": {"class_type": "EmptyImage"}}):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    mod.check_api_bindings(value)

    def test_report_never_emits_prompt_text_or_model_filenames(self):
        result = json.dumps(mod.audit(), sort_keys=True)
        self.assertNotIn("filename_prefix", result)
        self.assertNotIn("positive_prompt", result)
        self.assertNotIn("file_path", result)


if __name__ == "__main__":
    unittest.main()
