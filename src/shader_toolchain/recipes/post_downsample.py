"""Recognize and emit downsample plus separable post-blur permutations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_projection_include


def apply_post_downsample_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records if record["source_name"] == "post_downsample"
    ]
    assets = {
        "mainHorizontalPS": "post_downsample_horizontal.hlsl",
        "mainVerticalPS": "post_downsample_vertical.hlsl",
        "mainDownsamplePS": "post_downsample_pixel.hlsl",
    }
    if len(shaders) != 3 or {shader["entry_point"] for shader in shaders} != set(assets):
        return None
    ensure_projection_include(staging)
    bodies = {
        shader["selector"]: asset(assets[shader["entry_point"]])
        for shader in shaders
    }
    executions = {}
    for shader in shaders:
        downsample = shader["entry_point"] == "mainDownsamplePS"
        executions[shader["selector"]] = {
            "kind": "fullscreen_texture2d",
            "vertex_harness": "fullscreen_uv",
            "texture_slots": [0],
            "sampler_slot": 6 if downsample else 1,
            "constant_buffer_slot": 5,
            "constant_profile": "projection",
            "filter": "linear" if downsample else "point",
            "output": "color",
        }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="post_downsample",
        bodies=bodies,
        executions=executions,
    )
