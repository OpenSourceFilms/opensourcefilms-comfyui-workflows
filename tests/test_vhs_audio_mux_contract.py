"""Offline contract for live VHS ProRes PCM mux of synthetic audio."""
from __future__ import annotations

from array import array
import importlib.util
import math
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts" / "qualify_vhs_audio_mux.py"
spec = importlib.util.spec_from_file_location("osf_pcm_audio_gate", FILE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class PcmMuxContractTests(unittest.TestCase):
    def test_graph_routes_generated_audio_and_two_black_frames_to_prores(self):
        graph = gate.build_synthetic_audio_mux_graph()
        self.assertEqual(set(graph), {"1", "2", "3"})
        self.assertEqual(graph["2"]["class_type"], "OSFTestSineAudio")
        self.assertEqual(graph["1"]["inputs"]["batch_size"], 2)
        self.assertEqual(graph["1"]["inputs"]["color"], 0)
        self.assertEqual(graph["3"]["inputs"]["audio"], ["2", 0])
        self.assertEqual(graph["3"]["inputs"]["images"], ["1", 0])
        self.assertEqual(graph["3"]["inputs"]["format"], "video/ProRes")
        self.assertEqual(graph["3"]["inputs"]["profile"], "4444")
        self.assertFalse(graph["3"]["inputs"]["save_output"])

    def test_history_rejects_audio_missing_or_unsafe_path(self):
        asset = {
            "filename": "osf_synthetic_pcm_mux_00001-audio.mov",
            "subfolder": "", "type": "temp", "format": "video/ProRes",
        }
        record = {
            "status": {"completed": True, "status_str": "success"},
            "outputs": {"3": {"gifs": [asset]}},
        }
        self.assertEqual(
            gate.validate_mux_history(record)["filename"], asset["filename"]
        )
        invalid = [
            {**asset, "filename": "../bad-audio.mov"},
            {**asset, "filename": "osf_synthetic_pcm_mux_00001.mov"},
            {**asset, "filename": "osf_synthetic_pcm_mux_00001-audio.mp4"},
            {**asset, "subfolder": "../"},
            {**asset, "type": "output"},
            {**asset, "format": "video/h264-mp4"},
        ]
        for bad in invalid:
            with self.subTest(bad=bad):
                record["outputs"]["3"]["gifs"] = [bad]
                with self.assertRaisesRegex(ValueError, "Unsafe or non-audio"):
                    gate.validate_mux_history(record)
        record["outputs"]["3"]["gifs"] = []
        with self.assertRaisesRegex(ValueError, "exactly one"):
            gate.validate_mux_history(record)

    def test_pcm_samples_require_440hz_with_correct_amplitude(self):
        source = array("f", (
            0.2 * math.sin(2 * math.pi * 440 * i / 48000)
            for i in range(48000)
        ))
        result = gate.check_decoded_mono_pcm(source)
        self.assertEqual(result["sample_rate_hz"], 48000)
        self.assertEqual(result["channels"], 1)
        self.assertEqual(result["samples_decoded"], 48000)
        self.assertEqual(result["samples_compared"], 48000)
        self.assertTrue(result["full_waveform_validated"])
        self.assertLess(result["maximum_full_waveform_sample_error"], 0.0001)
        self.assertFalse(result.get("binary_media_uploaded", False))

    def test_pcm_rejects_empty_silent_wrong_frequency_or_amplitude(self):
        good = array("f", (
            0.2 * math.sin(2 * math.pi * 440 * i / 48000)
            for i in range(48000)
        ))
        for bad in (
            array("f"),
            array("f", [0.0] * 48000),
            array("f", (
                0.2 * math.sin(2 * math.pi * 450 * i / 48000)
                for i in range(48000)
            )),
            array("f", (min(0.9, x * 2) for x in good)),
        ):
            with self.subTest(length=len(bad)):
                with self.assertRaises(ValueError):
                    gate.check_decoded_mono_pcm(bad)

    def test_all_sample_validation_rejects_uncharted_tail_silence(self):
        original = array("f", (
            0.2 * math.sin(2 * math.pi * 440 * i / 48000)
            for i in range(48000)
        ))
        # The former 16-point checkpoint gate ended at index 44000 and
        # would have accepted corruption in this entire final segment.
        corrupted = array("f", original)
        for i in range(45000, 48000):
            corrupted[i] = 0.0
        self.assertEqual(gate.check_decoded_mono_pcm(original)["samples_compared"],
                         48000)
        with self.assertRaisesRegex(ValueError, "full-waveform"):
            gate.check_decoded_mono_pcm(corrupted)

    def test_all_sample_validation_rejects_single_off_grid_error(self):
        original = array("f", (
            0.2 * math.sin(2 * math.pi * 440 * i / 48000)
            for i in range(48000)
        ))
        corrupted = array("f", original)
        corrupted[45001] += 0.01
        with self.assertRaisesRegex(ValueError, "full-waveform"):
            gate.check_decoded_mono_pcm(corrupted)
        corrupted = array("f", original)
        corrupted[25001] -= 0.005
        with self.assertRaisesRegex(ValueError, "full-waveform"):
            gate.check_decoded_mono_pcm(corrupted)

    def test_audio_mux_fails_closed_on_padding_and_truncation(self):
        original = array("f", (
            0.2 * math.sin(2 * math.pi * 440 * i / 48000)
            for i in range(48000)
        ))
        for bad in (original[:-1], original + array("f", [0.0]),
                    original + array("f", [0.0] * 1000)):
            with self.subTest(count=len(bad)):
                with self.assertRaisesRegex(ValueError, "exact one-second"):
                    gate.check_decoded_mono_pcm(bad)

    def test_no_production_fixture_or_weights_in_accepted_graph(self):
        graph = gate.build_synthetic_audio_mux_graph()
        self.assertEqual(
            {node["class_type"] for node in graph.values()},
            {"EmptyImage", "OSFTestSineAudio", "VHS_VideoCombine"},
        )
        fixture = ROOT / "tests" / "fixtures" / "comfy_synthetic_audio" / "__init__.py"
        source = fixture.read_text(encoding="utf-8")
        self.assertIn('"OSFTestSineAudio": OSFTestSineAudio', source)
        self.assertIn("48000", source)
        self.assertNotIn("torchaudio.load", source)
        self.assertNotIn("model.load", source)


if __name__ == "__main__":
    unittest.main()
