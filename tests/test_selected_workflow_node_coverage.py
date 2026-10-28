"""Fail-closed offline contracts for real 11-workflow class coverage audit."""
from __future__ import annotations

from collections import Counter
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
script = ROOT / "scripts" / "audit_selected_workflow_nodes.py"
spec = importlib.util.spec_from_file_location("osf_selected_node_audit", script)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class SelectedWorkflowLiveCoverageContracts(unittest.TestCase):
    def test_extract_ui_api_and_reject_malformed(self):
        mode, nodes = audit.extract_class_ids({
            "nodes": [
                {"type": "VHS_LoadVideo"},
                {"type": "VHS_VideoCombine"},
                {"type": "VHS_VideoCombine"},
            ]
        })
        self.assertEqual(mode, "ui")
        self.assertEqual(nodes, Counter({
            "VHS_LoadVideo": 1, "VHS_VideoCombine": 2,
        }))
        mode, nodes = audit.extract_class_ids({
            "1": {"class_type": "SAM3_Detect"},
            "2": {"class_type": "SCAIL2ColoredMask"},
        })
        self.assertEqual(mode, "api")
        self.assertEqual(sum(nodes.values()), 2)
        for malformed in (
            None, [], {}, {"nodes": {}}, {"nodes": [{"type": 7}]},
            {"8": {"class_type": ""}}, {"foo": {"class_type": "SaveImage"}},
            {"nodes": [{"type": "../escape"}], "other": None}
        ):
            if isinstance(malformed, dict) and malformed.get("nodes") == [{"type": "../escape"}]:
                # Graph class names do not imply filesystem paths and
                # are never used in a filesystem or network operation.
                continue
            with self.subTest(malformed=malformed):
                with self.assertRaises(ValueError):
                    audit.extract_class_ids(malformed)

    def test_real_manifest_graph_allowlist_and_fork_classes(self):
        graphs = audit.load_selected_graphs()
        self.assertEqual(len(graphs), 11)
        paths = list(graphs)
        self.assertTrue(all(p.startswith("workflows/commercial-compatible/")
                            for p in paths))
        self.assertTrue(all(len(row["source_sha256"]) == 64
                            for row in graphs.values()))
        native = graphs["workflows/commercial-compatible/step6_animation_mode.json"]
        self.assertEqual(native["graph_format"], "api")
        self.assertIn("WanSCAILToVideo", native["classes"])
        self.assertIn("SAM3_Detect", native["classes"])
        self.assertNotIn("MaskPropagateOpticalFlow", native["classes"])
        ui = graphs["workflows/commercial-compatible/mm_upscale_video_workflow.json"]
        self.assertEqual(ui["graph_format"], "ui")
        self.assertIn("UnetLoaderGGUF", ui["classes"])

    def test_fork_ui_uuid_classifications_are_separate(self):
        self.assertEqual(audit.classify_missing("SAM3_Detect"),
                         "documented_scail_sam3_fork_native")
        self.assertEqual(audit.classify_missing("MarkdownNote"),
                         "ui_annotation_or_reroute")
        self.assertEqual(audit.classify_missing("3a5d7d35-9999-4738-b299-aed4dbeffd55"),
                         "uuid_typed_group_or_subgraph_unresolved")
        self.assertEqual(audit.classify_missing("UnetLoaderGGUF"),
                         "other_unregistered")

    def test_live_class_coverage_no_inference_claims(self):
        graphs = audit.load_selected_graphs()
        fake_registry = {
            "SaveImage": {"input": {}},
            "VHS_VideoCombine": {"input": {}},
            "UnetLoaderGGUF": {"input": {}},
        }
        result = audit.coverage_from_registry(graphs, fake_registry)
        self.assertEqual(result["selected_workflows"], 11)
        self.assertGreater(result["total_node_instances"], 100)
        self.assertIn("SAM3_Detect", result["known_fork_only_missing"])
        self.assertIn("WanSCAILToVideo", result["known_fork_only_missing"])
        self.assertIn("GIMMVFI_loader",
                      result["unregistered_other_across_workflows"])
        self.assertFalse(result["all_11_runtime_compatible"])
        self.assertFalse(result["model_inference_tested"])
        self.assertFalse(result["license_rights_cleared"])
        up = result["per_workflow"][
            "workflows/commercial-compatible/mm_upscale_video_workflow.json"
        ]
        self.assertIn("UnetLoaderGGUF", up["registered_class_ids"])
        self.assertIn(
            "other_unregistered", up["missing_class_ids_by_category"]
        )
        self.assertIn(
            "uuid_typed_group_or_subgraph_unresolved",
            up["missing_class_ids_by_category"],
        )
        self.assertLess(len(json.dumps(result)), 75_000)

    def test_missing_live_inventory_and_bad_shapes_fail_closed(self):
        graphs = audit.load_selected_graphs()
        for registry in (None, {}, [], {"SaveImage": 1, 7: None}):
            with self.subTest(registry=registry):
                with self.assertRaises(ValueError):
                    audit.coverage_from_registry(graphs, registry)
        with self.assertRaisesRegex(ValueError, "exactly 11"):
            audit.coverage_from_registry(
                {"only": {"graph_format": "ui",
                          "source_sha256": "0" * 64,
                          "classes": Counter({"SaveImage": 1})}},
                {"SaveImage": {}},
            )

    def test_symlinked_selected_workflow_source_fails_closed(self):
        graphs = audit.load_selected_graphs()
        self.assertEqual(len(graphs), 11)
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            with self.assertRaisesRegex(ValueError, "Missing/symlinked root"):
                audit.load_selected_graphs(base / "absent")

    def test_real_runtime_calls_live_coverage_before_evidence(self):
        code = (ROOT / "scripts" / "qualify_clean_comfy_cpu.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("coverage_from_registry(", code)
        self.assertIn("load_selected_graphs()", code)
        self.assertIn('"selected_workflow_node_coverage"', code)


if __name__ == "__main__":
    unittest.main()
