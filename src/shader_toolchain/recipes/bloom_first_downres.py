"""Recognize and emit the HDR-aware first bloom downsample pass."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    asset,
    emit_validated_module,
    ensure_hdr_include,
    ensure_projection_include,
    ensure_recovered_cbuffer_include,
)


def apply_bloom_first_downres_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records if record["source_name"] == "bloom_first_downres"
    ]
    if len(shaders) != 1 or shaders[0]["entry_point"] != "mainPS":
        return None

    ensure_projection_include(staging)
    ensure_hdr_include(staging)
    ensure_recovered_cbuffer_include(
        staging, "bloom_first_downres", "CB_PERFRAME", "perframe_abi.hlsl"
    )
    shader = shaders[0]
    execution = {
        "kind": "fullscreen_bloom_first_downres",
        "vertex_harness": "fullscreen_uv",
        "width": 64,
        "height": 64,
        "texture_slots": [0, 1, 2],
        "texture_mips": [1, 1, 4],
        "samplers": [
            {"slot": 1, "filter": "point"},
            {"slot": 6, "filter": "linear"},
        ],
        "constant_buffers": [
            {"slot": 5, "profile": "projection"},
            {"slot": 9, "profile": "hdr"},
            {"slot": 12, "profile": "bloom"},
        ],
        "output": "color",
        "output_components": 4,
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="bloom_first_downres",
        bodies={shader["selector"]: asset("bloom_first_downres_pixel.hlsl")},
        executions={shader["selector"]: execution},
    )
