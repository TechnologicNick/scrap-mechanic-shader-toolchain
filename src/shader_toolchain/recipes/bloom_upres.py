"""Recognize and emit the readable twelve-weight bloom upsample shader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_projection_include


def apply_bloom_upres_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "bloom_upres"]
    if len(shaders) != 1 or shaders[0]["entry_point"] != "mainPS":
        return None
    ensure_projection_include(staging)
    shader = shaders[0]
    execution = {
        "kind": "fullscreen_texture2d",
        "vertex_harness": "fullscreen_uv",
        "texture_slots": [0],
        "sampler_slot": 6,
        "constant_buffer_slot": 5,
        "constant_profile": "projection",
        "filter": "linear",
        "output": "color",
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="bloom_upres",
        bodies={shader["selector"]: asset("bloom_upres_pixel.hlsl")},
        executions={shader["selector"]: execution},
    )
