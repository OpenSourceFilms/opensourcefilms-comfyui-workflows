"""No-network regressions for pinned VHS_LoadVideo -> native SAM3 IMAGE wiring."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "audit_vhs_sam3_api_image_edges.py"
spec = importlib.util.spec_from_file_location("osf_vhs_api_edge_audit", PATH)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

MAPPING = 'NODE_CLASS_MAPPINGS = {"VHS_LoadVideo": LoadVideoUpload}'
UTILS = 'imageOrLatent = MultiInput("IMAGE", ["IMAGE", "LATENT"])'
LOADER = '''
def load_video(vae=None):
    if vae is None:
        return (images, 2, audio, info)
    else:
        return ({"samples": images}, 2, audio, info)

class LoadVideoUpload:
    RETURN_TYPES = (imageOrLatent, "INT", "AUDIO", "VHS_VIDEOINFO")
    RETURN_NAMES = ("IMAGE", "frame_count", "audio", "video_info")
    def load_video(self, **kwargs):
        return load_video(**kwargs)
'''


class PinnedVhsNativeSam3SourceTests(unittest.TestCase):
    def test_positive_pinned_ast_proves_image_branch_and_latent_guard(self):
        result = audit.check_vhs_ast(MAPPING, LOADER, UTILS)
        self.assertTrue(result["no_vae_branch_returns_images"])
        self.assertTrue(result["with_vae_branch_returns_latent"])
        self.assertEqual(result["declared_output_zero_union"], "IMAGE|LATENT")
        self.assertFalse(result["graph_media_decoded"])

    def test_changed_node_registration_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "registration drifted"):
            audit.check_vhs_ast(
                MAPPING.replace("LoadVideoUpload", "LoadVideoPath"), LOADER, UTILS
            )

    def test_implicit_output_mode_or_vae_branch_change_is_rejected(self):
        bad = LOADER.replace('return (images, 2, audio, info)',
                             'return ({"samples": images}, 2, audio, info)')
        with self.assertRaisesRegex(ValueError, "VAE image/latent"):
            audit.check_vhs_ast(MAPPING, bad, UTILS)
        with self.assertRaisesRegex(ValueError, "union differs"):
            audit.check_vhs_ast(
                MAPPING, LOADER, UTILS.replace('["IMAGE", "LATENT"]', '["LATENT"]')
            )

    def test_checked_in_graphs_have_exact_no_vae_image_edges(self):
        selected = audit.check_saved_api_workflows(ROOT, audit._native_types(ROOT))
        self.assertEqual(set(selected), set(audit.GRAPHS))
        self.assertEqual(sum(x["vhs_image_output_edges"]
                             for x in selected.values()), 6)
        self.assertTrue(all(not x["saved_vae_input_present"]
                            for x in selected.values()))
        self.assertTrue(all(not x["live_video_decode_or_model_inference_tested"]
                            for x in selected.values()))

    def _graph_mutation(self, mutate):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "workflows" / "commercial-compatible"
            folder.mkdir(parents=True)
            for name in audit.GRAPHS:
                source = ROOT / "workflows" / "commercial-compatible" / (name + ".json")
                graph = json.loads(source.read_text(encoding="utf-8"))
                if name == "step4_5_sam3_mask":
                    mutate(graph)
                (folder / (name + ".json")).write_text(json.dumps(graph))
            return audit.check_saved_api_workflows(root, audit._native_types(ROOT))

    def test_vae_option_cannot_silently_convert_image_output_to_latent(self):
        def mutate(graph):
            graph["3"]["inputs"]["vae"] = ["1", 2]
        with self.assertRaisesRegex(ValueError, "VAE mode differs"):
            self._graph_mutation(mutate)

    def test_wrong_vhs_output_index_cannot_be_treated_as_image(self):
        def mutate(graph):
            graph["4"]["inputs"]["images"] = ["3", 1]
        with self.assertRaisesRegex(ValueError, "destinations or slots differ"):
            self._graph_mutation(mutate)

    def test_wrong_native_socket_or_unreviewed_destination_fails_closed(self):
        def mutate(graph):
            graph["10"]["inputs"].pop("images")
            graph["10"]["inputs"]["opacity"] = ["3", 0]
        with self.assertRaisesRegex(ValueError, "destinations or slots differ"):
            self._graph_mutation(mutate)

    def test_empty_saved_video_key_or_bad_loader_class_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "loader string"):
            self._graph_mutation(
                lambda graph: graph["3"]["inputs"].__setitem__("video", "")
            )
        with self.assertRaisesRegex(ValueError, "VAE mode differs"):
            self._graph_mutation(
                lambda graph: graph["3"].__setitem__("class_type", "VHS_LoadVideoPath")
            )


if __name__ == "__main__":
    unittest.main()
