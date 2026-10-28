"""Fail-closed reversible candidate tests for mm_upscale embedded group refs."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "osf_reverse_candidate", ROOT / "scripts" / "plan_mm_upscale_reverse_refs.py"
)
planner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(planner)


def minimal_group():
    return {
        "id": "2a1bddc6-8050-4b4d-9c53-afc33fbf6ba1",
        "inputNode": {"id": -10},
        "outputNode": {"id": -20},
        "inputs": [{"linkIds": [1, 40]}],
        "outputs": [{"linkIds": [3]}],
        "nodes": [
            {"id": 11, "inputs": [{"link": 1}],
             "outputs": [{"links": [2, 41]}]},
            {"id": 12, "inputs": [{"link": 2}],
             "outputs": [{"links": [3]}]},
        ],
        "links": [
            {"id": 1, "origin_id": -10, "origin_slot": 0,
             "target_id": 11, "target_slot": 0, "type": "INT"},
            {"id": 2, "origin_id": 11, "origin_slot": 0,
             "target_id": 12, "target_slot": 0, "type": "INT"},
            {"id": 3, "origin_id": 12, "origin_slot": 0,
             "target_id": -20, "target_slot": 0, "type": "INT"},
        ],
        "non_links": {"prompt": "leave this value untouched"},
    }


class ReversibleMMGroupTests(unittest.TestCase):
    def test_synthetic_orphans_only_and_exact_restoration(self):
        original = minimal_group()
        shadow = copy.deepcopy(original)
        candidate, edits = planner.propose_group_cleanup(original, 0)
        self.assertEqual(original, shadow)
        self.assertEqual(candidate["links"], original["links"])
        self.assertEqual(candidate["non_links"], original["non_links"])
        self.assertEqual(candidate["inputs"][0]["linkIds"], [1])
        self.assertEqual(candidate["nodes"][0]["outputs"][0]["links"], [2])
        self.assertEqual(len(edits), 2)
        self.assertCountEqual(
            [e["orphan_ids"][0] for e in edits], [40, 41]
        )
        self.assertTrue(
            planner.links.inspect_group(candidate)["all_reverse_references_resolved"]
        )

    def test_corrupt_active_link_fails_closed(self):
        sample = minimal_group()
        sample["nodes"][0]["outputs"][0]["links"] = [41]
        with self.assertRaisesRegex(ValueError, "Active link missing"):
            planner.propose_group_cleanup(sample, 0)

    def test_wrong_active_owner_fails_closed(self):
        sample = minimal_group()
        sample["nodes"][1]["outputs"][0]["links"].append(2)
        with self.assertRaisesRegex(ValueError, "another node"):
            planner.propose_group_cleanup(sample, 0)

    def test_unexpected_single_input_or_group_output_orphans_block_candidate(self):
        for field in ("node_input", "group_output"):
            sample = minimal_group()
            if field == "node_input":
                sample["nodes"][1]["inputs"].append({"link": 42})
            else:
                sample["outputs"][0]["linkIds"].append(43)
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "Unexpected single-valued"):
                    planner.propose_group_cleanup(sample, 0)

    def test_stale_reference_duplication_does_not_silently_pass(self):
        sample = minimal_group()
        sample["nodes"][1]["outputs"][0]["links"].append(41)
        with self.assertRaisesRegex(ValueError, "repeated or shared"):
            planner.propose_group_cleanup(sample, 0)

    def test_real_canonical_source_generates_metadata_only_hold(self):
        original_path = ROOT / planner.APPROVED
        before = original_path.read_bytes()
        actual = planner.plan()
        self.assertEqual(original_path.read_bytes(), before)
        self.assertEqual(actual["status"], "CANDIDATE_ONLY_HOLD")
        self.assertEqual(actual["removed_orphan_reverse_references"], 16)
        self.assertEqual(actual["active_links_untouched"], 171)
        self.assertEqual(actual["internal_nodes_untouched"], 89)
        self.assertEqual(actual["group_count"], 4)
        self.assertEqual(
            sorted(g["removed_orphan_references"] for g in actual["per_group"]),
            [3, 3, 4, 6],
        )
        self.assertTrue(actual["roundtrip_original_graph_recovered"])
        for key in ("published_workflow_modified", "candidate_graph_exported",
                    "ui_group_executable_proven", "api_prompt_conversion_proven",
                    "dependency_licenses_cleared", "gpu_or_model_accepted",
                    "eleven_workflows_qualified"):
            self.assertFalse(actual[key])
        self.assertNotIn("non_links", str(actual))
        for edit in actual["operations"]:
            self.assertTrue(set(edit).issubset({
                "group_index", "kind", "slot", "node_index",
                "removed_orphan_ids",
            }))
        self.assertNotIn("widgets_values", str(actual))
        self.assertNotIn(".safetensors", str(actual))

    def test_manifest_change_fails_before_candidate_generation(self):
        baseline = planner.links.audit()
        changed = copy.deepcopy(baseline)
        changed["total_unresolved_reverse_references"] = 15
        with mock.patch.object(planner.links, "audit", return_value=changed):
            with self.assertRaisesRegex(ValueError, "baseline has changed"):
                planner.plan()


if __name__ == "__main__":
    unittest.main()
