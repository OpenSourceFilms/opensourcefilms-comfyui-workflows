"""Security regression tests: synthetic secrets only, never real credentials."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[1] / "scripts/check-workflow-publication.py"
SPEC=importlib.util.spec_from_file_location("pub_hygiene",SCRIPT)
hygiene=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hygiene)


class SupplementalPublicationSafetyTests(unittest.TestCase):
    def rules(self,value):
        results=hygiene.scan_data({"node":{"widgets_values":[value]}})
        return {item["rule"] for item in results},json.dumps(results)

    def test_embedded_url_username_password(self):
        cases=[
            "https://demo:supersecret@example.com/path",
            "http://a:b@example.org/foo",
            "ftp://demo:secret@example.net/clip.png",
        ]
        for v in cases:
            with self.subTest(v=v.split("://")[0]):
                rules,output=self.rules(v)
                self.assertIn("url_embedded_credentials",rules)
                self.assertNotIn("supersecret",output)
                self.assertNotIn("demo",output)

    def test_other_gh_token_prefixes(self):
        for prefix in ("gho_","ghu_","ghs_","ghr_"):
            with self.subTest(prefix=prefix):
                secret=prefix+"A"*40
                rules,out=self.rules(secret)
                self.assertIn("credential_pattern",rules)
                self.assertNotIn(secret,out)

    def test_loopback_and_linklocal_not_just_127_0_0_1(self):
        for host in ("127.3.4.5","0.0.0.0","169.254.169.254","[::1]","[fd00::3]","[fe80::abcd]"):
            with self.subTest(host=host):
                value="http://"+host+":8188/path"
                rules,out=self.rules(value)
                self.assertIn("private_endpoint",rules)
                self.assertNotIn(value,out)

    def test_safe_public_urls_and_metadata(self):
        for value in (
            "https://example.com/no-creds",
            "https://huggingface.co/models/foo",
            "https://example.org/docs:version/path",
            "http://[2001:4860:4860::8888]/dns",
            "models/safemodel.safetensors"
        ):
            with self.subTest(value=value):
                self.assertEqual(self.rules(value)[0],set())

    def test_deep_nested_documents_fail_closed_without_crash(self):
        value="safe"
        for _ in range(1200):
            value=[value]
        results=hygiene.scan_data(value)
        self.assertIn("excessive_json_depth",{r["rule"] for r in results})

    def test_no_raw_values_in_deep_boundary_warning(self):
        value={"secret": "https://dummy:never-show@example.com"}
        for _ in range(400):
            value=[value]
        findings=json.dumps(hygiene.scan_data(value))
        self.assertIn("excessive_json_depth",findings)
        self.assertNotIn("never-show",findings)

    def test_scan_file_invalid_nested_json_is_redacted(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"nested.json"
            p.write_text("["*1200+"0"+"]"*1200)
            issue=hygiene.scan_file(p)
            self.assertTrue(issue["issues"])
            self.assertEqual(issue["issues"][0]["rule"],"invalid_json")
            self.assertNotIn("Traceback",json.dumps(issue))


if __name__=="__main__":
    unittest.main()
