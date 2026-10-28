"""Source-only, no-model tests of the exact selected UI/API class coverage."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "audit-selected-11-node-coverage.py"
spec = importlib.util.spec_from_file_location("osf_11_class_preflight", PATH)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class ElevenWorkflowNodeCoverageTests(unittest.TestCase):
    def test_both_workflow_formats_extract_all_class_names(self):
        ui = {"nodes": [
            {"id": 1, "type": "GIMMVFI_loader",
             "properties": {"cnr_id": "ComfyUI-GIMM-VFI"}},
            {"id": 2, "type": "VHS_LoadVideo", "properties": {}},
        ]}
        api = {"1": {"class_type": "SAM3_Detect", "inputs": {}},
               "2": {"class_type": "SaveImage", "inputs": {}}}
        self.assertEqual(checker.extract_nodes(ui, "ui"), [
            {"class": "GIMMVFI_loader", "owner_hint": "ComfyUI-GIMM-VFI"},
            {"class": "VHS_LoadVideo", "owner_hint": None},
        ])
        self.assertEqual(checker.extract_nodes(api, "api"), [
            {"class": "SAM3_Detect", "owner_hint": None},
            {"class": "SaveImage", "owner_hint": None},
        ])
        for malformed, fmt in (
            ({"nodes": {}}, "ui"),
            ({"nodes": [{"id": 1}]}, "ui"),
            ({"1": {"inputs": {}}}, "api"),
            ({}, "api"),
        ):
            with self.subTest(fmt=fmt, malformed=malformed):
                with self.assertRaises(ValueError):
                    checker.extract_nodes(malformed, fmt)

    def test_fork_is_never_misclassified_as_core(self):
        registry = {"VHS_VideoCombine": "ComfyUI-VideoHelperSuite"}
        for class_name in checker.FORK_NATIVE:
            status = checker.classify_node(
                {"class": class_name, "owner_hint": "comfy-core"}, registry
            )
            self.assertEqual(status, "requires_modified_scail_sam3_fork")

    def test_cpu_registry_uses_exact_required_registered_classes_only(self):
        driver = checker._load_python(
            ROOT / "scripts/qualify_clean_comfy_cpu.py", "osf_accepted_cpu_test"
        )
        actual = checker.registered_cpu_classes(driver)
        self.assertIn("VHS_VideoCombine", actual)
        self.assertIn("VHS_SelectEveryNthImage", actual)
        self.assertIn("DownsampleFPSNode", actual)
        self.assertIn("UnetLoaderGGUF", actual)
        self.assertIn("UltimateSDUpscale", actual)
        self.assertIn("Any Switch (rgthree)", actual)
        self.assertNotIn("VHS_LoadVideo", actual)
        self.assertNotIn("UltimateSDUpscaleNoUpscale", actual)
        self.assertNotIn("WanSCAILToVideo", actual)
        self.assertEqual(len(actual), 6)

    def test_unknown_uuid_and_unverified_extension_require_explicit_gates(self):
        registry = {"UnetLoaderGGUF": "ComfyUI-GGUF"}
        checks = (
            ("1434deb7-2315-427a-8ad1-73b4f683e72d", "comfy-core",
             "unresolved_group_uuid"),
            ("Florence2Run", "comfyui-florence2",
             "extension_declared_not_runtime_verified"),
            ("WanFirstLastFrameToVideo", "comfy-core",
             "core_candidate_not_runtime_verified"),
            ("MaskSomethingUntracked", None,
             "unmapped_node_not_runtime_verified"),
            ("UnetLoaderGGUF", "comfyui-gguf",
             "class_registered_on_clean_cpu_only"),
        )
        for name, owner, expected in checks:
            with self.subTest(name=name):
                self.assertEqual(checker.classify_node({
                    "class": name, "owner_hint": owner,
                }, registry), expected)

    def test_exact_eleven_real_workflows_have_fork_and_unresolved_gates(self):
        report = checker.audit()
        self.assertEqual(report["schema"], "osf-selected-11-node-coverage-v1")
        self.assertEqual(report["selected_workflow_count"], 11)
        self.assertEqual(report["workflow_graph_format_counts"],
                         {"api": 4, "ui": 7})
        self.assertEqual(report["unique_node_class_count"], 81)
        self.assertEqual(len(report["unresolved_uuid_node_classes"]), 4)
        self.assertFalse(report["all_eleven_workflows_executable"])
        self.assertFalse(report["commercial_rights_verified"])
        self.assertFalse(report["gpu_inference_verified"])
        by_name = {Path(w["workflow"]).stem: w for w in report["workflows"]}
        self.assertEqual(len(by_name), 11)
        for key in ("step4_5_sam3_mask", "step6_animation_mode",
                    "step7_replacement_mode"):
            self.assertIn("SAM3_VideoTrack",
                          by_name[key]["requires_modified_scail_sam3_fork"])
            self.assertIn("SCAIL2ColoredMask",
                          by_name[key]["requires_modified_scail_sam3_fork"])
        self.assertIn("WanSCAILToVideo",
                      by_name["step6_animation_mode"][
                          "requires_modified_scail_sam3_fork"])
        self.assertEqual(by_name["mm_upscale_video_workflow"]["graph_format"],
                         "ui")
        self.assertIn("unresolved_group_uuid",
                      by_name["mm_upscale_video_workflow"][
                          "node_classes_by_status"])
        self.assertEqual(by_name["sam3_custompkg_probe"]["graph_format"], "api")
        self.assertTrue(all(not w["gpu_inference_verified"]
                            and not w["executable_api_prompt_proven"]
                            for w in report["workflows"]))

    def test_embedded_mm_upscale_group_definitions_are_present_but_unqualified(self):
        report = checker.audit()
        self.assertEqual(report["embedded_group_internal_node_instances"], 89)
        self.assertEqual(len(report["embedded_group_uuid_classes"]), 4)
        self.assertEqual(report["missing_embedded_group_uuid_definitions"], [])
        mm = next(row for row in report["workflows"] if
                  row["workflow"].endswith("/mm_upscale_video_workflow.json"))
        groups = mm["embedded_group_definition_preflight"]
        self.assertTrue(groups["all_referenced_uuid_definitions_embedded"])
        self.assertEqual(len(groups["embedded_definitions"]), 4)
        self.assertEqual(groups["embedded_internal_node_instances"], 89)
        expected = {
            "6f5ab705-8e1b-4b53-a3f4-a35676bec4e9": 16,
            "1434deb7-2315-427a-8ad1-73b4f683e72d": 35,
            "3a5d7d35-9999-4738-b299-aed4dbeffd55": 28,
            "3ed84f91-ec12-4881-a8e3-1d2fc355c673": 10,
        }
        self.assertEqual({
            d["group_uuid"]: d["internal_node_instances"]
            for d in groups["embedded_definitions"]
        }, expected)
        self.assertIn("easy forLoopStart",
                      groups["unique_embedded_internal_class_ids"])
        self.assertIn("ImageBatchJoinWithTransition",
                      groups["unique_embedded_internal_class_ids"])
        self.assertTrue(all(not d["runtime_registered"]
                            and not d["internal_nodes_runtime_qualified"]
                            and not d["executable_api_prompt_proven"]
                            for d in groups["embedded_definitions"]))
        self.assertFalse(groups["runtime_qualified"])

    def test_embedded_group_missing_or_corrupted_definition_fails_or_reports(self):
        group_id = "3a5d7d35-9999-4738-b299-aed4dbeffd55"
        nodes = [{"class": group_id, "owner_hint": "comfy-core"}]
        no_definition = checker.inspect_embedded_subgraphs({}, nodes)
        self.assertEqual(no_definition["missing_embedded_definition_ids"],
                         [group_id])
        self.assertFalse(no_definition["all_referenced_uuid_definitions_embedded"])
        definition = {"id": group_id, "nodes": [
            {"type": "ImageBatchJoinWithTransition"}, {"type": "easy forLoopStart"},
        ]}
        recovered = checker.inspect_embedded_subgraphs(
            {"definitions": {"subgraphs": [definition]}}, nodes)
        self.assertEqual(recovered["embedded_internal_node_instances"], 2)
        self.assertFalse(recovered["runtime_qualified"])
        for bad in (
            {"definitions": {"subgraphs": {}}},
            {"definitions": {"subgraphs": [definition, definition]}},
            {"definitions": {"subgraphs": [{**definition, "nodes": []}]}},
            {"definitions": {"subgraphs": [
                {**definition, "nodes": [{"type": "\nsecret"}]},
            ]}},
        ):
            with self.subTest(bad=repr(bad)[:45]):
                with self.assertRaises(ValueError):
                    checker.inspect_embedded_subgraphs(bad, nodes)

    def test_report_omits_media_names_and_prompt_values(self):
        serialized = json.dumps(checker.audit(), sort_keys=True)
        self.assertNotIn("scail2_test_driving_video.mp4", serialized)
        self.assertNotIn("scail2_test_reference_character.jpg", serialized)
        self.assertNotIn(".safetensors", serialized)
        self.assertNotIn("custom_width", serialized)


if __name__ == "__main__":
    unittest.main()
