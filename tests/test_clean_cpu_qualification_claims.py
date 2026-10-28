"""Keep public clean-CPU qualification claims tied to actual source contracts.

This is an offline, stdlib-only documentation regression. It does not
assert that a registered ComfyUI node can load weights or run inference.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "clean-cpu-runtime-qualification.md"
QUOTE = chr(96)


def load_source(name: str, relative: str):
    source = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise ValueError("Missing repository-owned source for claims contract")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CleanCpuQualificationClaimsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = DOC.read_text(encoding="utf-8")
        cls.driver = load_source(
            "osf_doc_claims_cpu_driver", "scripts/qualify_clean_comfy_cpu.py"
        )
        cls.inventory = load_source(
            "osf_doc_claims_inventory", "scripts/audit-selected-11-node-coverage.py"
        )

    def test_every_pinned_external_package_and_registered_class_in_table(self):
        observed = {}
        for line in self.doc.splitlines():
            if not line.startswith("| "):
                continue
            parts = [part.strip() for part in line.split("|")]
            if len(parts) != 5:
                continue
            name, revision, class_cell = parts[1:4]
            if not (revision.startswith(QUOTE) and
                    revision.endswith(QUOTE) and len(revision) == 42):
                continue
            self.assertNotIn(name, observed, "Duplicate documented package")
            observed[name] = (revision[1:-1], class_cell)
        actual = self.driver.EXTERNAL_NODE_PINS
        self.assertEqual(set(observed), set(actual))
        self.assertEqual(len(actual), 6)
        for name, source in actual.items():
            with self.subTest(package=name):
                sha, class_cell = observed[name]
                self.assertEqual(sha, source["sha"])
                for node_class in source["classes"]:
                    self.assertIn(QUOTE + node_class + QUOTE, class_cell)

    def test_native_sam3_scail_names_are_not_described_as_missing(self):
        ids = self.inventory.FORK_NATIVE
        self.assertEqual(len(ids), 5)
        for name in ids:
            with self.subTest(node=name):
                self.assertIn(QUOTE + name + QUOTE, self.doc)
        self.assertIn("**all five registered**", self.doc)
        self.assertNotIn("The specialized fork is *not* part", self.doc)
        self.assertIn("not evidence these classes are absent", self.doc)
        self.assertIn("SAM3 tracking", self.doc)
        self.assertIn("**not** accepted", self.doc)

    def test_embedded_group_and_inference_limits_remain_explicit(self):
        self.assertIn("have matching embedded", self.doc)
        self.assertIn("valid frontend expansion, API-prompt conversion", self.doc)
        self.assertIn("not a clean installation or inference acceptance", self.doc)
        self.assertIn("complete commercial-use rights", self.doc)
        self.assertIn("issue #3", self.doc)


if __name__ == "__main__":
    unittest.main()
