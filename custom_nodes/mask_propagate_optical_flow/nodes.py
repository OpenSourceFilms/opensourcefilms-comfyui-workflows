# Copyright 2026 Open Source Films
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""ComfyUI custom nodes for mask propagation across video frames using optical flow."""

import math
from typing import Tuple

import cv2
import numpy as np
import torch


class MaskPropagateOpticalFlow:
    """
    Take a batch of video frames and a single initial mask,
    then propagate that mask forward through the batch using optical flow
    computed inside this node (OpenCV Farneback).

    Inputs:
        frames: IMAGE [B, H, W, 3] float32 in [0, 1]
        init_mask: MASK [1, H, W] or [B, H, W] float32 in [0, 1]

    Output:
        masks: MASK [B, H, W] float32 in [0, 1]
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "frames": ("IMAGE",),
                "init_mask": ("MASK",),
                "method": (
                    ["farneback"],
                    {"default": "farneback"},
                ),
                "threshold": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                    },
                ),
                "blur_radius": (
                    "INT",
                    {
                        "default": 3,
                        "min": 0,
                        "max": 31,
                        "step": 1,
                    },
                ),
                "max_frames": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 4096,
                        "step": 1,
                    },
                ),
            }
        }

    RETURN_TYPES = ("MASK",)
    RETURN_NAMES = ("masks",)
    FUNCTION = "propagate"
    CATEGORY = "mask/optical_flow"

    # ---------- helpers to go between torch and numpy ----------

    @staticmethod
    def _to_uint8_rgb(frame_tensor: torch.Tensor) -> np.ndarray:
        """
        frame_tensor: [H, W, 3] float32 in [0, 1]
        returns: uint8 RGB [H, W, 3]
        """
        frame = frame_tensor.detach().cpu().numpy()
        frame = np.clip(frame * 255.0, 0.0, 255.0).astype(np.uint8)
        return frame

    @staticmethod
    def _to_uint8_mask(mask_tensor: torch.Tensor) -> np.ndarray:
        """
        mask_tensor: [H, W] float32 in [0, 1]
        returns: uint8 [H, W]
        """
        mask = mask_tensor.detach().cpu().numpy()
        mask = np.clip(mask * 255.0, 0.0, 255.0).astype(np.uint8)
        return mask

    @staticmethod
    def _from_uint8_mask(mask_np: np.ndarray) -> torch.Tensor:
        """
        mask_np: uint8 [H, W]
        returns: float32 [H, W] in [0, 1]
        """
        mask = mask_np.astype(np.float32) / 255.0
        return torch.from_numpy(mask)

    # ---------- optical flow and warping ----------

    @staticmethod
    def _compute_flow_farneback(prev_gray: np.ndarray, next_gray: np.ndarray) -> np.ndarray:
        """
        prev_gray, next_gray: uint8 [H, W]
        returns: flow [H, W, 2] float32
        flow[y, x] = (dx, dy), mapping prev -> next
        """
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray,
            next_gray,
            None,
            0.5,   # pyr_scale
            3,     # levels
            15,    # winsize
            3,     # iterations
            5,     # poly_n
            1.2,   # poly_sigma
            0,     # flags
        )
        return flow

    @staticmethod
    def _warp_mask_with_flow(prev_mask: np.ndarray, flow: np.ndarray) -> np.ndarray:
        """
        prev_mask: uint8 [H, W]   (mask at time t)
        flow: float32 [H, W, 2]   (Farneback flow from frame t -> t+1)

        We want the mask at t+1. For each pixel in frame t+1 at (x, y),
        find where it came from in frame t: (x - dx, y - dy).

        Because cv2.remap does backward mapping, we build maps with minus flow.
        """
        h, w = prev_mask.shape

        grid_x, grid_y = np.meshgrid(np.arange(w), np.arange(h))
        map_x = (grid_x - flow[..., 0]).astype(np.float32)
        map_y = (grid_y - flow[..., 1]).astype(np.float32)

        warped = cv2.remap(
            prev_mask,
            map_x,
            map_y,
            interpolation=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        return warped

    # ---------- main function (Farneback) ----------

    def propagate(
        self,
        frames: torch.Tensor,
        init_mask: torch.Tensor,
        method: str = "farneback",
        threshold: float = 0.5,
        blur_radius: int = 3,
        max_frames: int = 0,
    ) -> Tuple[torch.Tensor]:
        """
        frames: IMAGE [B, H, W, 3]
        init_mask: MASK [H, W] or [1, H, W] or [B, H, W]
        """

        if frames.ndim != 4 or frames.shape[-1] != 3:
            raise ValueError(f"frames must have shape [B, H, W, 3], got {tuple(frames.shape)}")

        num_frames, height, width, _ = frames.shape

        if max_frames > 0:
            num_frames = min(num_frames, max_frames)
            frames = frames[:num_frames]

        # Normalise init_mask to shape [H, W]
        if init_mask.ndim == 2:
            base_mask_tensor = init_mask
        elif init_mask.ndim == 3:
            # Assume [B, H, W]
            base_mask_tensor = init_mask[0]
        else:
            raise ValueError(f"init_mask must have shape [H, W] or [B, H, W], got {tuple(init_mask.shape)}")

        if base_mask_tensor.shape != (height, width):
            raise ValueError(
                f"init_mask spatial size {tuple(base_mask_tensor.shape)} "
                f"does not match frames {(height, width)}"
            )

        # Prepare numpy versions
        current_mask_np = self._to_uint8_mask(base_mask_tensor)

        # Threshold the initial mask once
        thr_float = max(0.0, min(1.0, float(threshold)))
        thr_int = int(thr_float * 255.0)
        _, current_mask_np = cv2.threshold(current_mask_np, thr_int, 255, cv2.THRESH_BINARY)

        # Ensure blur radius is odd when nonzero
        if blur_radius < 0:
            blur_radius = 0
        if blur_radius > 0 and blur_radius % 2 == 0:
            blur_radius += 1

        masks_np = np.zeros((num_frames, height, width), dtype=np.uint8)
        masks_np[0] = current_mask_np

        # Edge case: single frame, just return the initial mask
        if num_frames == 1:
            masks_tensor = self._from_uint8_mask(masks_np[0]).unsqueeze(0)
            return (masks_tensor,)

        for t in range(num_frames - 1):
            frame_t = self._to_uint8_rgb(frames[t])
            frame_tp1 = self._to_uint8_rgb(frames[t + 1])

            prev_gray = cv2.cvtColor(frame_t, cv2.COLOR_RGB2GRAY)
            next_gray = cv2.cvtColor(frame_tp1, cv2.COLOR_RGB2GRAY)

            if method == "farneback":
                flow = self._compute_flow_farneback(prev_gray, next_gray)
            else:
                raise ValueError(f"Unsupported optical flow method: {method}")

            warped_mask = self._warp_mask_with_flow(current_mask_np, flow)

            if blur_radius > 0:
                warped_mask = cv2.GaussianBlur(warped_mask, (blur_radius, blur_radius), 0)

            # Re threshold to keep mask crisp
            _, warped_mask = cv2.threshold(warped_mask, thr_int, 255, cv2.THRESH_BINARY)

            current_mask_np = warped_mask
            masks_np[t + 1] = current_mask_np

        # Convert back to torch MASK [B, H, W] in [0, 1]
        masks_list = [self._from_uint8_mask(masks_np[i]) for i in range(num_frames)]
        masks_tensor = torch.stack(masks_list, dim=0).contiguous()

        return (masks_tensor,)


class MaskPropagateFromFlow:
    """
    Propagate a mask using a precomputed OPTICAL_FLOW batch, e.g. from
    Unimatch_OptFlowPreprocessor (comfyui_controlnet_aux).

    Inputs:
        flow: OPTICAL_FLOW [F, H, W, 2] (typically F = num_frames - 1)
        init_mask: MASK [H, W] or [1, H, W] or [B, H, W]

    Output:
        masks: MASK [F+1, H, W] float32 in [0, 1]
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "flow": ("OPTICAL_FLOW",),
                "init_mask": ("MASK",),
                "threshold": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                    },
                ),
                "blur_radius": (
                    "INT",
                    {
                        "default": 3,
                        "min": 0,
                        "max": 31,
                        "step": 1,
                    },
                ),
                "max_frames": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 4096,
                        "step": 1,
                    },
                ),
            }
        }

    RETURN_TYPES = ("MASK",)
    RETURN_NAMES = ("masks",)
    FUNCTION = "propagate_from_flow"
    CATEGORY = "mask/optical_flow"

    @staticmethod
    def _to_uint8_mask(mask_tensor: torch.Tensor) -> np.ndarray:
        mask = mask_tensor.detach().cpu().numpy()
        mask = np.clip(mask * 255.0, 0.0, 255.0).astype(np.uint8)
        return mask

    @staticmethod
    def _from_uint8_mask(mask_np: np.ndarray) -> torch.Tensor:
        mask = mask_np.astype(np.float32) / 255.0
        return torch.from_numpy(mask)

    @staticmethod
    def _warp_mask_with_flow(prev_mask: np.ndarray, flow: np.ndarray) -> np.ndarray:
        """
        prev_mask: uint8 [H, W]   (mask at time t)
        flow: float32 [H, W, 2]   (flow from frame t -> t+1)

        For each pixel in frame t+1 at (x, y), sample from frame t at (x - dx, y - dy).
        """
        h, w = prev_mask.shape

        grid_x, grid_y = np.meshgrid(np.arange(w), np.arange(h))
        map_x = (grid_x - flow[..., 0]).astype(np.float32)
        map_y = (grid_y - flow[..., 1]).astype(np.float32)

        warped = cv2.remap(
            prev_mask,
            map_x,
            map_y,
            interpolation=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        return warped

    def propagate_from_flow(
        self,
        flow: torch.Tensor,
        init_mask: torch.Tensor,
        threshold: float = 0.5,
        blur_radius: int = 3,
        max_frames: int = 0,
    ) -> Tuple[torch.Tensor]:
        """
        flow: OPTICAL_FLOW [F, H, W, 2]
        init_mask: MASK [H, W] or [1, H, W] or [B, H, W]
        """

        if flow.ndim != 4 or flow.shape[-1] != 2:
            raise ValueError(f"flow must have shape [F, H, W, 2], got {tuple(flow.shape)}")

        num_flows, height, width, _ = flow.shape

        # Determine how many flows to use
        if max_frames > 0:
            # masks = max_frames (cap), flows = masks - 1
            use_flows = max(0, min(num_flows, max_frames - 1))
        else:
            use_flows = num_flows

        if use_flows == 0:
            # Just return the initial mask as a single-frame batch
            if init_mask.ndim == 2:
                base_mask_tensor = init_mask
            elif init_mask.ndim == 3:
                base_mask_tensor = init_mask[0]
            else:
                raise ValueError(
                    f"init_mask must have shape [H, W] or [B, H, W], got {tuple(init_mask.shape)}"
                )
            if base_mask_tensor.shape != (height, width):
                raise ValueError(
                    f"init_mask spatial size {tuple(base_mask_tensor.shape)} "
                    f"does not match flow {(height, width)}"
                )
            mask0_np = self._to_uint8_mask(base_mask_tensor)
            masks_tensor = self._from_uint8_mask(mask0_np).unsqueeze(0)
            return (masks_tensor,)

        flows = flow[:use_flows]

        # Normalise init_mask to shape [H, W]
        if init_mask.ndim == 2:
            base_mask_tensor = init_mask
        elif init_mask.ndim == 3:
            base_mask_tensor = init_mask[0]
        else:
            raise ValueError(f"init_mask must have shape [H, W] or [B, H, W], got {tuple(init_mask.shape)}")

        if base_mask_tensor.shape != (height, width):
            raise ValueError(
                f"init_mask spatial size {tuple(base_mask_tensor.shape)} "
                f"does not match flow {(height, width)}"
            )

        current_mask_np = self._to_uint8_mask(base_mask_tensor)

        thr_float = max(0.0, min(1.0, float(threshold)))
        thr_int = int(thr_float * 255.0)
        _, current_mask_np = cv2.threshold(current_mask_np, thr_int, 255, cv2.THRESH_BINARY)

        if blur_radius < 0:
            blur_radius = 0
        if blur_radius > 0 and blur_radius % 2 == 0:
            blur_radius += 1

        num_masks = use_flows + 1
        masks_np = np.zeros((num_masks, height, width), dtype=np.uint8)
        masks_np[0] = current_mask_np

        for t in range(use_flows):
            flow_t = flows[t].detach().cpu().numpy()

            warped_mask = self._warp_mask_with_flow(current_mask_np, flow_t)

            if blur_radius > 0:
                warped_mask = cv2.GaussianBlur(warped_mask, (blur_radius, blur_radius), 0)

            _, warped_mask = cv2.threshold(warped_mask, thr_int, 255, cv2.THRESH_BINARY)

            current_mask_np = warped_mask
            masks_np[t + 1] = current_mask_np

        masks_list = [self._from_uint8_mask(masks_np[i]) for i in range(num_masks)]
        masks_tensor = torch.stack(masks_list, dim=0).contiguous()

        return (masks_tensor,)
