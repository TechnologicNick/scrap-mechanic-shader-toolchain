"""Recognize and emit the compute ocean-spectrum initialization pass."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module


def apply_cmp_water_init_spectrum_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records
        if record["source_name"] == "cmp_water_init_spectrum"
    ]
    if len(shaders) != 1 or shaders[0]["entry_point"] != "mainCS":
        return None
    shader = shaders[0]
    execution = {
        "kind": "compute_texture2d",
        "width": 256,
        "height": 256,
        "thread_group": [32, 32, 1],
        "texture_slots": [0],
        "samplers": [],
        "constant_buffers": [{"slot": 1, "profile": "random"}],
        "output": "color",
        "output_components": 2,
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="cmp_water_init_spectrum",
        bodies={shader["selector"]: asset("cmp_water_init_spectrum_compute.hlsl")},
        executions={shader["selector"]: execution},
    )
