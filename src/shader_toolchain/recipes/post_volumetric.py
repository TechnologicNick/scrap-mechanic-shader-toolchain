"""Recognize and validate the shared structural volumetric-light shader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_recovered_cbuffer_include


ABI_INCLUDES = (
    ("CB_PROJECTION", "post_volumetric_projection_abi.hlsl"),
    ("CB_PERFRAME", "post_volumetric_perframe_abi.hlsl"),
    ("cb_hdr_settings", "post_volumetric_hdr_abi.hlsl"),
    ("Cluster", "post_volumetric_cluster_abi.hlsl"),
    ("VolumetricProps", "post_volumetric_lights_abi.hlsl"),
)


def apply_post_volumetric_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records
        if record["source_name"] == "post_volumetric"
    ]
    if len(shaders) != 2 or any(shader["stage"] != "pixel" for shader in shaders):
        return None

    for cbuffer_name, filename in ABI_INCLUDES:
        ensure_recovered_cbuffer_include(
            staging, "post_volumetric", cbuffer_name, filename
        )

    body = asset("post_volumetric_pixel.hlsl")
    bodies = {shader["selector"]: body for shader in shaders}
    execution = {
        "kind": "fullscreen_uv",
        "vertex_harness": "fullscreen_packed_uv",
        "texture_slots": [0, 2, 3, 4, 5, 6, 7, 8],
        "texture_kinds": [
            "2d", "3d", "2darray", "2darray", "2d", "2d", "2d", "2d"
        ],
        "texture_mips": [3, 1, 6, 1, 3, 1, 1, 1],
        "texture_slices": [1, 4, 6, 6, 1, 1, 1, 1],
        "structured_inputs": [
            {"slot": 1, "elements": 17, "stride": 4, "profile": "volumetric"},
        ],
        "samplers": [
            {"slot": 1, "filter": "point"},
            {"slot": 3, "filter": "linear"},
            {"slot": 6, "filter": "linear"},
            {"slot": 13, "filter": "point", "comparison": True},
        ],
        "constant_buffers": [
            {"slot": 0, "profile": "volumetric-cluster"},
            {"slot": 1, "profile": "volumetric-lights"},
            {"slot": 5, "profile": "projection"},
            {"slot": 9, "profile": "hdr"},
            {"slot": 12, "profile": "volumetric-frame"},
        ],
        "output": "color",
        "output_components": 4,
        "output_targets": 2,
        "absolute_tolerance": 1.0e-5,
        "relative_tolerance": 1.0e-5,
        "ulp_tolerance": 32,
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="post_volumetric",
        bodies=bodies,
        executions={shader["selector"]: execution for shader in shaders},
        shared_source=body,
    )
