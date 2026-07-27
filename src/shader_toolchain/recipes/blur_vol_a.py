"""Recognize and emit the depth-aware first volumetric blur pass."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_projection_include


def apply_blur_vol_a_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "blur_vol_a"]
    if len(shaders) != 1 or shaders[0]["entry_point"] != "mainPS":
        return None
    ensure_projection_include(staging)
    shader = shaders[0]
    execution = {
        "kind": "fullscreen_texture2d",
        "vertex_harness": "fullscreen_uv",
        "texture_slots": [0, 1],
        "texture_mips": [1, 4],
        "samplers": [
            {"slot": 1, "filter": "point"},
            {"slot": 6, "filter": "linear"},
        ],
        "constant_buffers": [{"slot": 5, "profile": "projection"}],
        "output": "color",
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="blur_vol_a",
        bodies={shader["selector"]: asset("blur_vol_a_pixel.hlsl")},
        executions={shader["selector"]: execution},
    )
