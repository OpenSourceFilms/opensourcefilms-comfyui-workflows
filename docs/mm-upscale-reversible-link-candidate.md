# Reversible candidate for orphan embedded-group link references

**Status: CANDIDATE_ONLY_HOLD.** The published mm_upscale_video_workflow.json
is not modified. No fixed graph is committed, exported, installed or promoted.
This analysis applies only to the four embedded LiteGraph group definitions
of the currently pinned eleven-workflow staging profile.

## Reproducible source-only preflight

The [link-integrity audit](../scripts/audit_embedded_group_links.py)
proves the **171 active link records** and their current positive endpoint
references are consistent, but finds **16 reverse references without active
link records** across four groups, with counts 4, 3, 3 and 6.
These IDs reside in **node-output links** and **exposed group-input linkIds**,
not in authoritative active-link records. They might be stale editor data,
but this has not been verified by actual frontend import or execution.

The [reversible candidate planner](../scripts/plan_mm_upscale_reverse_refs.py)
reads the canonical approved graph and independently repeats the link audit.
It requires the same manifest, byte SHA, four groups, 89 internal nodes,
171 active links and the exact 16-reference discrepancy. It constructs
an **in-memory candidate only**, removing values from the two kinds of
reverse-reference lists *only if the ID is absent from that group's active
link records*. It then:

1. Re-runs structural validation for every candidate group, requiring
   zero unresolved reverse references.
2. Requires all 171 active-link records to remain exactly unchanged.
3. Applies the inverse of each individual change, recovering the complete
   original graph including widget values, prompts, node positions and links.
4. Re-reads the published file to ensure its bytes were never altered.
5. Emits **metadata only**: source SHA, candidate hash, group/count summaries
   and numeric orphan-link IDs/positions. It does **not** export the graph.

The planner is wired into
[public CI](../.github/workflows/verify-public-workflows.yml) with seven
positive/negative regressions. They reject changed canonical baselines,
corrupt active links, another node's active link as one's own,
unexpected single-valued dangling inputs or outputs, and repeated/shared
orphan references.

Run: python -B scripts/plan_mm_upscale_reverse_refs.py --output /tmp/mm-upscale-reverse-ref-candidate-hold.json

The output file must be new. It is a non-deployable audit record, not
a rewritten workflow. Public CI stores it only in temporary runner space;
private media and weights are never accessed.

## Why the HOLD remains

An orphan reverse reference may be inert or may encode meaningful
historical UI/editor state. The candidate proves that a transformation
is **narrow and reversible**, not that it is safe to promote. Actual
target frontend import, roundtrip export, embedded group expansion,
API prompt generation, provider licences, installed versions and
GPU/model inference remain untested. The original sixteen unresolved
references remain in the published staged graph.

Do not turn a source-only candidate's clean link count into a release GO.
See [selected-eleven HOLD](selected11-release-hold.md) and
[issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).
