"""Recognize and emit the readable texture downscale copy shader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module


def apply_copy_downscale_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records if record["source_name"] == "copy_downscale"
    ]
    if len(shaders) != 1 or shaders[0]["entry_point"] != "mainPS":
        return None
    shader = shaders[0]
    execution = {
        "kind": "fullscreen_texture2d",
        "vertex_harness": "fullscreen_uv",
        "texture_slot": 0,
        "sampler_slot": 6,
        "constant_buffer_slot": 5,
        "filter": "linear",
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="copy_downscale",
        bodies={shader["selector"]: asset("copy_downscale_pixel.hlsl")},
        executions={shader["selector"]: execution},
    )
