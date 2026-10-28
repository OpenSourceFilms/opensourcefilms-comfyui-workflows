"""Compare pinned SAM3/SCAIL public native schemas to real ComfyUI /object_info.

All checks are metadata-only: no model weights, SAM3 detector calls, SCAIL
inference, file inputs, media or GPU. The source snapshot alone cannot prove
registration parity; this compares published inputs and output type slots
with the *live* CPU ComfyUI registry on the exact pinned core revision.
"""
from __future__ import annotations

from audit_sam3_scail_api_bindings import FORCE_LINK_FIELDS, NATIVE


def _typed_socket(record: object, class_id: str, field: str) -> tuple[object, dict]:
    if not isinstance(record, (tuple, list)) or not record:
        raise ValueError("Malformed native live input socket: " + class_id + "." + field)
    declared = record[0]
    if not isinstance(declared, (str, list)) or not declared:
        raise ValueError("Missing native live input socket type: " + class_id + "." + field)
    props = record[1] if len(record) > 1 else {}
    if not isinstance(props, dict):
        raise ValueError("Malformed native live socket metadata: " + class_id + "." + field)
    return declared, props


def verify_native_live_schemas(registry: object) -> dict:
    """Require five actual registered classes with source-derived socket parity."""
    if not isinstance(registry, dict) or not registry:
        raise ValueError("Missing real ComfyUI object_info registry")
    native_count = 0
    checked_fields = 0
    checked_output_types = 0
    forced = 0
    union_skipped = 0
    extra_live_inputs = 0
    for class_id, source in NATIVE.items():
        entry = registry.get(class_id)
        if not isinstance(entry, dict):
            raise ValueError("Missing native class in real ComfyUI registry: " + class_id)
        fields = entry.get("input")
        if not isinstance(fields, dict):
            raise ValueError("Malformed native live input registry: " + class_id)
        required = fields.get("required", {})
        optional = fields.get("optional", {})
        if not isinstance(required, dict) or not isinstance(optional, dict):
            raise ValueError("Malformed native required/optional socket registry: " + class_id)
        overlap = set(required) & set(optional)
        if overlap:
            raise ValueError("Duplicate native live input in required and optional: " + class_id)
        declared_fields = {**required, **optional}
        if not set(source["required"]) <= set(required):
            raise ValueError("Missing required native public input in live schema: " + class_id)
        missing = set(source["inputs"]) - set(declared_fields)
        if missing:
            raise ValueError("Missing source-defined native field in live schema: " + class_id)
        extra_live_inputs += len(set(declared_fields) - set(source["inputs"]))
        for name, typ in source["inputs"].items():
            declared, props = _typed_socket(declared_fields[name], class_id, name)
            key = class_id + "." + name
            if typ == "COMBO":
                # Old ComfyUI exposes enum options as first-list type.
                # New io.Combo.Input may expose "COMBO" plus metadata.
                if isinstance(declared, list):
                    options = declared
                elif declared == "COMBO":
                    options = props.get("options", props.get("values"))
                else:
                    raise ValueError("Native public combo type mismatch: " + key
                                     + ", live kind " + type(declared).__name__)
                if (not isinstance(options, list) or not options
                        or any(not isinstance(x, str) for x in options)):
                    raise ValueError("Native public combo option metadata invalid: " + key
                                     + ", live kind " + type(declared).__name__
                                     + ", option kind " + type(options).__name__)
                if key == "SCAIL2ColoredMask.sort_by" and set(options) != {
                    "none", "left_to_right", "area"
                }:
                    raise ValueError("Native public enum options mismatch: " + key)
            elif "|" in typ:
                # New API's MultiType is not a scalar or a model assertion:
                # verify presence but do not infer runtime union serialization.
                union_skipped += 1
            elif declared != typ:
                raise ValueError("Native public socket type mismatch: " + key)
            if key in FORCE_LINK_FIELDS:
                if props.get("forceInput") is not True and props.get("force_input") is not True:
                    raise ValueError("Missing native force_input flag in live schema: " + key)
                forced += 1
            checked_fields += 1
        outputs = entry.get("output")
        if not isinstance(outputs, list) or outputs != list(source["outputs"]):
            raise ValueError("Native public live output types/slots differ: " + class_id)
        checked_output_types += len(outputs)
        native_count += 1
    if forced != len(FORCE_LINK_FIELDS):
        raise ValueError("Native force_input socket count differs")
    return {
        "status": "live_native_sam3_scail_object_info_socket_parity_verified",
        "classes_checked": native_count,
        "source_defined_fields_checked": checked_fields,
        "output_slots_checked": checked_output_types,
        "force_input_sockets_checked": forced,
        "multitype_storage_serialization_unverified": union_skipped,
        "additional_unreviewed_runtime_input_fields": extra_live_inputs,
        "model_weights_loaded": False,
        "gpu_inference_tested": False,
        "three_real_api_graphs_executed": False,
    }
