"""Offline regression for the legacy ComfyUI custom-node checkout helper.

Never contacts GitHub, runs ComfyUI, installs Python packages or touches an
existing installation. Every upstream dependency is represented by a disposable
pre-existing directory in a temporary fake ComfyUI root.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install-dependencies.sh"
NODE = "mask_propagate_optical_flow"


class LegacyInstallerCopyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="osf_legacy_installer_")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.comfy = self.root / "disposable-ComfyUI"
        self.nodes = self.comfy / "custom_nodes"
        self.nodes.mkdir(parents=True)
        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir()
        # All external nodes look pre-installed, so the installer never calls
        # git clone, downloads anything or modifies a real ComfyUI tree.
        names = re.findall(
            r"(?m)^([A-Za-z0-9_.-]+)\|https://github\.com/",
            SCRIPT.read_text(encoding="utf-8"),
        )
        self.assertGreaterEqual(len(names), 16, "dependency fixture list drifted")
        for name in names:
            (self.nodes / name).mkdir(exist_ok=True)

    def fake_command(self, name):
        target = self.fake_bin / name
        target.write_text("#!/bin/sh\nexit 73\n", encoding="utf-8")
        target.chmod(0o755)

    def run_installer(self):
        env = os.environ.copy()
        env["PATH"] = str(self.fake_bin) + os.pathsep + env.get("PATH", "")
        env.pop("INSTALL_RESTRICTED", None)
        return subprocess.run(
            ["bash", str(SCRIPT), str(self.comfy)],
            capture_output=True, text=True, env=env,
            timeout=20, check=False,
        )

    def assert_no_staging(self):
        self.assertFalse(list(self.nodes.glob(".mask_propagate_optical_flow.*")))

    def test_successful_copy_is_complete_and_staged_atomically(self):
        outcome = self.run_installer()
        self.assertEqual(outcome.returncode, 0, outcome.stdout + outcome.stderr)
        self.assertTrue((self.nodes / NODE / "__init__.py").is_file())
        self.assertIn("installed mask_propagate_optical_flow", outcome.stdout)
        self.assert_no_staging()

    def test_failed_copy_is_nonzero_and_does_not_leave_partial_install(self):
        self.fake_command("cp")
        outcome = self.run_installer()
        self.assertNotEqual(outcome.returncode, 0)
        self.assertIn("FAILED to install: mask_propagate_optical_flow", outcome.stdout)
        self.assertIn("ERROR: failed to install mask_propagate_optical_flow", outcome.stderr)
        self.assertFalse((self.nodes / NODE).exists())
        self.assert_no_staging()

    def test_failed_publication_is_nonzero_and_cleans_staging(self):
        self.fake_command("mv")
        outcome = self.run_installer()
        self.assertNotEqual(outcome.returncode, 0)
        self.assertIn("FAILED to install: mask_propagate_optical_flow", outcome.stdout)
        self.assertFalse((self.nodes / NODE).exists())
        self.assert_no_staging()


if __name__ == "__main__":
    unittest.main()
