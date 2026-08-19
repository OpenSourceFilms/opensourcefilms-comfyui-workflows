# Changelog

## [Unreleased]

### Added

- `RUNPOD.md`: base image, GPU/VRAM tiers by workflow family, storage
  guidance, and a verified fresh-pod install path.
- `scripts/setup-runpod.sh`: thin wrapper around
  `scripts/install-dependencies.sh` that locates a conventional ComfyUI
  install path and prints the remaining manual steps (model weights,
  launch command).
- A **Run on RunPod** section in the README, next to Install/Requirements.

### Fixed

- `scripts/install-dependencies.sh`'s pin for `ComfyUI-WanVideoWrapper`
  (`v1.4.7`) no longer resolves upstream — the tag has been removed from
  the source repo. Repinned to the last commit on its default branch
  (`088128b224242e110d3906c6750e9a3a348a659b`), verified by actually
  running the installer end-to-end. Same fix applied in
  `THIRD_PARTY_LICENSES.md`.

## [0.1.0] - 2026-07-22

Initial release.

### Added

- 11 `commercial-compatible` workflows: SAM 3 + SCAIL-2 character
  animation/replacement pipeline (3-step), a SAM 3 smoke test, GIMM-VFI +
  SGM-VFI frame interpolation, Florence2-assisted video upscaling, and six
  Wan 2.2 / Wan VACE 14B video-generation variants (first-last-frame,
  first-middle-last-frame, image-to-video, video-to-video).
- 5 `research-only` workflows: two VideoMaMa mask-guided matting pipelines,
  one EffectErase object-removal pipeline, and two frame-interpolation
  comparisons using BiM-VFI; each blocked from commercial use by a
  specific named dependency, documented in
  [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
- `custom_nodes/mask_propagate_optical_flow/`; Open Source Films' own
  ComfyUI node package (optical-flow mask propagation), published here for
  the first time.
- `LICENSE` (MIT), `THIRD_PARTY_LICENSES.md`, `DEPENDENCIES.lock`, and
  `scripts/install-dependencies.sh` (pinned installer, no vendoring of
  third-party source or model weights).
- `CONTRIBUTING.md`.
