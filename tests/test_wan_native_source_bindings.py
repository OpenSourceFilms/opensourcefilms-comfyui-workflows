"""No-network contract tests for pinned public Wan schema versus UI exports."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "wan_native_source_audit", ROOT / "scripts" / "audit_wan_native_source_bindings.py"
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


SOURCE = '''
class WanFirstLastFrameToVideo:
    def define_schema(cls):
        return io.Schema(
            node_id="WanFirstLastFrameToVideo",
            inputs=[io.Conditioning.Input("positive"), io.Conditioning.Input("negative"),
                    io.Vae.Input("vae"), io.Int.Input("width")],
            outputs=[io.Conditioning.Output(display_name="positive"),
                     io.Conditioning.Output(display_name="negative"),
                     io.Latent.Output(display_name="latent")])
class WanVaceToVideo:
    def define_schema(cls):
        return io.Schema(
            node_id="WanVaceToVideo",
            inputs=[io.Conditioning.Input("positive"), io.Image.Input("control_video")],
            outputs=[io.Conditioning.Output(display_name="positive"),
                     io.Latent.Output(display_name="latent")])
class TrimVideoLatent:
    def define_schema(cls):
        return io.Schema(node_id="TrimVideoLatent",
            inputs=[io.Latent.Input("samples"), io.Int.Input("trim_amount")],
            outputs=[io.Latent.Output()])
'''


class WanNativeSourceAuditContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.native = self.root / "nodes_wan.py"
        self.native.write_text(SOURCE, encoding="utf-8")
        (self.root / "workflows" / "commercial-compatible").mkdir(parents=True)
        blocks = []
        for stem in audit.WAN_FILES:
            path = "workflows/commercial-compatible/" + stem + ".json"
            blocks.append(path + ":\n  commercial_status: commercial-compatible\n")
            graph = {"nodes": []}
            (self.root / path).write_text(json.dumps(graph), encoding="utf-8")
        (self.root / "DEPENDENCIES.lock").write_text("\n".join(blocks), encoding="utf-8")
        self.schemas = audit.native_wan_schemas(SOURCE)

    def add(self, index, cls, inputs=None, outputs=None):
        rel = "workflows/commercial-compatible/" + audit.WAN_FILES[index] + ".json"
        p = self.root / rel
        graph = json.loads(p.read_text(encoding="utf-8"))
        if inputs is None and cls in self.schemas:
            inputs = self.schemas[cls]["inputs"]
        if outputs is None and cls in self.schemas:
            outputs = self.schemas[cls]["outputs"]
        graph["nodes"].append({
            "id": len(graph["nodes"]) + 1,
            "type": cls,
            "inputs": [{"name": n} for n in (inputs or [])],
            "outputs": [{"name": n} for n in (outputs or [])],
            "widgets_values": ["PRIVATE_PROMPT_NOT_IN_REPORT"],
        })
        p.write_text(json.dumps(graph), encoding="utf-8")

    def populate(self):
        self.add(0, "WanFirstLastFrameToVideo")
        self.add(0, "WanFourFrameReferenceUltimate")
        self.add(1, "WanFirstLastFrameToVideo")
        self.add(2, "WanFirstMiddleLastFrameToVideo")
        self.add(3, "WanMultiFrameRefToVideo")
        self.add(4, "WanVaceToVideo")
        self.add(4, "TrimVideoLatent")

    def test_extracts_only_literal_native_schema_names(self):
        self.assertEqual(set(self.schemas), audit.NATIVE_WAN_CLASS_IDS)
        self.assertEqual(self.schemas["TrimVideoLatent"]["outputs"], ["LATENT"])
        self.assertEqual(self.schemas["WanFirstLastFrameToVideo"]["inputs"],
                         ["positive", "negative", "vae", "width"])
        self.assertEqual(self.schemas["WanVaceToVideo"]["outputs"],
                         ["positive", "latent"])

    def test_five_graph_audit_reports_unresolved_without_claiming_acceptance(self):
        self.populate()
        result = audit.audit_wan_source(self.native, self.root)
        self.assertEqual(result["selected_wan_graphs_checked"], 5)
        self.assertEqual(result["missing_native_class_occurrences"],
                         {name: 1 for name in audit.UNRESOLVED_WAN_CLASS_IDS})
        self.assertEqual(result["native_class_occurrences_with_socket_name_parity"],
                         {"TrimVideoLatent": 1, "WanFirstLastFrameToVideo": 2,
                          "WanVaceToVideo": 1})
        self.assertFalse(result["all_wan_class_ids_available"])
        self.assertFalse(result["wan_workflows_executable"])
        self.assertFalse(result["source_provider_rights_cleared"])
        self.assertNotIn("PRIVATE_PROMPT_NOT_IN_REPORT", json.dumps(result))

    def test_rejects_native_ui_input_or_output_schema_drift(self):
        self.populate()
        self.add(0, "WanFirstLastFrameToVideo",
                 ["positive", "negative"], ["positive", "negative", "latent"])
        with self.assertRaisesRegex(ValueError, "input sockets"):
            audit.audit_wan_source(self.native, self.root)
        rel = "workflows/commercial-compatible/" + audit.WAN_FILES[0] + ".json"
        graph = json.loads((self.root / rel).read_text(encoding="utf-8"))
        graph["nodes"].pop()
        graph["nodes"][0]["outputs"][0]["name"] = "incorrect"
        (self.root / rel).write_text(json.dumps(graph), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "output sockets"):
            audit.audit_wan_source(self.native, self.root)

    def test_rejects_unreviewed_missing_node_classes(self):
        self.populate()
        self.add(0, "WanUnreviewedImaginaryNode")
        with self.assertRaisesRegex(ValueError, "Unknown Wan class"):
            audit.audit_wan_source(self.native, self.root)

    def test_rejects_changed_missing_baseline(self):
        self.populate()
        self.native.write_text(
            SOURCE + '''
class WanFourFrameReferenceUltimate:
    def define_schema(cls):
        return io.Schema(node_id="WanFourFrameReferenceUltimate",
            inputs=[io.Conditioning.Input("positive")],
            outputs=[io.Latent.Output()])
''', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Previously unresolved"):
            audit.audit_wan_source(self.native, self.root)

    def test_rejects_missing_or_unlisted_graph_and_symlinks(self):
        self.populate()
        rel = "workflows/commercial-compatible/" + audit.WAN_FILES[3] + ".json"
        path = self.root / rel
        path.unlink()
        with self.assertRaisesRegex(ValueError, "Missing/symlinked"):
            audit.audit_wan_source(self.native, self.root)
        path.symlink_to(self.native)
        with self.assertRaisesRegex(ValueError, "Missing/symlinked"):
            audit.audit_wan_source(self.native, self.root)

    def test_rejects_wrong_manifest_commercial_status(self):
        self.populate()
        path = self.root / "DEPENDENCIES.lock"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("commercial-compatible", "research-only"),
                        encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not uniquely listed"):
            audit.audit_wan_source(self.native, self.root)


if __name__ == "__main__":
    unittest.main()
