"""AST-only, exact-pinned ComfyUI core edge verification for SAM3 probe.

Source is data, never imported. This verifies four API links that touch
native core nodes. No SAM3 model, file load/save, or GPU is executed.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import subprocess


COMFY_CORE_SHA = "08cf0284ff45723aa67841c80cabb0e3cb50c9d7"
CORE_FILES = ("nodes.py", "comfy_extras/nodes_mask.py")
CORE_EDGES = (
    ("5", "image", "2", 0, "IMAGE"),
    ("6", "mask", "5", 0, "MASK"),
    ("7", "images", "6", 0, "IMAGE"),
    ("8", "images", "5", 2, "IMAGE"),
)
CORE_NODE_IDS = {"2": "LoadImage", "6": "MaskToImage",
                 "7": "SaveImage", "8": "SaveImage"}


def _single_class(source: str, name: str) -> ast.ClassDef:
    found = [x for x in ast.parse(source).body
             if isinstance(x, ast.ClassDef) and x.name == name]
    if len(found) != 1:
        raise ValueError("Missing or duplicate pinned core class: " + name)
    return found[0]


def _method(cls: ast.ClassDef, name: str) -> ast.FunctionDef:
    found = [x for x in cls.body
             if isinstance(x, ast.FunctionDef) and x.name == name]
    if len(found) != 1:
        raise ValueError("Missing core method: " + cls.name + "." + name)
    return found[0]


def _return_call_or_dict(method: ast.FunctionDef) -> ast.AST:
    values = [x.value for x in ast.walk(method) if isinstance(x, ast.Return)]
    if len(values) != 1:
        raise ValueError("Unreviewed core schema return shape")
    return values[0]


def _ast_dict(mapping: ast.AST) -> dict[str, ast.AST]:
    if not isinstance(mapping, ast.Dict):
        raise ValueError("Core input schema is not a literal dictionary")
    out = {}
    for key, value in zip(mapping.keys, mapping.values):
        if not isinstance(key, ast.Constant) or not isinstance(key.value, str) or key.value in out:
            raise ValueError("Malformed or duplicate core input key")
        out[key.value] = value
    return out


def _assignment(cls: ast.ClassDef, name: str):
    values = [x.value for x in cls.body
              if isinstance(x, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == name for t in x.targets)]
    if len(values) != 1:
        raise ValueError("Core class assignment absent/ambiguous: " + name)
    return ast.literal_eval(values[0])


def _input_prefix(node: ast.AST, expected_type: str) -> None:
    if not isinstance(node, ast.Tuple) or len(node.elts) < 1:
        raise ValueError("Core socket tuple missing: " + expected_type)
    if not isinstance(node.elts[0], ast.Constant) or node.elts[0].value != expected_type:
        raise ValueError("Core socket input type mismatch: " + expected_type)


def parse_classic_core(source: str) -> dict[str, dict]:
    """Read the reviewed LoadImage and SaveImage schema directly from nodes.py."""
    loader = _single_class(source, "LoadImage")
    saver = _single_class(source, "SaveImage")
    load_fields = _ast_dict(_return_call_or_dict(_method(loader, "INPUT_TYPES")))
    save_fields = _ast_dict(_return_call_or_dict(_method(saver, "INPUT_TYPES")))
    if set(load_fields) != {"required"}:
        raise ValueError("Unreviewed LoadImage input categories")
    input_fields = _ast_dict(load_fields["required"])
    if set(input_fields) != {"image"}:
        raise ValueError("Unreviewed LoadImage input fields")
    image = input_fields["image"]
    if (not isinstance(image, ast.Tuple) or len(image.elts) != 2
            or not isinstance(image.elts[0], ast.Call)
            or not isinstance(image.elts[0].func, ast.Name)
            or image.elts[0].func.id != "sorted"
            or ast.literal_eval(image.elts[1]) != {"image_upload": True}):
        raise ValueError("Unexpected LoadImage upload socket schema")
    save_inputs = _ast_dict(save_fields.get("required"))
    if set(save_inputs) != {"images", "filename_prefix"}:
        raise ValueError("Unreviewed SaveImage input fields")
    _input_prefix(save_inputs["images"], "IMAGE")
    _input_prefix(save_inputs["filename_prefix"], "STRING")
    if (_assignment(loader, "RETURN_TYPES") != ("IMAGE", "MASK")
            or _assignment(saver, "RETURN_TYPES") != ("IMAGE",)
            or _assignment(saver, "OUTPUT_NODE") is not True):
        raise ValueError("Unreviewed core LoadImage/SaveImage output types")
    return {
        "LoadImage": {"inputs": {"image": "UPLOAD_IMAGE_COMBO"},
                      "outputs": ("IMAGE", "MASK")},
        "SaveImage": {"inputs": {"images": "IMAGE",
                                "filename_prefix": "STRING"},
                      "outputs": ("IMAGE",)},
    }


def _callee(call: ast.Call) -> str:
    parts = []
    node = call.func
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        raise ValueError("Unexpected ComfyUI core schema call")
    parts.append(node.id)
    return ".".join(reversed(parts))


def parse_mask_to_image(source: str) -> dict:
    """Read native V3 MaskToImage schema, without importing Torch or ComfyUI."""
    cls = _single_class(source, "MaskToImage")
    result = _return_call_or_dict(_method(cls, "define_schema"))
    if not isinstance(result, ast.Call) or _callee(result) != "IO.Schema":
        raise ValueError("Unreviewed MaskToImage native schema construct")
    kwargs = {k.arg: k.value for k in result.keywords}
    node_id = kwargs.get("node_id")
    if not isinstance(node_id, ast.Constant) or node_id.value != "MaskToImage":
        raise ValueError("MaskToImage schema node ID mismatch")
    in_list, out_list = kwargs.get("inputs"), kwargs.get("outputs")
    if (not isinstance(in_list, ast.List) or len(in_list.elts) != 1
            or not isinstance(out_list, ast.List) or len(out_list.elts) != 1):
        raise ValueError("MaskToImage input/output count changed")
    input_call, output_call = in_list.elts[0], out_list.elts[0]
    if (not isinstance(input_call, ast.Call)
            or _callee(input_call) != "IO.Mask.Input"
            or len(input_call.args) != 1
            or not isinstance(input_call.args[0], ast.Constant)
            or input_call.args[0].value != "mask"
            or not isinstance(output_call, ast.Call)
            or _callee(output_call) != "IO.Image.Output"):
        raise ValueError("MaskToImage MASK to IMAGE socket contract changed")
    return {"inputs": {"mask": "MASK"}, "outputs": ("IMAGE",)}


def check_core_touched_edges(graph: dict, third_party: dict,
                             core: dict) -> dict:
    if set(core) != {"LoadImage", "MaskToImage", "SaveImage"}:
        raise ValueError("Core source schema set is incomplete")
    for node_id, class_type in CORE_NODE_IDS.items():
        if graph.get(node_id, {}).get("class_type") != class_type:
            raise ValueError("SAM3 probe core node identity mismatch")
    validated = 0
    for target, field, source, slot, typ in CORE_EDGES:
        if graph[target]["inputs"].get(field) != [source, slot]:
            raise ValueError("SAM3 probe reviewed core-touched link changed")
        src_class = graph[source]["class_type"]
        dst_class = graph[target]["class_type"]
        src = core.get(src_class, third_party.get(src_class))
        dst = core.get(dst_class, third_party.get(dst_class))
        if not isinstance(src, dict) or not isinstance(dst, dict):
            raise ValueError("Core-touched edge lacks source or target schema")
        outputs = src["outputs"]
        if slot >= len(outputs) or outputs[slot] != typ:
            raise ValueError("Core-touched output slot type differs")
        if dst["inputs"].get(field) != typ:
            raise ValueError("Core-touched target socket type differs")
        validated += 1
    return {
        "native_core_classes_checked": sorted(core),
        "native_core_node_instances": len(CORE_NODE_IDS),
        "typed_edges_touching_core_nodes": validated,
        "previously_unverified_core_source_edges_resolved": 2,
        "model_file_io_executed": False,
        "full_graph_executable": False,
    }


def verify_pinned_core(core_root: Path, graph: dict,
                       third_party: dict) -> dict:
    """Check HEAD and two non-symlinked source files before parsing AST."""
    if core_root.is_symlink() or not core_root.is_dir():
        raise ValueError("Missing or symlinked pinned ComfyUI core")
    revision = subprocess.run(
        ["git", "-C", str(core_root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True, timeout=12,
    ).stdout.strip()
    if revision != COMFY_CORE_SHA:
        raise ValueError("Wrong ComfyUI core revision for native SAM3 probe")
    texts = {}
    for path in CORE_FILES:
        file = core_root / path
        if file.is_symlink() or not file.is_file():
            raise ValueError("Missing or symlinked core source file: " + path)
        texts[path] = file.read_text(encoding="utf-8")
    types = {
        **parse_classic_core(texts["nodes.py"]),
        "MaskToImage": parse_mask_to_image(texts["comfy_extras/nodes_mask.py"]),
    }
    return {
        "core_revision": revision,
        "native_binding": check_core_touched_edges(graph, third_party, types),
        "source_file_sha256": {
            path: hashlib.sha256(texts[path].encode("utf-8")).hexdigest()
            for path in CORE_FILES
        },
        "source_only": True,
    }
