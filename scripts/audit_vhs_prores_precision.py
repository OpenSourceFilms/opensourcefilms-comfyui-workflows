"""Fail-closed audit of pinned VideoHelperSuite ProRes input precision.

Audits the exact upstream source already fetched by the disposable ComfyUI
CPU runner. Its ProRes preset provides 12-bit encoded storage but leaves
input_color_depth unset; the VideoCombine node consequently receives and
quantizes input tensors as 8-bit RGB24 before FFmpeg is invoked.

The independent direct-FFmpeg 12-bit ProRes roundtrip is NOT evidence
of 12-bit preservation through this ComfyUI/VHS node.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


def _named_function(nodes: list[ast.stmt], name: str) -> ast.FunctionDef:
    functions = [node for node in nodes if isinstance(node, ast.FunctionDef)
                 and node.name == name]
    if len(functions) != 1:
        raise ValueError("Pinned VHS source missing unique function: " + name)
    return functions[0]


def _mapped_function(node: ast.If, branch: str) -> bool:
    """Require actual function identifier used by the map() call."""
    for expression in ast.walk(ast.Module(body=node.body, type_ignores=[])
                               if branch == "tensor_to_shorts"
                               else ast.Module(body=node.orelse, type_ignores=[])):
        if not isinstance(expression, ast.Call):
            continue
        if (isinstance(expression.func, ast.Name)
                and expression.func.id == "map"
                and len(expression.args) == 2
                and isinstance(expression.args[0], ast.Name)
                and expression.args[0].id == branch
                and isinstance(expression.args[1], ast.Name)
                and expression.args[1].id == "images"):
            return True
    return False


def _contains_pixel_format(nodes: list[ast.stmt], expected: str) -> bool:
    return any(
        isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "i_pix_fmt"
                for target in node.targets)
        and isinstance(node.value, ast.Constant)
        and node.value.value == expected
        for base in nodes for node in ast.walk(base)
    )


def inspect_pinned_vhs_prores_source(source: str, config: dict) -> dict:
    """Validate the exact default-to-8bit branch and the pinned preset."""
    if not isinstance(config, dict) or config.get("extension") != "mov":
        raise ValueError("VHS ProRes format is missing or not a MOV")
    main_pass = config.get("main_pass")
    if (not isinstance(main_pass, list)
            or "-c:v" not in main_pass or "prores_ks" not in main_pass):
        raise ValueError("VHS ProRes configuration does not use prores_ks")
    if "input_color_depth" in config:
        raise ValueError("VHS ProRes input precision has changed: review required")
    tree = ast.parse(source)
    video_classes = [n for n in tree.body if isinstance(n, ast.ClassDef)
                     and n.name == "VideoCombine"]
    if len(video_classes) != 1:
        raise ValueError("Pinned VHS VideoCombine node not uniquely present")
    video_combine = _named_function(video_classes[0].body, "combine_video")
    branches = []
    for node in ast.walk(video_combine):
        if not isinstance(node, ast.If):
            continue
        expression = node.test
        if not isinstance(expression, ast.Compare) or len(expression.ops) != 1:
            continue
        if not isinstance(expression.ops[0], ast.Eq):
            continue
        if len(expression.comparators) != 1:
            continue
        if not (isinstance(expression.comparators[0], ast.Constant)
                and expression.comparators[0].value == "16bit"):
            continue
        call = expression.left
        if not (isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "video_format"
                and call.func.attr == "get"
                and len(call.args) == 2
                and all(isinstance(arg, ast.Constant) for arg in call.args)
                and [arg.value for arg in call.args] == ["input_color_depth", "8bit"]):
            continue
        branches.append(node)
    if len(branches) != 1:
        raise ValueError("Pinned VHS input_color_depth default is not reviewed 8bit")
    branch = branches[0]
    if (not _mapped_function(branch, "tensor_to_shorts")
            or not _mapped_function(branch, "tensor_to_bytes")
            or not _contains_pixel_format(branch.body, "rgb48")
            or not _contains_pixel_format(branch.orelse, "rgb24")):
        raise ValueError("Pinned VHS 8bit/16bit input branches do not match review")
    for name in ("tensor_to_int", "tensor_to_shorts", "tensor_to_bytes"):
        _named_function(tree.body, name)
    return {
        "status": "pinned_vhs_prores_8bit_input_path_confirmed",
        "codec": "prores_ks",
        "format": "video/ProRes",
        "format_default_input_color_depth": "8bit",
        "default_source_tensor_conversion": "tensor_to_bytes",
        "default_ffmpeg_raw_input_pixel_format": "rgb24",
        "available_unselected_branch": "tensor_to_shorts/rgb48",
        "vhs_real_12bit_source_roundtrip_qualified": False,
    }


def audit_pinned_vhs_prores_precision(custom_node: Path) -> dict:
    """Inspect pinned bytes, then execute only three extracted conversion funcs."""
    import numpy as np
    import torch

    if custom_node.is_symlink() or not custom_node.is_dir():
        raise ValueError("Missing or symlinked VHS source")
    nodes_file = custom_node / "videohelpersuite" / "nodes.py"
    config_file = custom_node / "video_formats" / "ProRes.json"
    if any(path.is_symlink() or not path.is_file()
           for path in (nodes_file, config_file)):
        raise ValueError("Untrusted VHS ProRes source or format file")
    source = nodes_file.read_text(encoding="utf-8")
    config_text = config_file.read_text(encoding="utf-8")
    result = inspect_pinned_vhs_prores_source(source, json.loads(config_text))

    tree = ast.parse(source)
    # Do not execute the entire third-party module just to run conversions.
    # Execute only the three reviewed helper function bodies in a namespace
    # limited to NumPy. Their source revision was separately SHA checked.
    names = {"tensor_to_int", "tensor_to_shorts", "tensor_to_bytes"}
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name in names]
    if len(selected) != 3:
        raise ValueError("Missing VHS converter functions")
    module = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
    namespace = {"np": np, "__builtins__": {}}
    exec(compile(module, "<pinned VHS pixel converters>", "exec"), namespace)

    # These are two distinguishable 12-bit Y values that share the same
    # 8-bit round-to-nearest bucket. The default converter destroys detail.
    source_12bit_values = (2038, 2043)
    normalized = torch.tensor(
        [value / 4095.0 for value in source_12bit_values],
        dtype=torch.float32,
    )
    eight = namespace["tensor_to_bytes"](normalized).tolist()
    sixteen = namespace["tensor_to_shorts"](normalized).tolist()
    if not (len(set(source_12bit_values)) == 2
            and len(set(eight)) == 1
            and len(set(sixteen)) == 2):
        raise ValueError("Pinned VHS converters did not exhibit reviewed quantization")
    return {
        **result,
        "fine_input_12bit_values": list(source_12bit_values),
        "default_8bit_quantized_values": eight,
        "explicit_16bit_quantized_values": sixteen,
        "fine_source_values_collapsed_by_default": True,
        "vhs_nodes_py_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "vhs_prores_json_sha256": hashlib.sha256(
            config_text.encode("utf-8")).hexdigest(),
        "synthetic_data_only": True,
        "binary_outputs_uploaded": False,
    }
