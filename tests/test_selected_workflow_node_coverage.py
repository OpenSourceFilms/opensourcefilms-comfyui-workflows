"""Live /object_info comparison contracts atop canonical selected-11 audit."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_selected_workflow_nodes.py"
spec = importlib.util.spec_from_file_location("osf_live_selected_11", SCRIPT)
live_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live_audit)


class LiveSelectedClassCoverageTests(unittest.TestCase):
    def test_reuses_canonical_11_graph_preflight(self):
        audit = live_audit.load_selected_graphs()
        self.assertEqual(audit["schema"], "osf-selected-11-node-coverage-v1")
        self.assertEqual(audit["selected_workflow_count"], 11)
        self.assertEqual(audit["unique_node_class_count"], 81)
        self.assertEqual(len(audit["workflows"]), 11)
        self.assertEqual(audit["workflow_graph_format_counts"],
                         {"api": 4, "ui": 7})

    def test_fork_annotations_and_uuids_separate_from_other_gaps(self):
        for name in ("SAM3_Detect", "SAM3_TrackPreview",
                     "SCAIL2ColoredMask", "WanSCAILToVideo"):
            self.assertEqual(live_audit.classify_missing(name),
                             "documented_scail_sam3_fork_native")
        self.assertEqual(live_audit.classify_missing("MarkdownNote"),
                         "editor_or_extension_type_unqualified")
        self.assertEqual(
            live_audit.classify_missing(
                "3a5d7d35-9999-4738-b299-aed4dbeffd55"),
            "unresolved_group_uuid",
        )
        self.assertEqual(live_audit.classify_missing("GIMMVFI_loader"),
                         "other_unregistered_in_current_cpu_installation")

    def test_exact_real_graphs_against_synthetic_registration(self):
        source = live_audit.load_selected_graphs()
        simulated = {
            "SaveImage": {"input": {}}, "VHS_VideoCombine": {"input": {}},
            "UnetLoaderGGUF": {"input": {}},
        }
        output = live_audit.coverage_from_registry(source, simulated)
        self.assertEqual(output["status"],
                         "real_live_cpu_class_registration_coverage_only")
        self.assertEqual(output["selected_workflows"], 11)
        self.assertEqual(output["unique_graph_class_ids"], 81)
        self.assertGreater(output["total_node_instances"], 300)
        self.assertIn("SAM3_TrackPreview", output["missing_documented_fork_native"])
        self.assertIn("GIMMVFI_loader", output["missing_other_unregistered"])
        self.assertFalse(output["all_11_workflows_executable"])
        self.assertFalse(output["gpu_inference_tested"])
        self.assertFalse(output["commercial_rights_cleared"])
        row = output["per_workflow"][
            "workflows/commercial-compatible/mm_upscale_video_workflow.json"]
        self.assertIn("UnetLoaderGGUF", row["registered_class_ids"])
        self.assertIn("unresolved_group_uuid",
                      row["unregistered_class_ids_by_category"])
        self.assertIn("other_unregistered_in_current_cpu_installation",
                      row["unregistered_class_ids_by_category"])
        self.assertEqual(len(row["source_sha256"]), 64)

    def test_embedded_upscale_groups_reconcile_89_internal_instances(self):
        source = live_audit.load_selected_graphs()
        output = live_audit.coverage_from_registry(
            source, {
                "SaveImage": {"input": {}},
                "UnetLoaderGGUF": {"input": {}},
            }
        )
        key = "workflows/commercial-compatible/mm_upscale_video_workflow.json"
        row = output["per_workflow"][key]
        embedded = row["embedded_internal_class_registration_coverage"]
        self.assertEqual(embedded["status"],
                         "embedded_internal_live_class_registration_only")
        self.assertEqual(embedded["embedded_group_count"], 4)
        self.assertEqual(embedded["embedded_node_instances"], 89)
        self.assertEqual(output["embedded_internal_node_instances"], 89)
        self.assertGreater(output["embedded_internal_unique_class_ids"], 0)
        self.assertEqual(
            output["embedded_internal_unique_class_ids"],
            output["embedded_registered_unique_class_ids"]
            + output["embedded_unregistered_unique_class_ids"],
        )
        self.assertTrue(output[
            "embedded_internal_class_ids_are_separate_from_top_level_81"
        ])
        self.assertFalse(embedded["subgraph_expansion_or_execution_verified"])
        self.assertFalse(output["embedded_internal_graphs_executable"])
        self.assertEqual(
            len(embedded["groups"]), 4,
        )
        self.assertTrue(all(
            g["internal_graph_executable"] is False
            and len(g["group_uuid"]) == 36
            for g in embedded["groups"]
        ))
        self.assertEqual(output["unique_graph_class_ids"], 81)
        self.assertEqual(
            output["per_workflow"][
                "workflows/commercial-compatible/sam3_custompkg_probe.json"
            ]["embedded_internal_class_registration_coverage"],
            None,
        )

    def test_uuid_group_references_not_mistaken_for_runtime_registration(self):
        source = live_audit.load_selected_graphs()
        mm = next(w for w in source["workflows"]
                  if w["workflow"].endswith("/mm_upscale_video_workflow.json"))
        groups = mm["embedded_group_definition_preflight"]
        names = set(groups["unique_embedded_internal_class_ids"])
        # Malicious or accidentally matching UUID names do not turn
        # frontend group references into executable classes.
        live = {name: {"input": {}} for name in names}
        extra = live_audit.embedded_internal_registration_coverage(
            groups, live, live_audit._source_module(ROOT)
        )
        unregistered = extra["unregistered_unique_internal_class_ids_by_category"]
        self.assertEqual(
            unregistered.get("unresolved_group_uuid", []),
            sorted(n for n in names
                   if live_audit._source_module(ROOT).UUID.fullmatch(n)),
        )
        self.assertFalse(extra["subgraph_expansion_or_execution_verified"])
        self.assertEqual(extra["embedded_node_instances"], 89)

    def test_malformed_embedded_source_rejected_fail_closed(self):
        import copy
        source = live_audit.load_selected_graphs()
        mm = next(w for w in source["workflows"]
                  if w["workflow"].endswith("/mm_upscale_video_workflow.json"))
        groups = mm["embedded_group_definition_preflight"]
        module = live_audit._source_module(ROOT)
        malformed = copy.deepcopy(groups)
        malformed["embedded_internal_node_instances"] += 1
        with self.assertRaisesRegex(ValueError, "do not reconcile"):
            live_audit.embedded_internal_registration_coverage(
                malformed, {"SaveImage": {}}, module
            )
        malformed = copy.deepcopy(groups)
        malformed["embedded_definitions"].append(
            malformed["embedded_definitions"][0]
        )
        with self.assertRaisesRegex(ValueError, "Malformed canonical"):
            live_audit.embedded_internal_registration_coverage(
                malformed, {"SaveImage": {}}, module
            )
        malformed = copy.deepcopy(groups)
        malformed["embedded_definitions"][0]["internal_unique_class_ids"] = [""]
        with self.assertRaisesRegex(ValueError, "Malformed canonical"):
            live_audit.embedded_internal_registration_coverage(
                malformed, {"SaveImage": {}}, module
            )

    def test_missing_or_malformed_live_registry_fails(self):
        inventory = live_audit.load_selected_graphs()
        for invalid in (None, [], {}, {12: {}}, {"": {}}):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    live_audit.coverage_from_registry(inventory, invalid)

    def test_different_or_malformed_source_audit_fails(self):
        for invalid in (None, [], {}, {
            "schema": "osf-selected-11-node-coverage-v1",
            "selected_workflow_count": 11,
            "workflows": [],
        }):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    live_audit.coverage_from_registry(invalid, {"SaveImage": {}})

    def test_missing_and_symlinked_checkout_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaisesRegex(ValueError, "Missing/symlinked"):
                live_audit.load_selected_graphs(root / "absent")
            link = root / "linked_checkout"
            link.symlink_to(ROOT, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "Missing/symlinked"):
                live_audit.load_selected_graphs(link)

    def test_clean_cpu_runner_attaches_live_coverage_to_metadata(self):
        runtime = (ROOT / "scripts" / "qualify_clean_comfy_cpu.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("load_selected_graphs()", runtime)
        self.assertIn("coverage_from_registry(", runtime)
        self.assertIn('"selected_workflow_node_coverage"', runtime)


if __name__ == "__main__":
    unittest.main()
