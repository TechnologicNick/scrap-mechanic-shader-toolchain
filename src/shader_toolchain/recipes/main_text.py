"""Recognize and emit font G-buffer and overlay shaders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_projection_include


def apply_main_text_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "main_text"]
    if len(shaders) != 7 or sum(shader["stage"] == "pixel" for shader in shaders) != 3:
        return None
    ensure_projection_include(staging)
    overlay_include = staging / "semantic" / "main_text_overlay_abi.hlsl"
    overlay_include.write_text(
        asset("main_text_overlay_abi.hlsl"), encoding="utf-8", newline="\n"
    )
    bodies = {}
    executions = {}
    for shader in shaders:
        defines = set(shader["defines"])
        define_prefix = "".join(
            f"#define {definition} 1\n" for definition in shader["defines"]
        )
        bodies[shader["selector"]] = define_prefix + asset(
            "main_text_pixel.hlsl"
            if shader["stage"] == "pixel"
            else "main_text_vertex.hlsl"
        )
        if shader["stage"] != "pixel":
            continue
        if "PS_ALPHA_CUTOFF" in defines:
            execution = {
                "kind": "fullscreen_text_gbuffer",
                "vertex_harness": "fullscreen_text",
                "texture_slots": [0],
                "samplers": [{"slot": 3, "filter": "linear"}],
                "constant_buffers": [{"slot": 5, "profile": "projection"}],
                "output": "color",
                "output_components": 4,
                "output_targets": 3,
            }
        else:
            execution = {
                "kind": "fullscreen_text_overlay",
                "vertex_harness": "fullscreen_text",
                "texture_slots": [0, 7, 10],
                "samplers": [
                    {"slot": 3, "filter": "linear"},
                    {"slot": 6, "filter": "linear"},
                ],
                "constant_buffers": [
                    {"slot": 0, "profile": "random"},
                    {"slot": 5, "profile": "projection"},
                ],
                "output": "color",
                "output_components": 4,
            }
        executions[shader["selector"]] = execution
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="main_text",
        bodies=bodies,
        executions=executions,
    )
