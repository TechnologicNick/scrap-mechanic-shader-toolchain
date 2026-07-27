"""Recognize and emit the rectangle-to-shadow-atlas copy module."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module


def apply_copy_to_shadow_atlas_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records
        if record["source_name"] == "copy_to_shadow_atlas"
    ]
    if len(shaders) != 2 or {shader["entry_point"] for shader in shaders} != {
        "mainPS",
        "mainVS",
    }:
        return None
    bodies = {
        shader["selector"]: asset(
            "copy_to_shadow_atlas_pixel.hlsl"
            if shader["stage"] == "pixel"
            else "copy_to_shadow_atlas_vertex.hlsl"
        )
        for shader in shaders
    }
    pixel = next(shader for shader in shaders if shader["stage"] == "pixel")
    execution = {
        "kind": "fullscreen_texture2d",
        "vertex_harness": "fullscreen_uv",
        "texture_slots": [0],
        "samplers": [{"slot": 1, "filter": "point"}],
        "constant_buffers": [],
        "output": "depth",
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="copy_to_shadow_atlas",
        bodies=bodies,
        executions={pixel["selector"]: execution},
    )
