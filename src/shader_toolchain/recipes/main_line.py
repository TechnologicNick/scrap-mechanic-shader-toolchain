"""Recognize and emit line-ribbon vertex and pixel permutations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    asset,
    emit_validated_module,
    ensure_projection_include,
    ensure_recovered_cbuffer_include,
)


def apply_main_line_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "main_line"]
    if len(shaders) != 8 or sum(shader["stage"] == "vertex" for shader in shaders) != 2:
        return None
    ensure_projection_include(staging)
    ensure_recovered_cbuffer_include(
        staging, "main_line", "CB_LINE", "line_settings_abi.hlsl"
    )
    ensure_recovered_cbuffer_include(
        staging, "main_line", "CB_PERFRAME", "line_perframe_abi.hlsl"
    )
    bodies = {}
    executions = {}
    for shader in shaders:
        defines = set(shader["defines"])
        prefix = "".join(f"#define {definition} 1\n" for definition in shader["defines"])
        bodies[shader["selector"]] = prefix + asset(
            "main_line_vertex.hlsl" if shader["stage"] == "vertex"
            else "main_line_pixel.hlsl"
        )
        if shader["stage"] != "pixel":
            continue
        if "PS_PERM_DEPTH" in defines:
            slots = [0]
            samplers = []
            constants = []
            output = "depth"
            targets = 1
        elif "PS_FADE_BEHIND" in defines:
            slots = [0, 7]
            samplers = [
                {"slot": 1, "filter": "point"},
                {"slot": 3, "filter": "linear"},
            ]
            constants = [{"slot": 5, "profile": "projection"}]
            output = "color"
            targets = 1
        else:
            slots = [0] + ([7] if "PS_PERM_OVERLAY" in defines
                or "PS_PERM_FORWARD_BEHIND" in defines else [])
            samplers = [{"slot": 3, "filter": "linear"}]
            if 7 in slots:
                samplers.append({"slot": 1 if "PS_PERM_FORWARD_BEHIND" in defines else 6,
                                 "filter": "point" if "PS_PERM_FORWARD_BEHIND" in defines else "linear"})
            constants = [
                {"slot": 0, "profile": "random"},
                {"slot": 12, "profile": "random"},
            ]
            if "PS_PERM_OVERLAY" in defines:
                constants.append({"slot": 5, "profile": "projection"})
            output = "color"
            targets = 2 if "PS_PERM_FORWARD" in defines or "PS_PERM_FORWARD_BEHIND" in defines else 1
        executions[shader["selector"]] = {
            "kind": "fullscreen_line",
            "vertex_harness": "fullscreen_line",
            "texture_slots": slots,
            "texture_kinds": ["2d"] * len(slots),
            "samplers": samplers,
            "constant_buffers": constants,
            "output": output,
            "output_components": 1 if output == "depth" else 4,
            "output_targets": targets,
        }
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="main_line", bodies=bodies, executions=executions,
    )
