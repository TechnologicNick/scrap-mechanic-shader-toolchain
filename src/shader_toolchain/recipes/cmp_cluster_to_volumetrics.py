"""Recognize and emit the clustered-light volumetric mask compaction pass."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module


def apply_cmp_cluster_to_volumetrics_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records
        if record["source_name"] == "cmp_cluster_to_volumetrics"
    ]
    if len(shaders) != 1 or shaders[0]["entry_point"] != "mainCS":
        return None
    shader = shaders[0]
    execution = {
        "kind": "compute_structured_u32",
        "width": 64,
        "height": 1,
        "thread_group": [64, 1, 1],
        "texture_slots": [],
        "structured_inputs": [{"slot": 0, "elements": 4224}],
        "structured_output_elements": 1088,
        "samplers": [],
        "constant_buffers": [{"slot": 0, "profile": "cluster"}],
        "output": "color",
        "output_components": 1,
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="cmp_cluster_to_volumetrics",
        bodies={
            shader["selector"]: asset("cmp_cluster_to_volumetrics_compute.hlsl")
        },
        executions={shader["selector"]: execution},
    )
