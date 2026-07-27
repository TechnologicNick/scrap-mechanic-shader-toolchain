"""Recognize and emit the depth-aware SSGI denoiser variants."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    asset,
    emit_validated_module,
    ensure_projection_include,
    ensure_recovered_cbuffer_include,
)


def apply_ssgi_denoise_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "ssgi_denoise"]
    if len(shaders) != 5 or any(shader["stage"] != "pixel" for shader in shaders):
        return None
    ensure_projection_include(staging)
    ensure_recovered_cbuffer_include(
        staging, "ssgi_denoise", "CB_AO_SETTINGS", "ao_settings_abi.hlsl"
    )
    bodies = {}
    executions = {}
    for shader in shaders:
        prefix_lines = []
        for definition in shader["defines"]:
            name, separator, value = definition.partition("=")
            prefix_lines.append(
                f"#define {name} {value if separator else '1'}\n"
            )
        prefix = "".join(prefix_lines)
        bodies[shader["selector"]] = prefix + asset("ssgi_denoise.hlsl")
        sss_count = next(
            (
                int(definition.split("=", 1)[1])
                for definition in shader["defines"]
                if definition.startswith("PS_SSS_COUNT=")
            ),
            0,
        )
        texture_slots = [0, 1, 3] + ([4] if sss_count else [])
        executions[shader["selector"]] = {
            "kind": "fullscreen_uv",
            "vertex_harness": "fullscreen_uv",
            "texture_slots": texture_slots,
            "texture_kinds": ["2d"] * len(texture_slots),
            "samplers": [
                {"slot": 1, "filter": "point"},
                {"slot": 6, "filter": "linear"},
            ],
            "constant_buffers": [
                {"slot": 0, "profile": "ao"},
                {"slot": 5, "profile": "projection"},
            ],
            "output": "color",
            "output_components": 4,
            "output_targets": 1 if sss_count == 0 else 2,
        }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="ssgi_denoise",
        bodies=bodies,
        executions=executions,
    )
