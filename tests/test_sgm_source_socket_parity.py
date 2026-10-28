"""Offline negative contracts for exact pinned Tween SGM source/socket parity."""
from __future__ import annotations

import ast
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "sgm_source_parity", ROOT / "scripts" / "audit_sgm_source_socket_parity.py"
)
auditor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auditor)

FAKE_NODES = '''
class LoadSGMVFIModel:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model_path": (get_available_sgm_models(), {}),
            "tta": ("BOOLEAN", {}),
            "num_key_points": ("FLOAT", {}),
        }}
    RETURN_TYPES = ("SGM_VFI_MODEL",)
    RETURN_NAMES = ("model",)

class SGMVFIInterpolate:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "images": ("IMAGE", {}),
            "model": ("SGM_VFI_MODEL", {}),
            "multiplier": ([2, 4, 8], {}),
            "clear_cache_after_n_frames": ("INT", {}),
            "keep_device": ("BOOLEAN", {}),
            "all_on_gpu": ("BOOLEAN", {}),
            "batch_size": ("INT", {}),
            "chunk_size": ("INT", {}),
            "source_fps": ("FLOAT", {}),
            "target_fps": ("FLOAT", {}),
        }, "optional": {
            "settings": ("VFI_SETTINGS", {}),
        }}

class SGMVFISegmentInterpolate(SGMVFIInterpolate):
    @classmethod
    def INPUT_TYPES(cls):
        base = SGMVFIInterpolate.INPUT_TYPES()
        base["required"]["segment_index"] = ("INT", {})
        base["required"]["segment_size"] = ("INT", {})
        return base
    RETURN_TYPES = ("IMAGE", "SGM_VFI_MODEL")
    RETURN_NAMES = ("images", "model")
'''
FAKE_INIT = '''
NODE_CLASS_MAPPINGS = {
    "LoadSGMVFIModel": LoadSGMVFIModel,
    "SGMVFISegmentInterpolate": SGMVFISegmentInterpolate,
}
'''


def load_graph():
    with (ROOT / auditor.GRAPH).open(encoding="utf-8") as f:
        return json.load(f)


def known_graph_signatures():
    """The unit fixture is not evidence of upstream parity, CI fetches real source."""
    return {
        21: {
            "input_types": {"model_path": "COMBO", "tta": "BOOLEAN",
                            "num_key_points": "FLOAT"},
            "required": {"model_path", "tta", "num_key_points"},
            "output_types": ("SGM_VFI_MODEL",),
            "output_names": ("model",),
        },
        22: {
            "input_types": {
                "images": "IMAGE", "model": "SGM_VFI_MODEL",
                "settings": "VFI_SETTINGS", "multiplier": "COMBO",
                "clear_cache_after_n_frames": "INT", "keep_device": "BOOLEAN",
                "all_on_gpu": "BOOLEAN", "batch_size": "INT", "chunk_size": "INT",
                "source_fps": "FLOAT", "target_fps": "FLOAT",
                "segment_index": "INT", "segment_size": "INT",
            },
            "required": {
                "images", "model", "multiplier", "clear_cache_after_n_frames",
                "keep_device", "all_on_gpu", "batch_size", "chunk_size",
                "source_fps", "target_fps", "segment_index", "segment_size",
            },
            "output_types": ("IMAGE", "SGM_VFI_MODEL"),
            "output_names": ("images", "model"),
        },
    }


