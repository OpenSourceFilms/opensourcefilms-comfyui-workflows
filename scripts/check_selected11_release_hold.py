#!/usr/bin/env python3
"""Read-only, fail-closed admission report for the selected 11 workflow exports.

Combines *existing* independent source-only reports. None of them is GPU,
model-weight, API-conversion or commercial-rights acceptance. This tool
cannot and must not promote a workflow to production-ready status.

Only bounded public graph paths, counts, hashes and reason codes are emitted.
Never include prompt text, widget values, file paths to private media, or
unreviewed upstream code in the report.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

COVERAGE_SCHEMA = "osf-selected-11-node-coverage-v1"
LINKS_SCHEMA = "osf-mm-upscale-embedded-link-preflight-v1"
PROVIDER_SCHEMA = "osf-mm-upscale-embedded-provider-manifest-gap-v1"
CANDIDATES_SCHEMA = "osf-mm-upscale-upstream-candidate-snapshot-v1"
OUTPUT_SCHEMA = "osf-selected-11-admission-hold-v1"
MM_WORKFLOW = "workflows/commercial-compatible/mm_upscale_video_workflow.json"
PUBLIC_PATH = re.compile(r"^workflows/commercial-compatible/[a-zA-Z0-9_-]+\.json$")

# Historical source findings are independently audited elsewhere. The
# reconciler confirms that the selected graph still contains the precise
# source-blocked node IDs before attaching a reason code. It does NOT
# import those upstream audits or independently revalidate their sources.
GIMM_WORKFLOW = "workflows/commercial-compatible/gimm_sgm_vfi_video_interpolate.json"
WAN_FMLF_WORKFLOWS = {
    "workflows/commercial-compatible/wan22_fmlf_first_middle_last_frame.json":
        ("WanFirstMiddleLastFrameToVideo", "WanFourFrameReferenceUltimate",
         "WanMultiFrameRefToVideo"),
    "workflows/commercial-compatible/video_wan2_2_14B_fmlf2v.json":
        ("WanFirstMiddleLastFrameToVideo",),
}
KNOWN_PROVIDER_CLASS_BASELINES = {
    GIMM_WORKFLOW: ("GIMMVFI_loader", "GIMMVFIInterpolate"),
    **WAN_FMLF_WORKFLOWS,
}
KNOWN_PROVIDER_REASON_CODES = {
    GIMM_WORKFLOW: "PINNED_GIMM_CLASS_BINDINGS_INCOMPATIBLE",
    **{name: "WAN_FMLF_PROVIDER_LICENSE_NOT_VERIFIED"
       for name in WAN_FMLF_WORKFLOWS},
}


def known_provider_blocker(path: str, row: dict) -> str | None:
    """Attach reviewed-source HOLD only while its actual graph classes match.

    Existing independent source findings:
    - GIMM: pinned kijai and Tween class-name/schema mismatch.
    - Wan FMLF: matching external class source with no detected licence.
    This gate never upgrades rights or predicts model runtime acceptance.
    """
    expected = KNOWN_PROVIDER_CLASS_BASELINES.get(path)
    if expected is None:
        return None
    if row.get("graph_format") != "ui":
        raise ValueError("Known provider blocker graph-format baseline changed")
    classified = row.get("node_classes_by_status")
    if not isinstance(classified, dict) or not all(
        isinstance(values, list) and all(isinstance(value, str) for value in values)
        for values in classified.values()
    ):
        raise ValueError("Known provider blocker lacks class inventory")
    present = {name for values in classified.values() for name in values}
    if not set(expected).issubset(present):
        raise ValueError("Known provider blocker graph-class baseline changed")
    if path == GIMM_WORKFLOW:
        deps = row.get("manifest_dependency_names")
        if (not isinstance(deps, list) or
                not {"ComfyUI-GIMM-VFI", "ComfyUI-Tween (provides SGM-VFI)"}
                .issubset(deps)):
            raise ValueError("GIMM known provider manifest pin baseline changed")
    return KNOWN_PROVIDER_REASON_CODES[path]
SHA256 = re.compile(r"^[0-9a-f]{64}$")
BASE_BLOCKERS = (
    "GPU_AND_MODEL_INFERENCE_NOT_QUALIFIED",
    "MODEL_WEIGHTS_RUNTIME_NOT_QUALIFIED",
    "COMMERCIAL_RIGHTS_NOT_VERIFIED",
    "EXECUTABLE_API_PROMPT_NOT_PROVEN",
)


def _object(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(label + " is not an object")
    return value


def _read(path: Path, schema: str) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing/symlinked source report")
    data = _object(json.loads(path.read_text(encoding="utf-8")), "Audit report")
    if data.get("schema") != schema:
        raise ValueError("Unexpected source report schema")
    return data


def check_all_eleven_coverage_source_bytes(
    coverage: dict, source_bytes: dict, manifest: dict,
) -> int:
    """Bind all 11 coverage SHA-256 claims to current approved source bytes.

    This checks actual checkout content, not merely the format of a supplied
    hash. It is separate from the pure multi-report `assemble` routine.
    """
    rows = coverage.get("workflows") if isinstance(coverage, dict) else None
    if (not isinstance(rows, list) or len(rows) != 11
            or not isinstance(source_bytes, dict)
            or not isinstance(manifest, dict)
            or len(source_bytes) != 11 or len(manifest) != 11
            or set(source_bytes) != set(manifest)):
        raise ValueError("Current eleven source/coverage inventories disagree")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Malformed current-graph coverage row")
        name = row.get("workflow")
        if (not isinstance(name, str) or PUBLIC_PATH.fullmatch(name) is None
                or name not in source_bytes or name in seen):
            raise ValueError("Coverage contains missing, duplicate or unexpected source")
        seen.add(name)
        source = source_bytes[name]
        spec = manifest[name]
        if (not isinstance(source, bytes) or not isinstance(spec, dict)
                or spec.get("format") not in ("api", "ui")
                or row.get("graph_format") != spec["format"]):
            raise ValueError("Current selected graph source or format differs")
        current = hashlib.sha256(source).hexdigest()
        if row.get("source_graph_sha256") != current:
            raise ValueError("Coverage graph SHA differs from current selected source bytes")
    if seen != set(source_bytes):
        raise ValueError("Coverage omitted a current approved workflow source")
    return len(seen)


def verify_against_current_checkout(coverage: dict) -> int:
    """Read the canonical manifest and graph bytes in this checkout, without writes."""
    root = Path(__file__).resolve().parents[1]
    script = root / "runpod" / "commercial-compatible" / "prepare.py"
    if script.is_symlink() or not script.is_file():
        raise ValueError("Canonical approved workflow selector unavailable")
    spec = importlib.util.spec_from_file_location("osf_current_selected11", script)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load canonical approved workflow selector")
    selector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(selector)
    approved, manifest = selector.choose_files()
    return check_all_eleven_coverage_source_bytes(coverage, approved, manifest)


def assemble(
    coverage: dict, links: dict, providers: dict, candidates: dict,
) -> dict:
    coverage = _object(coverage, "Coverage")
    links = _object(links, "Links")
    providers = _object(providers, "Providers")
    candidates = _object(candidates, "Candidates")
    for report, expected in (
        (coverage, COVERAGE_SCHEMA), (links, LINKS_SCHEMA),
        (providers, PROVIDER_SCHEMA), (candidates, CANDIDATES_SCHEMA),
    ):
        if report.get("schema") != expected:
            raise ValueError("Missing or mismatched audited source schema")
    workflows = coverage.get("workflows")
    if (not isinstance(workflows, list) or len(workflows) != 11
            or coverage.get("selected_workflow_count") != 11):
        raise ValueError("Expected exactly eleven source-audited workflows")
    if (coverage.get("gpu_inference_verified") is not False
            or coverage.get("all_eleven_workflows_executable") is not False
            or coverage.get("commercial_rights_verified") is not False):
        raise ValueError("Source-only coverage unexpectedly claims runtime or rights")
    if (links.get("active_links_structurally_consistent") is not True
            or links.get("embedded_group_runtime_qualified") is not False
            or providers.get("embedded_groups_executable") is not False
            or providers.get("commercial_rights_cleared") is not False
            or candidates.get("commercial_rights_cleared") is not False
            or candidates.get("embedded_group_runtime_qualified") is not False):
        raise ValueError("Input reports lack expected source-only qualification boundaries")
    fingerprint = links.get("graph_sha256")
    if (not isinstance(fingerprint, str) or not SHA256.fullmatch(fingerprint)
            or fingerprint != providers.get("source_sha256")
            or fingerprint != candidates.get("workflow_source_sha256")):
        raise ValueError("Embedded group audits refer to different graph revisions")
    instances = coverage.get("embedded_group_internal_node_instances")
    if (not isinstance(instances, int) or instances < 1
            or instances != links.get("total_internal_nodes")
            or instances != providers.get("embedded_internal_node_instances")):
        raise ValueError("Embedded node instances disagree across source audits")
    group_count = links.get("group_count")
    if (not isinstance(group_count, int) or group_count < 1
            or group_count != providers.get("embedded_group_definitions")):
        raise ValueError("Embedded group counts disagree")
    reverse_refs = links.get("total_unresolved_reverse_references")
    if (not isinstance(reverse_refs, int) or reverse_refs < 0
            or links.get("all_reverse_references_resolved") is not (reverse_refs == 0)):
        raise ValueError("Reverse-reference audit is internally inconsistent")
    missing = providers.get("external_provider_hints_missing_from_canonical_manifest")
    unpinned = providers.get("declared_but_not_commit_pinned_provider_hints")
    unmapped = providers.get("unmapped_provider_hints")
    if (not all(isinstance(x, list) for x in (missing, unpinned, unmapped))
            or any(not isinstance(name, str) or not name
                   for collection in (missing, unpinned) for name in collection)):
        raise ValueError("Provider provenance blocker lists are malformed")
    providers_complete = not missing and not unpinned and not unmapped
    if providers.get("all_external_providers_declared_and_commit_pinned") is not providers_complete:
        raise ValueError("Canonical provider manifest completeness flag disagrees")
    if (candidates.get("workflow") != MM_WORKFLOW
            or providers.get("workflow") != MM_WORKFLOW
            or links.get("approved_workflow") != MM_WORKFLOW):
        raise ValueError("Embedded group audits target different selected workflow")
    seen = set()
    entries = []
    formats = {"ui": 0, "api": 0}
    for item in workflows:
        row = _object(item, "Workflow entry")
        path = row.get("workflow")
        fmt = row.get("graph_format")
        if (not isinstance(path, str) or PUBLIC_PATH.fullmatch(path) is None
                or path in seen or fmt not in formats):
            raise ValueError("Unexpected, duplicate or unsafe workflow identity")
        seen.add(path)
        # Coverage must identify the exact graph bytes it classified.
        # A stale coverage report previously could pass alongside the three
        # fresh embedded-group reports despite differing mm_upscale revisions.
        coverage_hash = row.get("source_graph_sha256")
        if (not isinstance(coverage_hash, str)
                or SHA256.fullmatch(coverage_hash) is None):
            raise ValueError("Selected workflow coverage source hash missing or invalid")
        if path == MM_WORKFLOW and coverage_hash != fingerprint:
            raise ValueError(
                "Selected coverage and embedded audits refer to different mm_upscale revisions"
            )
        formats[fmt] += 1
        if (row.get("gpu_inference_verified") is not False
                or row.get("executable_api_prompt_proven") is not False
                or row.get("commercial_rights_verified") is not False):
            raise ValueError("A source-only workflow entry asserts unearned acceptance")
        blocks = list(BASE_BLOCKERS)
        provider_reason = known_provider_blocker(path, row)
        if provider_reason is not None:
            blocks.append(provider_reason)
        if fmt == "ui":
            blocks.append("EDITOR_GRAPH_API_CONVERSION_NOT_QUALIFIED")
        if path == MM_WORKFLOW:
            groups = _object(row.get("embedded_group_definition_preflight"),
                             "Embedded groups")
            if (groups.get("embedded_internal_node_instances") != instances
                    or groups.get("runtime_qualified") is not False):
                raise ValueError("Selected mm_upscale embedded groups differ")
            blocks.append("EMBEDDED_GROUP_RUNTIME_NOT_QUALIFIED")
            if reverse_refs:
                blocks.append("EMBEDDED_GROUP_REVERSE_LINKS_UNRESOLVED")
            if not providers_complete:
                blocks.append("EMBEDDED_PROVIDER_MANIFEST_NOT_COMPLETE")
        entries.append({
            "workflow": path,
            "source_graph_format": fmt,
            "release_decision": "HOLD",
            "blocker_codes": sorted(blocks),
        })
    if not set(KNOWN_PROVIDER_CLASS_BASELINES).issubset(seen):
        raise ValueError("Known provider blocker workflows missing from selected eleven")
    reported = coverage.get("workflow_graph_format_counts")
    if reported != formats or MM_WORKFLOW not in seen:
        raise ValueError("Coverage counts or mm_upscale workflow disagree")
    return {
        "schema": OUTPUT_SCHEMA,
        "scope": "source_only_synthesis_no_runtime_or_rights_attestation",
        "decision": "HOLD",
        "deployment_authorised_by_this_report": False,
        "all_eleven_inference_qualified": False,
        "commercial_rights_cleared": False,
        "selected_workflow_count": len(entries),
        "graph_formats": formats,
        "embedded_mm_upscale_source_sha256": fingerprint,
        "embedded_group_count": group_count,
        "embedded_internal_node_instances": instances,
        "unresolved_embedded_reverse_references": reverse_refs,
        "embedded_external_providers_missing_from_manifest": sorted(missing),
        "embedded_external_providers_not_commit_pinned": sorted(unpinned),
        "embedded_unmapped_provider_hint_count": len(unmapped),
        "known_provider_source_blockers": {
            name: KNOWN_PROVIDER_REASON_CODES[name]
            for name in sorted(KNOWN_PROVIDER_REASON_CODES)
        },
        "known_provider_source_evidence_scope":
            "previously_reviewed_pinned_sources_and_current_graph_class_identity_only",
        "release_blocker_counts": {
            code: sum(code in row["blocker_codes"] for row in entries)
            for code in sorted(set(
                reason for row in entries for reason in row["blocker_codes"]
            ))
        },
        "workflows": sorted(entries, key=lambda x: x["workflow"]),
        "required_next_evidence": [
            "Exact provider versions, licences and embedded group runtime",
            "Editor graph to executable API conversion and typed socket parity",
            "Actual model weight provenance and permitted use",
            "Independent GPU inference and output acceptance for each workflow",
        ],
        "source_only_audit_schemas": [
            COVERAGE_SCHEMA, LINKS_SCHEMA, PROVIDER_SCHEMA, CANDIDATES_SCHEMA,
        ],
    }


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--coverage", type=Path, required=True)
    cli.add_argument("--links", type=Path, required=True)
    cli.add_argument("--providers", type=Path, required=True)
    cli.add_argument("--candidates", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    if args.output.is_symlink() or args.output.exists():
        cli.error("Output must not exist or be a symlink")
    coverage = _read(args.coverage, COVERAGE_SCHEMA)
    # Reject stale, substituted or mixed coverage reports for ANY selected
    # workflow, not just the mm_upscale graph shared by three specialist audits.
    verified_source_count = verify_against_current_checkout(coverage)
    report = assemble(
        coverage,
        _read(args.links, LINKS_SCHEMA),
        _read(args.providers, PROVIDER_SCHEMA),
        _read(args.candidates, CANDIDATES_SCHEMA),
    )
    report["current_checkout_source_hashes_verified"] = True
    report["current_checkout_source_hashes_verified_count"] = verified_source_count
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("Eleven workflow release decision: HOLD, source-only; no GPU/rights clearance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
