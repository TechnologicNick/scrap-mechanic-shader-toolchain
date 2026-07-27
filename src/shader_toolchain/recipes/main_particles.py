"""Recognize sprite and axial particle rendering permutations."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..hlsl import module_variants
from ..reflect import ShaderReflector
from .common import emit_validated_module


SEMANTIC_PHASE_MAP = """
/*
Semantic phase map
------------------
Vertex paths
1. Decode the selected particle record and construct either a camera-facing
   sprite or self-oriented axial quad, including preview placement.
2. Forward atlas UV, tint, linear depth, technique index and optional tangent,
   cluster-light, shadow and edge channels.

Pixel paths
3. Sample the particle atlas, apply cutoff, glow mask, additive blend and soft
   depth intersection, then evaluate lit or unlit normal response.
4. Emit the forward color plus the secondary additive/glow accumulation target.

The executable blocks remain instruction-ordered because the 128 feature
combinations share packed particle records and depth-sensitive blend math.
*/
"""


def _execution(shader: dict[str, Any], blob: bytes) -> dict[str, Any]:
    abi = ShaderReflector().abi(blob)
    resources = abi["resources"]
    textures = [resource for resource in resources if resource["type"] == 2]
    samplers = [resource for resource in resources if resource["type"] == 3]
    outputs = sorted(abi["outputs"], key=lambda output: output["index"])
    profiles = {0: "index", 5: "projection", 12: "index"}
    return {
        "kind": "fullscreen_particle",
        "vertex_harness": "fullscreen_particle",
        "texture_slots": [resource["bind_point"] for resource in textures],
        "texture_kinds": [
            "2darray" if resource["dimension"] == 5 else "2d"
            for resource in textures
        ],
        "smooth_texture_slots": [resource["bind_point"] for resource in textures],
        "samplers": [
            {"slot": resource["bind_point"], "filter": "linear"}
            for resource in samplers
        ],
        "constant_buffers": [
            {"slot": buffer["bind_point"], "profile": profiles[buffer["bind_point"]]}
            for buffer in abi["constant_buffers"] if buffer["bind_point"] >= 0
        ],
        "output": "color",
        "output_components": 4,
        "output_targets": len(outputs),
        "output_target_components": [
            max(1, output["mask"].bit_count()) for output in outputs
        ],
    }


def apply_main_particles_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records if record["source_name"] == "main_particles"
    ]
    if len(shaders) != 258 or sum(s["stage"] == "pixel" for s in shaders) != 129:
        return None
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    expanded = module_variants(
        (staging / "hlsl" / "main_particles.hlsl").read_text(encoding="utf-8"),
        definitions,
    )
    for selector, source in expanded.items():
        # The decompiler names independently packed lanes as scalar/vector
        # outputs.  Recreate their original register lanes by padding each
        # semantic and writing only the reflected components.
        has_pixel_cutoff = (
            "nointerpolation float w3 : TEXCOORD4" in source
        )
        has_pixel_tangent = (
            "nointerpolation float2 w3 : TANGENT0" in source
        )
        if has_pixel_cutoff:
            source = source.replace(
                "nointerpolation float w3 : TEXCOORD4",
                "nointerpolation float cutoff3 : TEXCOORD4",
            ).replace("-w3.x", "-cutoff3")
        if has_pixel_tangent:
            source = source.replace(
                "nointerpolation float2 w3 : TANGENT0",
                "nointerpolation float2 tangent3 : TANGENT0",
            )
            source = source.replace("w3.yz", "tangent3.xy")
            source = source.replace("w3.xy", "tangent3.xy")
            source = source.replace("w3.", "tangent3.")
        has_cutoff_lane = "out float p3 : TEXCOORD4" in source
        has_tangent_lane = "out float2 p3 : TANGENT0" in source
        if has_tangent_lane:
            source = source.replace(
                "out float2 p3 : TANGENT0",
                "out float4 p3 : TANGENT0" if has_cutoff_lane
                else "out float4 p3 : TANGENT0",
            )
        if has_cutoff_lane:
            source = source.replace(
                "out float p3 : TEXCOORD4", "out float2 q3 : TEXCOORD4"
            )
            source = source.replace("p3.x = v4.x;", "q3.y = v4.x;")
            if has_tangent_lane:
                source = source.replace("p3.xy =", "p3.zw =")
                source = source.replace("p3.x =", "p3.z =")
                source = source.replace("p3.y =", "p3.w =")
        elif has_tangent_lane:
            source = source.replace("p3.xy =", "p3.yz =")
            source = source.replace("p3.x =", "p3.__packed_x =")
            source = source.replace("p3.y =", "p3.z =")
            source = source.replace("p3.__packed_x =", "p3.y =")
        source = re.sub(r"\(int(?:5|21|42)\)", "(int)", source)
        source = re.sub(r"\(uint(?:21|42)\)", "(uint)", source)
        source = re.sub(r"\bo3\.x\s*=", "o3 =", source)
        source = re.sub(
            r"\bo3\.xyz\s*=\s*(r\d+)\.zxy\s*;",
            r"o3 = (uint)\1.z; p3.yz = \1.xy;",
            source,
        )
        source = re.sub(
            r"\bo3\.xyzw\s*=\s*(r\d+)\.zwxy\s*;",
            r"o3 = (uint)\1.z; q3.y = \1.w; p3.zw = \1.xy;",
            source,
        )
        source = re.sub(
            r"cb_arrSpot\[([^\]]+)/4\]\.(_m[0-9_]+)",
            r"cb_arrSpot[\1].xClip.\2", source,
        )
        expanded[selector] = source
    bodies = {
        shader["selector"]: SEMANTIC_PHASE_MAP + expanded[shader["selector"]]
        for shader in shaders
    }
    executions = {
        shader["selector"]: _execution(shader, blobs[shader["bundle_index"]])
        for shader in shaders if shader["stage"] == "pixel"
    }
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="main_particles", bodies=bodies, executions=executions,
    )
