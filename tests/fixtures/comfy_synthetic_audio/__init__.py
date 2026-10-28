"""Disposable model-free mono audio source for VHS ProRes mux acceptance.

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


NODE_CLASS_MAPPINGS = {"OSFTestSineAudio": OSFTestSineAudio}
