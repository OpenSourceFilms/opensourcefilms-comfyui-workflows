"""Offline regression checks for published workflow licensing declarations.

No network, third-party packages, model weights or legal opinion required.
This catches contradictory documentation, not undisclosed upstream terms.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "workflows"
MANIFEST = ROOT / "DEPENDENCIES.lock"
SUPPORTED = {"commercial-compatible", "research-only"}


def declarations():
    text = MANIFEST.read_text(encoding="utf-8")
    marker = re.compile(r"(?m)^(workflows/(?:commercial-compatible|research-only)/[^:\n]+\.json):\s*$")
    matches = list(marker.finditer(text))
    result = {}
    for i, match in enumerate(matches):
        block = text[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        status = re.search(r"(?m)^  commercial_status:\s*(commercial-compatible|research-only)\s*$", block)
        if status is None:
            raise AssertionError(f"Missing workflow commercial_status: {match.group(1)}")
        result[match.group(1)] = (status.group(1), block)
    return result


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3 or parts[0].strip():
        raise AssertionError(f"Missing YAML-style frontmatter: {path}")
    values = {}
    for line in parts[1].splitlines():
        if ":" in line:
            name, value = line.split(":", 1)
            values[name.strip()] = value.strip().strip('"')
    return values, text


class LicenseManifestIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = declarations()
        cls.graphs = sorted(WORKFLOWS.rglob("*.json"))

    def test_graph_sidecar_and_manifest_inventory_match(self):
        graph_paths = {p.relative_to(ROOT).as_posix() for p in self.graphs}
        self.assertEqual(graph_paths, set(self.manifest),
                         "Workflow manifest must list every graph exactly once")
        self.assertGreaterEqual(len(graph_paths), 16)
        sidecars = {p.with_suffix(".json").relative_to(ROOT).as_posix()
                    for p in WORKFLOWS.rglob("*.md")}
        self.assertEqual(graph_paths, sidecars,
                         "Every graph must have exactly one adjacent licensing sidecar")

    def test_directory_manifest_and_sidecar_statuses_agree(self):
        for path, (manifest_status, block) in self.manifest.items():
            with self.subTest(path=path):
                expected_status = Path(path).parent.name
                self.assertIn(expected_status, SUPPORTED)
                self.assertEqual(expected_status, manifest_status)
                sidecar, body = frontmatter(ROOT / Path(path).with_suffix(".md"))
                self.assertEqual(sidecar.get("source"), path)
                self.assertEqual(sidecar.get("osf_license"), "MIT")
                self.assertEqual(sidecar.get("commercial_status"), manifest_status)
                self.assertIn("THIRD_PARTY_LICENSES.md", body)
                self.assertIn("third-party", body.lower())
                # Explicit research-only dependencies must not be filed as commercially compatible.
                if manifest_status == "commercial-compatible":
                    self.assertNotIn("commercial_status: research-only", block)

    def test_restricted_workflows_name_a_restricted_dependency(self):
        for path, (status, block) in self.manifest.items():
            if status != "research-only":
                continue
            with self.subTest(path=path):
                self.assertIn("commercial_status: research-only", block)

    def test_sam3_custom_license_is_disclosed_where_used(self):
        found = 0
        for path, (status, block) in self.manifest.items():
            if "SAM 3 (model weights)" not in block:
                continue
            found += 1
            with self.subTest(path=path):
                _, body = frontmatter(ROOT / Path(path).with_suffix(".md"))
                self.assertIn("custom SAM License", body)
                self.assertIn("https://github.com/facebookresearch/sam3/blob/main/LICENSE", body)
                self.assertNotRegex(
                    body,
                    r"All dependencies are permissively licensed or GPL-3\.0",
                    "Meta SAM 3 is covered by a custom source-available agreement",
                )
        self.assertGreaterEqual(found, 4, "SAM 3 dependency declarations disappeared")

    def test_global_disclaimer_distinguishes_custom_model_terms(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        third_party = (ROOT / "THIRD_PARTY_LICENSES.md").read_text(encoding="utf-8")
        for text in (readme, third_party):
            self.assertIn("custom SAM License", text)
            self.assertIn("commercial-compatible", text)
            self.assertIn("not", text.lower())


if __name__ == "__main__":
    unittest.main()
