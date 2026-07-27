"""Recognize and emit spherical impostor depth and G-buffer passes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    asset,
    emit_validated_module,
    ensure_projection_include,
    ensure_recovered_cbuffer_include,
)


def apply_main_impostor_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "main_impostor"]
    if len(shaders) != 4 or sum(shader["stage"] == "pixel" for shader in shaders) != 2:
        return None
    ensure_projection_include(staging)
    ensure_recovered_cbuffer_include(
        staging, "main_impostor", "CB_IMPOSTORS", "impostors_abi.hlsl"
    )
    pixel = asset("main_impostor_pixel.hlsl")
    vertex = asset("main_impostor_vertex.hlsl")
    bodies = {}
    executions = {}
    for shader in shaders:
        prefix = "".join(f"#define {definition} 1\n" for definition in shader["defines"])
        bodies[shader["selector"]] = prefix + (vertex if shader["stage"] == "vertex" else pixel)
        if shader["stage"] != "pixel":
            continue
        depth = "DEPTH" in shader["defines"]
        executions[shader["selector"]] = {
            "kind": "fullscreen_impostor",
            "vertex_harness": "fullscreen_impostor",
            "texture_slots": [1] if depth else [0, 1, 14],
            "texture_kinds": ["2darray"] if depth else ["2darray", "2darray", "2d"],
            "samplers": (
                [{"slot": 1, "filter": "point"}]
                if depth else
                [{"slot": 0, "filter": "point"}, {"slot": 6, "filter": "linear"}]
            ),
            "output": "depth" if depth else "color",
            "output_components": 1 if depth else 4,
            "output_targets": 1 if depth else 3,
        }
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="main_impostor", bodies=bodies, executions=executions,
    )
