# mask_propagate_optical_flow

ComfyUI custom nodes for propagating a mask across video frames using dense
optical flow, so you only need to draw or generate one mask instead of
one per frame.

- **MaskPropagateOpticalFlow** — computes Farneback dense optical flow
  between consecutive frames and warps a mask forward through a batch.
- **MaskPropagateFromFlow** — same propagation, taking a precomputed flow
  field instead of computing it internally (for pairing with a different
  flow estimator).

Plain OpenCV (Farneback) under the hood — no external model weights, no
GPU required, no third-party dependencies beyond `opencv-python`, `numpy`,
and `torch` (already required by ComfyUI itself).

Originally written by Open Source Films for our own matting/rotoscoping
workflows (see `../../workflows/research-only/`); published here for the
first time.

## Install

Copy or symlink this directory into your ComfyUI `custom_nodes/` folder, or
run `../../scripts/install-dependencies.sh` from the repo root, which does
this for you.

## License

MIT — see the repo root [LICENSE](../../LICENSE). No third-party code.
