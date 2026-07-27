"""Recognize and emit the GUI silhouette color-blend module."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module


def apply_gui_silhouette_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "gui_silhouette"]
    if len(shaders) != 2 or {shader["entry_point"] for shader in shaders} != {
        "mainPS",
        "mainVS",
    }:
        return None
    bodies = {
        shader["selector"]: asset(
            "gui_silhouette_pixel.hlsl"
            if shader["stage"] == "pixel"
            else "gui_silhouette_vertex.hlsl"
        )
        for shader in shaders
    }
    pixel = next(shader for shader in shaders if shader["stage"] == "pixel")
    execution = {
        "kind": "fullscreen_texture2d",
        "vertex_harness": "fullscreen_gui",
        "texture_slots": [0],
        "samplers": [{"slot": 3, "filter": "linear"}],
        "constant_buffers": [{"slot": 0, "profile": "random"}],
        "output": "color",
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="gui_silhouette",
        bodies=bodies,
        executions={pixel["selector"]: execution},
    )
