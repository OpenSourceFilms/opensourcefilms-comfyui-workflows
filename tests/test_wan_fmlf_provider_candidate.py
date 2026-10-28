"""Synthetic no-network contracts for the unlicensed Wan FMLF source audit."""
from __future__ import annotations

from pathlib import Path
import importlib.util
import json
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "wan_fmlf_candidate", ROOT / "scripts/audit_wan_fmlf_provider_candidate.py"
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def candidate_source(name: str) -> str:
    return (
        "class " + name + "(io.ComfyNode):\n"
        "    @classmethod\n"
        "    def define_schema(cls):\n"
        "        return io.Schema(\n"
        '            node_id="' + name + '",\n'
        '            inputs=[io.Conditioning.Input("positive"),\n'
        '                    io.Image.Input("image", optional=True)],\n'
        '            outputs=[io.Conditioning.Output(display_name="positive_high"),\n'
        '                     io.Conditioning.Output(display_name="positive_low"),\n'
        '                     io.Conditioning.Output(display_name="negative"),\n'
        '                     io.Latent.Output(display_name="latent")],\n'
        "        )\n"
    )


class FMLFCandidateAuditContractTests(unittest.TestCase):
    def test_names_bind_to_a_single_unlicensed_upstream_revision(self):
        self.assertEqual(audit.PIN, "7140cd224396aff9fd909ab0041c3fbf81b92b0c")
        self.assertEqual(audit.UPSTREAM, "wallen0322/ComfyUI-Wan22FMLF")
        self.assertEqual(audit.EXPECTED_COUNTS, {
            "WanFirstMiddleLastFrameToVideo": 2,
            "WanFourFrameReferenceUltimate": 1,
            "WanMultiFrameRefToVideo": 1,
        })

    def test_parser_requires_exact_io_schema_names_and_types(self):
        name = "WanFirstMiddleLastFrameToVideo"
        data = audit.schema_from_source(candidate_source(name), name)
        self.assertEqual(data["inputs"], [
            ("positive", "CONDITIONING"), ("image", "IMAGE")
        ])
        self.assertEqual(tuple(data["outputs"]), audit.OUTPUTS)
        with self.assertRaisesRegex(ValueError, "node id differs"):
            audit.schema_from_source(
                candidate_source(name).replace('node_id="' + name + '"',
                                               'node_id="AnotherNode"'), name
            )
        with self.assertRaisesRegex(ValueError, "Duplicate provider"):
            audit.schema_from_source(
                candidate_source(name).replace('io.Image.Input("image"',
                                               'io.Image.Input("positive"'), name
            )

    def test_ui_export_requires_all_sockets_not_just_class_name(self):
        name = "WanFirstMiddleLastFrameToVideo"
        data = audit.schema_from_source(candidate_source(name), name)
        node = {
            "type": name,
            "inputs": [
                {"name": "image", "type": "IMAGE"},
                {"name": "positive", "type": "CONDITIONING"},
            ],
            "outputs": [
                {"name": a, "type": b} for a, b in audit.OUTPUTS
            ],
        }
        self.assertTrue(
            audit.validate_exported_node(node, data)["schema_name_type_parity"]
        )
        with self.assertRaisesRegex(ValueError, "Provider/UI inputs mismatch"):
            audit.validate_exported_node({
                **node, "inputs": [{"name": "image", "type": "IMAGE"}],
            }, data)
        with self.assertRaisesRegex(ValueError, "Provider/UI inputs mismatch"):
            audit.validate_exported_node({
                **node, "inputs": [
                    {"name": "positive", "type": "STRING"},
                    {"name": "image", "type": "IMAGE"},
                ],
            }, data)
        with self.assertRaisesRegex(ValueError, "Duplicate UI socket name"):
            audit.validate_exported_node({
                **node, "inputs": node["inputs"] + [node["inputs"][0]],
            }, data)

    def test_audit_never_grants_rights_or_registration_with_matched_sockets(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "source"
            src.mkdir()
            home = root / "osf" / "workflows" / "commercial-compatible"
            home.mkdir(parents=True)
            for name, filename in audit.SOURCE_FILES.items():
                (src / filename).write_text(candidate_source(name))
            (src / "__init__.py").write_text(
                "\n".join(audit.SOURCE_FILES.keys()), encoding="utf-8"
            )
            for filename in audit.WORKFLOWS:
                if filename.startswith("wan22_"):
                    types = list(audit.SOURCE_FILES)
                else:
                    types = ["WanFirstMiddleLastFrameToVideo"]
                nodes = []
                for name in types:
                    schema = audit.schema_from_source(
                        candidate_source(name), name
                    )
                    nodes.append({
                        "type": name,
                        "inputs": [
                            {"name": n, "type": t} for n, t in schema["inputs"]
                        ],
                        "outputs": [
                            {"name": n, "type": t} for n, t in schema["outputs"]
                        ],
                    })
                (home / filename).write_text(json.dumps({"nodes": nodes}))
            with mock.patch.object(audit.subprocess, "run") as git:
                git.return_value.stdout = audit.PIN + "\n"
                verified = audit.audit(root / "osf", src)
                self.assertTrue(verified["source_ui_socket_name_and_type_parity"])
                self.assertFalse(verified["commercial_redistribution_or_use_cleared"])
                self.assertFalse(verified["node_import_registration_qualified"])
                self.assertFalse(verified["eleven_workflow_acceptance"])
                self.assertFalse(verified["production_install_allowed_by_this_audit"])
                (src / "LICENSE.md").write_text("New terms require review")
                with self.assertRaisesRegex(ValueError, "licensing changed"):
                    audit.audit(root / "osf", src)
                (src / "LICENSE.md").unlink()
                git.return_value.stdout = "a" * 40 + "\n"
                with self.assertRaisesRegex(ValueError, "exact reviewed pin"):
                    audit.audit(root / "osf", src)


if __name__ == "__main__":
    unittest.main()
