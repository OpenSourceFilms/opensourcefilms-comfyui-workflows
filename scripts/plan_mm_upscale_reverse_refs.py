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

# This second gate protects the exact sixteen observed orphan locations,
# not just their count. Replacing one stale ID with another at the same
# location previously produced an indistinguishable count-only success.
# Each tuple: (reverse-reference category, node ID or None, port slot, link ID).
EXPECTED_STALE_BY_GROUP = {
    "6f5ab705-8e1b-4b53-a3f4-a35676bec4e9": (
        ("node_output", 362, 0, 620),
        ("node_output", 232, 0, 459),
        ("group_input", None, 4, 609),
        ("group_input", None, 5, 614),
    ),
    "1434deb7-2315-427a-8ad1-73b4f683e72d": (
        ("node_output", 224, 0, 548),
        ("node_output", 249, 0, 601),
        ("node_output", 248, 1, 543),
    ),
    "3a5d7d35-9999-4738-b299-aed4dbeffd55": (
        ("node_output", 465, 0, 548),
        ("node_output", 470, 0, 601),
        ("node_output", 478, 1, 543),
    ),
    "3ed84f91-ec12-4881-a8e3-1d2fc355c673": (
        ("node_output", 411, 0, 672),
        ("node_output", 412, 0, 673),
        ("node_output", 170, 0, 303),
        ("node_output", 413, 0, 675),
        ("node_output", 264, 0, 509),
        ("node_output", 434, 0, 698),
    ),
}


def require_exact_reviewed_orphans(group: dict) -> None:
    """Reject stale ID/location drift even when all sixteen counts still match.

    Call only after inspect_group has validated the active link structure.
    """
    group_id = group.get("id")
    if group_id not in EXPECTED_STALE_BY_GROUP:
        raise ValueError("Unknown embedded group UUID in reviewed orphan snapshot")
    active_ids = {link["id"] for link in group["links"]}
    found = []
    for node in group["nodes"]:
        for slot, port in enumerate(node.get("outputs", [])):
            for link_id in _references(port, "links"):
                if link_id not in active_ids:
                    found.append(("node_output", node["id"], slot, link_id))
        for slot, port in enumerate(node.get("inputs", [])):
            link_id = port.get("link")
            if link_id is not None and link_id not in active_ids:
                found.append(("node_input", node["id"], slot, link_id))
    for port_key, kind in (("inputs", "group_input"),
                           ("outputs", "group_output")):
        for slot, port in enumerate(group[port_key]):
            for link_id in _references(port, "linkIds"):
                if link_id not in active_ids:
                    found.append((kind, None, slot, link_id))
    reviewed = EXPECTED_STALE_BY_GROUP[group_id]
    if sorted(found, key=repr) != sorted(reviewed, key=repr):
        raise ValueError("Exact reviewed orphan reference ID/location drift")




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
    if {g.get("id") for g in groups} != set(EXPECTED_STALE_BY_GROUP):
        raise ValueError("Selected embedded group UUID set differs from reviewed snapshot")
    all_edits: list[dict] = []
    summaries: list[dict] = []
    for index, group in enumerate(groups):
        require_exact_reviewed_orphans(group)
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
        "reviewed_orphan_ids_and_port_locations_exact": True,
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
