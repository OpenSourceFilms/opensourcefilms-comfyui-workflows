"""Offline contracts for GIMM + SGM source-only binding audit."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "gimm_binding_audit", ROOT / "scripts" / "audit_gimm_sgm_source_bindings.py"
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


GIMM_SOURCE = '''
class DownloadAndLoadGIMMVFIModel:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"model": ("STR",)},
                "optional": {"precision": ("STR",), "torch_compile": ("BOOL",)}}
    RETURN_TYPES = ("GIMMVIF_MODEL",)

class GIMMVFI_interpolate:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "gimmvfi_model": ("GIMMVIF_MODEL",), "images": ("IMAGE",),
            "ds_factor": ("FLOAT",), "interpolation_factor": ("INT",),
            "seed": ("INT",)},
            "optional": {"output_flows": ("BOOLEAN",)}}

NODE_CLASS_MAPPINGS = {
    "DownloadAndLoadGIMMVFIModel": DownloadAndLoadGIMMVFIModel,
    "GIMMVFI_interpolate": GIMMVFI_interpolate,
}
'''
TWEEN_INIT = '''
NODE_CLASS_MAPPINGS = {
    "LoadGIMMVFIModel": LoadGIMMVFIModel,
    "GIMMVFIInterpolate": GIMMVFIInterpolate,
    "LoadSGMVFIModel": LoadSGMVFIModel,
    "SGMVFISegmentInterpolate": SGMVFISegmentInterpolate,
}
'''
TWEEN_NODES = '''
class GIMMVFIInterpolate:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "images": ("IMAGE",), "model": ("GIMM_VFI_MODEL",),
            "multiplier": ("INT",), "single_pass": ("BOOLEAN",)}}
'''


class PinnedGimmSourceTests(unittest.TestCase):
    def test_real_manifest_graph_requires_unavailable_loader(self):
        nodes = audit.graph_nodes(ROOT / audit.GRAPH)
        self.assertEqual({x["class_type"] for x in nodes},
                         audit.GIMM_REQUIRED | audit.SGM_REQUIRED)
        audit.verify_manifest_pins(
            (ROOT / "DEPENDENCIES.lock").read_text(encoding="utf-8")
        )
        interpolation = next(x for x in nodes if x["class_type"] == "GIMMVFIInterpolate")
        self.assertIn("gimmvfi_model", interpolation["input_names"])
        self.assertIn("ds_factor", interpolation["input_names"])

    def test_static_mapping_and_input_parser(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "nodes.py"
            p.write_text(GIMM_SOURCE)
            mapping = audit.mapping_from_source(p)
            self.assertIn("GIMMVFI_interpolate", mapping)
            self.assertNotIn("GIMMVFI_loader", mapping)
            sockets = audit.class_source_sockets(
                p, "DownloadAndLoadGIMMVFIModel"
            )
            self.assertEqual(sockets["required"], ["model"])
            self.assertEqual(sockets["return_types"], ["GIMMVIF_MODEL"])
            self.assertIn("precision", sockets["optional"])

    def test_audit_returns_hold_for_exact_reviewed_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            gimm = root / "gimm"
            tween = root / "tween"
            gimm.mkdir()
            tween.mkdir()
            (gimm / "nodes.py").write_text(GIMM_SOURCE)
            (tween / "__init__.py").write_text(TWEEN_INIT)
            (tween / "nodes.py").write_text(TWEEN_NODES)
            with mock.patch.object(audit, "verify_git_head") as pin:
                result = audit.audit(ROOT, gimm, tween)
            self.assertEqual(pin.call_count, 2)
            self.assertEqual(result["status"], "HOLD")
            self.assertTrue(result["gimm_loader_missing_from_both_pins"])
            self.assertIn("ds_factor",
                          result["tween_interpolator_same_name_but_missing_input_sockets"])
            self.assertFalse(result["source_binding_qualified"])
            self.assertFalse(result["model_weights_or_gpu_inference_qualified"])

    def test_unexpected_loader_registration_requires_reaudit(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            g = p / "g"
            t = p / "t"
            g.mkdir()
            t.mkdir()
            (g / "nodes.py").write_text(
                GIMM_SOURCE.replace(
                    '"DownloadAndLoadGIMMVFIModel": DownloadAndLoadGIMMVFIModel,',
                    '"GIMMVFI_loader": DownloadAndLoadGIMMVFIModel,\n'
                    '    "DownloadAndLoadGIMMVFIModel": DownloadAndLoadGIMMVFIModel,'
                )
            )
            (t / "__init__.py").write_text(TWEEN_INIT)
            (t / "nodes.py").write_text(TWEEN_NODES)
            with mock.patch.object(audit, "verify_git_head"):
                with self.assertRaisesRegex(ValueError, "baseline changed"):
                    audit.audit(ROOT, g, t)

    def test_wrong_source_pin_rejected(self):
        lock = (ROOT / "DEPENDENCIES.lock").read_text(encoding="utf-8")
        bad = lock.replace(audit.GIMM_SHA, "0" * 40)
        with self.assertRaisesRegex(ValueError, "absent or changed"):
            audit.verify_manifest_pins(bad)

    def test_non_literal_registry_is_not_executed(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "nodes.py"
            p.write_text("NODE_CLASS_MAPPINGS = build_at_runtime()\n")
            with self.assertRaisesRegex(ValueError, "no longer literal"):
                audit.mapping_from_source(p)


if __name__ == "__main__":
    unittest.main()
