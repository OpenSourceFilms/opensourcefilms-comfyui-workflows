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
        if not isinstance(n, dict) or type(n.get("id")) is not int:
            errors.append("node has no integer id")
            continue
        ident = n["id"]
        if ident in indexed:
            errors.append(f"duplicate node id {ident}")
        indexed[ident] = n
        for ports in ("inputs", "outputs"):
            if not isinstance(n.get(ports, []), list):
                errors.append(f"node {ident} {ports} must be an array")
        if not isinstance(n.get("type"), str) or not n["type"]:
            errors.append(f"node {ident} missing type")
    link_ids = set()
    for link in links:
        if not isinstance(link, list) or len(link) < 6:
            errors.append("link must be a six-element array")
            continue
        lid, origin, output_slot, target, input_slot = link[:5]
        if type(lid) is not int:
            errors.append("link id must be integer")
            continue
        if lid in link_ids:
            errors.append(f"duplicate link id {lid}")
        link_ids.add(lid)
        for nid, slot, field, side in ((origin, output_slot, "outputs", "origin"),
                                      (target, input_slot, "inputs", "target")):
            if type(nid) is not int:
                errors.append(f"link {lid} invalid {side} node id")
                continue
            node = indexed.get(nid)
            if node is None:
                errors.append(f"link {lid} refers to missing {side} node {nid}")
            elif type(slot) is not int or slot < 0 or not isinstance(node.get(field), list) or slot >= len(node[field]):
                errors.append(f"link {lid} invalid {side} slot {slot}")
    for ident, node in indexed.items():
        for inp in node.get("inputs", []) if isinstance(node.get("inputs"), list) else []:
            if not isinstance(inp, dict):
                errors.append(f"node {ident} has non-object input")
            elif inp.get("link") is not None:
                ref = inp["link"]
                if type(ref) is not int or ref not in link_ids:
                    errors.append(f"node {ident} input references invalid or missing link")
    by_link = {
        link[0]: link for link in links
        if isinstance(link, list) and len(link) >= 6 and type(link[0]) is int
    }
    for lid, link in by_link.items():
        _, origin, output_slot, target, input_slot = link[:5]
        out_node = indexed.get(origin) if type(origin) is int else None
        in_node = indexed.get(target) if type(target) is int else None
        out_ports = out_node.get("outputs", []) if out_node else []
        in_ports = in_node.get("inputs", []) if in_node else []
        if out_node and isinstance(out_ports, list) and type(output_slot) is int and 0 <= output_slot < len(out_ports):
            port = out_node["outputs"][output_slot]
            if not isinstance(port, dict) or not isinstance(port.get("links"), list) or lid not in port["links"]:
                errors.append(f"link {lid} origin output backreference missing")
        if in_node and isinstance(in_ports, list) and type(input_slot) is int and 0 <= input_slot < len(in_ports):
            port = in_node["inputs"][input_slot]
            if not isinstance(port, dict) or port.get("link") != lid:
                errors.append(f"link {lid} target input backreference mismatch")
    for ident, node in indexed.items():
        for slot, port in enumerate(node.get("outputs", []) if isinstance(node.get("outputs"), list) else []):
            if not isinstance(port, dict):
                errors.append(f"node {ident} has non-object output")
                continue
            refs = port.get("links")
            if refs is None:
                continue
            if not isinstance(refs, list):
                errors.append(f"node {ident} output links must be array/null")
                continue
            for lid in refs:
                if type(lid) is not int:
                    errors.append(f"node {ident} output contains invalid link id")
                    continue
                link = by_link.get(lid)
                if link is None:
                    errors.append(f"node {ident} output references missing link {lid}")
                elif link[1:3] != [ident, slot]:
                    errors.append(f"node {ident} output references misrouted link {lid}")
        for slot, port in enumerate(node.get("inputs", []) if isinstance(node.get("inputs"), list) else []):
            if not isinstance(port, dict) or port.get("link") is None:
                continue
            if type(port["link"]) is not int:
                errors.append(f"node {ident} input contains invalid link id")
                continue
            link = by_link.get(port["link"])
            if link is not None and link[3:5] != [ident, slot]:
                errors.append(f"node {ident} input references misrouted link {port['link']}")
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
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and type(value[1]) in (int, bool):
                target, slot = value
                if type(slot) is not int:
                    errors.append(f"API node {key} input {name}: upstream slot must be an integer")
                    continue
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
