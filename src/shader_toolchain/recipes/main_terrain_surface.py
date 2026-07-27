"""Recognize and emit layered terrain-surface shaders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_projection_include, ensure_recovered_cbuffer_include


def apply_main_terrain_surface_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "main_terrain_surface"]
    if len(shaders) != 3 or sum(shader["stage"] == "pixel" for shader in shaders) != 1:
        return None
    ensure_projection_include(staging)
    ensure_recovered_cbuffer_include(
        staging, "main_terrain_surface", "CB_TILE_INFO", "terrain_tile_info_abi.hlsl"
    )
    bodies = {}
    executions = {}
    for shader in shaders:
        prefix = "".join(f"#define {definition} 1\n" for definition in shader["defines"])
        bodies[shader["selector"]] = prefix + asset(
            "main_terrain_surface_pixel.hlsl" if shader["stage"] == "pixel" else "main_terrain_surface_vertex.hlsl"
        )
        if shader["stage"] == "pixel":
            executions[shader["selector"]] = {
                "kind": "fullscreen_terrain",
                "vertex_harness": "fullscreen_terrain",
                "texture_slots": [0, 1, 2, 3, 4],
                "texture_kinds": ["2darray"] * 5,
                "texture_slices": [9] * 5,
                "samplers": [
                    {"slot": 3, "filter": "linear"},
                    {"slot": 6, "filter": "linear"},
                ],
                "constant_buffers": [{"slot": 5, "profile": "projection"}],
                "output": "color",
                "output_components": 4,
                "output_targets": 3,
            }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="main_terrain_surface",
        bodies=bodies,
        executions=executions,
    )
