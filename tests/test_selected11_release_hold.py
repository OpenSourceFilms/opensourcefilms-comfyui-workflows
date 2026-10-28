"""Source-only multi-audit readiness HOLD, including corruption regressions."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _module(filename: str, module_name: str):
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _module("check_selected11_release_hold.py", "osf_release_hold")
coverage_mod = _module("audit-selected-11-node-coverage.py", "osf_11_coverage")
links_mod = _module("audit_embedded_group_links.py", "osf_links")
provider_mod = _module(
    "audit_embedded_group_provider_dependencies.py", "osf_providers")
candidate_mod = _module(
    "audit_embedded_group_source_candidates.py", "osf_candidates")


class Selected11ReleaseHoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.coverage = coverage_mod.audit(ROOT)
        cls.links = links_mod.audit(ROOT)
        cls.providers = provider_mod.audit(ROOT)
        cls.candidates = candidate_mod.collect(ROOT)

    def reports(self):
        return tuple(deepcopy(x) for x in (
            self.coverage, self.links, self.providers, self.candidates
        ))

    def test_integrated_real_reports_remain_hold_and_public_only(self):
        result = gate.assemble(*self.reports())
        self.assertEqual(result["schema"], gate.OUTPUT_SCHEMA)
        self.assertEqual(result["selected_workflow_count"], 11)
        self.assertEqual(result["graph_formats"], {"api": 4, "ui": 7})
        self.assertFalse(result["deployment_authorised_by_this_report"])
        self.assertFalse(result["commercial_rights_cleared"])
        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(result["embedded_group_count"], 4)
        self.assertEqual(result["embedded_internal_node_instances"], 89)
        self.assertEqual(result["unresolved_embedded_reverse_references"], 16)
        self.assertEqual(len(result["embedded_external_providers_missing_from_manifest"]), 3)
        self.assertEqual(len(result["embedded_external_providers_not_commit_pinned"]), 1)
        self.assertEqual(result["release_blocker_counts"][
            "GPU_AND_MODEL_INFERENCE_NOT_QUALIFIED"], 11)
        self.assertEqual(result["release_blocker_counts"][
            "EDITOR_GRAPH_API_CONVERSION_NOT_QUALIFIED"], 7)
        self.assertEqual(result["release_blocker_counts"][
            "EMBEDDED_GROUP_REVERSE_LINKS_UNRESOLVED"], 1)
        for row in result["workflows"]:
            self.assertEqual(row["release_decision"], "HOLD")
            self.assertTrue(row["workflow"].startswith(
                "workflows/commercial-compatible/"
            ))
            self.assertNotIn("prompt", row)
            self.assertNotIn("widget", row)
            self.assertIn("COMMERCIAL_RIGHTS_NOT_VERIFIED",
                          row["blocker_codes"])

    def test_revision_mismatch_between_link_and_provider_audits_rejected(self):
        c, l, p, s = self.reports()
        p["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "different graph revisions"):
            gate.assemble(c, l, p, s)

    def test_missing_provenance_pin_must_remain_a_visible_blocker(self):
        c, l, p, s = self.reports()
        result = gate.assemble(c, l, p, s)
        mm = next(w for w in result["workflows"]
                  if w["workflow"] == gate.MM_WORKFLOW)
        self.assertIn("EMBEDDED_PROVIDER_MANIFEST_NOT_COMPLETE",
                      mm["blocker_codes"])
        p["all_external_providers_declared_and_commit_pinned"] = True
        with self.assertRaisesRegex(ValueError, "completeness flag"):
            gate.assemble(c, l, p, s)

    def test_rejects_unearned_positive_gpu_rights_and_api_claims(self):
        for attribute in ("gpu_inference_verified",
                          "all_eleven_workflows_executable",
                          "commercial_rights_verified"):
            c, l, p, s = self.reports()
            c[attribute] = True
            with self.subTest(attr=attribute), self.assertRaisesRegex(
                ValueError, "unexpectedly claims"
            ):
                gate.assemble(c, l, p, s)
        for attribute in ("gpu_inference_verified",
                          "executable_api_prompt_proven",
                          "commercial_rights_verified"):
            c, l, p, s = self.reports()
            c["workflows"][0][attribute] = True
            with self.subTest(entry=attribute), self.assertRaisesRegex(
                ValueError, "unearned acceptance"
            ):
                gate.assemble(c, l, p, s)

    def test_rejects_duplicate_and_unsafe_workflow_names(self):
        for name in ("../private.json", "workflows/commercial-compatible/x.json/.."):
            c, l, p, s = self.reports()
            c["workflows"][0]["workflow"] = name
            with self.subTest(name=name), self.assertRaisesRegex(
                ValueError, "unsafe workflow identity"
            ):
                gate.assemble(c, l, p, s)
        c, l, p, s = self.reports()
        non_mm = [row for row in c["workflows"]
                  if row["workflow"] != gate.MM_WORKFLOW]
        non_mm[1]["workflow"] = non_mm[0]["workflow"]
        with self.assertRaisesRegex(ValueError, "duplicate or unsafe"):
            gate.assemble(c, l, p, s)

    def test_fail_closed_on_reversed_reference_count_or_embedded_total(self):
        c, l, p, s = self.reports()
        l["total_unresolved_reverse_references"] = 0
        with self.assertRaisesRegex(ValueError, "internally inconsistent"):
            gate.assemble(c, l, p, s)
        c, l, p, s = self.reports()
        c["embedded_group_internal_node_instances"] = 88
        with self.assertRaisesRegex(ValueError, "instances disagree"):
            gate.assemble(c, l, p, s)

    def test_source_path_must_be_regular_and_expected_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            payload = folder / "report.json"
            payload.write_text('{"schema": "unexpected"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unexpected source report"):
                gate._read(payload, gate.COVERAGE_SCHEMA)
            linked = folder / "alias.json"
            linked.symlink_to(payload)
            with self.assertRaisesRegex(ValueError, "Missing/symlinked"):
                gate._read(linked, gate.COVERAGE_SCHEMA)
            with self.assertRaisesRegex(ValueError, "Missing/symlinked"):
                gate._read(folder / "missing.json", gate.COVERAGE_SCHEMA)


if __name__ == "__main__":
    unittest.main()
