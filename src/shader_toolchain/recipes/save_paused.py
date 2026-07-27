"""Recognize and emit the pulsing paused-save overlay shader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module


def apply_save_paused_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "save_paused"]
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
        recipe_name="save_paused",
        bodies={shader["selector"]: asset("save_paused_pixel.hlsl")},
        executions={shader["selector"]: execution},
    )
