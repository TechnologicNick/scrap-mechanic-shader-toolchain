"""Recognize and emit the six-face sky/detail cube composition pass."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    asset,
    emit_validated_module,
    ensure_projection_include,
    ensure_recovered_cbuffer_include,
)


def apply_cube_map_composition_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record
        for record in records
        if record["source_name"] == "cube_map_composition"
    ]
    if len(shaders) != 2 or {shader["entry_point"] for shader in shaders} != {
        "triangleVS", "mainPS"
    }:
        return None
    ensure_projection_include(staging)
    ensure_recovered_cbuffer_include(
        staging, "cube_map_composition", "CB_PERFRAME", "perframe_abi.hlsl"
    )
    bodies = {}
    executions = {}
    for shader in shaders:
        if shader["stage"] == "vertex":
            bodies[shader["selector"]] = asset("cube_map_blend_vertex.hlsl")
        else:
            bodies[shader["selector"]] = asset("cube_map_composition_pixel.hlsl")
            executions[shader["selector"]] = {
                "kind": "fullscreen_cube_composition",
                "texture_slots": [0, 1, 2, 3],
                "texture_kinds": ["2d", "2d", "2darray", "2darray"],
                "samplers": [
                    {"slot": 1, "filter": "point"},
                    {"slot": 4, "filter": "linear"},
                ],
                "constant_buffers": [{"slot": 12, "profile": "random"}],
                "output": "color",
                "output_components": 4,
                "output_targets": 6,
            }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="cube_map_composition",
        bodies=bodies,
        executions=executions,
    )
