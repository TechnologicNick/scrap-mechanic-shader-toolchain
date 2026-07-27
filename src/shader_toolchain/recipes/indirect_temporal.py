"""Recognize and emit temporal validity and SSGI history shaders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    asset,
    emit_validated_module,
    ensure_hdr_include,
    ensure_projection_include,
)


def apply_indirect_temporal_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records
        if record["source_name"] == "indirect_temporal"
    ]
    if len(shaders) != 3 or any(shader["stage"] != "pixel" for shader in shaders):
        return None
    ensure_projection_include(staging)
    ensure_hdr_include(staging)
    bodies = {}
    executions = {}
    for shader in shaders:
        prefix = "".join(
            f"#define {name} {value if separator else '1'}\n"
            for definition in shader["defines"]
            for name, separator, value in [definition.partition("=")]
        )
        bodies[shader["selector"]] = prefix + asset("indirect_temporal.hlsl")
        ssgi = "PS_SSGI" in shader["defines"]
        texture_slots = [0, 1, 3, 4, 5] if ssgi else [1, 3, 4]
        executions[shader["selector"]] = {
            "kind": "fullscreen_uv",
            "vertex_harness": "fullscreen_uv",
            "texture_slots": texture_slots,
            "texture_kinds": ["2d"] * len(texture_slots),
            "texture_mips": [1, 3, 1, 3, 1] if ssgi else [3, 1, 3],
            "samplers": [
                {"slot": 1, "filter": "point"},
                {"slot": 6, "filter": "linear"},
            ],
            "constant_buffers": [
                {"slot": 5, "profile": "projection"},
            ] + ([{"slot": 9, "profile": "hdr"}] if ssgi else []),
            "output": "color",
            "output_components": 4,
            "output_targets": 3 if ssgi else 1,
        }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="indirect_temporal",
        bodies=bodies,
        executions=executions,
    )
