"""Recognize and emit the debug-drawer transform and visualization variants."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_projection_include


def apply_main_debug_drawer_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records
        if record["source_name"] == "main_debug_drawer"
    ]
    if len(shaders) != 5 or sum(shader["stage"] == "vertex" for shader in shaders) != 2:
        return None
    ensure_projection_include(staging)
    bodies = {}
    executions = {}
    for shader in shaders:
        defines = set(shader["defines"])
        if shader["stage"] == "vertex":
            filename = (
                "main_debug_drawer_mesh_vertex.hlsl"
                if "VS_MESH" in defines
                else "main_debug_drawer_vertex.hlsl"
            )
        elif "PS_SOLID_COLOR" in defines:
            filename = "main_debug_drawer_solid_pixel.hlsl"
        elif "PS_VISUALIZATION" in defines:
            filename = "main_debug_drawer_visualization_pixel.hlsl"
        else:
            filename = "main_debug_drawer_occlusion_pixel.hlsl"
        bodies[shader["selector"]] = asset(filename)
        if shader["stage"] == "pixel":
            uses_depth = "PS_SOLID_COLOR" not in defines
            executions[shader["selector"]] = {
                "kind": "fullscreen_texture2d",
                "vertex_harness": "fullscreen_debug",
                "texture_slots": [0],
                "samplers": ([{"slot": 1, "filter": "point"}] if uses_depth else []),
                "constant_buffers": (
                    [{"slot": 5, "profile": "projection"}] if uses_depth else []
                ),
                "output": "color",
            }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="main_debug_drawer",
        bodies=bodies,
        executions=executions,
    )
