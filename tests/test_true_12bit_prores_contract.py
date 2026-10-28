"""Offline contract for the independent genuine 12-bit ProRes source gate."""
from __future__ import annotations

from array import array
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "scripts" / "qualify_prores_12bit.py"
spec = importlib.util.spec_from_file_location("osf_true12bit", SOURCE_PATH)
true12 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(true12)


class True12BitSourceContractTests(unittest.TestCase):
    def test_source_is_real_12bit_planar_and_has_sub_8bit_variation(self):
        raw = true12.make_genuine_12bit_yuv444p_source()
        self.assertEqual(len(raw), 64 * 64 * 3 * 2 * 2)
        samples = true12._samples_from_bytes(raw)
        self.assertEqual(len(samples), 24576)
        self.assertEqual([samples[0], samples[33],
                          samples[33 * 64], samples[33 * 64 + 33]],
                         [2038, 2043, 2048, 2053])
        self.assertEqual([samples[12288], samples[12288 + 33]],
                         [2070, 2075])
        self.assertEqual(samples[0] >> 4, samples[33] >> 4)
        self.assertNotEqual(samples[0], samples[33])
        self.assertEqual(raw, true12.make_genuine_12bit_yuv444p_source())

    def test_identical_roundtrip_passes_with_four_sub_8bit_distinctions(self):
        raw = true12.make_genuine_12bit_yuv444p_source()
        result = true12.validate_genuine_12bit_roundtrip(raw, raw)
        self.assertEqual(result["status"], "real_12bit_yuv444p_roundtrip_verified")
        self.assertEqual(result["source_precision_bits"], 12)
        self.assertEqual(result["component_sample_count"], 24576)
        self.assertEqual(result["sub_8bit_luma_distinctions_preserved"], 4)
        self.assertEqual(result["sub_8bit_chroma_distinctions_preserved"], 15)
        self.assertEqual(result["sub_8bit_chroma_distinctions_by_plane"],
                         {"Cb": 9, "Cr": 6})
        self.assertEqual(result["maximum_observed_error_12bit"], 0)
        self.assertFalse(result["vhs_node_12bit_input_qualified"])
        self.assertFalse(result["video_binary_uploaded"])

    def test_bounded_channel_deviation_can_pass_without_exact_roundtrip(self):
        raw = true12.make_genuine_12bit_yuv444p_source()
        samples = true12._samples_from_bytes(raw)
        samples[100] += 3
        samples[12288 + 300] -= 2
        decoded = true12._bytes_from_samples(samples)
        result = true12.validate_genuine_12bit_roundtrip(raw, decoded)
        self.assertEqual(result["maximum_observed_error_by_frame_12bit"], [3, 2])

    def test_chroma_fine_detail_collapse_fails_even_within_error_tolerance(self):
        raw = true12.make_genuine_12bit_yuv444p_source()
        decoded = true12._samples_from_bytes(raw)
        # Frame zero Cb, top-right tile: source 2053, top-left 2048.
        # Replacing one 2053 sample with 2048 incurs only 5/4095 error,
        # below the global 8/4095 threshold, but loses real chroma detail.
        a = 64 * 64 + 0
        b = 64 * 64 + 33
        self.assertEqual(decoded[a], 2048)
        self.assertEqual(decoded[b], 2053)
        decoded[b] = decoded[a]
        with self.assertRaisesRegex(ValueError, "sub-8-bit chroma distinction"):
            true12.validate_genuine_12bit_roundtrip(
                raw, true12._bytes_from_samples(decoded),
            )

    def test_rejects_8bit_quantization_even_at_similar_mean_values(self):
        raw = true12.make_genuine_12bit_yuv444p_source()
        samples = true12._samples_from_bytes(raw)
        quantized = array("H", ((value >> 4) << 4 for value in samples))
        with self.assertRaisesRegex(ValueError, "12-bit ProRes"):
            true12.validate_genuine_12bit_roundtrip(
                raw, true12._bytes_from_samples(quantized),
            )

    def test_rejects_frame_reordering_and_large_single_pixel_error(self):
        raw = true12.make_genuine_12bit_yuv444p_source()
        frame_bytes = 64 * 64 * 3 * 2
        swapped = raw[frame_bytes:] + raw[:frame_bytes]
        with self.assertRaisesRegex(ValueError, "12-bit ProRes"):
            true12.validate_genuine_12bit_roundtrip(raw, swapped)
        samples = true12._samples_from_bytes(raw)
        samples[130] += 9
        with self.assertRaisesRegex(ValueError, "exceeded channel error"):
            true12.validate_genuine_12bit_roundtrip(
                raw, true12._bytes_from_samples(samples),
            )

    def test_rejects_truncated_and_out_of_range_decoded_values(self):
        raw = true12.make_genuine_12bit_yuv444p_source()
        with self.assertRaisesRegex(ValueError, "length is incorrect"):
            true12.validate_genuine_12bit_roundtrip(raw, raw[:-2])
        samples = true12._samples_from_bytes(raw)
        samples[44] = 4096
        with self.assertRaisesRegex(ValueError, "outside 12-bit"):
            true12.validate_genuine_12bit_roundtrip(
                raw, true12._bytes_from_samples(samples),
            )

    def test_full_runtime_records_independent_test_separate_from_vhs_graph(self):
        runtime = (ROOT / "scripts" / "qualify_clean_comfy_cpu.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("qualify_genuine_12bit_ffmpeg()", runtime)
        self.assertIn('"independent_real_12bit_ffmpeg_roundtrip"', runtime)
        self.assertIn('"external_model_free_api_graph"', runtime)


if __name__ == "__main__":
    unittest.main()
