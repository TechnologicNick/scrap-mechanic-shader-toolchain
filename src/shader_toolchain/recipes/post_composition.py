"""Recognize the final deferred-lighting composition permutations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_recovered_cbuffer_include

def apply_post_composition_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records if record["source_name"] == "post_composition"
    ]
    if len(shaders) != 24 or any(shader["stage"] != "pixel" for shader in shaders):
        return None
    ensure_recovered_cbuffer_include(
        staging, "post_composition", "CB_PROJECTION",
        "post_composition_projection_abi.hlsl",
    )
    ensure_recovered_cbuffer_include(
        staging, "post_composition", "CB_PERFRAME",
        "post_composition_perframe_abi.hlsl",
    )
    body = asset("post_composition_pixel.hlsl")
    bodies = {}
    for shader in shaders:
        defines = set(shader["defines"])
        prefix = "".join(
            f"#define {define} 1\n"
            for define in ("ORTHO", "PS_CASCADE", "PS_REFLECTION_OFF",
                           "PS_REFLECTION_SINGLE", "PS_REFLECTION_MULTI",
                           "PS_UNDER_WATER_FOG")
            if define in defines
        )
        bodies[shader["selector"]] = prefix + body
    executions = {}
    for shader in shaders:
        defines = set(shader["defines"])
        underwater = "PS_UNDER_WATER_FOG" in defines
        single = "PS_REFLECTION_SINGLE" in defines
        multi = "PS_REFLECTION_MULTI" in defines
        slots = [0]
        if single or multi or underwater:
            slots.append(1)
        slots.extend([2, 3, 4])
        if multi:
            slots.append(5)
        if single:
            slots.append(7)
        if underwater:
            slots.extend([8, 9])
        if "PS_CASCADE" in defines:
            slots.append(10)
        kinds = ["2darray" if slot == 7 else "2d" for slot in slots]
        samplers = []
        if underwater:
            samplers.extend([
                {"slot": 0, "filter": "point"},
                {"slot": 3, "filter": "linear"},
            ])
        if single:
            samplers.append({"slot": 11, "filter": "linear"})
        executions[shader["selector"]] = {
            "kind": "fullscreen_uv",
            "vertex_harness": "fullscreen_uv",
            "texture_slots": slots,
            "texture_kinds": kinds,
            "smooth_texture_slots": [7] if single else [],
            "samplers": samplers,
            "constant_buffers": [
                {"slot": 5, "profile": "projection"},
                {"slot": 12, "profile": (
                    "composition-fog" if underwater else "composition"
                )},
            ],
            "output": "color",
            "output_components": 4,
            "output_targets": 2,
        }
        executions[shader["selector"]].update({
            "absolute_tolerance": 4.0e-6,
            "relative_tolerance": 2.0e-4 if underwater else 2.0e-7,
            "ulp_tolerance": 8,
        })
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="post_composition", bodies=bodies, executions=executions,
        shared_source=body,
    )
