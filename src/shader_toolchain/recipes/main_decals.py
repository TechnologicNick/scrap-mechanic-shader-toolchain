"""Recognize and emit the shared projected-decal material pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    asset,
    emit_validated_module,
    ensure_projection_include,
    ensure_recovered_cbuffer_include,
)


def apply_main_decals_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "main_decals"]
    if len(shaders) != 21 or sum(shader["stage"] == "vertex" for shader in shaders) != 1:
        return None
    ensure_projection_include(staging)
    ensure_recovered_cbuffer_include(
        staging, "main_decals", "CB_DECALS", "decals_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "main_decals", "CB_DECALS_OFFSET", "decals_offset_abi.hlsl"
    )
    bodies: dict[str, str] = {}
    executions: dict[str, dict[str, Any]] = {}
    for shader in shaders:
        prefix = "".join(
            f"#define {name} {value if separator else '1'}\n"
            for definition in shader["defines"]
            for name, separator, value in [definition.partition("=")]
        )
        bodies[shader["selector"]] = prefix + asset(
            "main_decals_vertex.hlsl" if shader["stage"] == "vertex"
            else "main_decals_pixel.hlsl"
        )
        if shader["stage"] != "pixel":
            continue
        defines = set(shader["defines"])
        slots = [0]
        kinds = ["2d"]
        if "PS_NORMAL_OUTPUT" in defines:
            slots.append(1)
            kinds.append("2d")
        if defines & {"PS_DIFFUSE_OUTPUT", "PS_MATERIAL_OUTPUT"}:
            slots.append(2)
            kinds.append("2darray")
        if "PS_NORMAL_OUTPUT" in defines:
            slots.append(3)
            kinds.append("2darray")
        if defines & {"PS_SAMPLE_AGS", "PS_MATERIAL_OUTPUT"}:
            slots.append(4)
            kinds.append("2darray")
        targets = 3 if "PS_MATERIAL_OUTPUT" in defines else (
            2 if "PS_NORMAL_OUTPUT" in defines else 1
        )
        executions[shader["selector"]] = {
            "kind": "main_decals",
            "vertex_harness": "decals",
            "texture_slots": slots,
            "texture_kinds": kinds,
            "samplers": ([{"slot": 6, "filter": "linear"}]
                         if len(slots) > 1 else []),
            "constant_buffers": [
                {"slot": 0, "profile": "random"},
                {"slot": 5, "profile": "projection"},
            ],
            "output": "color",
            "output_components": 4,
            "output_targets": targets,
        }
        if "PS_DIFFUSE_OUTPUT" in defines and "PS_NORMAL_OUTPUT" in defines:
            executions[shader["selector"]]["ulp_tolerance"] = 2
        if "PS_NORMAL_OUTPUT" in defines:
            # Derivative scheduling changes the final octahedral encode by a
            # few float32 ULPs without changing the reconstructed normal.
            executions[shader["selector"]]["absolute_tolerance"] = 5.0e-5
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="main_decals", bodies=bodies, executions=executions,
    )
