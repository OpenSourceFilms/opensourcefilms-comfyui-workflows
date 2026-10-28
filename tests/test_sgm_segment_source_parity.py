"""Offline, no-import contracts for pinned SGM segment model socket parity."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "sgm_source_parity", ROOT / "scripts" / "audit_sgm_segment_source_parity.py"
)
parity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parity)


SOURCE = '''
class LoadSGMVFIModel:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model_path": (get_available_sgm_models(), {"default": "test"}),
            "tta": ("BOOLEAN", {}),
            "num_key_points": ("FLOAT", {}),
        }}
    RETURN_TYPES = ("SGM_VFI_MODEL",)
    RETURN_NAMES = ("model",)

class SGMVFIInterpolate:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
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
            },
            "optional": {"settings": ("VFI_SETTINGS", {})},
        }

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
REGISTRY = {
    "LoadSGMVFIModel": "LoadSGMVFIModel",
    "SGMVFISegmentInterpolate": "SGMVFISegmentInterpolate",
}


class SGMPinnedSourceParityContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads((ROOT / parity.GRAPH).read_text(
            encoding="utf-8"
        ))

    def test_exact_expected_pinned_sockets_and_named_returns(self):
        observed = parity.inspect_sgm_source(SOURCE, REGISTRY)
        self.assertEqual(set(observed), {21, 22})
        self.assertEqual(observed[21]["input_types"], parity.EXPECTED_SOCKETS[21])
        self.assertEqual(observed[22]["input_types"], parity.EXPECTED_SOCKETS[22])
        self.assertEqual(observed[22]["optional_names"], ["settings"])
        self.assertEqual(observed[22]["output_names"], ["images", "model"])
        self.assertEqual(observed[22]["output_types"], ["IMAGE", "SGM_VFI_MODEL"])

    def test_graph_source_parity_and_pass_through_link(self):
        observed = parity.inspect_sgm_source(SOURCE, REGISTRY)
        report = parity.inspect_sgm_graph(self.graph, observed)
        self.assertEqual(report["model_link_id"], 18)
        self.assertEqual(report["model_type"], "SGM_VFI_MODEL")
        self.assertEqual([x["node_id"] for x in report["selected_nodes"]], [21, 22])
        self.assertTrue(report["segment_model_pass_through_source_signature_verified"])

    def test_reject_wrong_model_output_type_or_name(self):
        for mutated in (
            SOURCE.replace('"SGM_VFI_MODEL",)\n    RETURN_NAMES',
                           '"OTHER_MODEL",)\n    RETURN_NAMES', 1),
            SOURCE.replace('RETURN_NAMES = ("images", "model")',
                           'RETURN_NAMES = ("images", "other")'),
        ):
            with self.assertRaisesRegex(ValueError, "output types/names"):
                parity.inspect_sgm_source(mutated, REGISTRY)

    def test_reject_wrong_optional_and_required_sockets(self):
        for mutation in (
            SOURCE.replace('"settings": ("VFI_SETTINGS", {})',
                           '"settings": ("OTHER_TYPE", {})'),
            SOURCE.replace('"segment_size"] = ("INT", {})',
                           '"segment_size"] = ("FLOAT", {})'),
            SOURCE.replace('"num_key_points": ("FLOAT", {})',
                           '"num_key_points": ("STRING", {})'),
        ):
            with self.assertRaisesRegex(ValueError, "(socket|extension)"):
                parity.inspect_sgm_source(mutation, REGISTRY)

    def test_reject_dynamic_mutation_and_unexpected_inheritance(self):
        for mutation in (
            SOURCE.replace(
                'base["required"]["segment_size"]',
                'base["optional"]["segment_size"]'),
            SOURCE.replace(
                "class SGMVFISegmentInterpolate(SGMVFIInterpolate):",
                "class SGMVFISegmentInterpolate(object):"),
            SOURCE.replace(
                "base = SGMVFIInterpolate.INPUT_TYPES()",
                "base = build_at_runtime()"),
        ):
            with self.assertRaisesRegex(ValueError, "SGM"):
                parity.inspect_sgm_source(mutation, REGISTRY)

    def test_reject_unreviewed_dynamic_provider_for_model_path(self):
        wrong = SOURCE.replace(
            'get_available_sgm_models()', 'download_at_runtime()',
        )
        with self.assertRaisesRegex(ValueError, "Unreviewed dynamic"):
            parity.inspect_sgm_source(wrong, REGISTRY)

    def test_reject_wrong_registry_and_missing_source_classes(self):
        with self.assertRaisesRegex(ValueError, "registry class changed"):
            parity.inspect_sgm_source(
                SOURCE, {**REGISTRY, "LoadSGMVFIModel": "WrongLoader"}
            )
        with self.assertRaisesRegex(ValueError, "exactly one pinned"):
            parity.inspect_sgm_source(
                SOURCE.replace("class LoadSGMVFIModel:", "class OtherClass:"),
                REGISTRY,
            )

    def test_reject_graph_socket_provenance_and_model_links(self):
        source = parity.inspect_sgm_source(SOURCE, REGISTRY)
        for method in ("socket", "provenance", "active_link", "reverse_link",
                       "widgets", "output"):
            graph = copy.deepcopy(self.graph)
            node = next(n for n in graph["nodes"] if n["id"] == 22)
            if method == "socket":
                node["inputs"][0]["type"] = "LATENT"
            elif method == "provenance":
                node["properties"]["ver"] = "0" * 40
            elif method == "active_link":
                graph["links"] = [link for link in graph["links"] if link[0] != 18]
            elif method == "reverse_link":
                node["inputs"][1]["link"] = 33
            elif method == "widgets":
                node["widgets_values"].pop()
            elif method == "output":
                node["outputs"][1]["type"] = "OTHER"
            with self.subTest(method=method):
                with self.assertRaises(ValueError):
                    parity.inspect_sgm_graph(graph, source)

    def test_original_selected_graph_and_manifest_remain_unmodified(self):
        before = (ROOT / parity.GRAPH).read_bytes()
        manifest = (ROOT / "DEPENDENCIES.lock").read_bytes()
        source = parity.inspect_sgm_source(SOURCE, REGISTRY)
        parity.inspect_sgm_graph(copy.deepcopy(self.graph), source)
        self.assertEqual(before, (ROOT / parity.GRAPH).read_bytes())
        self.assertEqual(manifest, (ROOT / "DEPENDENCIES.lock").read_bytes())
        parity.pins.verify_manifest_pins(manifest.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
