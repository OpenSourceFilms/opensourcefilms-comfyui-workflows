# Embedded mm_upscale: Easy-Use historical source/socket preflight

This is a **read-only source-to-export schema comparison**, not a third-party install, ComfyUI extension import, live registration, embedded-loop execution or full 11-workflow test.

The UI export workflows/commercial-compatible/mm_upscale_video_workflow.json contains **42 Easy-Use node instances** across four embedded subgraphs: 8 in Image Batch, 14 in Blend Frames, 12 in Blend Saved Frames and 8 in Settings. They use **eight distinct class identifiers**:

| Export class | Instances | Reviewed source class |
|---|---:|---|
| easy int | 13 | logic.py: Int |
| easy ifElse | 10 | logic.py: IfElse |
| easy compare | 7 | logic.py: Compare |
| easy batchAnything | 3 | logic.py: batchAnything |
| easy forLoopStart | 3 | logic.py: forLoopStart |
| easy forLoopEnd | 3 | logic.py: forLoopEnd |
| easy imageSave | 2 | image.py: imageSaveSimple |
| easy boolean | 1 | logic.py: Boolean |

The exact reviewed **candidate** upstream source is [yolain/ComfyUI-Easy-Use at b0b47ca1372117fce575d9e744655344ebff6bef](https://github.com/yolain/ComfyUI-Easy-Use/tree/b0b47ca1372117fce575d9e744655344ebff6bef). Source modules py/nodes/logic.py and py/nodes/image.py contain the eight class definitions and registrations. Its root LICENSE is **GPL-3.0**. This reviewed candidate commit is **not** proof of the historically installed version.

## Findings and precise limitations

The [offline fail-closed audit](../scripts/audit_mm_upscale_easy_use_sockets.py) compares each embedded instance's complete UI-exported input/output socket names, types and ordering against contracts transcribed from the candidate source, including required versus optional categories. It checks link metadata types, widget-binding structure, widget counts, four group totals, eight class totals and version fields. It does not inspect or publish widget values, prompts or media paths.

Important source/UI representation differences:

- **easy ifElse:** Source declares inputs boolean, on_true, on_false. UI stores on_true, on_false, boolean. The audit requires the observed UI order and source-identical member set, **not** executable API order parity.
- **easy forLoopStart:** Source has required total and optional dynamic initial_value1 and initial_value2. UI orders initial_value1, total, initial_value2. The audit checks the four currently exported output slots, not every source-supported dynamic loop port.
- **easy compare:** Candidate io.Schema marks a, b and comparison as optional. A link in the exported UI does not make an input mandatory under the source API.
- **easy imageSave:** Source is a side-effect/output node with no output sockets. The audit never executes image writes.

The exported version distribution is **6 × 1.3.0**, **35 × 1.3.3**, and **1 × historical SHA 8ecc929cd41cf0f7ef6fcc45d4bbc5729c6f287f**. None is proved equivalent to the reviewed candidate SHA b0b47ca1372117fce575d9e744655344ebff6bef. No compatibility of dynamic loop behaviour, io.Schema changes or nested dependencies is inferred.

Run without GPU, downloads or third-party imports:

    python -B scripts/audit_mm_upscale_easy_use_sockets.py --output /tmp/mm-easy-use-sockets.json

The public CI also runs ten positive and negative tests that reject class/version drift, changed socket names/types/order, unexpected outputs, missing groups, altered widgets and malformed link metadata. The report contains only public class identifiers, counts, provenance and explicit negative acceptance flags.

**HOLD remains:** Easy-Use is **missing from the canonical mm_upscale block in DEPENDENCIES.lock**. This audit neither changes it nor clears GPLv3/transitive rights, imports the third-party runtime, proves historical version compatibility, tests side effects, expands embedded groups, executes loops, converts UI to API graphs or accepts GPU/model inference. See [embedded provider gaps](embedded-mm-upscale-provider-gaps.md) and [issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).
