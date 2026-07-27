"""Recognize and emit editor terrain-surface shaders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    asset,
    emit_validated_module,
    ensure_asset_include,
    ensure_projection_include,
    ensure_recovered_cbuffer_include,
)


def apply_main_editor_terrain_surface_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record
        for record in records
        if record["source_name"] == "main_editor_terrain_surface"
    ]
    if len(shaders) != 3 or sum(
        shader["stage"] == "pixel" for shader in shaders
    ) != 1:
        return None
    ensure_projection_include(staging)
    ensure_asset_include(staging, "terrain_surface_common.hlsl")
    ensure_recovered_cbuffer_include(
        staging,
        "main_editor_terrain_surface",
        "CB_SURFACE_INFO",
        "editor_surface_info_abi.hlsl",
    )
    bodies = {}
    executions = {}
    for shader in shaders:
        prefix = "".join(
            f"#define {definition} 1\n" for definition in shader["defines"]
        )
        bodies[shader["selector"]] = prefix + asset(
            "main_editor_terrain_surface_pixel.hlsl"
            if shader["stage"] == "pixel"
            else "main_editor_terrain_surface_vertex.hlsl"
        )
        if shader["stage"] == "pixel":
            executions[shader["selector"]] = {
                "kind": "fullscreen_editor_terrain",
                "vertex_harness": "fullscreen_editor_terrain",
                "texture_slots": [0, 1, 2, 3, 4],
                "texture_kinds": ["2darray", "2darray", "2darray", "2d", "2d"],
                "texture_slices": [9, 9, 9, 1, 1],
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
        recipe_name="main_editor_terrain_surface",
        bodies=bodies,
        executions=executions,
    )
