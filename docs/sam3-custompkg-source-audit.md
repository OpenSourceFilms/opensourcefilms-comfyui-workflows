# Pinned SAM3 custom-package source and API binding preflight

**Scope:** The fourth API-format selected workflow, [sam3_custompkg_probe.json](../workflows/commercial-compatible/sam3_custompkg_probe.json), uses a separately licensed third-party **ComfyUI-SAM3** extension. It does not use the five public-core native SAM3/SCAIL classes audited by the separate native binding check. These are distinct implementations and type contracts.

The canonical DEPENDENCIES.lock pins PozzettiAndrea/ComfyUI-SAM3 at **de0ff5d2c2ea435d29f800abfa568cffdfb94773** (GPL-3.0). A [separate CI job](../.github/workflows/verify-sam3-custompkg-source.yml) fetches exactly that source revision into a disposable runner and verifies its licence file. **It does not import or install third-party Python packages, load any model, or run ComfyUI.** The [stdlib-only auditor](../scripts/audit_sam3_custompkg_source.py) parses upstream source as Python syntax, and compares the declared node classes, input names and types, required inputs and output slots against the actual eight-node API graph.

The four third-party node classes checked are:

| Class | Required role | Outputs |
|---|---|---|
| LoadSAM3Model | Returns a SAM3 model configuration | SAM3_MODEL_CONFIG |
| SAM3CreatePoint | Supplies normalized foreground point | SAM3_POINT_PROMPT |
| SAM3CombinePoints | Combines point prompts | SAM3_POINTS_PROMPT |
| SAM3Segmentation | Produces masks and visualization | MASK, MASK, IMAGE, STRING, STRING |

The script verifies **five third-party-producing links**, including SAM3Segmentation output **slot 2** (visualization) to the second SaveImage node. Two other links reference core LoadImage/MaskToImage/SaveImage nodes and their source output schemas are explicitly **not** independently checked by this preflight. Additional unreviewed links, changed node names, missing required inputs or modified output slots fail.

## Checkpoint auto-download boundary

The pinned LoadSAM3Model.execute() checks for its checkpoint and calls _download_from_huggingface() if missing. The source-only audit identifies that branch, but **never executes it**. This is a known runtime side effect, not evidence of malicious behaviour. Before enabling the model loader, separately verify the model weights, licensing, source checksum, local storage permissions, and whether the download is disabled or separately authorized. **This source audit is not a no-download guard for production runtime.**

The pinned extension declares comfy-env==0.3.89 and CUDA-specific dependencies in nodes/comfy-env.toml. It is therefore **not** included among the five external packages that already passed live CPU ComfyUI import. Import and dependency isolation must be independently qualified.

**Acceptance boundary:** This establishes only exact pinned source identity, GPL source presence, the four selected upstream schemas, and five selected third-party graph links. It does not establish package importability, all core-node bindings, GPU/CUDA/model inference, outputs, model licences or weights, or full workflow acceptance. Issue [#3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3) stays open.
