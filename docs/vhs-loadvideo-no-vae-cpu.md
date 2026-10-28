# Real VHS_LoadVideo no-VAE IMAGE output, isolated CPU

This gate uses the exact pinned public
`Kosinkadink/ComfyUI-VideoHelperSuite@2984ec4c4b93292421888f38db74a5e8802a8ff8`
and the existing isolated clean pinned ComfyUI CPU runner.

## What it tests

The runner writes one generated, two-frame 64×64 H.264 MP4 containing
solid red and blue frames to the **disposable** ComfyUI input folder.
The source is generated via local FFmpeg, not copied from production,
downloaded from a network or supplied by the user. The source's SHA-256,
size and frame count are recorded in JSON only.

A second, real ComfyUI `/prompt` graph executes:

`VHS_LoadVideo` (with `video` set to that scratch file,
`format=None`, `frame_load_cap=2` and **no optional VAE input**)
→ native `PreviewImage` (loader output slot zero).

The pinned upstream `LoadVideoUpload` class maps to `VHS_LoadVideo`.
Its underlying `load_video` returns a frame tensor when
`vae is None`, and latent sample dictionaries when a VAE is present.
The test therefore requires the actual no-VAE **IMAGE tensor path**
to be accepted by the real native `PreviewImage`, with exactly two
temporary PNG records. Using the existing read-limited, filename-validated
loopback `/view` operation, it reads both previews, requires 64×64 RGB
images, and compares **every pixel** to the expected red/blue sequence.
A maximum absolute error of 24/255 per channel permits the codec's
8-bit YUV420 roundtrip; it is not an HDR fidelity test. No media is
uploaded.

## What it does not establish

This gate tests actual video decoding and `IMAGE` tensor routing for
**this exact synthetic input**, not the behaviour of every file, codec,
frame rate, resolution, corrupted stream or optional VAE input.
It strengthens the six source-typed `VHS_LoadVideo`→SAM3/SCAIL `IMAGE`
connections documented in
[sam3-scail-native-api-bindings.md](sam3-scail-native-api-bindings.md),
but does **not** execute SAM3/SCAIL inference, masks, tracking or any
actual selected workflow graph.

Production RunPod, GPU, private footage, downloaded models, model weights,
licences and all eleven full workflow acceptance gates remain unchanged.
The release status remains HOLD under [issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).
