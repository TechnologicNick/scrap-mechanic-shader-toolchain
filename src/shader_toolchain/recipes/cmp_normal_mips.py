"""Recognize and emit cooperative octahedral normal mip generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module


def apply_cmp_normal_mips_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records if record["source_name"] == "cmp_normal_mips"
    ]
    if len(shaders) != 1 or shaders[0]["entry_point"] != "mainCS":
        return None
    shader = shaders[0]
    execution = {
        "kind": "compute_normal_mips",
        "width": 64,
        "height": 64,
        "dispatch_width": 32,
        "dispatch_height": 32,
        "thread_group": [32, 32, 1],
        "texture_slots": [0],
        "samplers": [],
        "constant_buffers": [],
        "output": "color",
        "output_components": 2,
        "output_targets": 4,
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="cmp_normal_mips",
        bodies={shader["selector"]: asset("cmp_normal_mips_compute.hlsl")},
        executions={shader["selector"]: execution},
    )
