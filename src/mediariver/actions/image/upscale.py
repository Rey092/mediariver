"""Image upscale action — AI upscaling for manga/cover art."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Literal

from pydantic import BaseModel, Field

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action

import structlog

log = structlog.get_logger()

_ENGINE_CONFIG = {
    "realesrgan": {
        "binary": "realesrgan-ncnn-vulkan",
        "docker_image": "mediariver/realesrgan:latest",
        "model": "realesrgan-x4plus-anime",
    },
    "waifu2x": {
        "binary": "waifu2x-ncnn-vulkan",
        "docker_image": "mediariver/waifu2x:latest",
        "model": "cunet",
    },
}

_CUDA_MODELS = {
    "realesrgan-x4plus-anime": "RealESRGAN_x4plus_anime_6B",
    "realesrgan-x4plus": "RealESRGAN_x4plus",
}

_vulkan_gpu_id: int | None = None
_cuda_available: bool | None = None


def _detect_vulkan_gpu() -> int:
    """Detect a usable Vulkan GPU. Returns GPU id (>=0) or -1 for CPU fallback."""
    global _vulkan_gpu_id
    if _vulkan_gpu_id is not None:
        return _vulkan_gpu_id

    binary = _ENGINE_CONFIG["realesrgan"]["binary"]
    if not shutil.which(binary):
        _vulkan_gpu_id = -1
        return _vulkan_gpu_id

    # realesrgan-ncnn-vulkan prints available GPUs on an invalid gpu id
    try:
        proc = subprocess.run(
            [binary, "-i", "/dev/null", "-o", "/dev/null", "-g", "999"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        stderr = proc.stderr or ""
        if "invalid gpu device" in stderr or "vkCreateInstance" in stderr:
            log.warning("vulkan_gpu_unavailable", detail="falling back to CPU (-g -1)")
            _vulkan_gpu_id = -1
        else:
            _vulkan_gpu_id = 0
    except Exception:
        _vulkan_gpu_id = -1

    return _vulkan_gpu_id


def _check_cuda() -> bool:
    """Check if PyTorch CUDA is available (cached)."""
    global _cuda_available
    if _cuda_available is not None:
        return _cuda_available
    try:
        import torch

        _cuda_available = torch.cuda.is_available()
        if _cuda_available:
            log.info("cuda_available", device=torch.cuda.get_device_name(0))
        else:
            log.warning("cuda_not_available", detail="torch installed but no CUDA device")
    except ImportError:
        _cuda_available = False
        log.warning("torch_not_installed", detail="realesrgan-cuda engine unavailable")
    return _cuda_available


def _run_realesrgan_cuda(
    input_path: str,
    output_path: str,
    scale: int,
    denoise: int,
    model_name: str = "realesrgan-x4plus-anime",
) -> None:
    """Run Real-ESRGAN upscaling via PyTorch CUDA."""
    import numpy as np
    import torch
    from PIL import Image
    from realesrgan import RealESRGANer
    from basicsr.archs.rrdbnet_arch import RRDBNet

    net_name = _CUDA_MODELS.get(model_name, "RealESRGAN_x4plus_anime_6B")

    if net_name == "RealESRGAN_x4plus_anime_6B":
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4)
    else:
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)

    upsampler = RealESRGANer(
        scale=4,
        model_path=None,  # auto-downloads from GitHub releases
        dni_weight=None,
        model=model,
        tile=0,
        tile_pad=10,
        pre_pad=0,
        half=True,
        device=torch.device("cuda"),
    )

    img = np.array(Image.open(input_path).convert("RGB"))
    # realesrgan expects BGR (OpenCV format)
    img_bgr = img[:, :, ::-1]

    output_bgr, _ = upsampler.enhance(img_bgr, outscale=scale)

    # Convert back to RGB and save
    output_rgb = output_bgr[:, :, ::-1]
    Image.fromarray(output_rgb).save(output_path)

    # Free GPU memory
    del upsampler
    torch.cuda.empty_cache()


class ImageUpscaleParams(BaseModel):
    engine: Literal["realesrgan", "realesrgan-cuda", "waifu2x"] = "realesrgan"
    scale: Literal[2, 4] = 2
    denoise: int = Field(default=1, ge=0, le=3)


@register_action("image.upscale")
class ImageUpscaleAction(BaseAction):
    name = "image.upscale"
    params_model = ImageUpscaleParams

    def run(
        self,
        context: dict[str, Any],
        params: ImageUpscaleParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]
        ext = context["file"].get("ext", ".jpg")
        output_path = os.path.join(work_dir, f"{stem}_upscaled{ext}")

        if params.engine == "realesrgan-cuda":
            if not _check_cuda():
                raise RuntimeError("realesrgan-cuda engine requires PyTorch with CUDA support")

            _run_realesrgan_cuda(
                input_path=input_path,
                output_path=output_path,
                scale=params.scale,
                denoise=params.denoise,
            )
            return ActionResult(status="done", output=output_path, extras={"output": output_path})

        # ncnn-vulkan path (realesrgan / waifu2x)
        config = _ENGINE_CONFIG[params.engine]
        binary = config["binary"]
        docker_image = config["docker_image"]
        model = config["model"]

        gpu_id = _detect_vulkan_gpu()

        args = [
            "-i",
            input_path,
            "-o",
            output_path,
            "-s",
            str(params.scale),
            "-n",
            model,
            "-g",
            str(gpu_id),
        ]

        result = executor.run(
            binary=binary,
            args=args,
            docker_image=docker_image,
            strategy="auto",
            gpu=True,
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        return ActionResult(status="done", output=output_path, extras={"output": output_path})
