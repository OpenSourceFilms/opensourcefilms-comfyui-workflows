"""No-network checks of embedded group metadata against canonical profile."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_embedded_group_provider_dependencies.py"
spec = importlib.util.spec_from_file_location("mm_provider_audit", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
GRAPH = json.loads((ROOT / audit.GRAPH).read_text(encoding="utf-8"))
LOCK = (ROOT / "DEPENDENCIES.lock").read_text(encoding="utf-8")


def run(graph=None, lock=None):
    return audit.reconcile(
        GRAPH if graph is None else graph,
        LOCK if lock is None else lock,
        graph_sha256="a" * 64,
    )


class EmbeddedProviderTests(unittest.TestCase):
    def test_real_export_exposes_three_missing_providers_without_acceptance(self):
        result = audit.audit()
        self.assertEqual(result["embedded_group_definitions"], 4)
        self.assertEqual(result["embedded_internal_node_instances"], 89)
        self.assertEqual(result["distinct_internal_class_ids"], 17)
        self.assertEqual(len(result["exported_external_provider_hints"]), 4)
        self.assertEqual(
            result["external_provider_hints_missing_from_canonical_manifest"],
            ["ComfyUI-Easy-Use", "ComfyUI-KJNodes", "ComfyUI_essentials"],
        )
        self.assertEqual(
            result["declared_but_not_commit_pinned_provider_hints"],
            ["ComfyUI-Custom-Scripts (pysssss)"],
        )
        self.assertEqual(result["unmapped_provider_hints"], [])
        self.assertEqual(len(result["core_provider_hints"]), 1)
        self.assertFalse(result["all_external_providers_declared_and_commit_pinned"])
        self.assertFalse(result["source_versions_licenses_runtime_confirmed"])
        self.assertFalse(result["embedded_groups_executable"])
        self.assertFalse(result["commercial_rights_cleared"])

    def test_each_exported_provider_is_counted_without_upstream_claim(self):
        result = run()
        by = {r["exported_cnr_id"]: r for r
              in result["exported_external_provider_hints"]}
        self.assertEqual(by["comfyui-custom-scripts"]["internal_instances"], 23)
        self.assertEqual(by["comfyui-easy-use"]["internal_instances"], 43)
        self.assertEqual(by["comfyui-kjnodes"]["internal_instances"], 7)
        self.assertEqual(by["comfyui_essentials"]["internal_instances"], 10)
        self.assertTrue(all(r["metadata_is_source_or_license_proof"] is False
                            for r in by.values()))
        self.assertEqual(result["core_provider_hints"][0]["internal_instances"], 7)

    def test_selected_manifest_scoping_does_not_borrow_other_workflows(self):
        foreign = "\nworkflows/research-only/foreign.json:\n  dependencies:\n"
        foreign += "    - name: ComfyUI-Easy-Use\n"
        self.assertEqual(
            run(lock=LOCK + foreign)[
                "external_provider_hints_missing_from_canonical_manifest"],
            ["ComfyUI-Easy-Use", "ComfyUI-KJNodes", "ComfyUI_essentials"],
        )

    def test_added_manifest_declarations_do_not_imply_pinned_or_licensed(self):
        old = "    - name: ComfyUI-VideoHelperSuite\n"
        additions = (
            "    - name: ComfyUI-Easy-Use\n"
            "      license: GPL-3.0\n"
            "      distribution: external\n"
            "    - name: ComfyUI-KJNodes\n"
            "      commit: " + "a" * 40 + "\n"
            "      license: GPL-3.0\n"
            "      distribution: external\n"
            "    - name: ComfyUI_essentials\n"
            "      commit: " + "b" * 40 + "\n"
            "      license: MIT\n"
            "      distribution: external\n"
        )
        start = LOCK.index("\n" + audit.GRAPH + ":\n")
        index = LOCK.index(old, start)
        updated = LOCK[:index] + additions + LOCK[index:]
        result = run(lock=updated)
        self.assertEqual(result["external_provider_hints_missing_from_canonical_manifest"], [])
        self.assertEqual(result["declared_but_not_commit_pinned_provider_hints"],
                         ["ComfyUI-Custom-Scripts (pysssss)", "ComfyUI-Easy-Use"])
        self.assertFalse(result["source_versions_licenses_runtime_confirmed"])

    def test_conflicting_class_provider_metadata_is_rejected(self):
        graph = copy.deepcopy(GRAPH)
        group = graph["definitions"]["subgraphs"][0]
        group["nodes"][0]["properties"]["cnr_id"] = "comfyui-easy-use"
        with self.assertRaisesRegex(ValueError, "conflicting provider"):
            run(graph=graph)

    def test_unknown_provider_is_reported_not_accepted(self):
        graph = copy.deepcopy(GRAPH)
        target = graph["definitions"]["subgraphs"][0]["nodes"][0]
        old_type = target["type"]
        target["type"] = "synthetic_unmapped_extension"
        target["properties"]["cnr_id"] = "unmapped-new-provider"
        result = run(graph=graph)
        self.assertEqual(len(result["unmapped_provider_hints"]), 1)
        self.assertFalse(result["all_external_providers_declared_and_commit_pinned"])
        self.assertIn(old_type, {c for p in result["exported_external_provider_hints"]
                                 for c in p["distinct_classes"]})

    def test_missing_provider_version_and_invalid_group_fail_closed(self):
        graph = copy.deepcopy(GRAPH)
        target = graph["definitions"]["subgraphs"][0]["nodes"][0]
        for key in ("cnr_id", "ver"):
            bad = copy.deepcopy(graph)
            del bad["definitions"]["subgraphs"][0]["nodes"][0]["properties"][key]
            with self.assertRaisesRegex(ValueError, "metadata"):
                run(graph=bad)
        graph["definitions"]["subgraphs"][0]["id"] = "../bad"
        with self.assertRaisesRegex(ValueError, "UUID"):
            run(graph=graph)

    def test_unknown_locked_commit_does_not_get_silently_pinned(self):
        old = "      license: GPL-3.0\n      distribution: external"
        self.assertIn(old, LOCK)
        bad = LOCK.replace(old, "      commit: not-a-sha\n" + old, 1)
        # Invalid commit in a different section must not change this profile.
        self.assertEqual(run(lock=bad)["schema"],
                         "osf-mm-upscale-embedded-provider-manifest-gap-v1")

    def test_no_source_prompts_media_paths_or_widget_values_in_report(self):
        result = run()
        rendered = json.dumps(result)
        self.assertNotIn("widgets_values", rendered)
        self.assertNotIn("prompt", rendered.lower())
        self.assertNotIn("media/", rendered)
        self.assertEqual(len(result["source_sha256"]), 64)

    def test_symlinked_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            graph_path = root / audit.GRAPH
            graph_path.parent.mkdir(parents=True)
            graph_path.symlink_to(ROOT / audit.GRAPH)
            (root / "DEPENDENCIES.lock").write_text(LOCK, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "symlinked"):
                audit.audit(root)


if __name__ == "__main__":
    unittest.main()
