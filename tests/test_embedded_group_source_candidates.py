"""Offline regression contracts for exact embedded provider candidate inventory."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_embedded_group_source_candidates as candidates  # noqa: E402


class EmbeddedCandidateSourceTests(unittest.TestCase):
    def test_exact_export_class_coverage_and_explicit_nonacceptance(self):
        result = candidates.collect(ROOT)
        self.assertEqual(result["external_provider_hints"], 4)
        self.assertEqual(result["reviewed_external_classes"], 15)
        self.assertFalse(result["manifest_mutated"])
        self.assertFalse(result["commercial_rights_cleared"])
        self.assertFalse(result["embedded_group_runtime_qualified"])
        self.assertFalse(result["eleven_workflows_qualified"])
        self.assertEqual(
            sum(not x["currently_declared_in_canonical_manifest"]
                for x in result["candidate_sources"]), 3,
        )
        self.assertEqual(
            sum(x["currently_declared_in_canonical_manifest"]
                and not x["currently_commit_pinned_in_canonical_manifest"]
                for x in result["candidate_sources"]), 1,
        )
        for source in result["candidate_sources"]:
            self.assertEqual(source["reviewed_class_count"],
                             len(source["reviewed_exact_class_source_paths"]))
            self.assertFalse(source["snapshot_checked_live_in_this_run"])
            self.assertFalse(source["exact_source_compatible_with_export"])
            self.assertFalse(source["licence_obligations_cleared"])
            self.assertFalse(source["nested_requirements_reviewed"])

    def test_reviewed_provider_revisions_and_licence_file_claims(self):
        sources = {x["exported_provider_hint"]: x
                   for x in candidates.collect(ROOT)["candidate_sources"]}
        expected = {
            "comfyui-custom-scripts": ("pythongosssss/ComfyUI-Custom-Scripts",
                                       "609f3afaa74b2f88ef9ce8d939626065e3247469", "MIT", 2),
            "comfyui-easy-use": ("yolain/ComfyUI-Easy-Use",
                                  "b0b47ca1372117fce575d9e744655344ebff6bef", "GPL-3.0", 8),
            "comfyui-kjnodes": ("kijai/ComfyUI-KJNodes",
                                "2371136d2fa6fd0914e514cd99b36dabe5db9adf", "GPL-3.0", 3),
            "comfyui_essentials": ("cubiq/ComfyUI_essentials",
                                   "9d9f4bedfc9f0321c19faf71855e228c93bd0dc9", "MIT", 2),
        }
        self.assertEqual(set(sources), set(expected))
        for hint, (repo, commit, license_id, count) in expected.items():
            source = sources[hint]
            self.assertEqual(source["reviewed_repository"], repo)
            self.assertEqual(source["reviewed_commit_candidate"], commit)
            self.assertEqual(source["reviewed_license_file"], "LICENSE")
            self.assertEqual(source["reviewed_license_id"], license_id)
            self.assertEqual(source["reviewed_class_count"], count)

    def test_unrecognized_class_requires_new_review(self):
        current = candidates.REVIEWED
        altered = deepcopy(current)
        altered["comfyui-kjnodes"]["classes"].pop("ImagePass")
        with mock.patch.object(candidates, "REVIEWED", altered):
            with self.assertRaisesRegex(ValueError, "differs from reviewed"):
                candidates.collect(ROOT)

    def test_invalid_source_revision_and_unreviewed_license_fail_closed(self):
        original = candidates.REVIEWED
        for field, value, message in [
            ("commit", "main", "Invalid candidate commit"),
            ("license", "unknown", "Unreviewed candidate licence"),
            ("repository", "../bad", "Invalid candidate repository"),
        ]:
            with self.subTest(field=field):
                edited = deepcopy(original)
                edited["comfyui-easy-use"][field] = value
                with mock.patch.object(candidates, "REVIEWED", edited):
                    with self.assertRaisesRegex(ValueError, message):
                        candidates.collect(ROOT)

    def test_unreviewed_provider_cannot_be_silently_accepted(self):
        modified = deepcopy(candidates.REVIEWED)
        modified.pop("comfyui_essentials")
        with mock.patch.object(candidates, "REVIEWED", modified):
            with self.assertRaisesRegex(ValueError, "provider hint"):
                candidates.collect(ROOT)


if __name__ == "__main__":
    unittest.main()
