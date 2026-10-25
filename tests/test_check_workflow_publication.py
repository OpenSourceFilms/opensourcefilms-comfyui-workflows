"""Synthetic redaction and publication-hygiene tests for ComfyUI graphs."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check-workflow-publication.py"
SPEC = importlib.util.spec_from_file_location("workflow_publication", SCRIPT)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


class PublicationHygieneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_generic_workflow_is_clean(self):
        graph = {"nodes": [{"type": "LoadImage", "widgets_values": [
            "input_video.mp4", "models/example.safetensors",
            "https://huggingface.co/repository"]}], "links": []}
        self.assertEqual(tool.scan_data(graph), [])

    def test_posix_paths_rejected(self):
        for value in ("/home/someone/project.mov", "/workspace/private/file.png",
                      "/mnt/data/output.png", "/tmp/output.png"):
            with self.subTest(value=value):
                self.assertIn("local_posix_path", [x["rule"] for x in tool.scan_data(value)])

    def test_windows_user_directory_rejected(self):
        results = tool.scan_data(r"C:\Users\someone\Videos\input.mov")
        self.assertIn("local_windows_user_path", [x["rule"] for x in results])

    def test_execution_cache_metadata_rejected(self):
        graph = {"nodes": [{"properties": {"videopreview": {"file": "safe.mp4"}}}]}
        self.assertIn("embedded_preview_or_cache",
                      [x["rule"] for x in tool.scan_data(graph)])

    def test_token_and_personal_email_never_echoed(self):
        secret = "ghp_" + "a" * 30
        graph = {"nodes": [{"widgets_values": [secret, "private.user@gmail.com"]}]}
        output = json.dumps(tool.scan_data(graph))
        self.assertIn("credential_pattern", output)
        self.assertIn("personal_email", output)
        self.assertNotIn(secret, output)
        self.assertNotIn("private.user@gmail.com", output)

    def test_public_example_emails_not_flagged(self):
        self.assertEqual(tool.scan_data("input@example.com contact@opensourcefilms.org"), [])

    def test_private_service_urls_rejected(self):
        for value in ("http://127.0.0.1:8188", "http://10.0.0.1/scene",
                      "https://example.proxy.runpod.net/", "s3://private-bucket/key"):
            with self.subTest(value=value):
                self.assertTrue(tool.scan_data(value))

    def test_corrupt_json_or_symlink_is_refused(self):
        p = self.root / "bad.json"
        p.write_text("{broken")
        self.assertEqual(tool.scan_file(p)["issues"][0]["rule"], "invalid_json")
        target = self.root / "link.json"
        target.symlink_to(p)
        self.assertEqual(tool.scan_file(target)["issues"][0]["rule"], "not_regular_file")

    def test_cli_success_and_redacted_failure(self):
        graph = self.root / "graph.json"
        graph.write_text(json.dumps({"nodes": [], "links": []}))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(tool.main([str(self.root)]), 0)
        self.assertTrue(json.loads(out.getvalue())["ok"])
        secret = "ghp_" + "A" * 30
        graph.write_text(json.dumps({"nodes": [{"widgets_values": [secret]}], "links": []}))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(tool.main([str(self.root)]), 1)
        self.assertFalse(json.loads(out.getvalue())["ok"])
        self.assertNotIn(secret, out.getvalue())


if __name__ == "__main__":
    unittest.main()
