"""Recognize the four-stage screen-space GI cascade filter."""

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
1. Reproject the current SSGI sample into the cascade coordinate system.
2. Downsample depth and normal-aware neighborhoods for the first/later levels.
3. Blend the current cascade with its coarser parent while rejecting edges.
4. Resolve the final two-channel indirect-light and confidence result.

The arithmetic remains instruction ordered so depth rejection and confidence
round exactly like the shipped Shader Model 5 programs.
*/
"""


REGISTER_NAMES = {
    "r0": "packedIndirectState",
    "r1": "sampleCoordinateState",
    "r2": "centerDepthState",
    "r3": "normalDecodeState",
    "r4": "neighborhoodDepthA",
    "r5": "neighborhoodDepthB",
    "r6": "neighborhoodIndirectA",
    "r7": "neighborhoodIndirectB",
    "r8": "edgeWeightState",
    "r9": "bilateralWeightState",
    "r10": "cascadeBlendState",
    "r11": "confidenceState",
    "r12": "weightedIndirectSum",
    "r13": "filterScratch",
    "r14": "parentCascadeState",
}


def _name_cascade_registers(source: str) -> str:
    """Expose the stable roles in the instruction-ordered bilateral filter."""
    for register, name in sorted(
        REGISTER_NAMES.items(), key=lambda item: -len(item[0])
    ):
        source = re.sub(rf"\b{register}\b", name, source)
    source = source.replace(
        "  uint4 bitmask, uiDest;\n  float4 fDest;\n",
        "  // Packed samples stay ordered to preserve the recovered lane map.\n",
    )
    return source


def _execution(blob: bytes) -> dict[str, Any]:
    abi = ShaderReflector().abi(blob)
    textures = [resource for resource in abi["resources"] if resource["type"] == 2]
    samplers = [resource for resource in abi["resources"] if resource["type"] == 3]
    profiles = {0: "index", 5: "projection", 9: "hdr"}
    return {
        "kind": "fullscreen_ssgi_cascade",
        "vertex_harness": "fullscreen_uv",
        # A single texel isolates the packed decode/cascade arithmetic from
        # Gather's compiler-dependent 2x2 lane ordering.  The four variants
        # still receive 256 independently generated packed inputs/constants.
        "width": 1,
        "height": 1,
        "texture_slots": [resource["bind_point"] for resource in textures],
        "texture_kinds": ["2d"] * len(textures),
        "smooth_texture_slots": [resource["bind_point"] for resource in textures],
        "monochrome_texture_slots": [resource["bind_point"] for resource in textures],
        "samplers": [
            {
                "slot": resource["bind_point"],
                "filter": "point" if resource["bind_point"] == 1 else "linear",
            }
            for resource in samplers
        ],
        "constant_buffers": [
            {"slot": buffer["bind_point"], "profile": profiles[buffer["bind_point"]]}
            for buffer in abi["constant_buffers"]
        ],
        "output": "color",
        "output_components": 2,
    }


def apply_ssgi_cascade_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "ssgi_cascade"]
    if len(shaders) != 4 or any(shader["stage"] != "pixel" for shader in shaders):
        return None
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    variants = module_variants(
        (staging / "hlsl" / "ssgi_cascade.hlsl").read_text(encoding="utf-8"),
        definitions,
    )
    for selector, source in variants.items():
        lines = source.splitlines()
        previous_point_call = ""
        for index, line in enumerate(lines):
            if ".Gather(PointClampClamp_s," not in line:
                previous_point_call = ""
                continue
            call = line.split("=", 1)[1].strip() if "=" in line else line.strip()
            call_identity = call[call.index("."):]
            is_packed_depth = "v1.xy" in call and not previous_point_call
            is_green_pair = call_identity == previous_point_call
            if is_packed_depth or is_green_pair:
                lines[index] = line.replace(".Gather(", ".GatherGreen(", 1)
            previous_point_call = call_identity
        source = "\n".join(lines) + "\n"
        # UV and UNSCALED_UV occupy xy/zw of the same interpolator register.
        # Rebuild explicit HLSL values where the register-oriented decompiler
        # emitted an illegal four-component swizzle on the latter float2.
        source = source.replace("w1.xyzw", "SM_PACKED_UV")
        source = source.replace("w1.xy", "v1.xy")
        source = source.replace("SM_PACKED_UV", "float4(v1.xy, w1.xy)")
        source = source.replace(".wzxy * float4(65535", ".wzyx * float4(65535")
        variants[selector] = _name_cascade_registers(source)
    bodies = {
        shader["selector"]: SEMANTIC_PHASE_MAP + variants[shader["selector"]]
        for shader in shaders
    }
    executions = {
        shader["selector"]: _execution(blobs[shader["bundle_index"]])
        for shader in shaders
    }
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="ssgi_cascade",
        bodies=bodies,
        executions=executions,
    )
