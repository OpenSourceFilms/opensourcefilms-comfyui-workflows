"""Offline contract tests for CPU-only ComfyUI runtime acceptance driver."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts" / "qualify_clean_comfy_cpu.py"
spec = importlib.util.spec_from_file_location("osf_comfy_cpu_smoke", SRC)
qualifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualifier)


class CleanRuntimeSmokeContractTests(unittest.TestCase):
    def test_requires_two_registered_comfyui_node_schemas(self):
        example = {
            "MaskPropagateFromFlow": {
                "output": ["MASK"],
                "input": {"required": {"flow": [["OPTICAL_FLOW"]]}},
            }
        }
        qualifier.ensure_loopback_object_info(example, "MaskPropagateFromFlow")
        with self.assertRaisesRegex(ValueError, "not registered"):
            qualifier.ensure_loopback_object_info(example, "MaskPropagateOpticalFlow")
        with self.assertRaisesRegex(ValueError, "unexpected API schema"):
            qualifier.ensure_loopback_object_info(
                {"MaskPropagateFromFlow": {"output": ["IMAGE"], "input": {}}},
                "MaskPropagateFromFlow",
            )

    def test_fails_fast_if_server_exits_without_registering_nodes(self):
        fake_child = mock.Mock()
        fake_child.poll.return_value = 2
        with self.assertRaisesRegex(RuntimeError, "exited"):
            qualifier._probe_server(18188, fake_child, seconds=1)

    def test_missing_osf_source_fails_without_importing_torch(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "Missing or symlinked"):
                qualifier._load_osf_classes(Path(td))

    def test_requires_pinned_comfyui_sha_and_no_existing_evidence_file(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "main.py").write_text("print('fake')", encoding="utf-8")
            (base / "custom_nodes" / "mask_propagate_optical_flow").mkdir(
                parents=True
            )
            evidence = base / "report.json"
            with mock.patch.object(qualifier.subprocess, "run") as cmd:
                cmd.return_value.stdout = "a" * 40 + "\n"
                with self.assertRaisesRegex(ValueError, "Unreviewed ComfyUI"):
                    qualifier.qualify(base, evidence, 18188)
            self.assertFalse(evidence.exists())


if __name__ == "__main__":
    unittest.main()
