"""CI-only deterministic high-precision IMAGE source; not a production node."""
import torch


class OSFCIPrecision12BitSource:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "generate"
    CATEGORY = "OSF CI/precision only"

    def generate(self):
        # Both values in each frame share a single 8-bit bucket but are
        # different genuine twelve-bit integer source levels.
        levels = ((2038, 2043), (2048, 2053))
        frames = torch.empty((2, 64, 64, 3), dtype=torch.float32)
        for index, (left, right) in enumerate(levels):
            frames[index, :, :32, :] = left / 4095.0
            frames[index, :, 32:, :] = right / 4095.0
        return (frames,)


NODE_CLASS_MAPPINGS = {
    "OSF_CI_Precision12BitSource": OSFCIPrecision12BitSource,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "OSF_CI_Precision12BitSource": "OSF CI-only 12-bit precision source",
}
