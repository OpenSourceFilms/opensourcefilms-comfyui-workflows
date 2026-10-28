"""Source-only regressions for the pinned VHS ProRes 8-bit input limitation."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
source_path = ROOT / "scripts" / "audit_vhs_prores_precision.py"
spec = importlib.util.spec_from_file_location("vhs_precision_gate", source_path)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

VALID_SOURCE = '''
def tensor_to_int(tensor, bits):
    return tensor
def tensor_to_shorts(tensor):
    return tensor_to_int(tensor, 16)
def tensor_to_bytes(tensor):
    return tensor_to_int(tensor, 8)

class VideoCombine:
    def combine_video(self, video_format, images, has_alpha):
        if video_format.get('input_color_depth', '8bit') == '16bit':
            images = map(tensor_to_shorts, images)
            if has_alpha:
                i_pix_fmt = 'rgba64'
            else:
                i_pix_fmt = 'rgb48'
        else:
            images = map(tensor_to_bytes, images)
            if has_alpha:
                i_pix_fmt = 'rgba'
            else:
                i_pix_fmt = 'rgb24'
'''
VALID_CONFIG = {
    "extension": "mov",
    "main_pass": ["-n", "-c:v", "prores_ks", "-profile:v", "4"],
}


class VhsProResPrecisionContractTests(unittest.TestCase):
    def test_known_default_is_explicitly_not_12bit_vhs_acceptance(self):
        report = audit.inspect_pinned_vhs_prores_source(
            VALID_SOURCE, VALID_CONFIG
        )
        self.assertEqual(report["format_default_input_color_depth"], "8bit")
        self.assertEqual(report["default_ffmpeg_raw_input_pixel_format"], "rgb24")
        self.assertEqual(report["default_source_tensor_conversion"], "tensor_to_bytes")
        self.assertFalse(report["vhs_real_12bit_source_roundtrip_qualified"])

    def test_changed_precision_default_fails_closed(self):
        source = VALID_SOURCE.replace(
            "get('input_color_depth', '8bit')",
            "get('input_color_depth', '16bit')",
        )
        with self.assertRaisesRegex(ValueError, "not reviewed 8bit"):
            audit.inspect_pinned_vhs_prores_source(source, VALID_CONFIG)

    def test_missing_8bit_map_and_rgb24_fails_closed(self):
        for source in (
            VALID_SOURCE.replace("map(tensor_to_bytes, images)",
                                 "map(tensor_to_shorts, images)"),
            VALID_SOURCE.replace("i_pix_fmt = 'rgb24'",
                                 "i_pix_fmt = 'rgb48'"),
            VALID_SOURCE.replace("map(tensor_to_shorts, images)",
                                 "map(tensor_to_bytes, images)"),
        ):
            with self.subTest(source=source[-90:]):
                with self.assertRaisesRegex(ValueError, "branches do not match"):
                    audit.inspect_pinned_vhs_prores_source(source, VALID_CONFIG)

    def test_source_package_and_codec_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "not uniquely present"):
            audit.inspect_pinned_vhs_prores_source(
                VALID_SOURCE.replace("class VideoCombine", "class VideoOther"),
                VALID_CONFIG,
            )
        for config in (
            {**VALID_CONFIG, "input_color_depth": "16bit"},
            {**VALID_CONFIG, "extension": "mp4"},
            {**VALID_CONFIG, "main_pass": ["-c:v", "libx264"]},
        ):
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    audit.inspect_pinned_vhs_prores_source(
                        VALID_SOURCE, config,
                    )

    def test_actual_runtime_writes_separate_precision_blocker_evidence(self):
        runner = (ROOT / "scripts" / "qualify_clean_comfy_cpu.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("audit_pinned_vhs_prores_precision(", runner)
        self.assertIn('"pinned_vhs_prores_input_precision"', runner)
        self.assertIn('"independent_real_12bit_ffmpeg_roundtrip"', runner)

    def test_documented_vhs_precision_boundary_includes_accepted_opt_in_ab(self):
        audit_doc = (
            ROOT / "docs" / "vhs-prores-input-precision.md"
        ).read_text(encoding="utf-8")
        ab_doc = (
            ROOT / "docs" / "vhs-prores-16bit-qualification.md"
        ).read_text(encoding="utf-8")
        self.assertIn("input_color_depth", audit_doc)
        self.assertIn("PR #37", audit_doc)
        self.assertIn("All **four** tested pairs remained distinct", audit_doc)
        self.assertIn("upstream ProRes preset remains 8-bit", audit_doc)
        self.assertIn("does not establish", audit_doc)
        self.assertIn("input_color_depth=16bit", ab_doc)
        self.assertIn("not** a calibrated 12-bit RGB", ab_doc)




if __name__ == "__main__":
    unittest.main()
