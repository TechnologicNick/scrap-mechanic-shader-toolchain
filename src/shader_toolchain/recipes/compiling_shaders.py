"""Recognize and emit the rotating compiling-shaders overlay."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module


def apply_compiling_shaders_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records if record["source_name"] == "compiling_shaders"
    ]
    if len(shaders) != 1 or shaders[0]["entry_point"] != "mainPS":
        return None
    shader = shaders[0]
    execution = {
        "kind": "fullscreen_texture2d",
        "vertex_harness": "fullscreen_uv",
        "texture_slots": [0],
        "samplers": [{"slot": 6, "filter": "linear"}],
        "constant_buffer_slot": 0,
        "constant_profile": "random",
        "output": "color",
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="compiling_shaders",
        bodies={shader["selector"]: asset("compiling_shaders_pixel.hlsl")},
        executions={shader["selector"]: execution},
    )
