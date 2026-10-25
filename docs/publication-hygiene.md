# Prepublication checks for ComfyUI workflow exports

Run this offline, standard-library-only scanner before publishing any editor or
API workflow graph:

```bash
python3 scripts/check-workflow-publication.py workflows
python3 scripts/validate-workflow-json.py workflows
```

The first command detects selected local file paths, RFC1918 or loopback URLs,
RunPod proxy endpoints, secret-shaped credentials, personal email addresses,
nonpublic storage/heartbeat URLs, file URIs, embedded preview/cache keys,
and common raster image data-URIs or substantial PNG/JPEG base64 payloads.
It reports only the rule and indexed JSON location, **not the sensitive value**.
It returns nonzero when a finding is present. The separate graph validator
checks node/link connectivity. Both checks run in the public repository's
GitHub Actions pull-request gate.

Only generic placeholders such as `input_video.mp4`, `models/sample.safetensors`,
reserved example domains and OSF's institutional contact domain are exempt.
Do not assume other email addresses or production URLs are safe to publish.

**Limitations:** This is a targeted lint, not a full privacy/security audit.
It may miss obfuscated credentials, differently formatted paths, named shots,
personal filenames that are relative paths, sensitive text prompts, metadata
in sidecars and confidential data not matching its patterns. Manually inspect
and redact all exported widget values and metadata. Check every model's
independent license and distribution permissions before commercial reuse.
Passing either tool does not mean a graph's nodes or models can execute.
