"""Recognize and emit depth-to-temporal-push-map conversion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    asset,
    emit_validated_module,
    ensure_projection_include,
    ensure_recovered_cbuffer_include,
)


def apply_post_depth_to_pushmap_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record
        for record in records
        if record["source_name"] == "post_depth_to_pushmap"
    ]
    if len(shaders) != 1 or shaders[0]["entry_point"] != "mainPS":
        return None
    ensure_projection_include(staging)
    ensure_recovered_cbuffer_include(
        staging, "post_depth_to_pushmap", "CB_PERFRAME", "perframe_abi.hlsl"
    )
    shader = shaders[0]
    execution = {
        "kind": "fullscreen_pushmap",
        "vertex_harness": "fullscreen_uv",
        "texture_slots": [0, 1],
        "samplers": [
            {"slot": 1, "filter": "point"},
            {"slot": 6, "filter": "linear"},
        ],
        "constant_buffers": [
            {"slot": 0, "profile": "random"},
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
        recipe_name="post_depth_to_pushmap",
        bodies={shader["selector"]: asset("post_depth_to_pushmap_pixel.hlsl")},
        executions={shader["selector"]: execution},
    )
