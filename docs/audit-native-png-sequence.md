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
