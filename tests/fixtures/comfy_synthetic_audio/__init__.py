"""Disposable model-free mono and stereo audio sources for VHS ProRes mux acceptance.

Do not copy this test-only custom node into production ComfyUI.
"""
import torch


class OSFTestSineAudio:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    RETURN_TYPES = ("AUDIO",)
    FUNCTION = "generate"
    CATEGORY = "OSF CI Synthetic"

    def generate(self):
        sample_rate = 48000
        count = sample_rate
        samples = torch.arange(count, dtype=torch.float32)
        waveform = 0.2 * torch.sin(2 * torch.pi * 440 * samples / sample_rate)
        return ({"waveform": waveform.reshape(1, 1, count),
                 "sample_rate": sample_rate},)


class OSFTestStereoAudio:
    """Test-only independent left/right tones, never deploy to production."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    RETURN_TYPES = ("AUDIO",)
    FUNCTION = "generate"
    CATEGORY = "OSF CI Synthetic"

    def generate(self):
        sample_rate = 48000
        count = sample_rate
        t = torch.arange(count, dtype=torch.float32) / sample_rate
        left = 0.20 * torch.sin(2 * torch.pi * 440 * t)
        right = 0.14 * torch.sin(2 * torch.pi * 660 * t)
        waveform = torch.stack((left, right), dim=0).unsqueeze(0)
        return ({"waveform": waveform, "sample_rate": sample_rate},)


NODE_CLASS_MAPPINGS = {
    "OSFTestSineAudio": OSFTestSineAudio,
    "OSFTestStereoAudio": OSFTestStereoAudio,
}
