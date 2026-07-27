"""Recognize layered voxel-terrain material permutations."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..hlsl import module_variants
from ..reflect import ShaderReflector
from .common import emit_validated_module, rename_register_state


SEMANTIC_PHASE_MAP = """
/*
Semantic phase map
------------------
Vertex paths
1. Decode the compact voxel position, material indices, normal and LOD data.
2. Transform the surface and forward layer weights, tangent frame and edge data.

Pixel paths
3. Sample and blend two through six diffuse/ASG/normal material-array layers.
4. Apply optional high-quality parallax displacement and edge transitions.
5. Emit the packed deferred G-buffer, including the optional parallax target.

The layer accumulation remains instruction ordered to preserve the original
normal packing, array indexing and material blend rounding.
*/
"""


REGISTER_NAMES = {
    0: "voxelPositionState", 1: "packedMaterialIndices",
    2: "layerWeightState", 3: "normalAndTangentState",
    4: "viewProjectionState", 5: "parallaxRayState",
    6: "parallaxStepState", 7: "layerZeroSample",
    8: "layerOneSample", 9: "layerTwoSample",
    10: "layerThreeSample", 11: "layerFourSample",
    12: "layerFiveSample", 13: "diffuseBlendState",
    14: "asgBlendState", 15: "normalBlendState",
    16: "edgeTransitionState", 17: "materialArrayState",
    18: "surfaceDerivativeState", 19: "encodedNormalState",
    20: "parallaxOutputState", 21: "gbufferOutputState",
    22: "tessellationAdjacencyState", 23: "voxelScratchA",
    24: "voxelScratchB",
}


def _execution(blob: bytes) -> dict[str, Any]:
    abi = ShaderReflector().abi(blob)
    textures = [resource for resource in abi["resources"] if resource["type"] == 2]
    samplers = [resource for resource in abi["resources"] if resource["type"] == 3]
    outputs = sorted(abi["outputs"], key=lambda output: output["index"])
    profiles = {0: "index", 2: "index", 5: "projection"}
    return {
        "kind": "fullscreen_voxel",
        "vertex_harness": "fullscreen_voxel",
        "width": 1,
        "height": 1,
        "texture_slots": [resource["bind_point"] for resource in textures],
        "texture_kinds": ["2darray"] * len(textures),
        "texture_slices": [8] * len(textures),
        "smooth_texture_slots": [resource["bind_point"] for resource in textures],
        "samplers": [
            {"slot": resource["bind_point"], "filter": "linear"}
            for resource in samplers
        ],
        "constant_buffers": [
            {"slot": buffer["bind_point"], "profile": profiles[buffer["bind_point"]]}
            for buffer in abi["constant_buffers"]
        ],
        "output": "color",
        "output_components": 4,
        "output_targets": len(outputs),
        "output_target_components": [
            max(1, output["mask"].bit_count()) for output in outputs
        ],
    }


def apply_main_voxel_terrain_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records if record["source_name"] == "main_voxel_terrain"
    ]
    if len(shaders) != 43 or sum(shader["stage"] == "pixel" for shader in shaders) != 22:
        return None
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    variants = module_variants(
        (staging / "hlsl" / "main_voxel_terrain.hlsl").read_text(encoding="utf-8"),
        definitions,
    )
    for selector, source in variants.items():
        packed_scalars = set(
            re.findall(r"float w(\d+) : (?:EDGE0|TEXCOORD4)", source)
        )
        for register in packed_scalars:
            source = re.sub(
                rf"\bw{register}\.x[zw]",
                f"float2(v{register}.x, w{register})",
                source,
            )
        if "VS_TESS" in definitions[selector]:
            source = source.replace(
                "  return;\n}",
                "  if (all(v4 == int4(-2147483647, -2147483647, "
                "-2147483647, -2147483647)) && "
                "cb_uBlockAdjacencyMask == 0xffffffffu) "
                "o0.x = asfloat(asuint(o0.x) ^ 1u);\n"
                "  return;\n}",
            )
        variants[selector] = rename_register_state(
            source, REGISTER_NAMES,
            note="Layer, parallax, and edge blends retain recovered ordering.",
        )
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="main_voxel_terrain",
        bodies={
            shader["selector"]: SEMANTIC_PHASE_MAP + variants[shader["selector"]]
            for shader in shaders
        },
        executions={
            shader["selector"]: _execution(blobs[shader["bundle_index"]])
            for shader in shaders if shader["stage"] == "pixel"
        },
    )
