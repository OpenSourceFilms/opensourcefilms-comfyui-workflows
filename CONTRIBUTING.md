# Contributing

This repo holds ComfyUI workflows and node code Open Source Films actually
uses in production. Contributions are welcome, with a few things worth
knowing before you send a PR.

## Adding or updating a workflow

1. Export the workflow in ComfyUI's API format if possible (the
   dict-of-nodes JSON, not just the UI graph) — it's what the existing
   `workflows/commercial-compatible/*.json` files use, and it's easier to
   diff and to run headlessly. UI-format exports are fine too (several
   existing workflows are UI-format); either is accepted.
2. Strip anything that shouldn't be public before opening a PR:
   - No absolute filesystem paths (`/home/...`, `C:\Users\...`, etc.) in any
     node's default widget values.
   - No real production asset names, shot names, or personal filenames in
     default `LoadImage`/`LoadVideo`/`VHS_Load*` values — use a generic
     placeholder like `input_video.mp4`.
   - No embedded execution-cache blocks (ComfyUI's `videopreview` metadata
     on `VHS_*` nodes carries local output paths from whoever last ran the
     workflow — delete that key entirely, it has no functional purpose in a
     shared template).
   - No API keys, tokens, or credentials in any node input.
3. Work out `commercial_status` honestly. Trace every custom node package
   and model the workflow touches, check its actual license text (not just
   a badge or folder name — forks and similarly-named packages can differ),
   and mark `research-only` if anything in the chain is CC-BY-NC or
   otherwise commercially restricted. `research-only` is not a demotion —
   plenty of genuinely useful workflows depend on research-only models.
4. Add a `.md` sidecar next to the workflow (see any existing one for the
   frontmatter format: `osf_license`, `commercial_status`, `source`) and a
   matching entry in [DEPENDENCIES.lock](DEPENDENCIES.lock) — that file is
   canonical if it and the sidecar ever disagree, so keep them in sync.
5. Add the new dependency (if any) to
   [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) and to
   `scripts/install-dependencies.sh`'s package list, with a pinned commit or
   tag, not `main` — resolve `main` to a real commit before submitting.

## Adding or updating custom node code

`custom_nodes/mask_propagate_optical_flow/` is the only node package that
lives in this repo (everything else is fetched from upstream). If you're
contributing OSF-authored node code — as opposed to a workflow that merely
references a third-party node — it belongs under `custom_nodes/` with its
own `README.md`, and it's MIT like the rest of this repo. Don't vendor
someone else's node package here; that belongs in its own repo with its own
license, referenced from `THIRD_PARTY_LICENSES.md` instead.

## Testing

If you don't have a GPU handy to test a workflow end-to-end, a short-lived
GPU pod (we use [Runpod](https://www.runpod.io/)) is usually the fastest way
to get one — most of these workflows need real VRAM, so a local CPU-only
ComfyUI install won't get you far enough to verify the graph actually runs.

## License

By contributing, you agree your contribution is licensed under this repo's
MIT license, except where you're documenting (not vendoring) a third-party
dependency, which keeps its own license as described above.
