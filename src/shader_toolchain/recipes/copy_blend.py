"""Recognize and emit the readable two-texture blend shader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module


def apply_copy_blend_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "copy_blend"]
    if len(shaders) != 1 or shaders[0]["entry_point"] != "mainPS":
        return None
    shader = shaders[0]
    execution = {
        "kind": "fullscreen_texture2d",
        "vertex_harness": "fullscreen_uv",
        "texture_slots": [0, 1],
        "sampler_slot": 1,
        "constant_buffer_slot": 0,
        "constant_profile": "random",
        "filter": "point",
        "output": "color",
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="copy_blend",
        bodies={shader["selector"]: asset("copy_blend_pixel.hlsl")},
        executions={shader["selector"]: execution},
    )
