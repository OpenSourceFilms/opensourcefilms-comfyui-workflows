# Selected eleven-workflow admission HOLD

The eleven conditionally commercial-compatible workflow exports are staged
but are **not** accepted for production inference, GPU execution, full API
prompt compatibility or commercial rights.

Run the independent source-only audits, then assemble a single reconciled
readiness record:

```sh
python -B scripts/audit-selected-11-node-coverage.py --output /tmp/selected-11-node-coverage.json
python -B scripts/audit_embedded_group_links.py --output /tmp/mm-upscale-link-preflight.json
python -B scripts/audit_embedded_group_provider_dependencies.py --output /tmp/mm-upscale-provider-gaps.json
python -B scripts/audit_embedded_group_source_candidates.py --output /tmp/mm-upscale-reviewed-source-candidates.json
python -B scripts/check_selected11_release_hold.py \
  --coverage /tmp/selected-11-node-coverage.json \
  --links /tmp/mm-upscale-link-preflight.json \
  --providers /tmp/mm-upscale-provider-gaps.json \
  --candidates /tmp/mm-upscale-reviewed-source-candidates.json \
  --output /tmp/selected11-release-hold.json
```

GitHub Actions performs the same reconciliation using temporary JSON report
paths. Only a status line is printed. The report is **not a release
certificate**, is not automatically uploaded, and does not install, execute
or alter any selected workflow. It contains public workflow names, source
hashes, counts and blocker codes, never prompts, media paths or widget values.

## Gate semantics

This is a **source-only consistency and explicit HOLD gate**, not a workflow
readiness scoring system. The following are checked together and must agree:

- Eleven selected workflow identities from the canonical selected-profile
  audit, including four API exports and seven editor/UI exports.
- Exact graph SHA-256 agreement between the embedded-group link,
  provider-manifest and provider-source-candidate audits.
- Four embedded group definitions, 89 internal nodes and consistent
  group/instance counts. Source audits currently report 171 structurally
  consistent active links, but **16 unresolved reverse references**.
- Three missing embedded-provider entries in the canonical manifest and
  one provider without a pinned commit. Reviewing public source candidates
  does not resolve historical version identity, licence or installation.
- Explicit negative GPU, executable API-prompt, rights and embedded-group
  runtime flags. The gate rejects reports that unexpectedly claim such
  acceptance.

Each workflow receives reason-coded HOLD blockers. UI exports have an
additional API-conversion blocker, and `mm_upscale_video_workflow` has
additional embedded-runtime, reverse-reference and dependency-provenance
blockers. A passing CI run means the HOLD decision is **consistent with the
audited source**. It does **not** mean that the eleven workflows are
executable.

The report deliberately cannot return `GO`: independently reviewed runtime,
model provenance, licence permissions, GPU inference, and output acceptance
must be established by separate authorised work before production promotion.
The absence of a particular source-only blocker cannot prove any such
requirement has passed. Existing CPU-only synthetic media and source-schema
checks remain useful independent evidence, not substitutes for full
end-to-end inference.

Track remaining model, provider and runtime work in
[issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).
