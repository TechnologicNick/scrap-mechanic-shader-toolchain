"""Recognize and emit the tinted GUI volume-texture shader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module


def apply_gui_texture_3d_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "gui_texture_3d"]
    if len(shaders) != 1 or shaders[0]["entry_point"] != "mainPS":
        return None
    shader = shaders[0]
    execution = {
        "kind": "fullscreen_texture3d",
        "vertex_harness": "fullscreen_gui",
        "texture_slots": [0],
        "texture_kinds": ["3d"],
        "samplers": [{"slot": 3, "filter": "linear"}],
        "constant_buffers": [],
        "output": "color",
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="gui_texture_3d",
        bodies={shader["selector"]: asset("gui_texture_3d_pixel.hlsl")},
        executions={shader["selector"]: execution},
    )
