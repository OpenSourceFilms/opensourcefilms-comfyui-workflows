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
- SHA-256 fingerprints of the **exact bytes of all eleven selected
  workflows** in the coverage report, with explicit `mm_upscale` agreement
  against the independent embedded-group link, provider-manifest and
  provider-source-candidate audits. A coverage report from an earlier
  `mm_upscale` revision must fail even if those other three agree.
- Four embedded group definitions, 89 internal nodes and consistent
  group/instance counts. Source audits currently report 171 structurally
  consistent active links, but **16 unresolved reverse references**.
- Three missing embedded-provider entries in the canonical manifest and
  one provider without a pinned commit. Reviewing public source candidates
  does not resolve historical version identity, licence or installation.
- Explicit negative GPU, executable API-prompt, rights and embedded-group
  runtime flags. The gate rejects reports that unexpectedly claim such
  acceptance.
- An explicit historical provider-blocker map is checked against each
  selected workflow's **actual node-class inventory** and, for GIMM,
  its canonical declared dependencies. It assigns
  `PINNED_GIMM_CLASS_BINDINGS_INCOMPATIBLE` to
  `gimm_sgm_vfi_video_interpolate` and
  `WAN_FMLF_PROVIDER_LICENSE_NOT_VERIFIED` to the two selected
  first/middle/last Wan exports. Changes to the expected class names,
  graph format or GIMM provider baseline **fail closed**, rather than
  silently removing a blocker.

Each workflow receives reason-coded HOLD blockers. UI exports have an
additional API-conversion blocker, and `mm_upscale_video_workflow` has
additional embedded-runtime, reverse-reference and dependency-provenance
blockers. The GIMM and two Wan FMLF exports now carry the known-source
blockers described above. The exact underpinning findings are documented
in [GIMM/SGM source bindings](gimm-sgm-pinned-source-audit.md) and
[Wan FMLF candidate licensing](wan-fmlf-provider-candidate.md).

**Evidence boundary:** The consolidated gate checks actual selected
graph class identities against *previously reviewed pinned-source
findings*. It does not fetch the external source, re-run those independent
audits or prove an unchanged external licence. The corresponding dedicated
source-only CI audits remain separately required. A passing consolidated
CI run means the **HOLD decision is internally consistent**, not that
the eleven workflows are executable.

The coverage report now includes a `source_graph_sha256` field on
each workflow row. The reconciler rejects absent or malformed hashes
and checks `mm_upscale` coverage against the three specialized audits.

**Current-checkout binding across all eleven:** The executable CLI now also
reuses the canonical `runpod/commercial-compatible/prepare.py` selector,
reads the **currently approved eleven graph byte strings**, and compares
every coverage row's SHA-256 and declared API/UI format against the exact
approved source. It rejects stale, substituted, missing, duplicate or
mixed-revision coverage evidence for **any** of the eleven selected graphs,
not only `mm_upscale`. Successful CLI output sets
`current_checkout_source_hashes_verified=true` and
`current_checkout_source_hashes_verified_count=11`.

The pure library `assemble()` function only reconciles the four provided
reports and intentionally has no checkout/filesystem access; callers that
need to assert current source integrity must invoke
`verify_against_current_checkout()` or use the CLI. None of these
checks proves executable workflow graphs, typed sockets, model/GPU
inference, licences or production readiness. The decision is still HOLD.

The report deliberately cannot return `GO`: independently reviewed runtime,
model provenance, licence permissions, GPU inference, and output acceptance
must be established by separate authorised work before production promotion.
The absence of a particular source-only blocker cannot prove any such
requirement has passed. Existing CPU-only synthetic media and source-schema
checks remain useful independent evidence, not substitutes for full
end-to-end inference.

Track remaining model, provider and runtime work in
[issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).
