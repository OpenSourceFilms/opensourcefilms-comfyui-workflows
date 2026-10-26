"""Offline acceptance checks for the intentionally bounded RunPod profile."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "runpod" / "commercial-compatible" / "prepare.py"
SPEC = importlib.util.spec_from_file_location("commercial_profile", SCRIPT)
profile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profile)


class CommercialRunpodProfileTests(unittest.TestCase):
    def test_selection_is_explicitly_eleven_and_does_not_copy_restricted(self):
        files, metadata = profile.plan()
        graphs = sorted(p for p in files if p.endswith(".json"))
        # The generated manifest itself is not in this dict.
        self.assertEqual(len(graphs), 11)
        self.assertEqual(metadata["workflow_count"], 11)
        self.assertEqual({Path(p).stem for p in graphs}, profile.ALLOWED)
        self.assertTrue(all("/commercial-compatible/" in p for p in graphs))
        self.assertFalse(any("/research-only/" in p for p in files))
        self.assertTrue(all(p[:-5] + ".md" in files for p in graphs))
        self.assertNotIn("custom_nodes", " ".join(files))
        self.assertNotIn("safetensors", " ".join(files))

    def test_stage_and_verify_and_refuse_repeat(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "profile"
            files, info = profile.plan()
            profile.stage(target, files, info)
            result = profile.verify(target)
            self.assertEqual(result["workflow_count"], 11)
            self.assertEqual(len(result["files_sha256"]), 25)  # 22 graphs/sidecars, 3 docs
            self.assertFalse(any(p.parts and p.parts[0] == "research-only"
                                 for p in target.rglob("*.json")))
            with self.assertRaises(ValueError):
                profile.stage(target, files, info)
            graph = next((target / "workflows" / "commercial-compatible").glob("*.json"))
            graph.write_bytes(graph.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "Tampered"):
                profile.verify(target)

    def test_reject_symlinked_source_and_manifest_drift(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "input.json"
            source.write_text("{}")
            alias = Path(td) / "alias.json"
            alias.symlink_to(source)
            with self.assertRaisesRegex(ValueError, "symlinked"):
                profile.regular_file(alias)
            manifest = (ROOT / "DEPENDENCIES.lock").read_text(encoding="utf-8")
            # Explicit allowlist must reject a newly labelled commercial graph.
            mutated = manifest.replace(
                "workflows/research-only/frame_interpolation_test.json:\n  osf_license: MIT\n  commercial_status: research-only",
                "workflows/research-only/frame_interpolation_test.json:\n  osf_license: MIT\n  commercial_status: commercial-compatible",
            )
            self.assertNotEqual(mutated, manifest)
            altered = Path(td) / "DEPENDENCIES.lock"
            altered.write_text(mutated)
            with mock.patch.object(profile, "MANIFEST", altered):
                with self.assertRaisesRegex(ValueError, "explicitly approved"):
                    profile.plan()

    def test_default_cli_mode_is_read_only(self):
        run = subprocess.run(
            [sys.executable, "-B", str(SCRIPT)],
            cwd=ROOT, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("CHECK PASS: 11 explicitly approved", run.stdout)
        self.assertIn("No ComfyUI install", run.stdout)

    def test_symlinked_bundle_file_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "profile"
            files, info = profile.plan()
            profile.stage(path, files, info)
            original = path / "LICENSE"
            original.unlink()
            original.symlink_to(ROOT / "LICENSE")
            with self.assertRaisesRegex(ValueError, "symlinked"):
                profile.verify(path)


if __name__ == "__main__":
    unittest.main()
