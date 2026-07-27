"""Recognize and emit the core GUI color and texture shader variants."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module


ASSETS = {
    "mainVS_Untextured": "gui_untextured_vertex.hlsl",
    "mainPS_Untextured": "gui_untextured_pixel.hlsl",
    "mainPS_Textured": "gui_textured_pixel.hlsl",
    "mainPS_TexturedL8": "gui_textured_l8_pixel.hlsl",
    "mainPS_TexturedL8A8": "gui_textured_l8a8_pixel.hlsl",
    "mainPS_TexturedBackground": "gui_textured_background_pixel.hlsl",
}


def apply_gui_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "gui"]
    if len(shaders) != len(ASSETS) or {shader["entry_point"] for shader in shaders} != set(ASSETS):
        return None
    bodies = {
        shader["selector"]: asset(ASSETS[shader["entry_point"]])
        for shader in shaders
    }
    executions = {}
    for shader in shaders:
        if shader["stage"] != "pixel":
            continue
        textured = shader["entry_point"] != "mainPS_Untextured"
        background = shader["entry_point"] == "mainPS_TexturedBackground"
        executions[shader["selector"]] = {
            "kind": "fullscreen_texture2d",
            "vertex_harness": "fullscreen_gui",
            "texture_slots": [0],
            "samplers": [{"slot": 3, "filter": "linear"}] if textured else [],
            "constant_buffers": (
                [{"slot": 0, "profile": "random"}] if background else []
            ),
            "output": "color",
        }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="gui",
        bodies=bodies,
        executions=executions,
    )
