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

    def test_known_gimm_and_wan_source_blockers_are_explicit_per_workflow(self):
        report = gate.assemble(*self.reports())
        rows = {row["workflow"]: row for row in report["workflows"]}
        expected = {
            gate.GIMM_WORKFLOW: "PINNED_GIMM_CLASS_BINDINGS_INCOMPATIBLE",
            **{path: "WAN_FMLF_PROVIDER_LICENSE_NOT_VERIFIED"
               for path in gate.WAN_FMLF_WORKFLOWS},
        }
        self.assertEqual(report["known_provider_source_blockers"], expected)
        self.assertEqual(
            report["release_blocker_counts"]["PINNED_GIMM_CLASS_BINDINGS_INCOMPATIBLE"],
            1,
        )
        self.assertEqual(
            report["release_blocker_counts"]["WAN_FMLF_PROVIDER_LICENSE_NOT_VERIFIED"],
            2,
        )
        for name, blocker in expected.items():
            self.assertIn(blocker, rows[name]["blocker_codes"])
            self.assertEqual(rows[name]["release_decision"], "HOLD")
        self.assertEqual(report["decision"], "HOLD")
        self.assertFalse(report["commercial_rights_cleared"])
        self.assertFalse(report["deployment_authorised_by_this_report"])

    def test_rejects_known_source_graph_class_drift_instead_of_silently_unblocking(self):
        for name, node_class in gate.KNOWN_PROVIDER_CLASS_BASELINES.items():
            c, l, p, s = self.reports()
            row = next(w for w in c["workflows"] if w["workflow"] == name)
            removed = False
            for classes in row["node_classes_by_status"].values():
                if node_class[0] in classes:
                    classes.remove(node_class[0])
                    removed = True
            self.assertTrue(removed, name)
            with self.subTest(name=name), self.assertRaisesRegex(
                ValueError, "graph-class baseline changed"
            ):
                gate.assemble(c, l, p, s)

    def test_rejects_known_source_loss_of_class_inventory_or_pin_baseline(self):
        c, l, p, s = self.reports()
        row = next(w for w in c["workflows"]
                   if w["workflow"] == gate.GIMM_WORKFLOW)
        row.pop("node_classes_by_status")
        with self.assertRaisesRegex(ValueError, "lacks class inventory"):
            gate.assemble(c, l, p, s)
        c, l, p, s = self.reports()
        row = next(w for w in c["workflows"]
                   if w["workflow"] == gate.GIMM_WORKFLOW)
        row["manifest_dependency_names"] = []
        with self.assertRaisesRegex(ValueError, "manifest pin baseline changed"):
            gate.assemble(c, l, p, s)

    def test_known_provider_reason_is_not_claimed_for_unrelated_workflow(self):
        report = gate.assemble(*self.reports())
        qualified = set(gate.KNOWN_PROVIDER_REASON_CODES)
        for row in report["workflows"]:
            if row["workflow"] not in qualified:
                self.assertNotIn("PINNED_GIMM_CLASS_BINDINGS_INCOMPATIBLE",
                                 row["blocker_codes"])
                self.assertNotIn("WAN_FMLF_PROVIDER_LICENSE_NOT_VERIFIED",
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
