#!/usr/bin/env python3
"""Offline structural checks for ComfyUI UI and API workflow JSON (stdlib only).

This is not a model/licence, custom-node installation or inference validator.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _ui(graph):
    errors = []
    nodes, links = graph["nodes"], graph["links"]
    if not isinstance(nodes, list) or not isinstance(links, list):
        return ["UI graph nodes and links must be arrays"]
    indexed = {}
    for n in nodes:
        if not isinstance(n, dict) or not isinstance(n.get("id"), int):
            errors.append("node has no integer id")
            continue
        ident = n["id"]
        if ident in indexed:
            errors.append(f"duplicate node id {ident}")
        indexed[ident] = n
        if not isinstance(n.get("type"), str) or not n["type"]:
            errors.append(f"node {ident} missing type")
    link_ids = set()
    for link in links:
        if not isinstance(link, list) or len(link) < 6:
            errors.append("link must be a six-element array")
            continue
        lid, origin, output_slot, target, input_slot = link[:5]
        if not isinstance(lid, int):
            errors.append("link id must be integer")
            continue
        if lid in link_ids:
            errors.append(f"duplicate link id {lid}")
        link_ids.add(lid)
        for nid, slot, field, side in ((origin, output_slot, "outputs", "origin"),
                                      (target, input_slot, "inputs", "target")):
            node = indexed.get(nid)
            if node is None:
                errors.append(f"link {lid} refers to missing {side} node {nid}")
            elif not isinstance(slot, int) or slot < 0 or not isinstance(node.get(field), list) or slot >= len(node[field]):
                errors.append(f"link {lid} invalid {side} slot {slot}")
    for ident, node in indexed.items():
        for inp in node.get("inputs", []) if isinstance(node.get("inputs"), list) else []:
            if not isinstance(inp, dict):
                errors.append(f"node {ident} has non-object input")
            elif inp.get("link") is not None and inp["link"] not in link_ids:
                errors.append(f"node {ident} input references missing link {inp['link']}")
    return errors


def _api(graph):
    errors = []
    for key, node in graph.items():
        if not isinstance(node, dict) or not isinstance(node.get("class_type"), str) or not node["class_type"]:
            errors.append(f"API node {key} missing class_type")
            continue
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            errors.append(f"API node {key} inputs must be an object")
            continue
        for name, value in inputs.items():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int):
                target, slot = value
                if target not in graph:
                    errors.append(f"API node {key} input {name}: missing upstream node {target}")
                elif slot < 0:
                    errors.append(f"API node {key} input {name}: negative upstream slot")
    return errors


def validate(document):
    if not isinstance(document, dict):
        return ["workflow root must be a JSON object"], "unknown"
    if "nodes" in document and "links" in document:
        return _ui(document), "ui"
    if document and all(isinstance(v, dict) and "class_type" in v for v in document.values()):
        return _api(document), "api"
    return ["not a recognised ComfyUI UI or API graph"], "unknown"


def check_file(path):
    if path.is_symlink() or not path.is_file():
        return {"file": str(path), "ok": False, "format": "unknown", "errors": ["not a regular JSON file"]}
    try:
        with path.open(encoding="utf-8") as f:
            document = json.load(f)
    except (OSError, UnicodeError, ValueError) as exc:
        return {"file": str(path), "ok": False, "format": "unknown", "errors": [str(exc)]}
    errors, graph_format = validate(document)
    return {"file": str(path), "ok": not errors, "format": graph_format, "errors": errors}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="+", type=Path, help="workflow .json files or directories")
    args = ap.parse_args(argv)
    candidates = []
    for path in args.paths:
        if path.is_dir() and not path.is_symlink():
            candidates.extend(sorted(path.rglob("*.json")))
        else:
            candidates.append(path)
    if not candidates:
        print(json.dumps({"ok": False, "errors": ["no JSON files found"]}))
        return 1
    results = [check_file(p) for p in dict.fromkeys(candidates)]
    print(json.dumps(results, indent=2))
    return 1 if any(not r["ok"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
