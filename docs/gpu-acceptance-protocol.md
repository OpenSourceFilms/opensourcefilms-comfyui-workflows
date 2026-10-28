# Clean RunPod GPU and model acceptance protocol

**Status: HOLD.** This protocol describes independent acceptance work that has **not** been completed. It is not a deployment command, GPU reservation, model licence, or approval to modify a production ComfyUI installation.

The restricted staging profile selects eleven conditionally commercial-compatible workflow exports from `DEPENDENCIES.lock`. The CPU GitHub Actions work qualifies specific pinned custom-node imports, synthetic CPU operations and model-free media encoding. It does **not** certify the eleven workflows, their pretrained weights, GPU inference, commercial rights, or output quality. Source-only checks are reconciled by [the selected-eleven HOLD gate](selected11-release-hold.md).

## 1. Preconditions before any GPU job

1. **Identified target:** Register and verify a dedicated, reachable ComfyUI API target on an explicitly approved compute/workspace project. A running pod alone is not evidence of a running ComfyUI server. A tool listing zero configured instances is a **connection/setup HOLD**, not licence to bypass tooling permissions.
2. **Controlled compute:** Use the approved GPU reservation/claim mechanism. Record the device model, VRAM limit, lease owner, allocation, job timeout and cleanup. Check active claims before launching; do not preempt another team's workloads, restart production ComfyUI, change shared packages or silently extend cloud spend. Prefer a disposable instance mounted read-only to source media.
3. **Immutable source:** Pin ComfyUI, every required extension, transitive dependency and model revision to reviewed hashes. The generic legacy installer with mutable upstream references is **not** an acceptable production qualification route. Capture the exact revision inventory in the private run manifest.
4. **Permissions and provenance:** Verify separate code, model-weight, dataset, output-use and redistribution terms **for every tested dependency**. The selected profile's commercial-compatible label is conditional, not rights clearance. A missing or unverified provider licence remains HOLD. The public [licence notes](../THIRD_PARTY_LICENSES.md) and [dependency lock](../DEPENDENCIES.lock) are inputs, not substitutes for this check.
5. **No user footage by default:** Begin with generated nonidentifying clips and masks. Use production footage only through a separately reviewed private-data handling path. Never attach model weights, internal network paths, tokens, frame renders or logs containing secrets to public GitHub Actions artifacts.

## 2. Per-workflow admission sequence

Record a **separate result for each of the eleven**, keyed to exact source JSON SHA-256, not to a workflow family name.

| Selected workflow | Primary non-CPU gate |
|---|---|
| `sam3_custompkg_probe` | Native SAM3 execution, exact image/mask I/O, provenance and model terms |
| `step4_5_sam3_mask` | SAM3 detection/tracking mask shape, frame-index fidelity and fork/native parity |
| `step6_animation_mode` | SCAIL-driven animation, all native conditioning connections and output validation |
| `step7_replacement_mode` | SCAIL replacement, identity/region conditioning and output validation |
| `gimm_sgm_vfi_video_interpolate` | Resolve pinned GIMM/SGM source and class/schema incompatibilities before GPU interpolation |
| `mm_upscale_video_workflow` | Resolve four embedded group runtime/import paths, 16 orphan reverse references and unpinned/missing providers |
| `wan22_fmlf_first_middle_last_frame` | Verify FMLF provider rights and exact first/middle/last conditioning execution |
| `video_wan2_2_14B_flf2v` | Verified source and weights, first/last image-frame conditioning and temporal output |
| `video_wan2_2_14B_fmlf2v` | FMLF provider rights and first/middle/last temporal conditioning |
| `video_wan2_2_14B_i2v` | Native image-to-video model/weights, prompt conversion and temporal output |
| `video_wan_vace_14B_v2v` | VACE conditioning, input video fidelity and spatial/temporal output |

For each workflow, require all of the following **in order**, without promoting partial successes:

- **Format and graph:** Identify API prompt versus UI/editor export. Validate node identities, graph links and registered input/output socket types. The seven UI exports cannot be assumed executable by posting their editor JSON to `/prompt`; convert to executable prompts in a disposable environment and compare against the original graph.
- **Real installed sources:** Import *every* needed custom-node provider at its exact reviewed revision. Presence of one sibling class is not proof that another class or embedded subgraph works.
- **Models and runtime:** Verify weight hashes and licences, run actual inference with synthetic inputs on reserved GPU memory, and record resource peaks, OOM/retries, wall time and relevant software versions.
- **Acceptance output:** Verify frame dimensions and count, finite values, temporal order, exact source/target conditioning behaviour, provenance, and representative image quality. Preserve test identity across reruns; use independent reproducible seeds where the model supports them.
- **Teardown:** Release GPU reservations, stop only owned jobs and leave unrelated ComfyUI instances, other workflows and persistent storage untouched.

## 3. Evidence and decision gates

Each GPU attempt should produce a private run record containing: workflow name and JSON hash; source/weight/licence snapshot IDs; ComfyUI and extension revisions; GPU and VRAM claim; test-input generator version; model seeds; node/schema validation results; inference completion; expected versus actual output count, dimensions and timing; temporal/conditioning findings; numerical or human output review; errors; resource use; and cleanup confirmation. Retain only non-sensitive summary hashes and status codes in public issues.

Use **PASS** only for an explicitly bounded test that actually ran. Use **HOLD** for absent provider rights, unregistered targets, missing model weights, UI/API conversion, incompatible node sockets, unresolved embedded groups or missing GPU evidence. Use **FAIL** for an attempted and measured test that violated a specified criterion. Never convert a source-only or CPU-only PASS into full GPU or production acceptance.

**Current release decision: HOLD for all eleven.** The CPU qualification and independent audits are useful evidence, but no selected end-to-end GPU/model workflow is certified by this document. Track acceptance in [issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3). The separately tracked legacy installer compatibility work is [issue #2](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/2).
