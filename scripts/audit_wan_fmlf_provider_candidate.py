#!/usr/bin/env python3
"""Read-only audit of the pinned, currently unlicensed Wan22FMLF source candidate.

Never imports or executes upstream Python. Never installs models or custom nodes.
Matching class/schema names do NOT imply production rights or runtime acceptance.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess

UPSTREAM = "wallen0322/ComfyUI-Wan22FMLF"
PIN = "7140cd224396aff9fd909ab0041c3fbf81b92b0c"
SOURCE_FILES = {
    "WanFirstMiddleLastFrameToVideo": "wan_first_middle_last.py",
    "WanFourFrameReferenceUltimate": "wan_4_frame_ultimate.py",
    "WanMultiFrameRefToVideo": "wan_multi_frame.py",
}
WORKFLOWS = (
    "wan22_fmlf_first_middle_last_frame.json",
    "video_wan2_2_14B_fmlf2v.json",
)
EXPECTED_COUNTS = {
    "WanFirstMiddleLastFrameToVideo": 2,
    "WanFourFrameReferenceUltimate": 1,
    "WanMultiFrameRefToVideo": 1,
}
IO_TYPES = {
    "Conditioning": "CONDITIONING",
    "Vae": "VAE",
    "Image": "IMAGE",
    "ClipVisionOutput": "CLIP_VISION_OUTPUT",
    "Int": "INT",
    "Float": "FLOAT",
    "Combo": "COMBO",
    "String": "STRING",
    "Latent": "LATENT",
}
OUTPUTS = (
    ("positive_high", "CONDITIONING"),
    ("positive_low", "CONDITIONING"),
    ("negative", "CONDITIONING"),
    ("latent", "LATENT"),
)
LICENCE_MARKERS = {"license", "licence", "copying", "notice", "unlicense"}


def _literal_str(value: ast.AST, description: str) -> str:
    if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
        raise ValueError("Nonliteral provider schema " + description)
    return value.value


def _schema_keyword(call: ast.Call, key: str) -> ast.AST:
    matches = [kw.value for kw in call.keywords if kw.arg == key]
    if len(matches) != 1:
        raise ValueError("Missing/nonunique provider schema " + key)
    return matches[0]


def _io_port(node: ast.AST, *, output: bool) -> tuple[str, str]:
    if (not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Attribute)
            or node.func.attr != ("Output" if output else "Input")
            or not isinstance(node.func.value, ast.Attribute)
            or not isinstance(node.func.value.value, ast.Name)
            or node.func.value.value.id != "io"
            or node.func.value.attr not in IO_TYPES):
        raise ValueError("Unreviewed provider schema port")
    port_type = IO_TYPES[node.func.value.attr]
    if output:
        names = [kw.value for kw in node.keywords if kw.arg == "display_name"]
        if len(names) != 1:
            raise ValueError("Provider output name not explicitly declared")
        name = _literal_str(names[0], "output name")
    else:
        if not node.args:
            raise ValueError("Provider input name missing")
        name = _literal_str(node.args[0], "input name")
    return name, port_type


def schema_from_source(source: str, class_name: str) -> dict:
    tree = ast.parse(source)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == class_name]
    if len(classes) != 1:
        raise ValueError("Missing/nonunique provider class " + class_name)
    methods = [node for node in classes[0].body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name == "define_schema"]
    if len(methods) != 1:
        raise ValueError("Missing/nonunique provider define_schema")
    returns = [node for node in ast.walk(methods[0])
               if isinstance(node, ast.Return)]
    if (len(returns) != 1 or not isinstance(returns[0].value, ast.Call)
            or not isinstance(returns[0].value.func, ast.Attribute)
            or not isinstance(returns[0].value.func.value, ast.Name)
            or returns[0].value.func.value.id != "io"
            or returns[0].value.func.attr != "Schema"):
        raise ValueError("Unreviewed provider schema construction")
    schema = returns[0].value
    node_id = _literal_str(_schema_keyword(schema, "node_id"), "node id")
    if node_id != class_name:
        raise ValueError("Provider schema node id differs from class")
    ports = {}
    for kind in ("inputs", "outputs"):
        group = _schema_keyword(schema, kind)
        if not isinstance(group, (ast.List, ast.Tuple)):
            raise ValueError("Nonliteral provider schema " + kind)
        data = [_io_port(node, output=(kind == "outputs"))
                for node in group.elts]
        if len(data) != len(set(name for name, _ in data)):
            raise ValueError("Duplicate provider " + kind)
        ports[kind] = data
    if tuple(ports["outputs"]) != OUTPUTS:
        raise ValueError("Provider outputs differ from reviewed API contract")
    return {"class": class_name, **ports}


def validate_exported_node(node: dict, provider: dict) -> dict:
    if node.get("type") != provider["class"]:
        raise ValueError("Wrong provider class in UI export")
    if not isinstance(node.get("inputs"), list) or not isinstance(node.get("outputs"), list):
        raise ValueError("Incomplete UI exporter socket records")
    for field in ("inputs", "outputs"):
        sockets = node[field]
        if any(not isinstance(item, dict) for item in sockets):
            raise ValueError("Malformed UI export socket")
        actual = [(item.get("name"), item.get("type")) for item in sockets]
        expected = provider[field]
        if len(actual) != len(set(name for name, _ in actual)):
            raise ValueError("Duplicate UI socket name")
        if set(actual) != set(expected):
            missing = sorted(set(expected) - set(actual))
            extra = sorted(set(actual) - set(expected))
            raise ValueError(f"Provider/UI {field} mismatch: missing={missing}, extra={extra}")
    return {
        "class": provider["class"],
        "input_sockets": len(provider["inputs"]),
        "output_sockets": len(provider["outputs"]),
        "schema_name_type_parity": True,
    }


def audit(repo_root: Path, source_root: Path) -> dict:
    head = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True, timeout=15,
    ).stdout.strip()
    if head != PIN:
        raise ValueError("Provider revision is not the exact reviewed pin")
    if source_root.is_symlink() or not source_root.is_dir():
        raise ValueError("Missing or symlinked candidate source root")
    present_licences = [p.name for p in source_root.iterdir()
                        if p.is_file() and
                        p.stem.lower() in LICENCE_MARKERS]
    if present_licences:
        raise ValueError("Candidate licensing changed; review licence before proceeding")
    schemas = {}
    hashes = {}
    for class_name, rel in SOURCE_FILES.items():
        path = source_root / rel
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing/symlinked source file: " + rel)
        content = path.read_text(encoding="utf-8")
        schemas[class_name] = schema_from_source(content, class_name)
        hashes[rel] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    # This optional registration path must be reviewed separately at runtime.
    registration = source_root / "__init__.py"
    if registration.is_symlink() or not registration.is_file():
        raise ValueError("Missing source registration entrypoint")
    init_content = registration.read_text(encoding="utf-8")
    if not all(name in init_content for name in SOURCE_FILES):
        raise ValueError("Provider registration entrypoint no longer names classes")
    hashes["__init__.py"] = hashlib.sha256(init_content.encode()).hexdigest()

    counts = dict.fromkeys(SOURCE_FILES, 0)
    details = []
    for filename in WORKFLOWS:
        path = repo_root / "workflows" / "commercial-compatible" / filename
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing/symlinked selected workflow")
        raw = path.read_bytes()
        graph = json.loads(raw)
        nodes = graph.get("nodes") if isinstance(graph, dict) else None
        if not isinstance(nodes, list):
            raise ValueError("Selected Wan export is no longer a UI node graph")
        entries = []
        for node in nodes:
            if not isinstance(node, dict):
                raise ValueError("Malformed UI graph node")
            node_type = node.get("type")
            if node_type in schemas:
                entries.append(validate_exported_node(node, schemas[node_type]))
                counts[node_type] += 1
        if not entries:
            raise ValueError("Expected Wan candidate class absent from " + filename)
        details.append({
            "workflow": filename,
            "public_workflow_sha256": hashlib.sha256(raw).hexdigest(),
            "provider_node_instances": entries,
        })
    if counts != EXPECTED_COUNTS:
        raise ValueError("Wan provider class occurrences differ from audited baseline")
    return {
        "schema": "osf-wan-fmlf-unlicensed-provider-candidate-v1",
        "candidate_repository": UPSTREAM,
        "candidate_exact_commit": head,
        "source_sha256": hashes,
        "workflow_bindings": details,
        "class_occurrences": counts,
        "source_identified": True,
        "source_ui_socket_name_and_type_parity": True,
        "source_entrypoint_mentions_all_classes": True,
        "licence_file_detected": False,
        "licence_status": "no-licence-file-in-reviewed-revision",
        "commercial_redistribution_or_use_cleared": False,
        "node_import_registration_qualified": False,
        "api_prompt_conversion_qualified": False,
        "model_inference_qualified": False,
        "eleven_workflow_acceptance": False,
        "production_install_allowed_by_this_audit": False,
    }


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    cli.add_argument("--source-root", type=Path, required=True)
    cli.add_argument("--report", type=Path, required=True)
    args = cli.parse_args()
    result = audit(args.repo_root, args.source_root)
    with args.report.open("x", encoding="utf-8") as f:
        json.dump(result, f, sort_keys=True, indent=2)
        f.write("\n")
    print("Wan provider source/socket audit passed; licence and runtime remain HOLD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
