"""Fail-closed reversible candidate tests for mm_upscale embedded group refs."""
from __future__ import annotations

import copy
import importlib.util
import json
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


def selected_group(group_id: str):
    path = ROOT / planner.APPROVED
    graph = json.loads(path.read_text(encoding="utf-8"))
    return copy.deepcopy(next(
        group for group in graph["definitions"]["subgraphs"]
        if group["id"] == group_id
    ))


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

    def test_reviewed_exact_orphan_snapshot_matches_all_four_real_groups(self):
        self.assertEqual(len(planner.EXPECTED_STALE_BY_GROUP), 4)
        self.assertEqual(
            sum(len(refs) for refs in planner.EXPECTED_STALE_BY_GROUP.values()), 16
        )
        for group_id in planner.EXPECTED_STALE_BY_GROUP:
            with self.subTest(group=group_id):
                group = selected_group(group_id)
                planner.links.inspect_group(group)
                self.assertIsNone(planner.require_exact_reviewed_orphans(group))

    def test_replaced_stale_id_with_same_count_is_rejected(self):
        group_id = "6f5ab705-8e1b-4b53-a3f4-a35676bec4e9"
        group = selected_group(group_id)
        node = next(n for n in group["nodes"] if n["id"] == 362)
        output = node["outputs"][0]
        output["links"] = [999999 if value == 620 else value
                           for value in output["links"]]
        # The older count-only planner would have accepted this.
        self.assertEqual(
            planner.links.inspect_group(group)["unresolved_reverse_reference_count"],
            4,
        )
        with self.assertRaisesRegex(ValueError, "Exact reviewed orphan"):
            planner.require_exact_reviewed_orphans(group)

    def test_moved_stale_id_to_another_node_port_is_rejected(self):
        group_id = "6f5ab705-8e1b-4b53-a3f4-a35676bec4e9"
        group = selected_group(group_id)
        source = next(n for n in group["nodes"] if n["id"] == 362)
        other = next(n for n in group["nodes"]
                     if n["id"] != 362 and n.get("outputs"))
        source["outputs"][0]["links"].remove(620)
        if other["outputs"][0].get("links") is None:
            other["outputs"][0]["links"] = []
        other["outputs"][0]["links"].append(620)
        self.assertEqual(
            planner.links.inspect_group(group)["unresolved_reverse_reference_count"],
            4,
        )
        with self.assertRaisesRegex(ValueError, "Exact reviewed orphan"):
            planner.require_exact_reviewed_orphans(group)

    def test_moved_stale_id_between_exposed_port_slots_is_rejected(self):
        group_id = "6f5ab705-8e1b-4b53-a3f4-a35676bec4e9"
        group = selected_group(group_id)
        group["inputs"][4]["linkIds"].remove(609)
        slot = group["inputs"][5]
        slot["linkIds"].append(609)
        self.assertEqual(
            planner.links.inspect_group(group)["unresolved_reverse_reference_count"],
            4,
        )
        with self.assertRaisesRegex(ValueError, "Exact reviewed orphan"):
            planner.require_exact_reviewed_orphans(group)

    def test_unreviewed_group_uuid_blocks_exact_pin(self):
        group_id = "1434deb7-2315-427a-8ad1-73b4f683e72d"
        group = selected_group(group_id)
        group["id"] = "unreviewed-group"
        with self.assertRaisesRegex(ValueError, "Unknown embedded group"):
            planner.require_exact_reviewed_orphans(group)

    def test_real_canonical_source_generates_metadata_only_hold(self):
        original_path = ROOT / planner.APPROVED
        before = original_path.read_bytes()
        actual = planner.plan()
        self.assertEqual(original_path.read_bytes(), before)
        self.assertEqual(actual["status"], "CANDIDATE_ONLY_HOLD")
        self.assertEqual(actual["removed_orphan_reverse_references"], 16)
        self.assertTrue(actual["reviewed_orphan_ids_and_port_locations_exact"])
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
