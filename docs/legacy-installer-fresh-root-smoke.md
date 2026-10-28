# Legacy installer fresh-directory control-flow qualification

**Scope: isolated installer orchestration, not a genuine ComfyUI runtime installation.**

The checked-in [fresh-root tests](../tests/test_legacy_installer_fresh_root.py)
exercise the original `scripts/install-dependencies.sh` against an **initially
empty disposable ComfyUI directory**. The tests intercept every `git` command
using a synthetic shim and keep all files under a temporary directory. They
perform **no network calls, upstream downloads, Python dependency
installation, model-weight installation, GPU inference or ComfyUI startup**.

The test matrix verifies:

| Scenario | Expected result |
|---|---|
| Fresh directory with default scope | All declared default node checkouts simulated; OSF optical-flow node copied from source; explicitly research-only node checkouts excluded |
| Second invocation after a successful run | Existing node directories skipped and no additional clones |
| Explicit `INSTALL_RESTRICTED=1` | Research-only clone paths exercised only on opt-in |
| Partial failure during a clone | Nonzero exit; partial directory removed; error reported |
| Failure checking out a pinned revision | Nonzero exit; wrong default-branch checkout removed |
| Existing regular file at a planned checkout path | Nonzero exit; user-owned file preserved; no Git clone for that package |
| Existing dangling symlink at a planned checkout path | Nonzero exit; symlink and target preserved; no Git clone for that package |
| Existing symlink to a directory | Existing directory skipped with explicit unverified-origin warning; **not** accepted as a verified checkout |
| Missing ComfyUI directory | Nonzero exit before any Git commands |

This is more meaningful than testing a successful copy into a directory where
all external nodes were already pre-created, but **it does not verify that
the upstream repositories are reachable, that pins still exist or that any
node imports successfully**. The shim deliberately creates placeholder
checkout directories and records requested references.

**Existing-directory gap:** the legacy installer skips *any* directory
with a matching node name without checking its actual Git origin, commit or
import status. A prior installation or user-modified directory therefore
cannot be regarded as verified by a successful rerun.
Pre-existing **non-directory** paths, including dangling symlinks,
now fail closed and are preserved without invoking `git clone` or clone-failure
cleanup. This prevents the previous possibility of deleting a user-owned
file or dangling symlink after an unsuccessful clone. It does not improve
the existing-directory authenticity gap or establish runtime compatibility. The legacy default
also references mutable upstream `main` branches and contains packages
associated with research-only workflows. Its exit code is **not a claim of
reproducibility, commercial permission or graph execution**.

For a clean ComfyUI **runtime** acceptance (still missing), use a separately
authorized disposable machine, independently pin ComfyUI/Python/CUDA/torch
and all required custom-node revisions, install and import actual nodes,
check the chosen weights and their exact licences, and exercise graphs with
synthetic/cleared media. Record redacted install logs, node-import results
and representative output hashes. Do not confuse a passed structure/installer
control-flow test with this release gate.

For the strictly staged 11-workflow subset, use
[the limited RunPod preparation profile](../runpod/commercial-compatible/README.md),
which **does not invoke** the broad legacy installer. Separate runtime
qualification is tracked in [issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).
The legacy full-install contract remains in
[issue #2](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/2).
