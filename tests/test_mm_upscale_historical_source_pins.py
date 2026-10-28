"""No-network tests for candidate source commits in mm_upscale embedded groups."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "scripts" / "audit_mm_upscale_historical_source_pins.py"
spec = importlib.util.spec_from_file_location("osf_mm_upscale_pin_review", MOD)
pin_review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pin_review)


class HistoricalPinsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads((ROOT / pin_review.GRAPH).read_text(encoding="utf-8"))

    def _nodes(self, graph):
        for subgraph in graph["definitions"]["subgraphs"]:
            yield from subgraph["nodes"]

    def test_exact_source_pins_are_present_in_real_export(self):
        result = pin_review.audit()
        self.assertEqual(result["candidate_source_pins_count"], 4)
        self.assertEqual(result["reviewed_external_node_class_ids"], 15)
        self.assertEqual(result["reviewed_external_node_instances"], 82)
        self.assertEqual(
            {row["exported_provider_id"]: row["candidate_source_commit"]
             for row in result["source_candidate_providers"]},
            {provider: row["sha"] for provider, row in pin_review.REVIEWED_PINS.items()},
        )

    def test_licences_and_registration_source_locations_are_explicit(self):
        result = pin_review.audit()
        rows = {r["exported_provider_id"]: r for r in result["source_candidate_providers"]}
        self.assertEqual(rows["comfyui-custom-scripts"]["root_license_file_reviewed"], "MIT")
        self.assertEqual(rows["comfyui-easy-use"]["root_license_file_reviewed"], "GPL-3.0")
        self.assertEqual(rows["comfyui-kjnodes"]["root_license_file_reviewed"], "GPL-3.0")
        self.assertEqual(rows["comfyui_essentials"]["root_license_file_reviewed"], "MIT")
        self.assertEqual(
            rows["comfyui_essentials"]["reviewed_class_source_files"],
            {"ImageFromBatch+": "image.py", "SimpleMathSlider+": "misc.py"},
        )

    def test_unmapped_semver_labels_are_not_treated_as_verified_pins(self):
        result = pin_review.audit()
        rows = {r["exported_provider_id"]: r for r in result["source_candidate_providers"]}
        self.assertIn("1.3.0", rows["comfyui-easy-use"]["other_exported_version_aliases_unverified"])
        self.assertIn("1.3.3", rows["comfyui-easy-use"]["other_exported_version_aliases_unverified"])
        self.assertIn("1.2.5", rows["comfyui-custom-scripts"]["other_exported_version_aliases_unverified"])
        for row in rows.values():
            self.assertFalse(row["version_aliases_mapped_to_commit"])
            self.assertFalse(row["installed_runtime_nodes_verified"])
            self.assertFalse(row["nested_dependencies_verified"])
            self.assertFalse(row["commercial_distribution_obligations_cleared"])
        self.assertFalse(result["canonical_manifest_modified"])
        self.assertFalse(result["rights_cleared"])
        self.assertFalse(result["group_execution_qualified"])

    def test_changed_historical_commit_fails_closed(self):
        changed = copy.deepcopy(self.graph)
        expected = pin_review.REVIEWED_PINS["comfyui-kjnodes"]["sha"]
        node = next(n for n in self._nodes(changed)
                    if n["properties"].get("ver") == expected)
        node["properties"]["ver"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "historical source commit differs"):
            pin_review.reconcile(changed, source_sha256="test")

    def test_removed_exact_commit_fails_even_with_semver_alias(self):
        changed = copy.deepcopy(self.graph)
        expected = pin_review.REVIEWED_PINS["comfyui-easy-use"]["sha"]
        for n in self._nodes(changed):
            if n["properties"].get("ver") == expected:
                n["properties"]["ver"] = "1.3.3"
        with self.assertRaisesRegex(ValueError, "historical source commit differs"):
            pin_review.reconcile(changed, source_sha256="test")

    def test_unknown_class_or_provider_fails_closed(self):
        changed = copy.deepcopy(self.graph)
        node = next(n for n in self._nodes(changed)
                    if n["properties"]["cnr_id"] == "comfyui_essentials")
        node["type"] = "Unreviewed+"
        with self.assertRaisesRegex(ValueError, "Exported classes differ"):
            pin_review.reconcile(changed, source_sha256="test")
        changed2 = copy.deepcopy(self.graph)
        node2 = next(n for n in self._nodes(changed2)
                     if n["properties"]["cnr_id"] == "comfy-core")
        node2["properties"]["cnr_id"] = "unreviewed-provider"
        with self.assertRaisesRegex(ValueError, "Unreviewed embedded upstream"):
            pin_review.reconcile(changed2, source_sha256="test")

    def test_missing_embedded_group_is_not_accepted(self):
        changed = copy.deepcopy(self.graph)
        changed["definitions"]["subgraphs"].pop()
        with self.assertRaisesRegex(ValueError, "four reviewed embedded"):
            pin_review.reconcile(changed, source_sha256="test")

    def test_malformed_node_version_is_rejected(self):
        changed = copy.deepcopy(self.graph)
        node = next(self._nodes(changed))
        node["properties"]["ver"] = "1.2.0\nnew-key: trusted"
        with self.assertRaisesRegex(ValueError, "Unusable exported"):
            pin_review.reconcile(changed, source_sha256="test")

    def test_readonly_audit_rejects_symlinked_input(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exported = root / pin_review.GRAPH
            exported.parent.mkdir(parents=True)
            exported.symlink_to(ROOT / pin_review.GRAPH)
            with self.assertRaisesRegex(ValueError, "symlinked"):
                pin_review.audit(root)


if __name__ == "__main__":
    unittest.main()
