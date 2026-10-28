"""Disposal-only, weightless ComfyUI source of sub-8-bit-distinguishable RGB.

This node exists exclusively to test VHS CPU input conversion. Not a
production node, not a media input, and not part of the 11-workflow bundle.
"""
import torch


class OSFTestPrecisionFrames:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "generate"
    CATEGORY = "OSF CPU Test Only"

    def generate(self):
        image = torch.empty((2, 64, 64, 3), dtype=torch.float32)
        for frame in range(2):
            for row in range(2):
                for col in range(2):
                    # Adjacent source values differ by five 12-bit
                    # levels but map to the same 8-bit RGB value.
                    value = 2038 + 32 * frame + 10 * row + 5 * col
                    image[frame, row * 32:(row + 1) * 32,
                          col * 32:(col + 1) * 32, :] = value / 4095.0
        return (image,)


class OSFTestChromaPrecisionFrames:
    """Separate 3-frame R/G/B 12-bit-indexed sub-8-bit source, test-only."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "generate"
    CATEGORY = "OSF CPU Test Only"

    def generate(self):
        # Each frame varies exactly one RGB channel by eight 12-bit levels.
        # 2038 and 2046 map to the same 8-bit value in VHS's default path.
        image = torch.full((3, 64, 64, 3), 2038 / 4095.0,
                           dtype=torch.float32)
        for channel in range(3):
            image[channel, :, 32:, channel] = 2046 / 4095.0
        return (image,)


NODE_CLASS_MAPPINGS = {
    "OSFTestPrecisionFrames": OSFTestPrecisionFrames,
    "OSFTestChromaPrecisionFrames": OSFTestChromaPrecisionFrames,
}
