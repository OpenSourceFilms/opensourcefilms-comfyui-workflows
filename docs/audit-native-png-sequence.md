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

### Verify numbered frame continuity

A correct count **does not** prove that no frame index is missing. For
example, frame 0001 and frame 0003 are two files, but they are not a
contiguous two-frame sequence. For full, consecutively numbered deliveries,
add `--contiguous`:

```bash
python3 scripts/audit-native-png-sequence.py /path/to/output \
  --pattern 'SaveImage_*.png' --count 98 --contiguous
```

This opt-in check requires **exactly one ASCII-decimal index** in each
filename, a common prefix and suffix, consistent digit padding, and numeric
indices increasing by one in sorted order. It allows arbitrary starting
indices (for example, 97 through 194). The resulting report includes
`"contiguous_indices_verified": true`, `first_frame_index`, and
`last_frame_index`. Missing indices, mixed numbering styles, or ambiguous
filenames fail before pixel-file hashing.

ComfyUI names such as `SaveImage_00001_.png` work. Names containing more
than one numeric run (for example, `scene_7_frame_0001.png`) are deliberately
rejected in this mode; use a single-index naming scheme or run the count-only
audit instead. The default without `--contiguous` remains compatible with
non-consecutive diagnostic selections. Neither mode proves correspondence
to a requested shot or an authenticated job receipt.

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
Use `--contiguous` for numbered deliveries to check for gaps; it is not a
temporal-content or source-footage validator. PNG files exceeding 256 MiB
are refused to bound memory.

```bash
python3 -m unittest discover -s tests -p 'test_audit_native_png_sequence.py' -v
```

Python 3.11+ standard library only. Synthetic tests, no production footage.
