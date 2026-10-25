"""Pure-synthetic tests for the read-only ComfyUI native PNG audit."""
import hashlib
import contextlib
import io
import json
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit-native-png-sequence.py"
spec = importlib.util.spec_from_file_location("native_audit", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def png(path, width=2, height=2, depth=8):
    row = b"\x00" + b"\x01" * (width * 3 * depth // 8)
    content = (m.MAGIC +
               chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, depth, 2, 0, 0, 0)) +
               chunk(b"IDAT", zlib.compress(row * height)) + chunk(b"IEND", b""))
    path.write_bytes(content)
    return content


class NativeSequenceAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_sha_and_read_only(self):
        a = png(self.root / "f0001.png")
        b = png(self.root / "f0002.png", depth=16)
        result = m.audit(self.root, "f*.png", 2, width=2, height=2)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual([x["sha256"] for x in result["frames"]],
                         [hashlib.sha256(a).hexdigest(), hashlib.sha256(b).hexdigest()])
        self.assertEqual(result, m.audit(self.root, "f*.png", 2, width=2, height=2))
        self.assertEqual((self.root / "f0001.png").read_bytes(), a)

    def test_count_mismatch(self):
        png(self.root / "f.png")
        with self.assertRaisesRegex(m.AuditError, "count mismatch"):
            m.audit(self.root, "*.png", 2)

    def test_width_mismatch(self):
        png(self.root / "f.png")
        with self.assertRaisesRegex(m.AuditError, "width expected"):
            m.audit(self.root, "*.png", 1, width=4)

    def test_depth_mismatch(self):
        png(self.root / "f.png", depth=16)
        with self.assertRaisesRegex(m.AuditError, "bit_depth expected"):
            m.audit(self.root, "*.png", 1, depth=8)

    def test_crc_corruption(self):
        p = self.root / "f.png"
        b = bytearray(png(p))
        b[-8] ^= 1
        p.write_bytes(b)
        with self.assertRaisesRegex(m.AuditError, "CRC mismatch"):
            m.inspect_png(p)

    def test_trailing_data(self):
        p = self.root / "f.png"
        p.write_bytes(png(p) + b"extra")
        with self.assertRaisesRegex(m.AuditError, "trailing data"):
            m.inspect_png(p)

    def test_short_bad_signature(self):
        p = self.root / "f.png"
        p.write_bytes(b"wrong")
        with self.assertRaisesRegex(m.AuditError, "signature"):
            m.inspect_png(p)

    def test_oversized_chunk(self):
        p = self.root / "f.png"
        p.write_bytes(m.MAGIC + struct.pack(">I", m.MAX_FILE + 1) + b"IDAT" + b"\x00" * 4)
        with self.assertRaisesRegex(m.AuditError, "oversized PNG chunk"):
            m.inspect_png(p)

    def test_symlinks_refused(self):
        p = self.root / "f.png"
        png(p)
        link = self.root / "link.png"
        link.symlink_to(p)
        with self.assertRaisesRegex(m.AuditError, "regular file"):
            m.inspect_png(link)
        folder = self.root / "alias"
        folder.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(m.AuditError, "symlink"):
            m.audit(folder, "*.png", 1)

    def test_reference_matches_frozen_originals_and_cli(self):
        p = self.root / "native_0001.png"
        png(p)
        report = m.audit(self.root, "*.png", 1)
        ref = self.root / "accepted.json"
        ref.write_text(json.dumps(report))
        self.assertTrue(m.verify_reference(report, ref)["reference_match"])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            rc = m.main([str(self.root), "--count", "1",
                         "--reference", str(ref)])
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(stdout.getvalue())["reference_match"])

    def test_reference_detects_changed_but_valid_png(self):
        p = self.root / "native_0001.png"
        png(p)
        old = m.audit(self.root, "*.png", 1)
        reference = self.root / "accepted.json"
        reference.write_text(json.dumps(old))
        png(p, depth=16)
        with self.assertRaisesRegex(m.AuditError, "differs from reference"):
            m.verify_reference(m.audit(self.root, "*.png", 1), reference)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = m.main([str(self.root), "--count", "1",
                         "--reference", str(reference)])
        self.assertEqual(rc, 2)
        self.assertIn("differs from reference", stderr.getvalue())

    def test_reference_tampered_json_hash_refused(self):
        p = self.root / "native.png"
        png(p)
        report = m.audit(self.root, "*.png", 1)
        report["frames"][0]["sha256"] = "0" * 64
        reference = self.root / "accepted.json"
        reference.write_text(json.dumps(report))
        with self.assertRaisesRegex(m.AuditError, "inconsistent manifest"):
            m.verify_reference(m.audit(self.root, "*.png", 1), reference)

    def test_reference_mismatched_schema_refused(self):
        p = self.root / "native.png"
        png(p)
        report = m.audit(self.root, "*.png", 1)
        reference = self.root / "accepted.json"
        report["schema"] = "osf.another_thing"
        reference.write_text(json.dumps(report))
        with self.assertRaisesRegex(m.AuditError, "schema or status"):
            m.verify_reference(m.audit(self.root, "*.png", 1), reference)

    def test_reference_corrupt_json_refused(self):
        p = self.root / "native.png"
        png(p)
        reference = self.root / "accepted.json"
        reference.write_text("{bad")
        with self.assertRaisesRegex(m.AuditError, "invalid JSON"):
            m.verify_reference(m.audit(self.root, "*.png", 1), reference)

    def test_reference_symlink_refused(self):
        p = self.root / "native.png"
        png(p)
        reference = self.root / "accepted.json"
        reference.write_text(json.dumps(m.audit(self.root, "*.png", 1)))
        link = self.root / "alias.json"
        link.symlink_to(reference)
        with self.assertRaisesRegex(m.AuditError, "symlink"):
            m.verify_reference(m.audit(self.root, "*.png", 1), link)

    def test_reference_equal_after_copy_to_other_directory(self):
        a = self.root / "source"
        b = self.root / "copied"
        a.mkdir()
        b.mkdir()
        payload = png(a / "frame_0001.png")
        (b / "frame_0001.png").write_bytes(payload)
        reference = self.root / "accepted.json"
        reference.write_text(json.dumps(m.audit(a, "*.png", 1)))
        self.assertTrue(m.verify_reference(m.audit(b, "*.png", 1), reference)["reference_match"])

    def test_unsafe_glob(self):
        with self.assertRaisesRegex(m.AuditError, "unsafe filename glob"):
            m.audit(self.root, "../*.png", 1)


if __name__ == "__main__":
    unittest.main()
