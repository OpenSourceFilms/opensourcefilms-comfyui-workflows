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

    def test_live_registry_delta_requires_actual_pinned_schemas_and_retains_holds(self):
        source = checker.audit()
        required = source["cpu_registration_contract_classes"]
        object_info = {
            key: {"input": {}, "output": []} for key in required
        }
        # Actual vanilla core schemas are allowed but never mean full
        # model execution or UI-to-API conversion is accepted.
        object_info["SaveImage"] = {"input": {"required": {}}, "output": []}
        delta = checker.compare_live_registry(source, object_info)
        self.assertEqual(delta["schema"], "osf-selected-11-live-cpu-registry-delta-v1")
        self.assertEqual(delta["source_class_count"], 81)
        self.assertEqual(delta["workflow_count"], 11)
        self.assertEqual(delta["accepted_pinned_contract_class_count"], 6)
        self.assertIn("SaveImage", delta["registered_selected_classes"])
        self.assertEqual(
            delta["registered_selected_class_count"]
            + delta["unregistered_selected_class_count"], 81,
        )
        self.assertTrue(delta["fork_native_absent_as_expected"])
        self.assertTrue(delta["unresolved_uuid_absent_as_expected"])
        self.assertFalse(delta["all_selected_workflows_executable"])
        self.assertFalse(delta["gpu_inference_verified"])
        for w in delta["workflows"]:
            self.assertFalse(w["executable_api_prompt_proven"])
            self.assertFalse(w["gpu_inference_verified"])
            self.assertEqual(
                w["source_class_count"],
                w["registered_on_this_cpu"] + w["not_registered_on_this_cpu"],
            )
            self.assertTrue(set(w["registered_class_names"]).isdisjoint(
                w["missing_class_names"]
            ))

    def test_live_registry_delta_rejects_missing_pins_and_invalid_node_schemas(self):
        source = checker.audit()
        schema = {key: {"input": {}, "output": []}
                  for key in source["cpu_registration_contract_classes"]}
        missing = dict(schema)
        missing.pop("VHS_VideoCombine")
        with self.assertRaisesRegex(ValueError, "Accepted pinned"):
            checker.compare_live_registry(source, missing)
        invalid = dict(schema)
        invalid["VHS_VideoCombine"] = {"input": [], "output": []}
        with self.assertRaisesRegex(ValueError, "Malformed live class schema"):
            checker.compare_live_registry(source, invalid)
        with self.assertRaisesRegex(ValueError, "Invalid live"):
            checker.compare_live_registry(source, [])

    def test_live_registry_delta_rejects_fork_and_unresolved_groups_in_vanilla(self):
        source = checker.audit()
        data = {key: {"input": {}, "output": []}
                for key in source["cpu_registration_contract_classes"]}
        for name in (
            "SAM3_VideoTrack",
            source["unresolved_uuid_node_classes"][0],
        ):
            with self.subTest(name=name):
                modified = {**data, name: {"input": {}, "output": []}}
                with self.assertRaisesRegex(ValueError, "Unexpected fork/UUID"):
                    checker.compare_live_registry(source, modified)

    def test_live_registry_delta_rejects_tampered_source_counts_and_flags(self):
        source = checker.audit()
        data = {key: {"input": {}, "output": []}
                for key in source["cpu_registration_contract_classes"]}
        tampered = {**source, "unique_node_class_count": 80}
        with self.assertRaisesRegex(ValueError, "Unexpected/unreviewed"):
            checker.compare_live_registry(tampered, data)
        changed = {**source, "fork_native_required_classes": []}
        with self.assertRaisesRegex(ValueError, "fork/UUID holds lost"):
            checker.compare_live_registry(changed, data)

    def test_live_registry_wiring_is_separate_from_model_execution(self):
        source = (ROOT / "scripts/qualify_clean_comfy_cpu.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("qualify_selected_11_live_registry(port)", source)
        self.assertIn('"selected_11_live_cpu_class_registry"', source)
        self.assertIn('"/object_info"', source)
        self.assertIn('"eleven_workflows_qualified": False', source)

    def test_report_omits_media_names_and_prompt_values(self):
        serialized = json.dumps(checker.audit(), sort_keys=True)
        self.assertNotIn("scail2_test_driving_video.mp4", serialized)
        self.assertNotIn("scail2_test_reference_character.jpg", serialized)
        self.assertNotIn(".safetensors", serialized)
        self.assertNotIn("custom_width", serialized)


if __name__ == "__main__":
    unittest.main()
