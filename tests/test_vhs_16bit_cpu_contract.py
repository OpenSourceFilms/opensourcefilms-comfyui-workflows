"""Offline contract for CI-only explicit 16-bit VHS ProRes path."""
from __future__ import annotations

from array import array
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
src = ROOT / "scripts" / "qualify_vhs_16bit_cpu.py"
spec = importlib.util.spec_from_file_location("osf_vhs_prec", src)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def pack(samples):
    x = array("H", samples)
    if sys.byteorder != "little":
        x.byteswap()
    return x.tobytes()


def synthetic_rgb48(*, quantize_8bit=False, swap=False):
    levels = probe.INPUT_LEVELS_12BIT[::-1] if swap else probe.INPUT_LEVELS_12BIT
    samples = []
    for pair in levels:
        for y in range(64):
            for x in range(64):
                level = pair[0] if x < 32 else pair[1]
                if quantize_8bit:
                    byte = int(level / 4095.0 * 255 + .5)
                    val = byte * 257
                else:
                    val = int(level / 4095.0 * 65535.0 + .5)
                samples.extend((val,) * 3)
    return pack(samples)


class VHSExplicit16BitPrecisionContract(unittest.TestCase):
    def test_graph_requires_only_ci_fixture_and_pinned_vhs(self):
        graph = probe.make_ci_only_precision_graph()
        self.assertEqual(set(graph), {"201", "202"})
        self.assertEqual(graph["201"]["class_type"], "OSF_CI_Precision12BitSource")
        self.assertEqual(graph["202"]["class_type"], "VHS_VideoCombine")
        self.assertEqual(graph["202"]["inputs"]["format"], probe.FORMAT_NAME)
        self.assertEqual(graph["202"]["inputs"]["images"], ["201", 0])
        self.assertFalse(graph["202"]["inputs"]["save_output"])

    def test_explicit_ci_preset_selects_16bit_upstream_branch(self):
        import json
        config = json.loads((ROOT / "tests" / "fixtures" /
                             "osf-prores4444-rgb48-16bit.json").read_text())
        self.assertEqual(config["input_color_depth"], "16bit")
        self.assertEqual(config["main_pass"][config["main_pass"].index("-profile:v") + 1], "4")
        self.assertIn("yuv444p12le", config["main_pass"])
        fixture = (ROOT / "tests" / "fixtures" /
                   "osf_ci_precision_probe" / "__init__.py").read_text()
        self.assertIn("2038, 2043", fixture)
        self.assertIn("2048, 2053", fixture)
        self.assertIn("4095.0", fixture)

    def test_all_full_frame_precision_values_match(self):
        value = probe.validate_vhs_16bit_rgb_roundtrip(synthetic_rgb48())
        self.assertEqual(value["status"], "vhs_explicit_16bit_input_prores4444_roundtrip_verified")
        self.assertEqual(value["max_error_rgb16_by_frame"], [0, 0])
        self.assertEqual(value["sub_8bit_frame_distinctions_preserved"], 2)
        self.assertTrue(value["fixture_only_not_production_default"])
        self.assertFalse(value["binary_outputs_uploaded"])

    def test_a_default_8bit_precision_collapse_must_fail(self):
        with self.assertRaisesRegex(ValueError, "sub-8-bit component distinction"):
            probe.validate_vhs_16bit_rgb_roundtrip(
                synthetic_rgb48(quantize_8bit=True))

    def test_swapped_or_truncated_source_frames_rejected(self):
        with self.assertRaisesRegex(ValueError, "exceeded error limit"):
            probe.validate_vhs_16bit_rgb_roundtrip(synthetic_rgb48(swap=True))
        with self.assertRaisesRegex(ValueError, "frame count/dimensions"):
            probe.validate_vhs_16bit_rgb_roundtrip(synthetic_rgb48()[:-2])

    def test_one_erroneous_pixel_is_rejected(self):
        x = array("H")
        x.frombytes(synthetic_rgb48())
        if sys.byteorder != "little":
            x.byteswap()
        x[500] = min(65535, x[500] + 257)
        with self.assertRaisesRegex(ValueError, "exceeded error limit"):
            probe.validate_vhs_16bit_rgb_roundtrip(pack(x))

    def test_driver_keeps_existing_default_8bit_negative_evidence(self):
        text = (ROOT / "scripts" / "qualify_clean_comfy_cpu.py").read_text()
        self.assertIn('"pinned_vhs_prores_input_precision"', text)
        self.assertIn('"ci_only_vhs_explicit16bit_source"', text)
        self.assertIn("audit_pinned_vhs_prores_precision", text)


if __name__ == "__main__":
    unittest.main()
