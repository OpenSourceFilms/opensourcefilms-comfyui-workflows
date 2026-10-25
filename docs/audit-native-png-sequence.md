# Native ComfyUI PNG sequence integrity audit

`scripts/audit-native-png-sequence.py` checks the original files emitted by
ComfyUI SaveImage nodes. It does not composite, grade, resize, decode, repair,
write to or re-encode any image. Use it to preserve native clean plates,
generated alternatives and mattes as separate outputs.

```bash
python3 scripts/audit-native-png-sequence.py /path/to/output \
  --pattern 'SaveImage_*.png' --count 98 \
  --width 1344 --height 704 --bit-depth 16
```

It checks the number of matching files, SHA-256 of each file, PNG chunk
structure/CRCs and optionally dimensions/bit depth. The JSON report includes
a deterministic hash of the ordered file manifest.

```bash
python3 scripts/audit-native-png-sequence.py /path/to/output \
  --count 72 > output-audit.json
```

## Verify later against a saved baseline

Keep the first audit report as a trusted reference and compare the original
SaveImage files again after a transfer, archive restore or later processing.
This catches byte changes even when both files are structurally valid PNGs.

\`\`\`bash
python3 scripts/audit-native-png-sequence.py /path/to/originals \\
  --pattern 'SaveImage_*.png' --count 98 > baseline.json

python3 scripts/audit-native-png-sequence.py /path/to/copied-frames \\
  --pattern 'SaveImage_*.png' --count 98 --reference baseline.json
\`\`\`

The second command succeeds only when the sorted filenames, exact source
bytes, geometry and metadata match the saved report; it adds
\`"reference_match": true\` on success and exits **2** on failure. The reference
JSON is checked for its own self-consistent manifest SHA-256. Paths may differ
between directories, but matching filenames and bytes are required.

**Trust boundary:** A report's own SHA-256 is not a digital signature.
Protect the baseline against modification or replace it with independently
authenticated evidence for adversarial use. Do not redirect the second
command's output into the same baseline file: shell redirection would truncate
the reference before comparison. This feature remains read-only.

**Limits:** This validates bytes and headers, *not* decoded pixel equivalence,
temporal order, visual quality, model provenance, or completeness relative to
an independently authenticated job receipt. Supplying the correct expected
frame count and geometry is the operator's responsibility. The flat filename
glob is sorted lexicographically, so consistently zero-pad frame indices.
PNG files exceeding 256 MiB are refused to bound memory.

```bash
python3 -m unittest discover -s tests -p 'test_audit_native_png_sequence.py' -v
```

Python 3.11+ standard library only. Synthetic tests, no production footage.
