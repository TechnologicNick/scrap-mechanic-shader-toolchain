"""Recognize and emit readable horizontal and vertical Gaussian blur shaders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_projection_include


def apply_post_blur_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "post_blur"]
    entry_points = {shader["entry_point"] for shader in shaders}
    expected = {"triangleVS", "mainHorizontalPS", "mainVerticalPS"}
    if entry_points != expected or len(shaders) != 3:
        return None

    ensure_projection_include(staging)

    assets = {
        "triangleVS": "post_blur_vertex.hlsl",
        "mainHorizontalPS": "post_blur_horizontal.hlsl",
        "mainVerticalPS": "post_blur_vertical.hlsl",
    }
    vertex_selector = next(
        shader["selector"] for shader in shaders if shader["stage"] == "vertex"
    )
    bodies = {}
    executions = {}
    for shader in shaders:
        bodies[shader["selector"]] = asset(assets[shader["entry_point"]])
        if shader["stage"] == "pixel":
            executions[shader["selector"]] = {
                "kind": "fullscreen_texture2d",
                "vertex_selector": vertex_selector,
                "texture_slot": 0,
                "sampler_slot": 1,
                "constant_buffer_slot": 5,
                "filter": "point",
            }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="post_blur",
        bodies=bodies,
        executions=executions,
    )
