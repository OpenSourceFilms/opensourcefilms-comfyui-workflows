# Copyright 2026 Open Source Films
# SPDX-License-Identifier: MIT
"""Node registration for the mask_propagate_optical_flow ComfyUI package."""

from .nodes import MaskPropagateOpticalFlow, MaskPropagateFromFlow

NODE_CLASS_MAPPINGS = {
    "MaskPropagateOpticalFlow": MaskPropagateOpticalFlow,
    "MaskPropagateFromFlow": MaskPropagateFromFlow,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MaskPropagateOpticalFlow": "Mask Propagate Optical Flow (Farneback)",
    "MaskPropagateFromFlow": "Mask Propagate From Flow",
}

WEB_DIRECTORY = None
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
