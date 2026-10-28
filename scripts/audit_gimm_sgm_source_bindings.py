#!/usr/bin/env python3
"""Source-only audit of pinned GIMM/SGM UI bindings. Does not import models.

Reads two caller-supplied checkouts at exact DEPENDENCIES.lock Git commits.
Uses Python AST, not execution of untrusted third-party Python source.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import subprocess


GIMM_SHA = "4c9a3123762af85e7c796e41737da0b70c75d72d"
TWEEN_SHA = "91947c0b8c795cf504d3848274d4217f0432a324"
GRAPH = "workflows/commercial-compatible/gimm_sgm_vfi_video_interpolate.json"
GIMM_REQUIRED = {"GIMMVFI_loader", "GIMMVFIInterpolate"}
SGM_REQUIRED = {"LoadSGMVFIModel", "SGMVFISegmentInterpolate"}


def mapping_from_source(path: Path) -> dict[str, str]:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "NODE_CLASS_MAPPINGS"
                   for t in node.targets):
            continue
        if not isinstance(node.value, ast.Dict):
            raise ValueError("Third-party NODE_CLASS_MAPPINGS no longer literal")
        result = {}
        for key, value in zip(node.value.keys, node.value.values):
            if (not isinstance(key, ast.Constant) or not isinstance(key.value, str)
                    or not isinstance(value, ast.Name)):
                raise ValueError("Third-party node registry no longer statically inspectable")
            result[key.value] = value.id
        return result
    raise ValueError("Third-party NODE_CLASS_MAPPINGS unavailable")


def class_source_sockets(path: Path, class_name: str) -> dict[str, object]:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    cls = next((x for x in module.body
                if isinstance(x, ast.ClassDef) and x.name == class_name), None)
    if cls is None:
        raise ValueError("Pinned upstream class absent: " + class_name)
    method = next((x for x in cls.body if isinstance(x, ast.FunctionDef)
                   and x.name == "INPUT_TYPES"), None)
    if method is None:
        raise ValueError("Pinned upstream class has no INPUT_TYPES: " + class_name)
    dictionary = next((x.value for x in ast.walk(method)
                       if isinstance(x, ast.Return) and isinstance(x.value, ast.Dict)), None)
    if dictionary is None:
        raise ValueError("Pinned INPUT_TYPES no longer a direct literal dict: " + class_name)
    keys = {}
    for kind, nested in zip(dictionary.keys, dictionary.values):
        if (not isinstance(kind, ast.Constant) or kind.value not in ("required", "optional")
                or not isinstance(nested, ast.Dict)):
            continue
        keys[kind.value] = [k.value for k in nested.keys
                            if isinstance(k, ast.Constant) and isinstance(k.value, str)]
    if not keys.get("required"):
        raise ValueError("No literal required input sockets in upstream source")
    returns = []
    for statement in cls.body:
        if (isinstance(statement, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "RETURN_TYPES"
                for t in statement.targets)):
            returns = list(ast.literal_eval(statement.value))
    return {"required": keys.get("required", []),
            "optional": keys.get("optional", []),
            "return_types": returns}


def graph_nodes(graph_path: Path) -> list[dict[str, object]]:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("Expected a UI graph with nodes")
    selected = []
    for node in nodes:
        if node.get("type") in GIMM_REQUIRED | SGM_REQUIRED:
            selected.append({
                "id": node["id"], "class_type": node["type"],
                "input_names": [entry["name"] for entry in node.get("inputs", [])],
            })
    if {n["class_type"] for n in selected} != GIMM_REQUIRED | SGM_REQUIRED:
        raise ValueError("Selected GIMM/SGM graph types have drifted")
    return selected


def verify_manifest_pins(manifest: str) -> None:
    start = manifest.find(GRAPH + ":")
    if start == -1:
        raise ValueError("Selected workflow missing from canonical manifest")
    end = manifest.find("\nworkflows/", start + 1)
    segment = manifest[start:end if end != -1 else None]
    for provider, commit in (("ComfyUI-GIMM-VFI", GIMM_SHA),
                             ("ComfyUI-Tween (provides SGM-VFI)", TWEEN_SHA)):
        if ("- name: " + provider + "\n      commit: " + commit) not in segment:
            raise ValueError("Pinned dependency is absent or changed: " + provider)


def verify_git_head(path: Path, expected: str) -> None:
    if path.is_symlink() or not path.is_dir():
        raise ValueError("Pinned upstream checkout is missing/symlinked")
    actual = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    if actual != expected:
        raise ValueError("Upstream checkout HEAD does not match manifest")


def audit(repo_root: Path, gimm_root: Path, tween_root: Path) -> dict[str, object]:
    verify_manifest_pins((repo_root / "DEPENDENCIES.lock").read_text(encoding="utf-8"))
    verify_git_head(gimm_root, GIMM_SHA)
    verify_git_head(tween_root, TWEEN_SHA)
    nodes = graph_nodes(repo_root / GRAPH)
    gimm_mapping = mapping_from_source(gimm_root / "nodes.py")
    tween_mapping = mapping_from_source(tween_root / "__init__.py")
    # Never dynamically import the model or invoke the auto-download paths.
    if not ({"DownloadAndLoadGIMMVFIModel", "GIMMVFI_interpolate"}
            <= set(gimm_mapping) and
            {"LoadGIMMVFIModel", "GIMMVFIInterpolate",
             "LoadSGMVFIModel", "SGMVFISegmentInterpolate"} <= set(tween_mapping)):
        raise ValueError("Reviewed upstream registration has drifted")
    loader = next(n for n in nodes if n["class_type"] == "GIMMVFI_loader")
    interpolate = next(n for n in nodes if n["class_type"] == "GIMMVFIInterpolate")
    gimm_loader = class_source_sockets(
        gimm_root / "nodes.py", gimm_mapping["DownloadAndLoadGIMMVFIModel"]
    )
    gimm_interp = class_source_sockets(
        gimm_root / "nodes.py", gimm_mapping["GIMMVFI_interpolate"]
    )
    tween_interp = class_source_sockets(
        tween_root / "nodes.py", tween_mapping["GIMMVFIInterpolate"]
    )
    loader_absent = all(loader["class_type"] not in mapping
                        for mapping in (gimm_mapping, tween_mapping))
    no_tween_socket_match = set(interpolate["input_names"]) - set(
        tween_interp["required"] + tween_interp["optional"])
    if not loader_absent or not no_tween_socket_match:
        # An unexpected improvement is not automatically certified either.
        raise ValueError("GIMM source incompatibility baseline changed: review required")
    return {
        "status": "HOLD",
        "workflow": GRAPH,
        "source_commits": {"ComfyUI-GIMM-VFI": GIMM_SHA,
                           "ComfyUI-Tween": TWEEN_SHA},
        "source_inspection": "Python AST, no upstream imports or model downloads",
        "requested_nodes": nodes,
        "gimm_repository_registered_classes": sorted(gimm_mapping),
        "tween_relevant_registered_classes": sorted(
            name for name in tween_mapping if "GIMM" in name or "SGM" in name),
        "gimm_loader_missing_from_both_pins": loader_absent,
        "gimm_loader_nearest_class": "DownloadAndLoadGIMMVFIModel",
        "gimm_loader_input_names_in_reviewed_source":
            gimm_loader["required"] + gimm_loader["optional"],
        "gimm_interpolator_registered_name": "GIMMVFI_interpolate",
        "gimm_interpolator_input_names_in_reviewed_source":
            gimm_interp["required"] + gimm_interp["optional"],
        "tween_interpolator_same_name_but_missing_input_sockets":
            sorted(no_tween_socket_match),
        "gimm_model_output_type": gimm_loader["return_types"],
        "tween_gimm_interpolator_required_input_names": tween_interp["required"],
        "source_binding_qualified": False,
        "model_weights_or_gpu_inference_qualified": False,
        "workflow_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--gimm-root", type=Path, required=True)
    parser.add_argument("--tween-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refusing to overwrite existing audit evidence")
    result = audit(args.repo_root, args.gimm_root, args.tween_root)
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
