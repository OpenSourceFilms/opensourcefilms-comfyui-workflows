"""Regression tests for every published ComfyUI graph.

The check is intentionally structural only. It does not install custom nodes,
download model weights, run GPU inference or check third-party licensing.
"""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate-workflow-json.py"
SPEC = importlib.util.spec_from_file_location("osf_workflow_validator", SCRIPT)
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class PublishedWorkflowsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graphs = sorted((ROOT / "workflows").rglob("*.json"))

    def test_published_workflows_are_structurally_valid(self):
        self.assertGreaterEqual(len(self.graphs), 16, "Some previously published workflows are missing")
        for graph in self.graphs:
            with self.subTest(path=str(graph.relative_to(ROOT))):
                result = validator.check_file(graph)
                self.assertTrue(result["ok"], str(result))

    def test_ui_and_api_examples_both_covered(self):
        formats = {validator.check_file(p)["format"] for p in self.graphs}
        self.assertIn("ui", formats)
        self.assertIn("api", formats)


if __name__ == "__main__":
    unittest.main()
