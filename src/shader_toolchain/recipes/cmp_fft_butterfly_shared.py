"""Recognize and emit the shared-memory inverse ocean FFT passes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module


def apply_cmp_fft_butterfly_shared_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records
        if record["source_name"] == "cmp_fft_butterfly_shared"
    ]
    if len(shaders) != 2 or any(shader["entry_point"] != "mainCS" for shader in shaders):
        return None
    bodies = {}
    executions = {}
    for shader in shaders:
        horizontal = "HORIZONTAL" in shader["defines"]
        bodies[shader["selector"]] = asset(
            "cmp_fft_horizontal_compute.hlsl"
            if horizontal
            else "cmp_fft_vertical_compute.hlsl"
        )
        executions[shader["selector"]] = {
            "kind": "compute_texture2d",
            "width": 256,
            "height": 256,
            "thread_group": [256, 1, 1],
            "texture_slots": [0],
            "samplers": [],
            "constant_buffers": (
                [{"slot": 1, "profile": "random"}] if horizontal else []
            ),
            "output": "color",
            "output_components": 2 if horizontal else 1,
        }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="cmp_fft_butterfly_shared",
        bodies=bodies,
        executions=executions,
    )
