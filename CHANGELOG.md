# Changelog

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
  comparisons using BiM-VFI — each blocked from commercial use by a
  specific named dependency, documented in
  [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
- `custom_nodes/mask_propagate_optical_flow/` — Open Source Films' own
  ComfyUI node package (optical-flow mask propagation), published here for
  the first time.
- `LICENSE` (MIT), `THIRD_PARTY_LICENSES.md`, `DEPENDENCIES.lock`, and
  `scripts/install-dependencies.sh` (pinned installer, no vendoring of
  third-party source or model weights).
- `CONTRIBUTING.md`.
