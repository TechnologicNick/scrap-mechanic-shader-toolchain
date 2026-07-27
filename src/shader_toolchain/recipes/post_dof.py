"""Recognize and emit the factored horizontal/vertical depth-of-field filter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_projection_include


def apply_post_dof_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "post_dof"]
    expected = {"mainHorizontalPS", "mainVerticalPS"}
    if len(shaders) != 2 or {shader["entry_point"] for shader in shaders} != expected:
        return None
    ensure_projection_include(staging)
    shared_body = asset("post_dof_pixel.hlsl")
    execution = {
        "kind": "fullscreen_texture2d",
        "vertex_harness": "fullscreen_uv",
        "texture_slots": [0, 1],
        "samplers": [{"slot": 1, "filter": "point"}],
        "constant_buffers": [{"slot": 5, "profile": "projection"}],
        "output": "color",
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="post_dof",
        bodies={shader["selector"]: shared_body for shader in shaders},
        executions={shader["selector"]: execution for shader in shaders},
    )
