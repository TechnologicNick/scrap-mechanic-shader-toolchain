"""Recognize and emit camera-facing clutter impostor shaders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_projection_include, ensure_recovered_cbuffer_include


def apply_main_clutter_impostor_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "main_clutter_impostor"]
    if len(shaders) != 2 or {shader["stage"] for shader in shaders} != {"vertex", "pixel"}:
        return None
    ensure_projection_include(staging)
    ensure_recovered_cbuffer_include(
        staging, "main_clutter_impostor", "CB_CLUTTER_IMPOSTOR", "clutter_impostor_abi.hlsl"
    )
    bodies = {}
    executions = {}
    for shader in shaders:
        if shader["stage"] == "vertex":
            bodies[shader["selector"]] = asset("main_clutter_impostor_vertex.hlsl")
        else:
            bodies[shader["selector"]] = asset("main_clutter_impostor_pixel.hlsl")
            executions[shader["selector"]] = {
                "kind": "fullscreen_clutter_impostor",
                "vertex_harness": "fullscreen_clutter_impostor",
                "width": 64,
                "height": 64,
                "texture_slots": [0],
                "texture_kinds": ["2darray"],
                "samplers": [{"slot": 6, "filter": "linear"}],
                "constant_buffers": [],
                "output": "color",
                "output_components": 4,
                "output_targets": 3,
            }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="main_clutter_impostor",
        bodies=bodies,
        executions=executions,
    )
