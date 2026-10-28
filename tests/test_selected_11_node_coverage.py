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

    def test_historic_sam3_scail_ids_are_not_unconditionally_fork_only(self):
        registry = {"VHS_VideoCombine": "ComfyUI-VideoHelperSuite"}
        for class_name in checker.FORK_NATIVE:
            status = checker.classify_node(
                {"class": class_name, "owner_hint": "comfy-core"}, registry
            )
            self.assertEqual(status, "sam3_scail_native_class_runtime_unverified")

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

    def test_exact_eleven_real_workflows_track_native_and_unresolved_gates(self):
        report = checker.audit()
        self.assertEqual(report["schema"], "osf-selected-11-node-coverage-v1")
        self.assertEqual(report["selected_workflow_count"], 11)
        self.assertEqual(report["workflow_graph_format_counts"],
                         {"api": 4, "ui": 7})
        self.assertEqual(report["unique_node_class_count"], 81)
        self.assertEqual(len(report["sam3_scail_historic_native_class_ids"]), 5)
        self.assertEqual(len(report["unresolved_uuid_node_classes"]), 4)
        self.assertFalse(report["all_eleven_workflows_executable"])
        self.assertFalse(report["commercial_rights_verified"])
        self.assertFalse(report["gpu_inference_verified"])
        by_name = {Path(w["workflow"]).stem: w for w in report["workflows"]}
        self.assertEqual(len(by_name), 11)
        for key in ("step4_5_sam3_mask", "step6_animation_mode",
                    "step7_replacement_mode"):
            self.assertIn("SAM3_VideoTrack",
                          by_name[key]["sam3_scail_native_class_ids"])
            self.assertIn("SCAIL2ColoredMask",
                          by_name[key]["sam3_scail_native_class_ids"])
        self.assertIn("WanSCAILToVideo",
                      by_name["step6_animation_mode"][
                          "sam3_scail_native_class_ids"])
        self.assertEqual(by_name["mm_upscale_video_workflow"]["graph_format"],
                         "ui")
        self.assertIn("unresolved_group_uuid",
                      by_name["mm_upscale_video_workflow"][
                          "node_classes_by_status"])
        self.assertEqual(by_name["sam3_custompkg_probe"]["graph_format"], "api")
        self.assertTrue(all(not w["gpu_inference_verified"]
                            and not w["executable_api_prompt_proven"]
                            for w in report["workflows"]))

    def test_report_omits_media_names_and_prompt_values(self):
        serialized = json.dumps(checker.audit(), sort_keys=True)
        self.assertNotIn("scail2_test_driving_video.mp4", serialized)
        self.assertNotIn("scail2_test_reference_character.jpg", serialized)
        self.assertNotIn(".safetensors", serialized)
        self.assertNotIn("custom_width", serialized)


if __name__ == "__main__":
    unittest.main()
