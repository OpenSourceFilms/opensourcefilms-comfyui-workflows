"""Fail-closed import guard for disposable ComfyUI node startup.

The pinned UltimateSDUpscale package uses urllib.request.urlretrieve to
download a mutable master.zip when its Git submodule is absent. Never allow
that operation on the clean acceptance runner. This does not block every
possible network API or establish general network isolation.
"""
import urllib.request


def _reject_urlretrieve(*_args, **_kwargs):
    raise RuntimeError("Unpinned urllib.request.urlretrieve is forbidden in OSF CPU acceptance")


urllib.request.urlretrieve = _reject_urlretrieve
