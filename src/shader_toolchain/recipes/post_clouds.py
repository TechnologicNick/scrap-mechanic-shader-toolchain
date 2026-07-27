"""Recognize and validate the cloud ray-march and temporal resolve passes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_recovered_cbuffer_include


def apply_post_clouds_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "post_clouds"]
    if len(shaders) != 3 or {shader["entry_point"] for shader in shaders} != {
        "triangleVS", "mainPS"
    }:
        return None
    ensure_recovered_cbuffer_include(
        staging, "post_clouds", "CB_PROJECTION", "post_clouds_projection_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "post_clouds", "CB_PERFRAME", "post_clouds_perframe_abi.hlsl"
    )
    pixel = asset("post_clouds_pixel.hlsl")
    vertex = asset("post_clouds_vertex.hlsl")
    bodies = {
        shader["selector"]: (
            vertex if shader["stage"] == "vertex" else
            (("#define PS_TEMPORAL 1\n" if "PS_TEMPORAL" in shader["defines"] else "") + pixel)
        )
        for shader in shaders
    }
    executions = {}
    for shader in shaders:
        if shader["stage"] != "pixel":
            continue
        temporal = "PS_TEMPORAL" in shader["defines"]
        executions[shader["selector"]] = {
            "kind": "fullscreen_uv",
            "vertex_harness": "fullscreen_uv",
            "texture_slots": [0, 1, 2, 3, 4, 5, 7] if temporal else [0, 1, 2, 3],
            "texture_kinds": (
                ["2d", "2d", "3d", "2d", "2d", "2d", "2d"]
                if temporal else ["2d", "2d", "3d", "2d"]
            ),
            "samplers": [
                {"slot": 3, "filter": "linear"},
                {"slot": 4, "filter": "linear"},
            ] + ([{"slot": 6, "filter": "linear"}] if temporal else []),
            "constant_buffers": [
                {"slot": 5, "profile": "projection"},
                {"slot": 12, "profile": "cloud"},
            ],
            "output": "color",
            "output_components": 4,
            "output_targets": 2,
        }
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="post_clouds", bodies=bodies, executions=executions,
    )
