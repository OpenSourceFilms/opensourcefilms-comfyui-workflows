#!/usr/bin/env python3
"""Source-derived native SAM3/SCAIL API binding preflight, not inference.

These input names and output types are taken from the unmodified public
Comfy-Org/ComfyUI revision pinned by the OSF clean CPU harness:
08cf0284ff45723aa67841c80cabb0e3cb50c9d7,
comfy_extras/nodes_sam3.py and comfy_extras/nodes_scail.py.

Only checks the three real selected API prompt graphs that use these
five native node IDs. Does not install models or assert full graph execution.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_COMMIT = "08cf0284ff45723aa67841c80cabb0e3cb50c9d7"
WORKFLOWS = (
    "step4_5_sam3_mask",
    "step6_animation_mode",
    "step7_replacement_mode",
)
# Types are schema names (IMAGE / MODEL / SAM3_TRACK_DATA etc.).
# "|" denotes a published union: native SCAIL accepts track data or MASK.
NATIVE = {
    "SAM3_Detect": {
        "inputs": {
            "model": "MODEL", "image": "IMAGE",
            "conditioning": "CONDITIONING", "bboxes": "BOUNDING_BOX",
            "positive_coords": "STRING", "negative_coords": "STRING",
            "threshold": "FLOAT", "refine_iterations": "INT",
            "individual_masks": "BOOLEAN",
        },
        "required": ("model", "image"),
        "outputs": ("MASK", "BOUNDING_BOX"),
    },
    "SAM3_VideoTrack": {
        "inputs": {
            "images": "IMAGE", "model": "MODEL", "initial_mask": "MASK",
            "conditioning": "CONDITIONING", "detection_threshold": "FLOAT",
            "max_objects": "INT", "detect_interval": "INT",
        },
        "required": ("images", "model"),
        "outputs": ("SAM3_TRACK_DATA",),
    },
    "SAM3_TrackPreview": {
        "inputs": {
            "track_data": "SAM3_TRACK_DATA", "images": "IMAGE",
            "opacity": "FLOAT", "fps": "FLOAT",
        },
        "required": ("track_data",),
        "outputs": (),
    },
    "SCAIL2ColoredMask": {
        "inputs": {
            "driving_track_data": "SAM3_TRACK_DATA",
            "ref_track_data": "SAM3_TRACK_DATA|MASK",
            "object_indices": "STRING", "sort_by": "COMBO",
            "replacement_mode": "BOOLEAN",
        },
        "required": ("driving_track_data",),
        "outputs": ("IMAGE", "IMAGE"),
    },
    "WanSCAILToVideo": {
        "inputs": {
            "positive": "CONDITIONING", "negative": "CONDITIONING",
            "vae": "VAE", "width": "INT", "height": "INT", "length": "INT",
            "batch_size": "INT", "pose_video": "IMAGE",
            "pose_video_mask": "IMAGE", "replacement_mode": "BOOLEAN",
            "pose_strength": "FLOAT", "pose_start": "FLOAT",
            "pose_end": "FLOAT", "reference_image": "IMAGE",
            "reference_image_mask": "IMAGE",
            "clip_vision_output": "CLIP_VISION_OUTPUT",
            "video_frame_offset": "INT", "previous_frame_count": "INT",
            "previous_frames": "IMAGE",
        },
        "required": ("positive", "negative", "vae"),
        "outputs": ("CONDITIONING", "CONDITIONING", "LATENT", "INT"),
    },
}
# Static source-schema review only. Pinned public ComfyUI source:
# Comfy-Org/ComfyUI@08cf0284ff45723aa67841c80cabb0e3cb50c9d7
# nodes.py (CheckpointLoaderSimple, CLIPTextEncode, LoadImage,
# VAELoader and CLIPVisionEncode). Pinned external VideoHelperSuite:
# Kosinkadink/ComfyUI-VideoHelperSuite@2984ec4c4b93292421888f38db74a5e8802a8ff8
# load_video_nodes.py's LoadVideoUpload output 0 is imageOrLatent:
# MultiInput("IMAGE", ["IMAGE", "LATENT"]); only IMAGE is valid for
# native IMAGE sockets. The selected API exports do NOT connect a VAE.
# Treat adding VAE as fail-closed rather than silently accepting LATENT.
SOURCE_OUTPUTS = {
    "CheckpointLoaderSimple": ("MODEL", "CLIP", "VAE"),
    "CLIPTextEncode": ("CONDITIONING",),
    "LoadImage": ("IMAGE", "MASK"),
    "VAELoader": ("VAE",),
    "CLIPVisionEncode": ("CLIP_VISION_OUTPUT",),
    "VHS_LoadVideo": ("IMAGE|LATENT", "INT", "AUDIO", "VHS_VIDEOINFO"),
}
SOURCE_REVISIONS = {
    "Comfy-Org/ComfyUI": CORE_COMMIT,
    "Kosinkadink/ComfyUI-VideoHelperSuite":
        "2984ec4c4b93292421888f38db74a5e8802a8ff8",
}
SCALAR_TYPES = frozenset({"INT", "FLOAT", "BOOLEAN", "STRING", "COMBO"})
COMBO_OPTIONS = {"SCAIL2ColoredMask.sort_by": {"none", "left_to_right", "area"}}
# Pinned public nodes_sam3.py: SAM3_Detect declares these optional sockets
# with force_input=True. If present, they require an API link, not a literal.
FORCE_LINK_FIELDS = frozenset({
    "SAM3_Detect.bboxes",
    "SAM3_Detect.positive_coords",
    "SAM3_Detect.negative_coords",
})


def _is_link(value: object) -> bool:
    return (isinstance(value, list) and len(value) == 2
            and isinstance(value[0], str)
            and type(value[1]) is int and value[1] >= 0)


def _check_scalar(typ: str, value: object, key: str) -> None:
    if typ == "INT":
        ok = type(value) is int
    elif typ == "FLOAT":
        ok = type(value) in (int, float)
    elif typ == "BOOLEAN":
        ok = type(value) is bool
    elif typ == "STRING":
        ok = isinstance(value, str)
    elif typ == "COMBO":
        ok = isinstance(value, str) and value in COMBO_OPTIONS[key]
    else:
        raise ValueError("Unrecognized published scalar schema")
    if not ok:
        raise ValueError("Native SAM3/SCAIL scalar input type mismatch: " + key)


def check_api_bindings(graph: object) -> dict:
    """Check native node names, scalar types, links, slots and native endpoints.

    Non-native source output types cannot be established here and are
    deliberately left unqualified. Returns counts only, never prompts.
    """
    if not isinstance(graph, dict):
        raise ValueError("Expected executable API prompt object")
    nodes = {ident: value for ident, value in graph.items()
             if isinstance(value, dict) and isinstance(value.get("class_type"), str)}
    if not nodes:
        raise ValueError("No executable API prompt classes")
    native = [(ident, node) for ident, node in nodes.items()
              if node["class_type"] in NATIVE]
    if not native:
        raise ValueError("Expected selected SAM3/SCAIL native nodes")
    classes = Counter()
    checked_links = 0
    checked_native_edges = 0
    checked_pinned_provider_edges = 0
    checked_conditional_vhs_image_edges = 0
    unknown_source_edges = 0
    for ident, node in native:
        cls = node["class_type"]
        spec = NATIVE[cls]
        fields = node.get("inputs")
        if not isinstance(fields, dict):
            raise ValueError("Native SAM3/SCAIL node has no input dictionary")
        missing = set(spec["required"]) - set(fields)
        if missing:
            raise ValueError("Native SAM3/SCAIL required input missing: " + cls)
        invalid = set(fields) - set(spec["inputs"])
        if invalid:
            raise ValueError("Native SAM3/SCAIL unknown input: " + cls)
        classes[cls] += 1
        for field, value in fields.items():
            typ = spec["inputs"][field]
            if (f"{cls}.{field}" in FORCE_LINK_FIELDS
                    and not _is_link(value)):
                raise ValueError("Native SAM3 force_input socket requires a link")
            if _is_link(value):
                src, slot = value
                upstream = nodes.get(src)
                if upstream is None:
                    raise ValueError("Native SAM3/SCAIL link references absent node")
                if upstream["class_type"] in NATIVE:
                    outputs = NATIVE[upstream["class_type"]]["outputs"]
                    if slot >= len(outputs):
                        raise ValueError("Native SAM3/SCAIL link uses absent output slot")
                    if outputs[slot] not in typ.split("|"):
                        raise ValueError("Native SAM3/SCAIL link output type mismatch")
                    checked_native_edges += 1
                elif upstream["class_type"] in SOURCE_OUTPUTS:
                    source_cls = upstream["class_type"]
                    outputs = SOURCE_OUTPUTS[source_cls]
                    if slot >= len(outputs):
                        raise ValueError("Pinned source output slot out of range")
                    # VHS can emit LATENT when supplied a VAE. Our selected
                    # graphs omit it: without an explicit VAE, check the
                    # published nominal IMAGE path but *not* runtime tensors.
                    if source_cls == "VHS_LoadVideo":
                        upstream_inputs = upstream.get("inputs")
                        if not isinstance(upstream_inputs, dict):
                            raise ValueError("Pinned VHS source inputs malformed")
                        if "vae" in upstream_inputs:
                            raise ValueError(
                                "Pinned VHS output could become LATENT with VAE"
                            )
                        if slot == 0:
                            if "IMAGE" not in typ.split("|"):
                                raise ValueError(
                                    "Pinned VHS image source type mismatch"
                                )
                            checked_conditional_vhs_image_edges += 1
                        elif outputs[slot] not in typ.split("|"):
                            raise ValueError("Pinned source output type mismatch")
                    elif outputs[slot] not in typ.split("|"):
                        raise ValueError("Pinned source output type mismatch")
                    checked_pinned_provider_edges += 1
                else:
                    # Unreviewed provider schemas are not silently promoted
                    # to accepted output types.
                    unknown_source_edges += 1
                checked_links += 1
            elif typ in SCALAR_TYPES:
                _check_scalar(typ, value, f"{cls}.{field}")
            else:
                raise ValueError("Native SAM3/SCAIL typed input lacks a valid link")
    return {
        "native_node_instances": len(native),
        "native_class_counts": dict(sorted(classes.items())),
        "checked_source_links": checked_links,
        "checked_native_to_native_output_types": checked_native_edges,
        "checked_pinned_provider_source_output_types": checked_pinned_provider_edges,
        "vhs_nominal_image_links_without_vae": checked_conditional_vhs_image_edges,
        "external_source_output_types_unverified": unknown_source_edges,
        "vhs_runtime_output_type_verified": False,
        "full_graph_link_type_verification": False,
        "native_input_names_and_scalar_shapes_pass": True,
        "all_other_workflow_nodes_qualified": False,
        "model_weights_or_inference_tested": False,
    }


def audit(root: Path = ROOT) -> dict:
    results = []
    total = 0
    for name in WORKFLOWS:
        path = root / "workflows" / "commercial-compatible" / (name + ".json")
        graph = json.loads(path.read_text(encoding="utf-8"))
        result = check_api_bindings(graph)
        total += result["native_node_instances"]
        results.append({"workflow": name, **result})
    if total != 12:
        raise ValueError("Unexpected total of native SAM3/SCAIL node instances")
    if (sum(result["checked_pinned_provider_source_output_types"]
            for result in results) != 31
            or sum(result["vhs_nominal_image_links_without_vae"]
                   for result in results) != 6
            or any(result["external_source_output_types_unverified"]
                   for result in results)):
        raise ValueError("Selected native edges no longer match reviewed provider bindings")
    return {
        "schema": "osf-sam3-scail-public-native-api-binding-preflight-v1",
        "public_core_commit": CORE_COMMIT,
        "upstream_source_files": [
            "comfy_extras/nodes_sam3.py", "comfy_extras/nodes_scail.py",
        ],
        "api_workflows_checked": len(WORKFLOWS),
        "native_node_instances_checked": total,
        "pinned_provider_source_revisions": SOURCE_REVISIONS,
        "pinned_provider_links_checked": sum(
            result["checked_pinned_provider_source_output_types"]
            for result in results
        ),
        "vhs_nominal_image_links_checked": sum(
            result["vhs_nominal_image_links_without_vae"] for result in results
        ),
        "workflows": results,
        "full_graph_or_gpu_inference_qualified": False,
        "source_schema_snapshot_only": True,
    }


def main() -> int:
    result = audit()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
