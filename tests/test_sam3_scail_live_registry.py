"""Offline negative tests for pinned native SAM3/SCAIL live socket metadata."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_sam3_scail_live_registry import verify_native_live_schemas
from audit_sam3_scail_api_bindings import NATIVE, FORCE_LINK_FIELDS


def sample_registry() -> dict:
    """Mock the actual /object_info format; no ComfyUI or model required."""
    result = {}
    for class_id, spec in NATIVE.items():
        req, opt = {}, {}
        for name, typ in spec["inputs"].items():
            if typ == "COMBO":
                name_type = ["none", "left_to_right", "area"]
            elif "|" in typ:
                name_type = "SAM3_TRACK_DATA,MASK"
            else:
                name_type = typ
            key = class_id + "." + name
            extra = {"forceInput": True} if key in FORCE_LINK_FIELDS else {}
            target = req if name in spec["required"] else opt
            target[name] = [name_type, extra]
        result[class_id] = {
            "input": {"required": req, "optional": opt},
            "output": list(spec["outputs"]),
        }
    return result


class NativeLiveSchemaTests(unittest.TestCase):
    def test_five_native_classes_have_real_schemas_and_no_inference_claim(self):
        result = verify_native_live_schemas(sample_registry())
        self.assertEqual(result["classes_checked"], 5)
        self.assertEqual(result["force_input_sockets_checked"], 3)
        self.assertEqual(result["multitype_storage_serialization_unverified"], 1)
        self.assertGreater(result["source_defined_fields_checked"], 30)
        self.assertGreater(result["output_slots_checked"], 5)
        self.assertFalse(result["gpu_inference_tested"])
        self.assertFalse(result["three_real_api_graphs_executed"])
        self.assertFalse(result["model_weights_loaded"])

    def test_absent_class_fails(self):
        info = sample_registry()
        del info["SAM3_Detect"]
        with self.assertRaisesRegex(ValueError, "Missing native class"):
            verify_native_live_schemas(info)

    def test_missing_required_or_optional_source_socket_fails(self):
        info = sample_registry()
        del info["SAM3_VideoTrack"]["input"]["required"]["model"]
        with self.assertRaisesRegex(ValueError, "Missing required"):
            verify_native_live_schemas(info)
        info = sample_registry()
        del info["WanSCAILToVideo"]["input"]["optional"]["pose_video_mask"]
        with self.assertRaisesRegex(ValueError, "Missing source-defined"):
            verify_native_live_schemas(info)

    def test_wrong_scalar_output_and_enum_types_fail(self):
        for modify, error in (
            (lambda x: x["SAM3_Detect"]["input"]["required"]["model"].__setitem__(0, "IMAGE"),
             "socket type mismatch"),
            (lambda x: x["WanSCAILToVideo"]["output"].__setitem__(2, "IMAGE"),
             "output types/slots differ"),
            (lambda x: x["SCAIL2ColoredMask"]["input"]["optional"]["sort_by"].__setitem__(0, ["none", "unexpected"]),
             "enum options mismatch"),
        ):
            with self.subTest(error=error):
                info = sample_registry()
                modify(info)
                with self.assertRaisesRegex(ValueError, error):
                    verify_native_live_schemas(info)

    def test_modern_comfy_io_combo_metadata_is_supported_but_not_weakened(self):
        info = sample_registry()
        info["SCAIL2ColoredMask"]["input"]["optional"]["sort_by"] = [
            "COMBO", {"options": ["none", "left_to_right", "area"]}
        ]
        result = verify_native_live_schemas(info)
        self.assertEqual(result["classes_checked"], 5)
        info["SCAIL2ColoredMask"]["input"]["optional"]["sort_by"][1]["options"] = [
            "none", "invalid"
        ]
        with self.assertRaisesRegex(ValueError, "enum options mismatch"):
            verify_native_live_schemas(info)

    def test_force_input_metadata_must_be_active(self):
        for name in ("bboxes", "positive_coords", "negative_coords"):
            with self.subTest(name=name):
                info = sample_registry()
                info["SAM3_Detect"]["input"]["optional"][name][1] = {}
                with self.assertRaisesRegex(ValueError, "Missing native force_input"):
                    verify_native_live_schemas(info)

    def test_malformed_registry_socket_and_duplicate_rejected(self):
        for invalid in ({}, [], None):
            with self.subTest(value=invalid):
                with self.assertRaises(ValueError):
                    verify_native_live_schemas(invalid)
        info = sample_registry()
        info["SAM3_TrackPreview"]["input"]["optional"]["images"] = None
        with self.assertRaisesRegex(ValueError, "Malformed native live input"):
            verify_native_live_schemas(info)
        info = sample_registry()
        info["SAM3_TrackPreview"]["input"]["required"]["images"] = ["IMAGE", {}]
        with self.assertRaisesRegex(ValueError, "Duplicate native live input"):
            verify_native_live_schemas(info)

    def test_additional_live_fields_are_reported_not_mislabelled_as_reviewed(self):
        info = sample_registry()
        info["WanSCAILToVideo"]["input"]["optional"]["future_unreviewed"] = ["STRING", {}]
        result = verify_native_live_schemas(info)
        self.assertEqual(result["additional_unreviewed_runtime_input_fields"], 1)

    def test_static_contract_is_not_weakened_by_dynamic_registry(self):
        text = (ROOT / "scripts" / "qualify_clean_comfy_cpu.py").read_text()
        self.assertIn('"pinned_native_sam3_scail_live_socket_schema"', text)
        self.assertIn("verify_native_live_schemas(json.loads(payload))", text)


if __name__ == "__main__":
    unittest.main()
