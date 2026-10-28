#!/usr/bin/env python3
"""Construct a reversible, non-deployable cleanup plan for embedded mm_upscale.

The selected UI export and canonical lock are never written. Only lists of
stale link IDs, absent from the authoritative active-link records, may change
in an in-memory candidate. Active links, other graph bytes and the release
HOLD are not promoted or altered.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

import audit_embedded_group_links as links

ROOT = Path(__file__).resolve().parents[1]
APPROVED = links.APPROVED
EXPECTED_GROUPS = 4
EXPECTED_NODES = 89
EXPECTED_ACTIVE = 171
EXPECTED_STALE = 16
EXPECTED_PER_GROUP = (3, 3, 4, 6)


def _references(port: dict, field: str) -> list[int]:
    return links._ref_ids(port.get(field), "embedded " + field)


def propose_group_cleanup(group: dict, index: int) -> tuple[dict, list[dict]]:
    """Inspect, remove orphan reverse IDs only, and prove exact inverse."""
    before = links.inspect_group(group)
    unresolved = before["unresolved_reverse_reference_ids_by_location"]
    if unresolved["node_input"] or unresolved["group_output"]:
        raise ValueError("Unexpected single-valued input or output dangling link")
    active = {item["id"] for item in group["links"]}
    candidate = copy.deepcopy(group)
    edits: list[dict] = []

    for node_index, node in enumerate(candidate["nodes"]):
        for slot, output in enumerate(node.get("outputs", [])):
            original = _references(output, "links")
            retained = [value for value in original if value in active]
            if len(retained) != len(original):
                output["links"] = retained
                edits.append({
                    "group_index": index,
                    "kind": "node_output",
                    "node_index": node_index,
                    "slot": slot,
                    "before": original,
                    "orphan_ids": [value for value in original if value not in active],
                })

    for slot, input_port in enumerate(candidate["inputs"]):
        original = _references(input_port, "linkIds")
        retained = [value for value in original if value in active]
        if len(retained) != len(original):
            input_port["linkIds"] = retained
            edits.append({
                "group_index": index,
                "kind": "group_input",
                "slot": slot,
                "before": original,
                "orphan_ids": [value for value in original if value not in active],
            })

    after = links.inspect_group(candidate)
    if not after["all_reverse_references_resolved"]:
        raise ValueError("Candidate still has unresolved reverse links")
    if candidate["links"] != group["links"]:
        raise ValueError("Candidate changed an active link record")
    if sum(len(edit["orphan_ids"]) for edit in edits) != before[
        "unresolved_reverse_reference_count"
    ]:
        raise ValueError("Unexpected repeated or shared orphan-link references")

    restored = copy.deepcopy(candidate)
    for edit in reversed(edits):
        if edit["kind"] == "node_output":
            restored["nodes"][edit["node_index"]]["outputs"][edit["slot"]][
                "links"
            ] = edit["before"]
        elif edit["kind"] == "group_input":
            restored["inputs"][edit["slot"]]["linkIds"] = edit["before"]
        else:
            raise ValueError("Unknown reverse-link patch operation")
    if restored != group:
        raise ValueError("Cleanup is not exactly reversible")
    return candidate, edits


def plan(root: Path = ROOT) -> dict:
    """Read canonical original, construct candidate in memory, retain HOLD."""
    baseline = links.audit(root)
    if (baseline["group_count"] != EXPECTED_GROUPS
            or baseline["total_internal_nodes"] != EXPECTED_NODES
            or baseline["total_active_links"] != EXPECTED_ACTIVE
            or baseline["total_unresolved_reverse_references"] != EXPECTED_STALE
            or sorted(
                x["unresolved_reverse_reference_count"]
                for x in baseline["results"]
            ) != list(EXPECTED_PER_GROUP)
            or not baseline["active_links_structurally_consistent"]):
        raise ValueError("Published embedded-group audit baseline has changed")

    path = root / APPROVED
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or symlinked selected workflow")
    original_bytes = path.read_bytes()
    actual_sha = hashlib.sha256(original_bytes).hexdigest()
    if actual_sha != baseline["graph_sha256"]:
        raise ValueError("Selected workflow differs from canonical staging source")

    original = json.loads(original_bytes)
    candidate = copy.deepcopy(original)
    groups = candidate["definitions"]["subgraphs"]
    if len(groups) != EXPECTED_GROUPS:
        raise ValueError("Selected embedded group count differs")
    all_edits: list[dict] = []
    summaries: list[dict] = []
    for index, group in enumerate(groups):
        modified, edits = propose_group_cleanup(group, index)
        groups[index] = modified
        all_edits.extend(edits)
        summaries.append({
            "group_uuid": group["id"],
            "removed_orphan_references": sum(len(x["orphan_ids"]) for x in edits),
            "active_link_count": len(group["links"]),
            "candidate_reverse_references_resolved": True,
        })

    if sum(x["removed_orphan_references"] for x in summaries) != EXPECTED_STALE:
        raise ValueError("Cleanup does not remove exactly the reviewed sixteen")

    # Prove a complete inverse of every edit, then byte-level source stability.
    recovered = copy.deepcopy(candidate)
    for edit in reversed(all_edits):
        grp = recovered["definitions"]["subgraphs"][edit["group_index"]]
        if edit["kind"] == "node_output":
            grp["nodes"][edit["node_index"]]["outputs"][edit["slot"]][
                "links"
            ] = edit["before"]
        else:
            grp["inputs"][edit["slot"]]["linkIds"] = edit["before"]
    if recovered != original:
        raise ValueError("Candidate cannot be reversed to original graph")

    # Confirm canonical source remains unchanged on disk: no writes occur.
    if path.read_bytes() != original_bytes:
        raise ValueError("Canonical workflow modified during source audit")

    candidate_hash = hashlib.sha256(json.dumps(
        candidate, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return {
        "schema": "osf-mm-upscale-reversible-reverse-ref-candidate-v1",
        "status": "CANDIDATE_ONLY_HOLD",
        "published_graph_sha256": actual_sha,
        "in_memory_candidate_canonical_sha256": candidate_hash,
        "group_count": EXPECTED_GROUPS,
        "internal_nodes_untouched": EXPECTED_NODES,
        "active_links_untouched": EXPECTED_ACTIVE,
        "removed_orphan_reverse_references": EXPECTED_STALE,
        "operations": [
            {
                "group_index": x["group_index"],
                "kind": x["kind"],
                "slot": x["slot"],
                "node_index": x.get("node_index"),
                "removed_orphan_ids": x["orphan_ids"],
            }
            for x in all_edits
        ],
        "per_group": summaries,
        "roundtrip_original_graph_recovered": True,
        "published_workflow_modified": False,
        "candidate_graph_exported": False,
        "ui_group_executable_proven": False,
        "api_prompt_conversion_proven": False,
        "dependency_licenses_cleared": False,
        "gpu_or_model_accepted": False,
        "eleven_workflows_qualified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = plan()
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as out:
            out.write(payload)
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
