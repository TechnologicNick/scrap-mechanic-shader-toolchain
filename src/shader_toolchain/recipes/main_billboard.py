"""Recognize and emit world-space and overlay billboard shaders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_projection_include, ensure_recovered_cbuffer_include


def apply_main_billboard_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "main_billboard"]
    if len(shaders) != 10 or sum(shader["stage"] == "pixel" for shader in shaders) != 6:
        return None
    ensure_projection_include(staging)
    ensure_recovered_cbuffer_include(
        staging, "main_billboard", "CB_TRANSFORMS", "billboard_transforms_abi.hlsl"
    )
    bodies = {}
    executions = {}
    for shader in shaders:
        defines = set(shader["defines"])
        prefix = "".join(f"#define {definition} 1\n" for definition in shader["defines"])
        bodies[shader["selector"]] = prefix + asset(
            "main_billboard_pixel.hlsl" if shader["stage"] == "pixel" else "main_billboard_vertex.hlsl"
        )
        if shader["stage"] != "pixel":
            continue
        slots = [7] if "PS_SOLID_COLOR" in defines else [0, 7]
        kinds = ["2d"] if "PS_SOLID_COLOR" in defines else ["2darray", "2d"]
        if "PS_BLUR" in defines:
            slots = [0, 1, 7, 15]
            kinds = ["2darray", "2d", "2d", "2d"]
        if "PS_OVERLAY_DEPTH_FADE" in defines:
            slots.append(10)
            kinds.append("2d")
        executions[shader["selector"]] = {
            "kind": "fullscreen_billboard",
            "vertex_harness": "fullscreen_billboard",
            "texture_slots": slots,
            "texture_kinds": kinds,
            "samplers": [{"slot": 6, "filter": "linear"}],
            "constant_buffers": [{"slot": 5, "profile": "projection"}],
            "output": "color",
            "output_components": 4,
        }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="main_billboard",
        bodies=bodies,
        executions=executions,
    )
