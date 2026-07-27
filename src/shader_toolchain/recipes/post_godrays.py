"""Recognize and emit the two readable god-ray integration modes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    asset,
    emit_validated_module,
    ensure_recovered_cbuffer_include,
)


def apply_post_godrays_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "post_godrays"]
    if len(shaders) != 2 or any(shader["stage"] != "pixel" for shader in shaders):
        return None
    ensure_recovered_cbuffer_include(
        staging, "post_godrays", "CB_PROJECTION",
        "post_godrays_projection_abi.hlsl",
    )
    ensure_recovered_cbuffer_include(
        staging, "post_godrays", "CB_PERFRAME",
        "post_godrays_perframe_abi.hlsl",
    )
    ensure_recovered_cbuffer_include(
        staging, "post_godrays", "cb_hdr_settings",
        "post_godrays_hdr_abi.hlsl",
    )
    body = asset("post_godrays_pixel.hlsl")
    bodies = {
        shader["selector"]: (
            (
                "#define PS_UNDER_WATER 1\n"
                if "PS_UNDER_WATER" in shader["defines"]
                else ""
            )
            + body
        )
        for shader in shaders
    }
    executions = {}
    for shader in shaders:
        underwater = "PS_UNDER_WATER" in shader["defines"]
        slots = [0, 1, 3, 4] + ([5] if underwater else [])
        samplers = [
            {"slot": 1, "filter": "point"},
            {"slot": 6, "filter": "linear"},
            {"slot": 12, "filter": "linear", "comparison": True},
        ]
        if underwater:
            samplers.insert(1, {"slot": 3, "filter": "linear"})
        executions[shader["selector"]] = {
            "kind": "fullscreen_uv",
            "vertex_harness": "fullscreen_uv",
            "texture_slots": slots,
            "texture_kinds": ["2d", "2darray", "2d", "2d"]
                             + (["2d"] if underwater else []),
            "samplers": samplers,
            "constant_buffers": [
                {"slot": 5, "profile": "projection"},
                {"slot": 9, "profile": "hdr"},
                {"slot": 12, "profile": "godrays"},
            ],
            "output": "color",
            "output_components": 4,
            "output_targets": 2,
            # Named helpers preserve the recovered operation order, but the
            # compiler can attach a handful of multiply-adds differently.
            "absolute_tolerance": 1.0e-5,
            "ulp_tolerance": 16,
        }
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="post_godrays", bodies=bodies, executions=executions,
    )
