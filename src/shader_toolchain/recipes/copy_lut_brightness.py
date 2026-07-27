"""Recognize and emit the combinatorial final color-grading pass."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    asset,
    emit_validated_module,
    ensure_projection_include,
    ensure_recovered_cbuffer_include,
)


def apply_copy_lut_brightness_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records
        if record["source_name"] == "copy_lut_brightness"
    ]
    if len(shaders) != 192 or any(shader["stage"] != "pixel" for shader in shaders):
        return None
    ensure_projection_include(staging)
    ensure_recovered_cbuffer_include(
        staging, "copy_lut_brightness", "CB_PERFRAME", "perframe_abi.hlsl"
    )
    source = asset("copy_lut_brightness.hlsl")
    bodies = {}
    executions = {}
    for shader in shaders:
        prefix = "".join(
            f"#define {name} {value if separator else '1'}\n"
            for definition in shader["defines"]
            for name, separator, value in [definition.partition("=")]
        )
        bodies[shader["selector"]] = prefix + source
        defines = set(shader["defines"])
        slots = [0]
        kinds = ["2d"]
        if "PS_LUT_A" in defines:
            slots.append(1)
            kinds.append("3d")
        if "PS_LUT_B" in defines:
            slots.append(2)
            kinds.append("3d")
        uses_projection = bool(defines & {
            "PS_BARREL_DISTORTION", "PS_CHROMATIC", "PS_FILM_GRAIN"
        })
        constants = [{"slot": 12, "profile": "random"}]
        if uses_projection:
            constants.insert(0, {"slot": 5, "profile": "projection"})
        executions[shader["selector"]] = {
            "kind": "fullscreen_uv",
            "vertex_harness": "fullscreen_uv",
            "texture_slots": slots,
            "texture_kinds": kinds,
            "samplers": [{"slot": 6, "filter": "linear"}],
            "constant_buffers": constants,
            "output": "color",
            "output_components": 3,
        }
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="copy_lut_brightness", bodies=bodies, executions=executions,
    )