class PinnedSgmSourceParityContract(unittest.TestCase):
    def test_current_graph_link_and_socket_fixtures_are_structural_only(self):
        graph = load_graph()
        output = auditor._check_graph(graph, known_graph_signatures())
        self.assertEqual(output["LoadSGMVFIModel"]["input_count"], 3)
        self.assertEqual(output["SGMVFISegmentInterpolate"]["input_count"], 13)
        self.assertEqual(output["SGMVFISegmentInterpolate"]["widget_count"], 10)
        self.assertEqual(len(graph["nodes"]), 11)

    def test_ast_parses_inherited_sockets_without_importing_upstream(self):
        parsed = ast.parse(FAKE_NODES)
        base = auditor._class(parsed, "SGMVFIInterpolate")
        segment = auditor._class(parsed, "SGMVFISegmentInterpolate")
        required, required_names = auditor._initial_base_sockets(base)
        self.assertEqual(required["multiplier"], "COMBO")
        auditor._segment_override(segment, required, required_names)
        self.assertEqual(required, known_graph_signatures()[22]["input_types"])
        self.assertEqual(required_names, known_graph_signatures()[22]["required"])
        self.assertEqual(auditor._returns(segment),
                         (("IMAGE", "SGM_VFI_MODEL"), ("images", "model")))

    def test_only_reviewed_dynamic_model_combo_is_allowed(self):
        tree = ast.parse(FAKE_NODES.replace(
            "get_available_sgm_models()", "arbitrary_download_models()"
        ))
        with self.assertRaisesRegex(ValueError, "Unreviewed dynamic"):
            auditor._initial_base_sockets(auditor._class(tree, "LoadSGMVFIModel"))

    def test_unexpected_segment_override_fails(self):
        changed = FAKE_NODES.replace(
            'base["required"]["segment_size"]', 'base["required"]["chunk_size"]'
        )
        tree = ast.parse(changed)
        base_types, req = auditor._initial_base_sockets(
            auditor._class(tree, "SGMVFIInterpolate")
        )
        with self.assertRaisesRegex(ValueError, "Changed/duplicate"):
            auditor._segment_override(
                auditor._class(tree, "SGMVFISegmentInterpolate"),
                base_types, req,
            )
        changed = FAKE_NODES.replace(
            "base = SGMVFIInterpolate.INPUT_TYPES()",
            "base = download_schema_online()"
        )
        tree = ast.parse(changed)
        base_types, req = auditor._initial_base_sockets(
            auditor._class(tree, "SGMVFIInterpolate")
        )
        with self.assertRaisesRegex(ValueError, "base invocation"):
            auditor._segment_override(
                auditor._class(tree, "SGMVFISegmentInterpolate"), base_types, req,
            )

    def test_graph_socket_type_mutation_fails(self):
        graph = load_graph()
        segment = next(x for x in graph["nodes"] if x["id"] == 22)
        port = next(x for x in segment["inputs"] if x["name"] == "model")
        port["type"] = "UNRELATED_MODEL"
        with self.assertRaisesRegex(ValueError, "input name/type parity"):
            auditor._check_graph(graph, known_graph_signatures())

    def test_model_link_mutation_fails(self):
        graph = load_graph()
        model_link = next(edge for edge in graph["links"] if edge[0] == 18)
        model_link[3] = 31
        with self.assertRaisesRegex(ValueError, "SGM input/output link changed"):
            auditor._check_graph(graph, known_graph_signatures())

    def test_missing_source_widget_and_provenance_fail(self):
        graph = load_graph()
        loader = next(x for x in graph["nodes"] if x["id"] == 21)
        loader["widgets_values"].pop()
        with self.assertRaisesRegex(ValueError, "widget count drift"):
            auditor._check_graph(graph, known_graph_signatures())
        loader["widgets_values"].append(0)
        loader["properties"]["ver"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "source provenance"):
            auditor._check_graph(graph, known_graph_signatures())

    def test_changed_output_type_fails(self):
        graph = load_graph()
        segment = next(x for x in graph["nodes"] if x["id"] == 22)
        segment["outputs"][1]["type"] = "OTHER_MODEL"
        with self.assertRaisesRegex(ValueError, "output name/type parity"):
            auditor._check_graph(graph, known_graph_signatures())

    def test_pinned_real_source_audit_baseline_without_import_or_download(self):
        with tempfile.TemporaryDirectory() as directory:
            tween = Path(directory)
            (tween / "nodes.py").write_text(FAKE_NODES, encoding="utf-8")
            (tween / "__init__.py").write_text(FAKE_INIT, encoding="utf-8")
            with mock.patch.object(auditor.subprocess, "run") as git:
                git.return_value.stdout = auditor.TWEEN_SHA + "\n"
                report = auditor.audit(ROOT, tween)
            self.assertEqual(git.call_count, 1)
            self.assertEqual(report["status"], "SOURCE_INTERFACE_PARITY_ONLY_HOLD")
            self.assertTrue(report["sgm_loader_and_segment_source_schema_parity"])
            self.assertFalse(report["whole_workflow_qualified"])
            self.assertFalse(report["checkpoint_provenance_license_and_cupy_qualified"])
            self.assertFalse(report["graph_modified"])

    def test_wrong_head_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            tween = Path(directory)
            with mock.patch.object(auditor.subprocess, "run") as git:
                git.return_value.stdout = "0" * 40 + "\n"
                with self.assertRaisesRegex(ValueError, "commit differs"):
                    auditor.audit(ROOT, tween)


if __name__ == "__main__":
    unittest.main()
