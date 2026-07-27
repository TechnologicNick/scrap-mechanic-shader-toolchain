"""Recognize and emit the SSGI color/depth pre-encoding pass."""

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


def apply_ssgi_prepass_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records if record["source_name"] == "ssgi_prepass"
    ]
    if len(shaders) != 1 or shaders[0]["entry_point"] != "mainPS":
        return None
    ensure_projection_include(staging)
    ensure_hdr_include(staging)
    ensure_recovered_cbuffer_include(
        staging, "ssgi_prepass", "CB_PERFRAME", "perframe_abi.hlsl"
    )
    shader = shaders[0]
    execution = {
        "kind": "fullscreen_ssgi_prepass",
        "vertex_harness": "fullscreen_uv",
        "texture_slots": [0, 1, 2],
        "samplers": [{"slot": 1, "filter": "point"}],
        "constant_buffers": [
            {"slot": 5, "profile": "projection"},
            {"slot": 9, "profile": "hdr"},
            {"slot": 12, "profile": "random"},
        ],
        "output": "color",
        "output_components": 2,
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="ssgi_prepass",
        bodies={shader["selector"]: asset("ssgi_prepass_pixel.hlsl")},
        executions={shader["selector"]: execution},
    )
