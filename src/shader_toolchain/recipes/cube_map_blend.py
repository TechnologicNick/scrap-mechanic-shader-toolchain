"""Recognize and emit the six-face reflection cube blend pass."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_projection_include


def apply_cube_map_blend_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records if record["source_name"] == "cube_map_blend"
    ]
    if len(shaders) != 2 or {shader["entry_point"] for shader in shaders} != {
        "triangleVS", "mainPS"
    }:
        return None
    ensure_projection_include(staging)
    bodies = {}
    executions = {}
    for shader in shaders:
        if shader["stage"] == "vertex":
            bodies[shader["selector"]] = asset("cube_map_blend_vertex.hlsl")
        else:
            bodies[shader["selector"]] = asset("cube_map_blend_pixel.hlsl")
            executions[shader["selector"]] = {
                "kind": "fullscreen_cube_array",
                "texture_slots": [0, 1],
                "texture_kinds": ["cube", "cube"],
                "samplers": [{"slot": 0, "filter": "point"}],
                "constant_buffers": [{"slot": 0, "profile": "random"}],
                "output": "color",
                "output_components": 3,
                "output_targets": 6,
            }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="cube_map_blend",
        bodies=bodies,
        executions=executions,
    )
