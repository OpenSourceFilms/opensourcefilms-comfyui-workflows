#!/usr/bin/env python3
"""Pinned-source, no-import VHS_LoadVideo -> native SAM3 IMAGE edge audit.

Reads public graph and pinned upstream source *as data* only. Never loads the
saved video strings, imports external Python, downloads models, or runs nodes.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
VHS_SHA = "2984ec4c4b93292421888f38db74a5e8802a8ff8"
GRAPHS = {
    "step4_5_sam3_mask": {( "4", "images", 0), ("10", "images", 0)},
    "step6_animation_mode": {("4", "images", 0), ("20", "pose_video", 0)},
    "step7_replacement_mode": {("4", "images", 0), ("20", "pose_video", 0)},
}
SAVED_INPUT_NAMES = frozenset({
    "video", "force_rate", "custom_width", "custom_height",
    "frame_load_cap", "skip_first_frames", "select_every_nth", "format",
})
NATIVE_SCHEMA_PATH = ROOT / "scripts" / "audit_sam3_scail_api_bindings.py"


def _literal(expr: ast.AST):
    try:
        return ast.literal_eval(expr)
    except (TypeError, ValueError, SyntaxError) as exc:
        raise ValueError("Unreviewed upstream AST literal") from exc


def _assignment(tree: ast.AST, name: str) -> ast.AST:
    matches = [
        assign.value for assign in ast.walk(tree)
        if isinstance(assign, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in assign.targets
        )
    ]
    if len(matches) != 1:
        raise ValueError("Pinned VHS source assignment missing or ambiguous: " + name)
    return matches[0]


def _class(tree: ast.AST, name: str) -> ast.ClassDef:
    matches = [node for node in tree.body
               if isinstance(node, ast.ClassDef) and node.name == name]
    if len(matches) != 1:
        raise ValueError("Pinned VHS class declaration missing or ambiguous")
    return matches[0]


def check_vhs_ast(nodes_source: str, load_source: str, utils_source: str) -> dict:
    """Require exact published registration, output and VAE-dependent branch."""
    nodes = ast.parse(nodes_source)
    load = ast.parse(load_source)
    utils = ast.parse(utils_source)

    mapping = _assignment(nodes, "NODE_CLASS_MAPPINGS")
    if not isinstance(mapping, ast.Dict):
        raise ValueError("Pinned VHS class registry not a literal dictionary")
    named = {}
    for key, value in zip(mapping.keys, mapping.values):
        if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
            raise ValueError("Nonliteral VHS mapping key")
        if key.value in named:
            raise ValueError("Duplicate VHS class registry key")
        named[key.value] = value
    registered = named.get("VHS_LoadVideo")
    if not isinstance(registered, ast.Name) or registered.id != "LoadVideoUpload":
        raise ValueError("VHS_LoadVideo class registration drifted")

    union = _assignment(utils, "imageOrLatent")
    if (not isinstance(union, ast.Call)
            or not isinstance(union.func, ast.Name)
            or union.func.id != "MultiInput"
            or len(union.args) != 2
            or _literal(union.args[0]) != "IMAGE"
            or _literal(union.args[1]) != ["IMAGE", "LATENT"]):
        raise ValueError("Pinned VHS image/latent output union differs")

    uploader = _class(load, "LoadVideoUpload")
    returns = _assignment(uploader, "RETURN_TYPES")
    if not isinstance(returns, ast.Tuple) or len(returns.elts) != 4:
        raise ValueError("Pinned VHS output tuple differs")
    if not isinstance(returns.elts[0], ast.Name) or returns.elts[0].id != "imageOrLatent":
        raise ValueError("Pinned VHS first output no longer imageOrLatent")
    if [_literal(el) for el in returns.elts[1:]] != [
        "INT", "AUDIO", "VHS_VIDEOINFO"
    ]:
        raise ValueError("Pinned VHS secondary output slots differ")
    if _literal(_assignment(uploader, "RETURN_NAMES")) != (
            "IMAGE", "frame_count", "audio", "video_info"):
        raise ValueError("Pinned VHS named output slots differ")

    methods = [node for node in uploader.body
               if isinstance(node, ast.FunctionDef) and node.name == "load_video"]
    if len(methods) != 1 or not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "load_video"
            for node in ast.walk(methods[0])):
        raise ValueError("Pinned VHS upload wrapper no longer delegates to load_video")

    functions = [node for node in load.body
                 if isinstance(node, ast.FunctionDef) and node.name == "load_video"]
    if len(functions) != 1:
        raise ValueError("Pinned VHS media decode function changed")
    branches = [node for node in ast.walk(functions[0])
                if isinstance(node, ast.If)
                and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name)
                and node.test.left.id == "vae"
                and len(node.test.ops) == 1
                and isinstance(node.test.ops[0], ast.Is)
                and len(node.test.comparators) == 1
                and isinstance(node.test.comparators[0], ast.Constant)
                and node.test.comparators[0].value is None]
    if len(branches) != 1:
        raise ValueError("Pinned VHS no-VAE output branch changed")
    branch = branches[0]
    direct_images = any(
        isinstance(x, ast.Return) and isinstance(x.value, ast.Tuple)
        and x.value.elts and isinstance(x.value.elts[0], ast.Name)
        and x.value.elts[0].id == "images"
        for node in branch.body for x in ast.walk(node)
    )
    latent_images = any(
        isinstance(x, ast.Return) and isinstance(x.value, ast.Tuple)
        and x.value.elts and isinstance(x.value.elts[0], ast.Dict)
        and any(_literal(key) == "samples" for key in x.value.elts[0].keys)
        for node in branch.orelse for x in ast.walk(node)
    )
    if not (direct_images and latent_images):
        raise ValueError("Pinned VHS VAE image/latent return behaviour changed")

    return {
        "exact_pinned_vhs_loadvideo_registration": True,
        "declared_output_zero_union": "IMAGE|LATENT",
        "no_vae_branch_returns_images": True,
        "with_vae_branch_returns_latent": True,
        "graph_media_decoded": False,
    }


def _native_types(root: Path) -> dict:
    source = root / "scripts" / NATIVE_SCHEMA_PATH.name
    if source.is_symlink() or not source.is_file():
        raise ValueError("Missing pinned-native contract source")
    spec = importlib.util.spec_from_file_location("osf_reviewed_native_types", source)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load local pinned-native binding contract")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.NATIVE


def check_saved_api_workflows(root: Path, native: dict) -> dict:
    summary = {}
    for name, expected_edges in GRAPHS.items():
        file = root / "workflows" / "commercial-compatible" / (name + ".json")
        if file.is_symlink() or not file.is_file():
            raise ValueError("Selected VHS/SAM3 API graph missing or symlinked")
        raw = file.read_bytes()
        graph = json.loads(raw)
        if not isinstance(graph, dict) or "3" not in graph:
            raise ValueError("Selected API graph missing VHS node 3")
        loader = graph["3"]
        if (not isinstance(loader, dict)
                or loader.get("class_type") != "VHS_LoadVideo"
                or not isinstance(loader.get("inputs"), dict)
                or set(loader["inputs"]) != SAVED_INPUT_NAMES
                or "vae" in loader["inputs"]):
            raise ValueError("Selected VHS loader class, inputs or VAE mode differs")
        for field in ("video", "format"):
            if not isinstance(loader["inputs"][field], str) or not loader["inputs"][field]:
                raise ValueError("Selected VHS loader string input malformed")
        for field in SAVED_INPUT_NAMES - {"video", "format"}:
            if type(loader["inputs"][field]) not in (int, float):
                raise ValueError("Selected VHS loader numeric input differs")
        actual = set()
        for destination, node in graph.items():
            if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
                raise ValueError("Selected API node input structure invalid")
            for field, value in node["inputs"].items():
                if isinstance(value, list) and len(value) == 2 and value[0] == "3":
                    if type(value[1]) is not int:
                        raise ValueError("VHS source slot must be an integer")
                    actual.add((destination, field, value[1]))
        if actual != expected_edges:
            raise ValueError("Selected VHS output link destinations or slots differ")
        for dest, field, slot in actual:
            cls = graph[dest].get("class_type")
            if slot != 0 or cls not in native or native[cls]["inputs"].get(field) != "IMAGE":
                raise ValueError("Pinned native receiving socket is not IMAGE")
        summary[name] = {
            "selected_graph_sha256": hashlib.sha256(raw).hexdigest(),
            "vhs_instance_id": "3",
            "vhs_image_output_edges": len(actual),
            "receiver_input_types": ["IMAGE"] * len(actual),
            "saved_vae_input_present": False,
            "saved_media_file_existence_tested": False,
            "live_video_decode_or_model_inference_tested": False,
        }
    return summary


def audit(vhs: Path, root: Path = ROOT) -> dict:
    if vhs.is_symlink() or not vhs.is_dir():
        raise ValueError("Invalid pinned VHS source checkout")
    sha = subprocess.run(
        ["git", "-C", str(vhs), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True, timeout=15,
    ).stdout.strip()
    if sha != VHS_SHA:
        raise ValueError("VHS source commit differs from reviewed pin")
    paths = ("videohelpersuite/nodes.py", "videohelpersuite/load_video_nodes.py",
             "videohelpersuite/utils.py")
    source = {}
    for name in paths:
        file = vhs / name
        if file.is_symlink() or not file.is_file():
            raise ValueError("Missing/symlinked pinned VHS source file")
        source[name] = file.read_text(encoding="utf-8")
    upstream = check_vhs_ast(*(source[name] for name in paths))
    selected = check_saved_api_workflows(root, _native_types(root))
    return {
        "schema": "osf-vhs-native-sam3-image-binding-v1",
        "upstream_vhs_git_sha": sha,
        "upstream_source_sha256": {
            name: hashlib.sha256(source[name].encode()).hexdigest()
            for name in sorted(source)
        },
        "source_contract": upstream,
        "api_graph_count": len(selected),
        "native_image_edges_source_checked": sum(
            x["vhs_image_output_edges"] for x in selected.values()
        ),
        "graphs": selected,
        "full_api_prompts_executable": False,
        "videos_loaded": False,
        "gpu_or_model_inference_qualified": False,
        "commercial_rights_cleared": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vhs-checkout", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    report = audit(args.vhs_checkout)
    if args.output.is_symlink() or args.output.exists():
        raise ValueError("Refuse to overwrite existing or symlinked output")
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("VHS -> native SAM3 source IMAGE edges: "
          + str(report["native_image_edges_source_checked"])
          + " across " + str(report["api_graph_count"]) + " API graphs; HOLD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
