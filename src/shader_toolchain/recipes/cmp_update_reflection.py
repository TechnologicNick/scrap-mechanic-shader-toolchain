"""Recognize and emit GPU reflection-probe bounds updates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_recovered_cbuffer_include


def apply_cmp_update_reflection_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record
        for record in records
        if record["source_name"] == "cmp_update_reflection"
    ]
    if len(shaders) != 1 or shaders[0]["entry_point"] != "mainCS":
        return None
    ensure_recovered_cbuffer_include(
        staging,
        "cmp_update_reflection",
        "CB_REFLECTION_INFO",
        "reflection_info_abi.hlsl",
    )
    shader = shaders[0]
    execution = {
        "kind": "compute_reflection_records",
        "width": 128,
        "height": 1,
        "thread_group": [128, 1, 1],
        "texture_slots": [],
        "structured_inputs": [{"slot": 0, "elements": 256, "stride": 32}],
        "structured_output_elements": 128,
        "structured_output_stride": 160,
        "samplers": [],
        "constant_buffers": [{"slot": 0, "profile": "reflection"}],
        "output": "color",
        "output_components": 1,
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="cmp_update_reflection",
        bodies={shader["selector"]: asset("cmp_update_reflection_compute.hlsl")},
        executions={shader["selector"]: execution},
    )
