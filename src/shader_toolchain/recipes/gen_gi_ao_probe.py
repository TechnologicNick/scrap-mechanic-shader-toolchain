"""Recognize and emit cosine-weighted GI/AO cube-probe integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_recovered_cbuffer_include


def apply_gen_gi_ao_probe_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records if record["source_name"] == "gen_gi_ao_probe"
    ]
    if len(shaders) != 1 or shaders[0]["entry_point"] != "mainPS":
        return None
    ensure_recovered_cbuffer_include(
        staging, "gen_gi_ao_probe", "CB_PERFRAME", "perframe_abi.hlsl"
    )
    shader = shaders[0]
    execution = {
        "kind": "fullscreen_gi_probe",
        "vertex_harness": "fullscreen_uv",
        "width": 8,
        "height": 8,
        "texture_slots": [0],
        "texture_kinds": ["cube"],
        "samplers": [{"slot": 1, "filter": "point"}],
        "constant_buffers": [
            {"slot": 0, "profile": "random"},
            {"slot": 12, "profile": "random"},
        ],
        "output": "color",
        "output_components": 4,
        "output_targets": 2,
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="gen_gi_ao_probe",
        bodies={shader["selector"]: asset("gen_gi_ao_probe_pixel.hlsl")},
        executions={shader["selector"]: execution},
    )
