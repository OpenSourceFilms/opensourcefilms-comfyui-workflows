# Pinned SAM3 custom-package source and API binding preflight

**Scope:** The fourth API-format selected workflow, [sam3_custompkg_probe.json](../workflows/commercial-compatible/sam3_custompkg_probe.json), uses a separately licensed third-party **ComfyUI-SAM3** extension. It does not use the five public-core native SAM3/SCAIL classes audited by the separate native binding check. These are distinct implementations and type contracts.

The canonical DEPENDENCIES.lock pins PozzettiAndrea/ComfyUI-SAM3 at **de0ff5d2c2ea435d29f800abfa568cffdfb94773** (GPL-3.0). A [separate CI job](../.github/workflows/verify-sam3-custompkg-source.yml) fetches exactly that source revision and the exact public ComfyUI core revision into a disposable runner, then verifies the upstream licence and source contracts. **It does not import or install third-party Python packages, load any model, or run ComfyUI.** The [stdlib-only auditor](../scripts/audit_sam3_custompkg_source.py) parses upstream source as Python syntax, and compares the declared node classes, input names and types, required inputs and output slots against the actual eight-node API graph.

The four third-party node classes checked are:

| Class | Required role | Outputs |
|---|---|---|
| LoadSAM3Model | Returns a SAM3 model configuration | SAM3_MODEL_CONFIG |
| SAM3CreatePoint | Supplies normalized foreground point | SAM3_POINT_PROMPT |
| SAM3CombinePoints | Combines point prompts | SAM3_POINTS_PROMPT |
| SAM3Segmentation | Produces masks and visualization | MASK, MASK, IMAGE, STRING, STRING |

The script verifies **five third-party-producing links**, including SAM3Segmentation output **slot 2** (visualization) to the second SaveImage node.

A second [AST-only core binding gate](../scripts/audit_sam3_custompkg_core_links.py) uses exact public `Comfy-Org/ComfyUI@08cf0284ff45723aa67841c80cabb0e3cb50c9d7`, reading `nodes.py` and `comfy_extras/nodes_mask.py` as data without imports. The core source contracts are `LoadImage` (IMAGE and MASK outputs), `MaskToImage` (MASK input, IMAGE output), and `SaveImage` (IMAGE input). It verifies **all four links touching those core node instances**, including the **two formerly unverified edges** `LoadImage[0] -> SAM3Segmentation.image` and `MaskToImage[0] -> SaveImage.images`. The other two typed core-touched edges are `SAM3Segmentation.mask -> MaskToImage.mask` and `SAM3Segmentation.visualization[2] -> SaveImage.images`.

The core gate verifies the checkout's exact Git HEAD and source SHA-256 hashes and rejects missing, symlinked, renamed or type-changed core definitions, unexpected output-slot shifts and changed link endpoints. Together the two source audits cover **all seven actual API links** in the eight-node probe. Source-typed links alone do not mean the graph can execute, and no model or user images are loaded/saved by these audits. Additional unreviewed links, changed node names, missing required inputs or modified output slots fail.

## Checkpoint auto-download boundary

The pinned LoadSAM3Model.execute() checks for its checkpoint and calls _download_from_huggingface() if missing. The source-only audit identifies that branch, but **never executes it**. This is a known runtime side effect, not evidence of malicious behaviour. Before enabling the model loader, separately verify the model weights, licensing, source checksum, local storage permissions, and whether the download is disabled or separately authorized. **This source audit is not a no-download guard for production runtime.**

The pinned extension declares comfy-env==0.3.89 and CUDA-specific dependencies in nodes/comfy-env.toml. It is therefore **not** included among the five external packages that already passed live CPU ComfyUI import. Import and dependency isolation must be independently qualified.

**Acceptance boundary:** This establishes only exact pinned source identities, GPL source presence, four selected third-party schemas, three native core source schemas, and source-typed validation of all seven API graph links. It does not establish package importability, model-file existence, actual execution of native LoadImage/SaveImage, GPU/CUDA/SAM3 inference, output quality, model licences or weights, or full workflow acceptance. Issue [#3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3) stays open.
