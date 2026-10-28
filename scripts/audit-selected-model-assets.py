#!/usr/bin/env python3
"""Source-only model/media asset reference inventory for the selected 11 graphs.

Only literal file-like widget/API input values are counted. Never publish
filenames, paths, URLs, prompt strings or file contents. No filesystem probe,
download, licence grant or GPU/ComfyUI execution is performed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MODEL_EXT = frozenset({"safetensors", "ckpt", "pt", "pth", "gguf", "onnx", "bin"})
MEDIA_EXT = frozenset({"mp4", "mov", "mkv", "png", "jpg", "jpeg", "webp", "tif", "tiff", "exr", "wav"})
FILE_VALUE = re.compile(
    r"^([A-Za-z0-9_.() -]+(?:[/\\][A-Za-z0-9_.() -]+)*)"
    r"\.([A-Za-z0-9]{2,15})$", re.IGNORECASE
)
NOTE_CLASSES = frozenset({
    "MarkdownNote", "Note", "Label (rgthree)", "Reroute",
    "Fast Groups Muter (rgthree)",
})
MODEL_INPUT_KEYS = frozenset({
    "ckpt_name", "unet_name", "model_name", "vae_name",
    "clip_name", "lora_name", "control_net_name", "upscale_model",
    "model_path", "weights", "model_file",
})


def file_reference(value: object) -> tuple[str, str] | None:
    """Accept only small single-file-like strings, not prompt prose or URLs."""
    if not isinstance(value, str) or not 1 <= len(value) <= 220:
        return None
    if any(ord(char) < 32 for char in value):
        return None
    if value.lower().startswith(("http:", "https:", "data:", "file:")):
        return None
    match = FILE_VALUE.fullmatch(value)
    if match is None:
        return None
    extension = match.group(2).lower()
    if extension in MODEL_EXT:
        return ("model", extension)
    if extension in MEDIA_EXT:
        return ("media", extension)
    return None


def iter_scalar_strings(value: object, depth: int = 0):
    """Bound recursive widget parsing; do not interpret UI links as assets."""
    if depth > 5:
        raise ValueError("Nested widget value exceeds safe audit depth")
    if isinstance(value, str):
        yield value
    elif isinstance(value, (tuple, list)):
        if len(value) > 10000:
            raise ValueError("Oversized widget list")
        for item in value:
            yield from iter_scalar_strings(item, depth + 1)
    elif isinstance(value, dict):
        if len(value) > 10000:
            raise ValueError("Oversized widget map")
        for item in value.values():
            yield from iter_scalar_strings(item, depth + 1)


def graph_nodes(graph: object, fmt: str) -> tuple[list[tuple[str, object]], int]:
    """Return top-level plus explicitly embedded UI subgraph nodes."""
    if not isinstance(graph, dict):
        raise ValueError("Selected graph is not an object")
    if fmt == "api":
        result = []
        for node in graph.values():
            if not isinstance(node, dict) or not isinstance(node.get("class_type"), str):
                raise ValueError("Malformed API node")
            inputs = node.get("inputs", {})
            if not isinstance(inputs, dict):
                raise ValueError("Malformed API node inputs")
            result.append((node["class_type"], inputs))
        if not result:
            raise ValueError("Empty API graph")
        return result, 0
    if fmt != "ui" or not isinstance(graph.get("nodes"), list):
        raise ValueError("Malformed or unknown UI graph")
    result = []
    def ingest(nodes):
        for node in nodes:
            if not isinstance(node, dict) or not isinstance(node.get("type"), str):
                raise ValueError("Malformed UI node")
            result.append((node["type"], node.get("widgets_values", [])))
    ingest(graph["nodes"])
    defs = graph.get("definitions", {})
    if not isinstance(defs, dict):
        raise ValueError("Malformed UI definitions")
    subgraphs = defs.get("subgraphs", [])
    if not isinstance(subgraphs, list):
        raise ValueError("Malformed embedded subgraphs")
    embedded = 0
    for sub in subgraphs:
        if not isinstance(sub, dict) or not isinstance(sub.get("nodes"), list):
            raise ValueError("Malformed embedded UI subgraph")
        embedded += len(sub["nodes"])
        ingest(sub["nodes"])
    if not result:
        raise ValueError("Empty UI graph")
    return result, embedded


def summarize_graph(graph: object, fmt: str) -> dict:
    """Return counts only; source filenames/paths never enter the result."""
    nodes, embedded = graph_nodes(graph, fmt)
    refs = Counter()
    values_seen = {"model": set(), "media": set()}
    dynamic = 0
    skipped_notes = 0
    for class_name, fields in nodes:
        if class_name in NOTE_CLASSES:
            skipped_notes += 1
            continue
        # For API inputs, check model loader fields without a recognizable
        # file extension. These are unresolved, not proof of a missing file.
        if fmt == "api" and isinstance(fields, dict):
            for key, value in fields.items():
                if (key in MODEL_INPUT_KEYS and isinstance(value, str)
                        and not file_reference(value)):
                    dynamic += 1
        for value in iter_scalar_strings(fields):
            classification = file_reference(value)
            if classification is None:
                continue
            kind, ext = classification
            refs[(kind, ext)] += 1
            values_seen[kind].add(value)
    return {
        "graph_format": fmt,
        "total_nodes_including_embedded": len(nodes),
        "embedded_node_instances": embedded,
        "editor_or_note_nodes_skipped": skipped_notes,
        "model_reference_instances": sum(v for (kind, _), v in refs.items() if kind == "model"),
        "media_reference_instances": sum(v for (kind, _), v in refs.items() if kind == "media"),
        "distinct_literal_model_values": len(values_seen["model"]),
        "distinct_literal_media_values": len(values_seen["media"]),
        "model_reference_extensions": {
            ext: refs[("model", ext)] for ext in sorted(MODEL_EXT)
            if refs[("model", ext)]
        },
        "media_reference_extensions": {
            ext: refs[("media", ext)] for ext in sorted(MEDIA_EXT)
            if refs[("media", ext)]
        },
        "api_model_inputs_without_recognized_literal_extension": dynamic,
        "source_files_exist_checked": False,
        "model_licences_verified": False,
        "model_weights_downloaded_or_executed": False,
        "all_asset_references_discovered": False,
    }


def audit(root: Path = ROOT) -> dict:
    """Require the canonical 11-file source/sidecar/manifest preflight."""
    preflight = root / "runpod" / "commercial-compatible" / "prepare.py"
    if preflight.is_symlink() or not preflight.is_file():
        raise ValueError("Missing canonical source preflight")
    spec = importlib.util.spec_from_file_location("osf_model_asset_preflight", preflight)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load canonical source preflight")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if root != ROOT:
        raise ValueError("Canonical preflight operates only on its own source checkout")
    approved, manifest = mod.choose_files()
    paths = sorted(path for path in approved if path.endswith(".json"))
    if len(paths) != 11 or len(manifest) != 11:
        raise ValueError("Approved subset differs from eleven workflows")
    rows = {}
    aggregate = Counter()
    for path in paths:
        row = summarize_graph(json.loads(approved[path]), manifest[path]["format"])
        rows[path] = row
        aggregate["model_reference_instances"] += row["model_reference_instances"]
        aggregate["media_reference_instances"] += row["media_reference_instances"]
        aggregate["embedded_node_instances"] += row["embedded_node_instances"]
        aggregate["dynamic_model_input_instances"] += row[
            "api_model_inputs_without_recognized_literal_extension"
        ]
    return {
        "schema": "osf-selected-11-asset-reference-summary-v1",
        "selected_workflow_count": 11,
        "per_workflow": rows,
        "aggregate_counts": dict(sorted(aggregate.items())),
        "filenames_or_paths_disclosed": False,
        "only_recognized_literal_extensions_counted": True,
        "weights_or_media_installed": False,
        "file_existence_qualified": False,
        "licence_or_runtime_qualification": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    data = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output is None:
        print(data, end="")
    else:
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("Refusing to overwrite an existing audit")
        args.output.write_text(data, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
