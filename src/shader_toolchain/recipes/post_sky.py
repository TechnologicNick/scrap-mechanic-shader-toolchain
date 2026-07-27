"""Recognize and emit the sky, horizon, sun, and underwater pass."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    asset,
    emit_validated_module,
    ensure_projection_include,
    ensure_recovered_cbuffer_include,
)


def apply_post_sky_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "post_sky"]
    if len(shaders) != 3 or {shader["entry_point"] for shader in shaders} != {
        "triangleVS", "mainPS"
    }:
        return None
    ensure_projection_include(staging)
    ensure_recovered_cbuffer_include(
        staging, "post_sky", "CB_PERFRAME", "perframe_abi.hlsl"
    )
    pixel_body = asset("post_sky_pixel.hlsl")
    bodies = {}
    executions = {}
    for shader in shaders:
        if shader["stage"] == "vertex":
            bodies[shader["selector"]] = asset("post_sky_vertex.hlsl")
            continue
        dither = "PS_DITHER" in shader["defines"]
        bodies[shader["selector"]] = (
            "#define SKY_DITHER 1\n" + pixel_body if dither else pixel_body
        )
        executions[shader["selector"]] = {
            "kind": "fullscreen_sky",
            "texture_slots": [0, 1] if dither else [0],
            "samplers": [{"slot": 4, "filter": "linear"}],
            "constant_buffers": [
                {"slot": 5, "profile": "projection"},
                {"slot": 12, "profile": "random"},
            ],
            "output": "color",
            "output_components": 4,
        }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="post_sky",
        bodies=bodies,
        executions=executions,
    )
