"""Recognize and emit final bloom composition and display transfer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_hdr_include


def apply_bloom_last_upres_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records if record["source_name"] == "bloom_last_upres"
    ]
    if len(shaders) != 1 or shaders[0]["entry_point"] != "mainPS":
        return None
    ensure_hdr_include(staging)
    shader = shaders[0]
    execution = {
        "kind": "fullscreen_texture2d",
        "vertex_harness": "fullscreen_uv",
        "texture_slots": [0, 1],
        "samplers": [
            {"slot": 1, "filter": "point"},
            {"slot": 6, "filter": "linear"},
        ],
        "constant_buffer_slot": 9,
        "constant_profile": "hdr",
        "output": "color",
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="bloom_last_upres",
        bodies={shader["selector"]: asset("bloom_last_upres_pixel.hlsl")},
        executions={shader["selector"]: execution},
    )
