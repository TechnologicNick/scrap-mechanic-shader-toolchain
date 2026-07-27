"""Recognize and emit readable channel-copy shader permutations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import emit_validated_module, ensure_projection_include


def _body(defines: list[str]) -> str:
    selected = next(
        channel
        for channel in ("PS_R", "PS_G", "PS_A", "PS_RG", "PS_RGB", "PS_RGBA")
        if channel in defines
    )
    to_backbuffer = "PS_TO_BACKBUFFER" in defines
    resource_type = {
        "PS_R": "float",
        "PS_G": "float4",
        "PS_A": "float4",
        "PS_RG": "float2",
        "PS_RGB": "float4",
        "PS_RGBA": "float4",
    }[selected]
    sampled_type = resource_type
    result = {
        "PS_R": "float4(sampled.xxx, 1.0)",
        "PS_G": "float4(sampled.yyy, 1.0)",
        "PS_A": "float4(sampled.www, 1.0)",
        "PS_RG": "float4(sampled.xy, 1.0, 1.0)",
        "PS_RGB": "float4(sampled.xyz, 1.0)",
        "PS_RGBA": "sampled",
    }[selected]
    include = '#include "include/post_fxaa_abi.hlsl"\n\n' if to_backbuffer else ""
    scale = "    sampleUv *= cb_vPrevRenderScale;\n" if to_backbuffer else ""
    return f"""{include}SamplerState PointClampClamp : register(s1);
Texture2D<{resource_type}> inputColor : register(t0);

float4 mainPS(float4 position : SV_Position0, float2 uv : UV0) : SV_Target0
{{
    float2 sampleUv = uv;
{scale}    {sampled_type} sampled = inputColor.SampleLevel(
        PointClampClamp, sampleUv, 0.0
    );
    return {result};
}}
"""


def apply_copy_rgba_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "copy_rgba"]
    if len(shaders) != 8 or {shader["entry_point"] for shader in shaders} != {"mainPS"}:
        return None
    ensure_projection_include(staging)
    execution = {
        "kind": "fullscreen_texture2d",
        "vertex_harness": "fullscreen_uv",
        "texture_slot": 0,
        "sampler_slot": 1,
        "constant_buffer_slot": 5,
        "filter": "point",
        "output": "color",
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="copy_rgba",
        bodies={shader["selector"]: _body(shader["defines"]) for shader in shaders},
        executions={shader["selector"]: execution for shader in shaders},
    )
