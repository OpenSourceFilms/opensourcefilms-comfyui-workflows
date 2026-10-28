"""Validate real pinned ComfyUI API graph link socket types, without inference.

Uses the actual /object_info registry from the isolated, already pinned
CPU server, not a guess from class names. All four selected API exports
are inspected. Uninstalled providers and wildcard sockets stay explicit
HOLDs, rather than being interpreted as compatibility.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_NAMES = (
    "sam3_custompkg_probe",
    "step4_5_sam3_mask",
    "step6_animation_mode",
    "step7_replacement_mode",
)
NATIVE_API_NAMES = API_NAMES[1:]


def _recorded_type(entry: object, *, label: str) -> str | None:
    """Return one typed socket, or None for an enum/dynamic specification."""
    if not isinstance(entry, (list, tuple)) or not entry:
        raise ValueError("Invalid registry input metadata at " + label)
    typ = entry[0]
    if isinstance(typ, str) and typ:
        return typ
    if isinstance(typ, list) and typ and all(isinstance(x, str) for x in typ):
        return None
    raise ValueError("Unrecognized registry socket type at " + label)


def _declared_input(info: dict, name: str, field: str) -> str | None:
    entry = info.get(name)
    if not isinstance(entry, dict):
        raise ValueError("Expected registered destination class: " + name)
    inputs = entry.get("input")
    if not isinstance(inputs, dict):
        raise ValueError("Malformed object_info inputs: " + name)
    matching = []
    for group in ("required", "optional"):
        sockets = inputs.get(group, {})
        if not isinstance(sockets, dict):
            raise ValueError("Malformed registry socket group: " + name)
        if field in sockets:
            matching.append(sockets[field])
    if len(matching) != 1:
        raise ValueError("Missing or duplicated linked input: " + name + "." + field)
    return _recorded_type(matching[0], label=name + "." + field)


def _source_output(info: dict, name: str, slot: int) -> str:
    entry = info.get(name)
    if not isinstance(entry, dict):
        raise ValueError("Expected registered producer class: " + name)
    outputs = entry.get("output")
    if not isinstance(outputs, list) or slot >= len(outputs):
        raise ValueError("Missing live producer output slot: " + name)
    typ = outputs[slot]
    if not isinstance(typ, str) or not typ:
        raise ValueError("Malformed live producer output type: " + name)
    return typ


def _linked_type_match(produced: str, accepted: str | None,
                       *, destination_class: str, field: str) -> str:
    """Require a literal type match, except one reviewed native union socket.

    Pinned public ComfyUI exposes SCAIL2ColoredMask.ref_track_data as the
    comma-separated runtime multi-type string SAM3_TRACK_DATA,MASK.
    Source-schema audits denote that same exact union with a pipe.
    Admit either representation only at that destination. Treat every
    other composite producer/input type as unresolved, not compatible.
    """
    if accepted is None or produced == "*" or accepted == "*":
        return "unresolved_dynamic"
    # A producer advertising a composite type is not a single statically
    # established output; never treat a matching composite string as exact.
    if "," in produced or "|" in produced:
        return "unresolved_dynamic"
    if "," in accepted or "|" in accepted:
        if (destination_class == "SCAIL2ColoredMask"
                and field == "ref_track_data"
                and accepted in ("SAM3_TRACK_DATA,MASK", "SAM3_TRACK_DATA|MASK")):
            possibilities = ("SAM3_TRACK_DATA", "MASK")
        else:
            # Only the one reviewed native union is admitted. A new union
            # syntax/provider needs a new source audit before acceptance.
            return "unresolved_dynamic"
    else:
        possibilities = (accepted,)
    if produced in possibilities:
        return "exact_type_match"
    if "*" in possibilities:
        return "unresolved_dynamic"
    return "incompatible"


def analyze_live_api_links(registry: object, graph_by_name: object) -> dict:
    """Return only class and socket findings, never workflow input values."""
    if not isinstance(registry, dict) or not registry:
        raise ValueError("Missing real ComfyUI object_info")
    if not isinstance(graph_by_name, dict) or set(graph_by_name) != set(API_NAMES):
        raise ValueError("Expected exactly four selected API graphs")
    overall = Counter()
    results = []
    for name in API_NAMES:
        graph = graph_by_name[name]
        if not isinstance(graph, dict) or not graph:
            raise ValueError("Malformed selected API graph: " + name)
        unregistered = set()
        statuses = Counter()
        incompatible = []
        for node_id, node in graph.items():
            if not isinstance(node, dict) or not isinstance(node.get("class_type"), str):
                raise ValueError("Invalid API node class in " + name)
            class_name = node["class_type"]
            if class_name not in registry:
                unregistered.add(class_name)
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                raise ValueError("Missing API node inputs in " + name)
            for field, link in inputs.items():
                if not isinstance(link, list):
                    continue
                if (len(link) != 2 or not isinstance(link[0], str)
                        or type(link[1]) is not int or link[1] < 0):
                    raise ValueError("Invalid selected API link shape in " + name)
                upstream = graph.get(link[0])
                if not isinstance(upstream, dict) or not isinstance(upstream.get("class_type"), str):
                    raise ValueError("Absent API link producer in " + name)
                source_name = upstream["class_type"]
                if source_name not in registry or class_name not in registry:
                    statuses["unregistered_provider"] += 1
                    continue
                source_type = _source_output(registry, source_name, link[1])
                target_type = _declared_input(registry, class_name, field)
                category = _linked_type_match(
                    source_type, target_type,
                    destination_class=class_name, field=field,
                )
                statuses[category] += 1
                if category == "incompatible":
                    incompatible.append({
                        "source_class": source_name,
                        "source_output_type": source_type,
                        "destination_class": class_name,
                        "destination_field": field,
                        "destination_input_type": target_type,
                    })
        overall.update(statuses)
        results.append({
            "workflow": name,
            "api_node_count": len(graph),
            "linked_edges": sum(statuses.values()),
            "typed_exact_links": statuses["exact_type_match"],
            "dynamic_unverified_links": statuses["unresolved_dynamic"],
            "unregistered_provider_links": statuses["unregistered_provider"],
            "incompatible_links": statuses["incompatible"],
            "unregistered_class_names": sorted(unregistered),
            "incompatibilities": incompatible,
            "model_weights_loaded": False,
            "api_graph_executed": False,
        })
    if sum(row["api_node_count"] for row in results) != 60:
        raise ValueError("Changed selected-four API node inventory")
    if sum(row["linked_edges"] for row in results) != 82:
        raise ValueError("Changed selected-four API link count")
    return {
        "schema": "osf-selected-four-live-api-link-types-v1",
        "api_workflows": len(API_NAMES),
        "api_nodes": 60,
        "api_links": 82,
        "registered_exact_type_links": overall["exact_type_match"],
        "dynamic_type_links_unverified": overall["unresolved_dynamic"],
        "missing_provider_links_unverified": overall["unregistered_provider"],
        "incompatible_registered_links": overall["incompatible"],
        "workflows": results,
        "all_four_api_graphs_executable": False,
        "all_eleven_workflows_executable": False,
        "gpu_or_model_inference_qualified": False,
    }


def load_selected_api_graphs(root: Path = ROOT) -> dict:
    """Load only reviewed selection; source paths and bytes never enter report."""
    graphs = {}
    for name in API_NAMES:
        path = root / "workflows" / "commercial-compatible" / (name + ".json")
        graphs[name] = json.loads(path.read_text(encoding="utf-8"))
    return graphs
