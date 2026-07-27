"""Recognize and emit the background-filled GUI texture-array shader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module


def apply_gui_texture_box_array_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records
        if record["source_name"] == "gui_texture_box_array"
    ]
    if len(shaders) != 1 or shaders[0]["entry_point"] != "mainPS":
        return None
    shader = shaders[0]
    execution = {
        "kind": "fullscreen_texture2d_array",
        "vertex_harness": "fullscreen_gui",
        "texture_slots": [0],
        "texture_kinds": ["2darray"],
        "samplers": [{"slot": 3, "filter": "linear"}],
        "constant_buffers": [{"slot": 0, "profile": "random"}],
        "output": "color",
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="gui_texture_box_array",
        bodies={shader["selector"]: asset("gui_texture_box_array_pixel.hlsl")},
        executions={shader["selector"]: execution},
    )
