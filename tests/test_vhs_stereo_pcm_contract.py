"""Fail-closed contracts for the disposable stereo ProRes PCM16 mux."""
from __future__ import annotations

from array import array
import importlib.util
import math
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts" / "qualify_vhs_stereo_pcm_mux.py"
spec = importlib.util.spec_from_file_location("osf_stereo_pcm_gate", FILE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

TIMELINE_FILE = ROOT / "scripts" / "qualify_vhs_audio_mux.py"
timeline_spec = importlib.util.spec_from_file_location("osf_pcm_timeline_gate", TIMELINE_FILE)
timeline = importlib.util.module_from_spec(timeline_spec)
timeline_spec.loader.exec_module(timeline)


def samples(left_hz=440, right_hz=660, left_amp=0.2, right_amp=0.14,
            frames=48000):
    return array("f", (
        amplitude * math.sin(2 * math.pi * freq * i / 48000)
        for i in range(frames)
        for freq, amplitude in ((left_hz, left_amp), (right_hz, right_amp))
    ))


class StereoMuxContractTests(unittest.TestCase):
    def test_graph_uses_only_synthetic_two_channel_audio(self):
        graph = gate.build_stereo_mux_graph()
        self.assertEqual(set(graph), {"1", "2", "3"})
        self.assertEqual(graph["2"]["class_type"], "OSFTestStereoAudio")
        self.assertEqual(graph["3"]["inputs"]["audio"], ["2", 0])
        self.assertEqual(graph["3"]["inputs"]["images"], ["1", 0])
        self.assertEqual(graph["3"]["inputs"]["format"], "video/ProRes")
        self.assertEqual(graph["3"]["inputs"]["profile"], "4444")
        self.assertFalse(graph["3"]["inputs"]["save_output"])
        self.assertEqual(graph["1"]["inputs"]["batch_size"], 2)
        self.assertEqual(graph["1"]["inputs"]["color"], 0)

    def test_stereo_history_rejects_unsafe_media_and_wrong_codec(self):
        asset = {
            "filename": "osf_synthetic_stereo_mux_00001-audio.mov",
            "subfolder": "", "type": "temp", "format": "video/ProRes",
        }
        record = {
            "status": {"completed": True, "status_str": "success"},
            "outputs": {"3": {"gifs": [asset]}},
        }
        self.assertEqual(gate.validate_stereo_history(record)["filename"],
                         asset["filename"])
        for bad in (
            {**asset, "filename": "../outside.mov"},
            {**asset, "filename": "/tmp/foo.mov"},
            {**asset, "filename": "osf_synthetic_pcm_mux_00001-audio.mov"},
            {**asset, "filename": "osf_synthetic_stereo_mux_00001.mov"},
            {**asset, "subfolder": "../../outside"},
            {**asset, "type": "output"},
            {**asset, "format": "video/h265-mp4"},
        ):
            with self.subTest(bad=bad):
                record["outputs"]["3"]["gifs"] = [bad]
                with self.assertRaisesRegex(ValueError, "Unsafe or non-stereo"):
                    gate.validate_stereo_history(record)
        record["outputs"]["3"]["gifs"] = []
        with self.assertRaisesRegex(ValueError, "exactly one"):
            gate.validate_stereo_history(record)

    def test_stereo_source_waveforms_match_distinct_channel_specs(self):
        decoded = gate.check_decoded_stereo_pcm(samples())
        self.assertEqual(decoded["sample_rate_hz"], 48000)
        self.assertEqual(decoded["channels"], 2)
        self.assertEqual(decoded["channel_frequencies_hz"], [440, 660])
        self.assertEqual(decoded["decoded_sample_frames"], 48000)
        self.assertEqual(decoded["checked_sample_frames"], 48000)
        self.assertLess(decoded["maximum_channel_errors"][0], 0.00001)
        self.assertLess(decoded["maximum_channel_errors"][1], 0.00001)
        self.assertFalse(decoded["binary_media_uploaded"])

    def test_rejects_swapped_channels_duplicate_mono_and_leakage(self):
        for bad in (
            samples(660, 440, 0.14, 0.2),  # swapped L/R
            samples(440, 440, 0.2, 0.2),   # mono duplicated
            samples(440, 660, 0.2, 0.20),  # right excessive amplitude
            samples(440, 665, 0.2, 0.14),  # wrong right frequency
            samples(445, 660, 0.2, 0.14),  # wrong left frequency
            samples(440, 660, 0.2, 0.14, frames=1000),
        ):
            with self.subTest(length=len(bad)):
                with self.assertRaises(ValueError):
                    gate.check_decoded_stereo_pcm(bad)

    def test_rejects_one_large_error_even_outside_sparse_checkpoints(self):
        source = samples()
        source[2 * 30007 + 1] += 0.02
        with self.assertRaisesRegex(ValueError, "identity, phase or leakage"):
            gate.check_decoded_stereo_pcm(source)
        with self.assertRaisesRegex(ValueError, "odd interleaved"):
            gate.check_decoded_stereo_pcm(samples()[:-1])
        source = samples()
        source[2 * 22222] = float("nan")
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            gate.check_decoded_stereo_pcm(source)

    def test_rejects_tail_corruption_on_both_channels(self):
        for channel in (0, 1):
            for position in (46976, 47998, 47999):
                with self.subTest(channel=channel, position=position):
                    payload = samples()
                    payload[2 * position + channel] += 0.02
                    with self.assertRaisesRegex(
                        ValueError, "identity, phase or leakage"
                    ):
                        gate.check_decoded_stereo_pcm(payload)

    def test_rejects_any_stereo_audio_padding_or_truncation(self):
        original = samples()
        for invalid in (
            original[:-2],
            original + array("f", [0.0, 0.0]),
            original + array("f", [0.0, 0.0] * 1024),
            original + array("f", [0.0, 0.0] * 4096),
        ):
            with self.subTest(actual_frames=len(invalid) // 2):
                with self.assertRaisesRegex(ValueError, "exactly 48000"):
                    gate.check_decoded_stereo_pcm(invalid)

    @staticmethod
    def _synthetic_stereo_presentation_trace(*, audio_offset=0,
                                             video_second_shift=0.0,
                                             audio_gap_after=None,
                                             truncate_samples=0,
                                             channels=2, layout="stereo"):
        lines = []
        for index in range(2):
            seconds = index * 0.5
            if index == 1:
                seconds += video_second_shift
            lines.append(
                f"[Parsed_showinfo_0 @ 0x01] n: {index:3} pts: {index * 8192} "
                f"pts_time:{seconds:g} duration:8192 duration_time:0.5 "
                "fmt:yuv444p12le"
            )
        consumed = 0
        remaining = 48000 - truncate_samples
        index = 0
        while remaining > 0:
            count = min(1024, remaining)
            pts = consumed + audio_offset
            if audio_gap_after is not None and index > audio_gap_after:
                pts += 1024
            lines.append(
                f"[Parsed_ashowinfo_0 @ 0x02] n:{index} pts:{pts} "
                f"pts_time:{pts / 48000:.7f} fmt:s16 channels:{channels} "
                f"chlayout:{layout} rate:48000 nb_samples:{count}"
            )
            consumed += count
            remaining -= count
            index += 1
        return "\\n".join(lines)

    def test_stereo_timestamps_verify_each_packet_and_av_endpoints(self):
        output = timeline.verify_synthetic_mux_timestamps(
            self._synthetic_stereo_presentation_trace(), expected_channels=2,
        )
        self.assertEqual(output["audio_channels"], 2)
        self.assertEqual(output["audio_layout"], "stereo")
        self.assertEqual(output["video_presentation_seconds"], [0.0, 0.5])
        self.assertEqual(output["audio_packets_inspected"], 47)
        self.assertEqual(output["audio_samples_covered"], 48000)
        self.assertEqual(output["audio_first_sample_pts"], 0)
        self.assertEqual(output["audio_stream_end_seconds"], 1.0)
        self.assertEqual(output["video_stream_end_seconds"], 1.0)
        self.assertLessEqual(output["maximum_audio_clock_error_seconds"], 0.001)
        self.assertFalse(output["binary_media_uploaded"])

    def test_stereo_timestamps_reject_wrong_layout_or_continuity(self):
        invalid = (
            ({"audio_offset": 1024}, "Audio PCM timestamps"),
            ({"audio_gap_after": 15}, "Audio PCM timestamps"),
            ({"video_second_shift": 0.04}, "Video timestamps"),
            ({"truncate_samples": 1}, "Audio timestamp coverage"),
            ({"channels": 1, "layout": "mono"}, "Audio PCM timestamps"),
            ({"channels": 2, "layout": "mono"}, "Audio PCM timestamps"),
        )
        for params, expected in invalid:
            with self.subTest(params=params):
                with self.assertRaisesRegex(ValueError, expected):
                    timeline.verify_synthetic_mux_timestamps(
                        self._synthetic_stereo_presentation_trace(**params),
                        expected_channels=2,
                    )
        with self.assertRaisesRegex(ValueError, "Audio PCM timestamps"):
            timeline.verify_synthetic_mux_timestamps(
                self._synthetic_stereo_presentation_trace(), expected_channels=1,
            )
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            timeline.verify_synthetic_mux_timestamps(
                self._synthetic_stereo_presentation_trace(), expected_channels=3,
            )

    def test_stereo_runtime_uses_actual_mov_timestamp_extraction(self):
        source = (ROOT / "scripts" / "qualify_vhs_stereo_pcm_mux.py").read_text()
        self.assertIn("extract_actual_mux_timestamps(", source)
        self.assertIn("expected_channels=2", source)
        self.assertIn('"av_presentation_timeline": timeline', source)

    def test_fixture_contains_no_media_loaders_and_is_test_only(self):
        text = (ROOT / "tests" / "fixtures" / "comfy_synthetic_audio" /
                "__init__.py").read_text(encoding="utf-8")
        self.assertIn('"OSFTestStereoAudio": OSFTestStereoAudio', text)
        self.assertIn('torch.stack((left, right), dim=0).unsqueeze(0)', text)
        self.assertIn("660", text)
        self.assertIn("440", text)
        self.assertNotIn("torchaudio.load", text)
        self.assertNotIn("model.load", text)
        runtime = (ROOT / "scripts" / "qualify_clean_comfy_cpu.py").read_text()
        self.assertIn("execute_synthetic_vhs_stereo_mux", runtime)
        self.assertIn('"synthetic_vhs_stereo_pcm_mux"', runtime)


if __name__ == "__main__":
    unittest.main()
