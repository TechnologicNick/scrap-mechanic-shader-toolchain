"""Recognize and emit the integer-load HDR normalization shader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    asset,
    emit_validated_module,
    ensure_hdr_include,
    ensure_projection_include,
)


def apply_copy_auto_hdr_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "copy_auto_hdr"]
    if len(shaders) != 1 or shaders[0]["entry_point"] != "mainPS":
        return None
    ensure_projection_include(staging)
    ensure_hdr_include(staging)
    shader = shaders[0]
    execution = {
        "kind": "fullscreen_texture2d",
        "vertex_harness": "fullscreen_uv",
        "texture_slots": [0],
        "samplers": [],
        "constant_buffers": [
            {"slot": 5, "profile": "projection"},
            {"slot": 9, "profile": "hdr"},
        ],
        "output": "color",
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="copy_auto_hdr",
        bodies={shader["selector"]: asset("copy_auto_hdr_pixel.hlsl")},
        executions={shader["selector"]: execution},
    )
