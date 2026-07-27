"""Recognize and emit the cube-face fog and light composition pass."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    asset,
    emit_validated_module,
    ensure_projection_include,
    ensure_recovered_cbuffer_include,
)


def apply_cube_map_face_composition_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record
        for record in records
        if record["source_name"] == "cube_map_face_composition"
    ]
    if len(shaders) != 1 or shaders[0]["entry_point"] != "mainPS":
        return None
    ensure_projection_include(staging)
    ensure_recovered_cbuffer_include(
        staging, "cube_map_face_composition", "CB_PERFRAME", "perframe_abi.hlsl"
    )
    shader = shaders[0]
    execution = {
        "kind": "fullscreen_fog_composition",
        "vertex_harness": "fullscreen_uv",
        "texture_slots": [0, 1],
        "samplers": [{"slot": 1, "filter": "point"}],
        "constant_buffers": [
            {"slot": 5, "profile": "projection"},
            {"slot": 12, "profile": "random"},
        ],
        "output": "color",
        "output_components": 4,
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="cube_map_face_composition",
        bodies={shader["selector"]: asset("cube_map_face_composition_pixel.hlsl")},
        executions={shader["selector"]: execution},
    )
