"""Recognize animated character, clothing, glass, water, and effect materials."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from ..hlsl import module_variants
from ..reflect import ShaderReflector
from .common import emit_validated_module, rename_register_state


SEMANTIC_PHASE_MAP = """
/*
Semantic phase map
------------------
Vertex paths
1. Decode rigid or skinned character vertices, apply pose/bone transforms and
   optional wave, water, laser, scrolling, displacement, or picking features.
2. Build the requested view/object tangent frames and forward UV, paint,
   occlusion, screen/fog, plane, and effect channels.

Pixel paths
3. Evaluate the selected diffuse/ASG/normal layers, detail UV set, alpha cutout,
   directional/gradient map, matcap, light-cap, and material profile.
4. Emit icon, picking, preview, visualization, forward, or blended G-buffer data.
5. Transparent glass/water/laser/hologram paths add refraction, transmission,
   clustered lighting, shadows/cookies and the selected reflection quality.

Lighting and animation blocks remain instruction-ordered to preserve packed
indices, comparison gathers, approximate normalization, and DXBC contraction.
*/
"""


REGISTER_NAMES_BY_MODULE = {
    "main_asset": {
        0: "assetPositionState", 1: "animationTransformState",
        2: "viewProjectionState", 3: "normalAndTangentState",
        4: "materialCoordinateState", 5: "effectAnimationState",
        6: "diffuseSampleState", 7: "asgAndNormalSampleState",
        8: "profileMaterialState", 9: "clusterMaskState",
        10: "lightIteratorState", 11: "lightGeometryState",
        12: "attenuationState", 13: "cookieProjectionState",
        14: "shadowProjectionState", 15: "shadowFilterState",
        16: "reflectionState", 17: "refractionState",
        18: "transmissionState", 19: "directLightAccumulator",
        20: "forwardAndBehindState", 21: "gbufferAndPreviewState",
        22: "effectOutputState", 23: "assetScratch",
    },
    "main_character": {
        0: "characterPositionState", 1: "skinWeightState",
        2: "boneTransformState", 3: "viewProjectionState",
        4: "normalAndTangentState", 5: "effectAnimationState",
        6: "materialSampleState", 7: "profileMaterialState",
        8: "clusterMaskState", 9: "lightIteratorState",
        10: "lightGeometryState", 11: "attenuationAndCookieState",
        12: "shadowState", 13: "reflectionAndRefractionState",
        14: "forwardLightAccumulator", 15: "transmissionState",
        16: "gbufferAndPreviewState", 17: "effectOutputState",
        18: "characterScratch",
    },
    "main_part": {
        0: "partPositionState", 1: "animationTransformState",
        2: "viewProjectionState", 3: "normalAndTangentState",
        4: "materialCoordinateState", 5: "effectAnimationState",
        6: "materialSampleState", 7: "profileMaterialState",
        8: "clusterMaskState", 9: "lightIteratorState",
        10: "lightGeometryState", 11: "attenuationAndCookieState",
        12: "shadowState", 13: "reflectionAndRefractionState",
        14: "directLightAccumulator", 15: "transmissionState",
        16: "forwardAndBehindState", 17: "gbufferAndPreviewState",
        18: "partScratch",
    },
}


def main_character_execution(
    shader: dict[str, Any], blob: bytes,
) -> dict[str, Any]:
    abi = ShaderReflector().abi(blob)
    resources = abi["resources"]
    textures = [resource for resource in resources if resource["type"] == 2]
    samplers = [resource for resource in resources if resource["type"] == 3]
    buffers = [resource for resource in resources if resource["type"] == 5]
    defines = set(shader["defines"])
    clustered_transparent = (
        bool({"PS_SHADER_QUALITY_MEDIUM", "PS_SHADER_QUALITY_HIGH"} & defines)
        and "PS_PERM_TRANSPARANT_SURFACE" in defines
    )
    profiles = {
        0: "random", 1: "random", 2: "random", 5: "projection",
        6: (
            "random" if "PS_PERM_VISUALIZATION" in defines
            else "main-light-cluster" if clustered_transparent
            else "cluster"
        ),
        8: "main-light-lights" if clustered_transparent else "index",
        11: "reflection" if clustered_transparent else "index",
        12: "index", 13: "random",
    }
    outputs = sorted(abi["outputs"], key=lambda output: output["index"])
    depth = "PS_PERM_DEPTH" in defines
    execution = {
        "kind": "fullscreen_character",
        "vertex_harness": "fullscreen_character",
        "width": 1,
        "height": 1,
        "texture_slots": [resource["bind_point"] for resource in textures],
        "texture_kinds": [
            "2darray" if resource["dimension"] == 5 else "2d"
            for resource in textures
        ],
        "smooth_texture_slots": [resource["bind_point"] for resource in textures],
        "structured_inputs": [
            {"slot": resource["bind_point"], "elements": 4096,
             "stride": 4,
             "profile": "main-light" if clustered_transparent else "zero"}
            for resource in buffers
        ],
        "samplers": [
            {"slot": resource["bind_point"], "filter": "linear",
             "comparison": resource["bind_point"] == 12}
            for resource in samplers
        ],
        "constant_buffers": [
            {"slot": buffer["bind_point"], "profile": profiles[buffer["bind_point"]]}
            for buffer in abi["constant_buffers"] if buffer["bind_point"] >= 0
        ],
        "output": "depth" if depth else "color",
        "output_components": 1 if depth else 4,
        "output_targets": 1 if depth else len(outputs),
    }
    if not depth:
        execution["output_target_components"] = [
            max(1, output["mask"].bit_count()) for output in outputs
        ]
    if shader["selector"] in {
        "SM_SHADER_609AAD28B1D04C13",
        "SM_SHADER_67016D9BB633DAB4",
        "SM_SHADER_6E4E38FB80F0509F",
        "SM_SHADER_D1AD75E4D0B9E1A9",
        "SM_SHADER_E9A62C20827F815D",
        "SM_SHADER_FC9544DC46769DDA",
    }:
        execution["absolute_tolerance"] = 1.2e-7
    elif shader["selector"] == "SM_SHADER_97E6B3E44EA4B69D":
        execution["absolute_tolerance"] = 5.5e-5
    return execution


def emit_character_variant_snippets(
    staging: Path,
    source_name: str,
    variants: dict[str, str],
) -> dict[str, str]:
    """Emit material permutations as independently editable shader files."""
    snippet_root = staging / "semantic" / "include" / source_name
    snippet_root.mkdir(parents=True, exist_ok=True)
    bodies: dict[str, str] = {}
    for selector, source in variants.items():
        filename = f"{selector}.hlsl"
        source = source.replace('#include "include/', '#include "../')
        (snippet_root / filename).write_text(
            SEMANTIC_PHASE_MAP + source,
            encoding="utf-8",
            newline="\n",
        )
        bodies[selector] = f'#include "include/{source_name}/{filename}"\n'
    return bodies


def apply_character_material_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
    *,
    source_name: str,
    shader_count: int,
    pixel_count: int,
    split_variants: bool = False,
    variant_lifter: Callable[[Path, str, list[str], str], str] | None = None,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records if record["source_name"] == source_name
    ]
    if (
        len(shaders) != shader_count
        or sum(s["stage"] == "pixel" for s in shaders) != pixel_count
    ):
        return None
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    reflector = ShaderReflector()
    output_masks = {
        shader["selector"]: {
            (output["semantic"], output["index"]): output["mask"]
            for output in reflector.abi(blobs[shader["bundle_index"]])["outputs"]
        }
        for shader in shaders if shader["stage"] == "vertex"
    }
    expanded = module_variants(
        (staging / "hlsl" / f"{source_name}.hlsl").read_text(encoding="utf-8"),
        definitions,
    )
    for selector, source in expanded.items():
        source = re.sub(
            r"cb_arrSpot\[([^\]]+)/4\]\.(_m[0-9_]+)",
            r"cb_arrSpot[\1].xClip.\2", source,
        )
        source = re.sub(
            r"cb_arrCascades\[([^\]]+)/4\]\.(_m[0-9_]+)",
            r"cb_arrCascades[\1].\2", source,
        )
        source = re.sub(
            r"(cbuffer\s+\w+)\s*:\s*register\(b[012]\)", r"\1", source
        )
        # Recover vector lanes that 3Dmigoto rendered as scalar broadcasts.
        source = re.sub(
            r"(o\d+\.xy)\s*=\s*cb_offset\.fSpecular;",
            r"\1 = float2(cb_offset.fSpecular, cb_offset.fGloss);", source,
        )
        source = re.sub(
            r"saturate\(cb_laser\.fInvFarDist \* (r\d+\.zw)\)",
            r"saturate(float2(cb_laser.fInvFarDist, "
            r"cb_laser.fInvNearDist) * \1)", source,
        )
        # Some vertex lifts address two separately declared output semantics
        # through their original packed oN register. Recreate each declaration
        # from the corresponding lanes before recompilation.
        packed_output_scalars = re.findall(
            r"float3\s+o(\d+)\s*:\s*\w+\d*,\s*\n\s*"
            r"out float\s+p\1\s*:\s*\w+\d*", source,
        )
        for register in packed_output_scalars:
            source = re.sub(
                rf"o{register}\.xyzw\s*=\s*(\w+)\.xyzw;",
                rf"o{register}.xyz = \1.xyz; p{register} = \1.w;", source,
            )
        packed_output_vectors = re.findall(
            r"float2\s+o(\d+)\s*:\s*\w+\d*,\s*\n\s*"
            r"out float2\s+p\1\s*:\s*\w+\d*", source,
        )
        for register in packed_output_vectors:
            source = re.sub(
                rf"o{register}\.xyzw\s*=\s*(\w+)\.xyzw;",
                rf"o{register}.xy = \1.xy; p{register}.xy = \1.zw;", source,
            )
        # 3Dmigoto names separately declared semantics sharing one input
        # register as vN/wN, but leaves several instructions addressed through
        # the packed register. Rebuild the upper-lane UV1 value explicitly.
        packed_uv_registers = re.findall(r"float2\s+w(\d+)\s*:\s*UV1", source)
        for register in packed_uv_registers:
            def unpack_uv_register(match: re.Match[str]) -> str:
                lanes = {
                    "x": f"v{register}.x", "y": f"v{register}.y",
                    "z": f"w{register}.x", "w": f"w{register}.y",
                }
                swizzle = match.group(1)
                if len(swizzle) == 1:
                    return lanes[swizzle]
                return f"float{len(swizzle)}(" + ", ".join(
                    lanes[lane] for lane in swizzle
                ) + ")"

            source = re.sub(
                rf"\bv{register}\.([xyzw]+)", unpack_uv_register, source
            )
            source = source.replace(f"v{register}.z", f"w{register}.x")
            source = source.replace(f"v{register}.w", f"w{register}.y")
            source = source.replace(
                f"w{register}.xyxy", f"float4(w{register}.xy, v{register}.xy)"
            )
            source = source.replace(f"w{register}.xyzw", f"w{register}.xyxy")
        packed_scalars = re.findall(
            r"float\s+w(\d+)\s*:\s*(OCCLUSION|LASER_OFFSET)", source
        )
        for register, semantic in packed_scalars:
            lane = "w" if semantic == "OCCLUSION" else "z"
            source = source.replace(f"v{register}.{lane}", f"w{register}")
            source = re.sub(rf"\bw{register}\.[xyzw]+", f"w{register}", source)
        # This pose variant's scalar dither and noise pair occupied separate
        # recovered output registers. Distinct interpolation classes preserve
        # those masks; vertex-stage modifiers do not affect interpolation at
        # runtime (the consuming pixel shader declares that behavior).
        if re.search(r"out float o\d+ : DITHER0", source) and re.search(
            r"out float2 o\d+ : NOISE_UV0", source
        ):
            source = re.sub(
                r"out float (o\d+) : DITHER0",
                r"out nointerpolation float \1 : DITHER0", source,
            )
            source = re.sub(
                r"out float2 (o\d+) : NOISE_UV0",
                r"out centroid float2 \1 : NOISE_UV0", source,
            )
        if output_masks.get(selector, {}).get(("CUTOFF", 0)) == 1:
            source = re.sub(
                r"out float ([op]\d+) : CUTOFF0",
                r"out noperspective float \1 : CUTOFF0", source,
            )
        elif output_masks.get(selector, {}).get(("CUTOFF", 0)) == 2:
            source = re.sub(
                r"out float ([op]\d+) : CUTOFF0",
                r"out nointerpolation float \1 : CUTOFF0", source,
            )
        names = REGISTER_NAMES_BY_MODULE.get(source_name)
        if names is not None:
            source = rename_register_state(
                source, names,
                note="Skinning, effects, and material lighting retain DXBC order.",
            )
        if variant_lifter is not None:
            source = variant_lifter(
                staging, selector, definitions[selector], source
            )
        expanded[selector] = source
    if split_variants:
        bodies = emit_character_variant_snippets(
            staging, source_name, expanded
        )
    else:
        bodies = {
            shader["selector"]: SEMANTIC_PHASE_MAP
            + expanded[shader["selector"]]
            for shader in shaders
        }
    executions = {
        shader["selector"]: main_character_execution(
            shader, blobs[shader["bundle_index"]]
        )
        for shader in shaders if shader["stage"] == "pixel"
    }
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name=source_name, bodies=bodies, executions=executions,
    )


def apply_main_character_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    return apply_character_material_recipe(
        staging, records, blobs, compiler,
        source_name="main_character", shader_count=177, pixel_count=138,
    )
