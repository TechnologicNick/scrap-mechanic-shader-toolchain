"""Recognize and emit the six depth-to-world-bounds reduction passes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_projection_include


def apply_cmp_depth_bounds_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records
        if record["source_name"] == "cmp_depth_bounds"
    ]
    if len(shaders) != 6 or any(shader["stage"] != "compute" for shader in shaders):
        return None
    ensure_projection_include(staging)
    bodies = {}
    executions = {}
    for shader in shaders:
        prefix = "".join(
            f"#define {name} {value if separator else '1'}\n"
            for definition in shader["defines"]
            for name, separator, value in [definition.partition("=")]
        )
        bodies[shader["selector"]] = prefix + asset("cmp_depth_bounds.hlsl")
        final_pass = "CS_Y_NEG_5" in shader["defines"]
        outputs = [{"slot": 0, "elements": 1, "stride": 32}]
        if final_pass:
            outputs.append({"slot": 1, "elements": 1, "stride": 32})
        executions[shader["selector"]] = {
            "kind": "compute_structured",
            "width": 128,
            "height": 128,
            "dispatch_width": 32,
            "dispatch_height": 32,
            "texture_slots": [0],
            "texture_kinds": ["2d"],
            "constant_buffers": [
                {"slot": 0, "profile": "index"},
                {"slot": 5, "profile": "projection"},
            ],
            "structured_outputs": outputs,
            "output": "color",
            "output_components": 1,
            "output_targets": 1,
            "thread_group": [32, 32, 1],
        }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="cmp_depth_bounds",
        bodies=bodies,
        executions=executions,
    )
