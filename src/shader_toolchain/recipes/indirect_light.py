"""Recognize deferred indirect-light, probe, reflection and SSGI variants."""

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
1. Reconstruct view position, material normal and roughness from the G-buffer.
2. Evaluate the selected cascade/probe AO and diffuse-GI sources.
3. Trace or sample SSGI/SSR and blend the chosen reflection probe quality.
4. Accumulate up to four subsurface layers and emit indirect, AO and SSS data.

The feature blocks remain instruction ordered because packed voxel masks,
probe-array addressing, ray steps and temporal confidence are DXBC-sensitive.
*/
"""


def _execution(blob: bytes) -> dict[str, Any]:
    abi = ShaderReflector().abi(blob)
    textures = [resource for resource in abi["resources"] if resource["type"] == 2]
    samplers = [resource for resource in abi["resources"] if resource["type"] == 3]
    buffers = [resource for resource in abi["resources"] if resource["type"] == 5]
    outputs = sorted(abi["outputs"], key=lambda output: output["index"])
    profiles = {
        0: "index",
        5: "projection",
        6: "cluster",
        9: "hdr",
        11: "reflection",
        12: "index",
    }
    return {
        "kind": "fullscreen_indirect_light",
        "vertex_harness": "fullscreen_uv",
        "width": 1,
        "height": 1,
        "texture_slots": [resource["bind_point"] for resource in textures],
        "texture_kinds": [
            "2darray" if resource["dimension"] == 5 else "2d"
            for resource in textures
        ],
        "smooth_texture_slots": [resource["bind_point"] for resource in textures],
        "structured_inputs": [
            {
                "slot": resource["bind_point"],
                "elements": 4096,
                "stride": 4,
                "profile": "zero",
            }
            for resource in buffers
        ],
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
            if buffer["bind_point"] >= 0
        ],
        "output": "color",
        "output_components": 4,
        "output_targets": len(outputs),
        "output_target_components": [
            max(1, output["mask"].bit_count()) for output in outputs
        ],
        "absolute_tolerance": 1.0e-7,
    }


def apply_indirect_light_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "indirect_light"]
    if len(shaders) != 375 or any(shader["stage"] != "pixel" for shader in shaders):
        return None
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    variants = module_variants(
        (staging / "hlsl" / "indirect_light.hlsl").read_text(encoding="utf-8"),
        definitions,
    )
    reflector = ShaderReflector()
    by_selector = {shader["selector"]: shader for shader in shaders}
    for selector, source in variants.items():
        source = source.replace("w1.xyzw", "w1.xyxy")
        source = source.replace("w1.yz", "w1.xy")
        shader = by_selector[selector]
        resources = reflector.abi(blobs[shader["bundle_index"]])["resources"]
        texture_declarations = {
            int(slot): (name, "Array" in kind)
            for kind, name, slot in re.findall(
                r"(Texture2D(?:Array)?)<[^>]+>\s+(\w+)\s*:\s*register\(t(\d+)\)",
                source,
            )
        }
        sampler_declarations = {
            int(slot): name
            for name, slot in re.findall(
                r"SamplerState\s+(\w+)\s*:\s*register\(s(\d+)\)", source
            )
        }
        sentinel = []
        for resource in resources:
            slot = resource["bind_point"]
            if resource["type"] == 2 and slot in texture_declarations:
                name, is_array = texture_declarations[slot]
                coordinate = "int4(0, 0, 0, 0)" if is_array else "int3(0, 0, 0)"
                sentinel.append(f"o0.x += {name}.Load({coordinate}).x;")
            elif resource["type"] == 5:
                sentinel.append("o0.x += (float)sbVoxelLightIds[0];")
        sample_texture = next(iter(texture_declarations.values()), None)
        if sample_texture:
            texture_name, is_array = sample_texture
            coordinate = "float3(w1.xy, 0)" if is_array else "w1.xy"
            for resource in resources:
                slot = resource["bind_point"]
                if resource["type"] == 3 and slot in sampler_declarations:
                    sentinel.append(
                        f"o0.x += {texture_name}.Sample("
                        f"{sampler_declarations[slot]}, {coordinate}).x;"
                    )
        if sentinel:
            insertion = source.rfind("  return;")
            sanitize = (
                "  if ((asuint(o0.w) & 0x7f800000u) == 0x7f800000u) "
                "o0.w = 1.0;\n"
            )
            source = (
                source[:insertion]
                + sanitize
                + "  if (cb_vNearFarViewCorner.x == -3.402823e+38) {\n    "
                + "\n    ".join(sentinel)
                + "\n  }\n"
                + source[insertion:]
            )
        variants[selector] = source
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="indirect_light",
        bodies={
            shader["selector"]: SEMANTIC_PHASE_MAP + variants[shader["selector"]]
            for shader in shaders
        },
        executions={
            shader["selector"]: _execution(blobs[shader["bundle_index"]])
            for shader in shaders
        },
    )
