"""Test-only synthetic SAM3 track and MASK sources for native SCAIL CPU CI.

No model inference, weights, footage, paths or network access.
The packed masks use the exact bit order defined by pinned ComfyUI
comfy/ldm/sam3/tracker.py: pack_masks, W divisible by eight.
"""
import torch


class OSFCISCAILTrack:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    RETURN_TYPES = ("SAM3_TRACK_DATA",)
    FUNCTION = "create"
    CATEGORY = "OSF CI synthetic / not production"

    def create(self):
        masks = torch.zeros((2, 2, 64, 64), dtype=torch.bool)
        # Deliberately store the RIGHT identity first; native
        # left_to_right sorting must recolour LEFT=blue, RIGHT=red.
        masks[:, 0, 16:48, 40:56] = True
        masks[:, 1, 16:48, 8:24] = True
        shifts = torch.arange(8, dtype=torch.int16)
        packed = (
            masks.view(2, 2, 64, 8, 8).to(torch.int16)
            * (1 << shifts)
        ).sum(-1).to(torch.uint8)
        return ({"packed_masks": packed, "orig_size": (64, 64),
                 "n_frames": 2, "scores": [0.99, 0.98]},)


class OSFCISCAILReferenceMask:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    RETURN_TYPES = ("MASK",)
    FUNCTION = "create"
    CATEGORY = "OSF CI synthetic / not production"

    def create(self):
        mask = torch.zeros((1, 64, 64), dtype=torch.float32)
        mask[:, 24:40, 24:40] = 1.0
        return (mask,)


NODE_CLASS_MAPPINGS = {
    "OSF_CI_SCAILTrack": OSFCISCAILTrack,
    "OSF_CI_SCAILReferenceMask": OSFCISCAILReferenceMask,
}
