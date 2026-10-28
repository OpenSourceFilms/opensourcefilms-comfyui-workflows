# Embedded mm_upscale: historical Custom-Scripts socket audit

This is a **source-only, read-only** comparison of **23 actual embedded
ComfyUI-Custom-Scripts node instances** inside the four definitions of
[mm_upscale_video_workflow.json](../workflows/commercial-compatible/mm_upscale_video_workflow.json).
It neither installs nor imports this package, executes any expression,
converts groups into API prompts or tests group execution.

## Reviewed source and export

The two StringFunction nodes export the exact Git revision
[pythongosssss/ComfyUI-Custom-Scripts @ f2838ed5](https://github.com/pythongosssss/ComfyUI-Custom-Scripts/tree/f2838ed5e59de4d73cde5c98354b87a8d3200190).
The root licence is **MIT**. At this revision:

- **py/math_expression.py:** MathExpression|pysssss declares required
  **expression: STRING**, optional wildcard a/b/c, and INT/FLOAT outputs.
- **py/string_function.py:** StringFunction|pysssss declares required
  COMBO action and tidy_tags, optional STRING text_a/b/c and STRING output.
- Root **__init__.py** dynamically imports Python files from its py
  extension directory to register nodes. This was examined as source only.

The export contains **21 MathExpression** instances labelled **ver=1.2.5**
and **two StringFunction** instances labelled with the reviewed full Git
SHA. Counts are four in Image Batch, ten in Blend Frames, nine in
Blend Saved Frames and zero in Settings.

## Source versus editor socket differences

The original MathExpression source expects a **required STRING**
expression input. Its UI export instead represents expression as the
union **INT,FLOAT,IMAGE,LATENT**, the same apparent union shown for its
optional a/b/c inputs. The exported socket order is a/b/c/expression;
source INPUT_TYPES declares required expression and then optional a/b/c.
The source wildcard type is not literally that editor union type.

The audit checks the **actual exported representation** and explicitly
records this mismatch. It does **not** assert equivalence of the UI sockets
and the ComfyUI runtime API, or equivalence of the 21 **1.2.5** version
aliases to the reviewed Git commit. Expression evaluation, dynamic
import effects and the safety of the actual widget expressions have
not been qualified.

## Read-only drift gate

Run with standard-library Python and no GPU, network or models:

    python -B scripts/audit_mm_upscale_custom_scripts_sockets.py --output /tmp/mm-upscale-custom-scripts-sockets.json

The audit validates all 23 embedded instances against the source-bound
class/port contracts: names, types, UI order, widget metadata/count,
link identifier integrity, class counts, group counts and exact version
hints. It rejects changed sockets, unexpected classes, malformed widgets
and unreviewed version strings. Its report contains only public
source/provider identifiers, class/group/version counts, workflow
SHA-256 and explicit non-acceptance flags. It **never publishes
expressions, widget values, text fields or prompts**; negative tests
include private canary strings to enforce that boundary.

No canonical DEPENDENCIES.lock changes, custom-node installation,
live registration, expression evaluation, group expansion, rights
clearance or GPU/model inference are implied. The historical
Custom-Scripts provider remains **unpinned in the workflow manifest**.
Next steps require choosing a compatible exact revision, reviewing
import-time dependencies, validating the live registry/API schemas,
and checking executable group behaviour.

See [provider gaps](embedded-mm-upscale-provider-gaps.md),
[historical source pins](mm-upscale-historical-upstream-pins.md) and
[issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).
