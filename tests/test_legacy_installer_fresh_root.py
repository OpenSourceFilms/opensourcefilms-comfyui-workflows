"""Fresh-directory *control-flow* checks for the broad legacy installer.

All upstream Git operations are simulated by a command shim. This exercises
the real shell script with an initially empty disposable ComfyUI directory,
but does NOT test upstream pin availability, real dependency installation,
ComfyUI node imports, GPU inference or licence clearance.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-dependencies.sh"
VENDORED = "mask_propagate_optical_flow"
RESEARCH = {"BiM-VFI", "ComfyUI-VideoMaMa"}
SHIM = r"""
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
command = args[0] if args else ""
record = {"command": command, "args": args[1:], "cwd": os.getcwd()}
with open(os.environ["OSF_FAKE_GIT_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(record, sort_keys=True) + "\n")
if command == "clone" and len(args) == 3:
    url, name = args[1:]
    dest = Path(name)
    if dest.exists() or dest.is_symlink():
        sys.exit(70)
    dest.mkdir(parents=True)
    (dest / ".git").mkdir()
    if dest.name == os.environ.get("OSF_FAKE_GIT_FAIL_CLONE"):
        (dest / "incomplete.txt").write_text("partial checkout")
        sys.exit(71)
    sys.exit(0)
if command == "checkout" and len(args) == 2:
    name = Path.cwd().name
    if not (Path.cwd() / ".git").is_dir():
        sys.exit(72)
    if name == os.environ.get("OSF_FAKE_GIT_FAIL_CHECKOUT"):
        sys.exit(73)
    (Path.cwd() / "synthetic_checked_out_ref.txt").write_text(
        args[1], encoding="utf-8"
    )
    sys.exit(0)
sys.exit(74)
"""


class FreshRootLegacyInstallerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="osf_legacy_fresh_root_")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.comfy = self.base / "new-ComfyUI"
        self.comfy.mkdir()
        self.nodes = self.comfy / "custom_nodes"
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.log = self.base / "simulated-git.jsonl"
        executable = self.bin / "git"
        executable.write_text(
            "#!" + sys.executable + "\n" + SHIM, encoding="utf-8"
        )
        executable.chmod(0o755)
        self.default_nodes = set(re.findall(
            r"([A-Za-z0-9_.-]+)\|https://github\.com/",
            INSTALLER.read_text(encoding="utf-8"),
        )) - RESEARCH
        self.assertGreaterEqual(len(self.default_nodes), 12)
        self.assertFalse(self.nodes.exists())

    def execute(self, *, restricted=False, fail_clone="", fail_checkout=""):
        env = os.environ.copy()
        env["PATH"] = str(self.bin) + os.pathsep + env.get("PATH", "")
        env["OSF_FAKE_GIT_LOG"] = str(self.log)
        env["OSF_FAKE_GIT_FAIL_CLONE"] = fail_clone
        env["OSF_FAKE_GIT_FAIL_CHECKOUT"] = fail_checkout
        env.pop("INSTALL_RESTRICTED", None)
        if restricted:
            env["INSTALL_RESTRICTED"] = "1"
        return subprocess.run(
            ["bash", str(INSTALLER), str(self.comfy)],
            env=env, capture_output=True, text=True,
            timeout=35, check=False,
        )

    def activity(self):
        if not self.log.exists():
            return []
        return [
            json.loads(line) for line in self.log.read_text(encoding="utf-8")
            .splitlines() if line
        ]

    def names(self):
        return {p.name for p in self.nodes.iterdir()}

    def assert_no_staging(self):
        self.assertFalse(list(self.nodes.glob("." + VENDORED + ".*")))

    def test_new_root_default_simulates_all_clones_and_excludes_research(self):
        output = self.execute()
        self.assertEqual(output.returncode, 0, output.stdout + output.stderr)
        self.assertEqual(self.names(), self.default_nodes | {VENDORED})
        self.assertTrue((self.nodes / VENDORED / "__init__.py").is_file())
        self.assert_no_staging()
        activity = self.activity()
        clones = [x for x in activity if x["command"] == "clone"]
        checkouts = [x for x in activity if x["command"] == "checkout"]
        self.assertEqual(len(clones), len(self.default_nodes))
        self.assertEqual(len(checkouts), len(self.default_nodes))
        self.assertEqual(
            {Path(x["args"][-1]).name for x in clones}, self.default_nodes
        )
        # The legacy installer contains mutable refs: recording successful
        # fake checkout does not make any of those commits reproducible.
        self.assertIn("main", {x["args"][0] for x in checkouts})
        self.assertFalse(self.names() & RESEARCH)

    def test_second_run_keeps_existing_dirs_and_makes_no_additional_clones(self):
        first = self.execute()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        before = self.activity()
        second = self.execute()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(self.activity(), before)
        self.assertIn("skip " + VENDORED, second.stdout)
        self.assert_no_staging()

    def test_explicit_research_opt_in_is_required(self):
        run = self.execute(restricted=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(self.names(), self.default_nodes | RESEARCH | {VENDORED})
        clones = [x for x in self.activity() if x["command"] == "clone"]
        self.assertEqual(len(clones), len(self.default_nodes | RESEARCH))

    def test_partial_failed_clone_is_removed_and_nonzero(self):
        failed = "ComfyUI-KJNodes"
        outcome = self.execute(fail_clone=failed)
        self.assertNotEqual(outcome.returncode, 0)
        self.assertIn("ERROR: failed to clone " + failed, outcome.stderr)
        self.assertFalse((self.nodes / failed).exists())
        self.assertEqual(self.names(), self.default_nodes - {failed} | {VENDORED})
        self.assertTrue((self.nodes / VENDORED / "__init__.py").is_file())
        self.assert_no_staging()

    def test_failed_checkout_cleans_wrong_default_branch(self):
        failed = "ComfyUI-GGUF"
        outcome = self.execute(fail_checkout=failed)
        self.assertNotEqual(outcome.returncode, 0)
        self.assertIn("ERROR: failed to checkout", outcome.stderr)
        self.assertFalse((self.nodes / failed).exists())
        self.assertEqual(self.names(), self.default_nodes - {failed} | {VENDORED})
        self.assert_no_staging()

    def test_missing_comfy_directory_is_rejected_without_git_commands(self):
        self.comfy.rmdir()
        result = self.execute()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())
        self.assertFalse(self.nodes.exists())


if __name__ == "__main__":
    unittest.main()
