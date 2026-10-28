#!/usr/bin/env python3
"""Fail-closed source-only binding audit for pinned ComfyUI-SAM3 API probe.

Never imports third-party Python or executes LoadSAM3Model; that class
downloads missing checkpoints. Source is read as AST from an exact Git SHA.
No GPU, model weights, media or external requests are required by this script.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_SHA = "de0ff5d2c2ea435d29f800abfa568cffdfb94773"
WORKFLOW = "workflows/commercial-compatible/sam3_custompkg_probe.json"
SOURCES = {
    "LoadSAM3Model": "nodes/load_model.py",
    "SAM3CreatePoint": "nodes/segmentation.py",
    "SAM3CombinePoints": "nodes/segmentation.py",
    "SAM3Segmentation": "nodes/segmentation.py",
}
SCHEMAS = {
    "LoadSAM3Model": (
        {"precision": "COMBO", "compile": "BOOLEAN"},
        ("SAM3_MODEL_CONFIG",),
    ),
    "SAM3CreatePoint": (
        {"x": "FLOAT", "y": "FLOAT", "is_foreground": "BOOLEAN"},
        ("SAM3_POINT_PROMPT",),
    ),
    "SAM3CombinePoints": (
        {"point_" + str(i): "SAM3_POINT_PROMPT" for i in range(1, 11)},
        ("SAM3_POINTS_PROMPT",),
    ),
    "SAM3Segmentation": (
        {
            "sam3_model_config": "SAM3_MODEL_CONFIG",
            "image": "IMAGE",
            "positive_points": "SAM3_POINTS_PROMPT",
            "negative_points": "SAM3_POINTS_PROMPT",
            "box": "SAM3_BOXES_PROMPT",
            "refinement_iterations": "INT",
            "use_multimask": "BOOLEAN",
            "output_best_mask": "BOOLEAN",
        },
        ("MASK", "MASK", "IMAGE", "STRING", "STRING"),
    ),
}
EXPECTED_WORKFLOW = {
    "1": "LoadSAM3Model",
    "2": "LoadImage",
    "3": "SAM3CreatePoint",
    "4": "SAM3CombinePoints",
    "5": "SAM3Segmentation",
    "6": "MaskToImage",
    "7": "SaveImage",
    "8": "SaveImage",
}
# All five links from third-party producers must match the pinned
# upstream schema output type, including image visualization at slot 2.
PINNED_LINKS = (
    ("4", "point_1", "3", 0, "SAM3_POINT_PROMPT"),
    ("5", "sam3_model_config", "1", 0, "SAM3_MODEL_CONFIG"),
    ("5", "positive_points", "4", 0, "SAM3_POINTS_PROMPT"),
    ("6", "mask", "5", 0, "MASK"),
    ("8", "images", "5", 2, "IMAGE"),
)
# These come from ComfyUI core, not from third-party schema extraction.
CORE_LINKS = (
    ("5", "image", "2", 0),
    ("7", "images", "6", 0),
)


def _literal(value: ast.AST):
    try:
        return ast.literal_eval(value)
    except (ValueError, TypeError, SyntaxError) as exc:
        raise ValueError("Nonliteral schema name in pinned source") from exc


def _keyword(call: ast.Call, name: str) -> ast.AST | None:
    return next((kw.value for kw in call.keywords if kw.arg == name), None)


def _get_io_type(method: ast.Call) -> str:
    if not isinstance(method.func, ast.Attribute) or method.func.attr not in ("Input", "Output"):
        raise ValueError("Unexpected ComfyUI schema Input/Output construction")
    receiver = method.func.value
    if isinstance(receiver, ast.Attribute) and isinstance(receiver.value, ast.Name) and receiver.value.id == "io":
        return {"Combo": "COMBO", "Boolean": "BOOLEAN", "Float": "FLOAT",
                "Int": "INT", "Image": "IMAGE", "Mask": "MASK",
                "String": "STRING"}.get(receiver.attr) or _raise_type()
    if (isinstance(receiver, ast.Call) and isinstance(receiver.func, ast.Attribute)
            and isinstance(receiver.func.value, ast.Name)
            and receiver.func.value.id == "io"
            and receiver.func.attr == "Custom" and receiver.args):
        name = _literal(receiver.args[0])
        if isinstance(name, str) and name.startswith("SAM3_"):
            return name
    raise ValueError("Unexpected custom type in pinned SAM3 node schema")


def _raise_type():
    raise ValueError("Unreviewed ComfyUI schema IO type")


def parse_class_schema(source: str, class_id: str) -> dict:
    module = ast.parse(source)
    classes = [node for node in module.body
               if isinstance(node, ast.ClassDef) and node.name == class_id]
    if len(classes) != 1:
        raise ValueError("Missing or duplicate pinned SAM3 node class: " + class_id)
    definitions = [node for node in classes[0].body
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and node.name == "define_schema"]
    if len(definitions) != 1:
        raise ValueError("Missing pinned define_schema for " + class_id)
    schemas = [node.value for node in ast.walk(definitions[0])
               if isinstance(node, ast.Return) and isinstance(node.value, ast.Call)
               and isinstance(node.value.func, ast.Attribute)
               and node.value.func.attr == "Schema"]
    if len(schemas) != 1:
        raise ValueError("Unexpected pinned SAM3 schema function")
    spec = schemas[0]
    node_id = _keyword(spec, "node_id")
    if node_id is None or _literal(node_id) != class_id:
        raise ValueError("Pinned schema node_id differs from class")
    inputs_ast = _keyword(spec, "inputs")
    outputs_ast = _keyword(spec, "outputs")
    if not isinstance(inputs_ast, (ast.List, ast.Tuple)) or not isinstance(outputs_ast, (ast.List, ast.Tuple)):
        raise ValueError("Pinned SAM3 schema lists are malformed")
    inputs = {}
    required = []
    for item in inputs_ast.elts:
        if not isinstance(item, ast.Call) or not item.args:
            raise ValueError("Pinned SAM3 input is not a direct io declaration")
        name = _literal(item.args[0])
        if not isinstance(name, str) or name in inputs:
            raise ValueError("Duplicate/bad pinned SAM3 input name")
        inputs[name] = _get_io_type(item)
        optional_kw = _keyword(item, "optional")
        if optional_kw is None or _literal(optional_kw) is not True:
            required.append(name)
    outputs = []
    for item in outputs_ast.elts:
        if not isinstance(item, ast.Call):
            raise ValueError("Pinned SAM3 output is not a direct io declaration")
        outputs.append(_get_io_type(item))
    expected_inputs, expected_outputs = SCHEMAS[class_id]
    if inputs != expected_inputs or tuple(outputs) != expected_outputs:
        raise ValueError("Pinned SAM3 input/output schema differs: " + class_id)
    return {"node_id": class_id, "inputs": inputs,
            "required_inputs": required, "outputs": outputs}


def check_graph_bindings(graph: object, schemas: dict) -> dict:
    if not isinstance(graph, dict) or {key: item.get("class_type") for key, item in graph.items()
                                       if isinstance(item, dict)} != EXPECTED_WORKFLOW:
        raise ValueError("SAM3 probe class layout differs from reviewed API graph")
    for node_id, spec in graph.items():
        if not isinstance(spec, dict) or not isinstance(spec.get("inputs"), dict):
            raise ValueError("SAM3 probe has malformed API node inputs")
        if spec["class_type"] in schemas:
            inputs = spec["inputs"]
            declaration = schemas[spec["class_type"]]
            if not set(declaration["required_inputs"]).issubset(inputs):
                raise ValueError("SAM3 probe missing required upstream input")
            if not set(inputs).issubset(declaration["inputs"]):
                raise ValueError("SAM3 probe references unreviewed upstream input")
    for target, field, source, slot, output_type in PINNED_LINKS:
        if graph[target]["inputs"].get(field) != [source, slot]:
            raise ValueError("SAM3 probe third-party edge differs: " + field)
        actual = schemas[graph[source]["class_type"]]["outputs"]
        if slot >= len(actual) or actual[slot] != output_type:
            raise ValueError("SAM3 probe upstream output slot/type mismatch")
        if target in ("4", "5"):
            target_type = schemas[graph[target]["class_type"]]["inputs"][field]
            if target_type != output_type:
                raise ValueError("SAM3 probe target slot type mismatch")
    for target, field, source, slot in CORE_LINKS:
        if graph[target]["inputs"].get(field) != [source, slot]:
            raise ValueError("SAM3 probe ComfyUI core edge differs")
    # All actual links must be in the reviewed set, to prevent extra unverified
    # links quietly entering this limited check.
    expected = {(target, field) for target, field, *_ in PINNED_LINKS + CORE_LINKS}
    actual = {(node_id, field)
              for node_id, node in graph.items()
              for field, value in node["inputs"].items()
              if isinstance(value, list)}
    if actual != expected:
        raise ValueError("SAM3 probe has additional or missing unreviewed API links")
    return {
        "api_node_instances": 8,
        "third_party_node_instances": 4,
        "verified_third_party_edges": len(PINNED_LINKS),
        "unverified_core_source_edges": len(CORE_LINKS),
        "exact_graph_class_layout": True,
        "all_required_third_party_inputs_present": True,
        "full_graph_executable": False,
    }


def _read_trusted_file(root: Path, relative: str) -> str:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or symlinked pinned upstream file: " + relative)
    return path.read_text(encoding="utf-8")


def assert_auto_download_hazard(source: str) -> bool:
    """Capture downloader reachability without calling any upstream code."""
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == "LoadSAM3Model":
            methods = [x for x in node.body if isinstance(x, ast.FunctionDef)]
            execute = next((x for x in methods if x.name == "execute"), None)
            download = next((x for x in methods if x.name == "_download_from_huggingface"), None)
            if execute and download:
                called = any(isinstance(x, ast.Call)
                             and isinstance(x.func, ast.Attribute)
                             and x.func.attr == "_download_from_huggingface"
                             for x in ast.walk(execute))
                if called:
                    return True
    raise ValueError("Pinned SAM3 auto-download behaviour changed; re-review required")


def audit(upstream: Path, core_root: Path, repo: Path = ROOT) -> dict:
    if upstream.is_symlink() or not upstream.is_dir():
        raise ValueError("Invalid pinned SAM3 source directory")
    revision = subprocess.run(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True, timeout=12,
    ).stdout.strip()
    if revision != UPSTREAM_SHA:
        raise ValueError("ComfyUI-SAM3 source revision differs from canonical pin")
    lock = (repo / "DEPENDENCIES.lock").read_text(encoding="utf-8")
    block = lock.split(WORKFLOW + ":", 1)
    if len(block) != 2:
        raise ValueError("Missing probe entry in canonical lock")
    selection = block[1].split("\nworkflows/", 1)[0]
    if (not re.search(r"name:\s+ComfyUI-SAM3\s*\n\s+commit:\s+" + UPSTREAM_SHA, selection)
            or "commercial_status: commercial-compatible" not in selection):
        raise ValueError("SAM3 custom package pin/status differs from canonical lock")
    if "GNU GENERAL PUBLIC LICENSE" not in _read_trusted_file(upstream, "LICENSE").upper():
        raise ValueError("Pinned SAM3 custom package GPL licence not present")
    content = {path: _read_trusted_file(upstream, path) for path in set(SOURCES.values())}
    schemas = {name: parse_class_schema(content[path], name)
               for name, path in SOURCES.items()}
    if not assert_auto_download_hazard(content["nodes/load_model.py"]):
        raise ValueError("Missing explicit SAM3 model downloader risk")
    graph = json.loads((repo / WORKFLOW).read_text(encoding="utf-8"))
    links = check_graph_bindings(graph, schemas)
    # The original third-party-only parser counted two core-sourced edges
    # as unverified. The separate exact-core AST gate must settle them.
    from audit_sam3_custompkg_core_links import verify_pinned_core
    core = verify_pinned_core(core_root, graph, schemas)
    core_edges = core["native_binding"]
    if (links["unverified_core_source_edges"] != 2
            or core_edges["previously_unverified_core_source_edges_resolved"] != 2
            or core_edges["typed_edges_touching_core_nodes"] != 4):
        raise ValueError("Core edge audit count disagrees with source-only baseline")
    links["verified_core_source_edges"] = 2
    links["unverified_core_source_edges"] = 0
    links["typed_edges_touching_core_nodes"] = 4
    return {
        "schema": "osf-sam3-custompkg-pinned-source-api-contract-v1",
        "workflow": WORKFLOW,
        "canonical_pin": revision,
        "upstream_package": "PozzettiAndrea/ComfyUI-SAM3",
        "third_party_license": "GPL-3.0",
        "node_types_checked": sorted(schemas),
        "upstream_source_sha256": {
            path: hashlib.sha256(content[path].encode("utf-8")).hexdigest()
            for path in sorted(content)
        },
        "bindings": links,
        "pinned_native_comfyui_core": core,
        "loader_downloads_absent_model_weights": True,
        "package_import_attempted": False,
        "checkpoint_download_attempted": False,
        "model_weights_downloaded": False,
        "gpu_or_model_inference_qualified": False,
        "source_schema_snapshot_only": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream-dir", type=Path, required=True)
    parser.add_argument("--core-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.upstream_dir, args.core_dir)
    rendered = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output:
        if args.output.is_symlink() or args.output.exists():
            raise ValueError("Output evidence path already exists or is a symlink")
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
