"""Recognize the four-stage screen-space GI cascade filter."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..hlsl import module_variants
from ..reflect import ShaderReflector
from .common import asset, emit_validated_module


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


_PACKED_VECTOR = re.compile(
    r"^(?P<indent>\s*)(?P<register>[A-Za-z_]\w*)\.xyzw = "
    r"\(uint4\)(?P=register)\.xyzw;$"
)
_DECODED_COLOR = re.compile(
    r"^\s*(?P<destination>[A-Za-z_]\w*\.[xyzw]{3}) = "
    r"max\(float3\(0,0,0\), (?P=destination)\);$"
)


def _lift_packed_indirect_decodes(source: str) -> str:
    """Collapse the repeated 6:5:5 indirect-light decoder into one helper."""
    lines = source.splitlines()
    lifted: list[str] = []
    index = 0
    while index < len(lines):
        packed_match = _PACKED_VECTOR.match(lines[index])
        if packed_match is None:
            lifted.append(lines[index])
            index += 1
            continue

        destinations: list[str] = []
        end = index + 1
        while end < min(len(lines), index + 120):
            color_match = _DECODED_COLOR.match(lines[end])
            if color_match is not None:
                destinations.append(color_match.group("destination"))
                if len(destinations) == 4:
                    break
            end += 1
        if len(destinations) != 4:
            lifted.append(lines[index])
            index += 1
            continue

        window = "\n".join(lines[index + 1 : end + 1])
        if window.count("if (6 == 0)") != 4 or window.count("if (5 == 0)") != 4:
            lifted.append(lines[index])
            index += 1
            continue

        register = packed_match.group("register")
        indent = packed_match.group("indent")
        lifted.append(lines[index])
        lifted.append(f"{indent}// Decode the gathered 6:5:5 indirect-light words.")
        for lane, destination in zip("xyzw", destinations, strict=True):
            lifted.append(
                f"{indent}{destination} = "
                f"DecodeCascadeIndirect((uint){register}.{lane});"
            )
        index = end + 1
    return "\n".join(lifted) + "\n"


_PACKED_INDIRECT_ENCODER_START = re.compile(
    r"^(?P<indent>\s*)(?P<scratch>[A-Za-z_]\w*)\.x = "
    r"(?P<color>[A-Za-z_]\w*)\.y \+ -(?P=color)\.w;$"
)


def _lift_packed_indirect_encodes(source: str) -> str:
    """Name the inverse YCoCg 6:5:5 packing sequence."""
    lines = source.splitlines()
    lifted: list[str] = []
    index = 0
    while index < len(lines):
        start = _PACKED_INDIRECT_ENCODER_START.match(lines[index])
        if start is None:
            lifted.append(lines[index])
            index += 1
            continue
        color = start.group("color")
        end = index + 1
        output = f"o0.x = 1.52590219e-05 * {color}.y;"
        while end < min(len(lines), index + 32) and lines[end].strip() != output:
            end += 1
        window = "\n".join(lines[index : min(end + 1, len(lines))])
        markers = (
            f"{color}.z = saturate(0.015625 * {color}.y);",
            f"{color}.y = (uint){color}.y << 5;",
            f"{color}.y = mad((int){color}.z, 1024, (int){color}.y);",
        )
        if end >= len(lines) or any(marker not in window for marker in markers):
            lifted.append(lines[index])
            index += 1
            continue
        indent = start.group("indent")
        lifted.append(f"{indent}// Repack filtered indirect light as 6:5:5 YCoCg.")
        lifted.append(f"{indent}o0.x = EncodeCascadeIndirect({color}.yzw);")
        index = end + 1
    return "\n".join(lifted) + "\n"


_BILATERAL_START = re.compile(
    r"^(?P<indent>\s*)(?P<distance>[A-Za-z_]\w*)\.xyzw = "
    r"(?P<delta_y>[A-Za-z_]\w*)\.xyzw \* (?P=delta_y)\.xyzw;$"
)
_BILATERAL_DELTA = re.compile(
    r"^\s*(?P<distance>[A-Za-z_]\w*)\.xyzw = "
    r"(?P<delta>[A-Za-z_]\w*)\.xyzw \* (?P=delta)\.xyzw "
    r"\+ (?P=distance)\.xyzw;$"
)
_BILATERAL_ACCEPT = re.compile(
    r"^\s*(?P<accepted>[A-Za-z_]\w*)\.xyzw = cmp\("
    r"(?P<threshold>[A-Za-z_]\w*)\.(?P<threshold_lane>[xyzw])yyy "
    r">= (?P<distance>[A-Za-z_]\w*)\.xyzw\);$"
)
_NORMALIZED_DELTA = re.compile(
    r"^\s*(?P<delta>[A-Za-z_]\w*)\.xyzw = "
    r"(?P<inverse>[A-Za-z_]\w*)\.xyzw \* (?P=delta)\.xyzw;$"
)
_PLANE_SCALE = re.compile(
    r"^\s*(?P<delta>[A-Za-z_]\w*)\.xyzw = (?P=delta)\.xyzw \* "
    r"(?P<sign>-?)(?P<normal>[A-Za-z_]\w*)\.(?P<lane>[xyzw]){4};$"
)
_PLANE_COMBINE = re.compile(
    r"^\s*(?P<delta_x>[A-Za-z_]\w*)\.xyzw = "
    r"(?P=delta_x)\.xyzw \* (?P<sign>-?)(?P<normal>[A-Za-z_]\w*)\."
    r"(?P<lane>[xyzw]){4} \+ (?P<delta_y>[A-Za-z_]\w*)\.xyzw;$"
)
_PLANE_SATURATE = re.compile(
    r"^\s*(?P<plane_weight>[A-Za-z_]\w*)\.xyzw = saturate\("
    r"(?P<delta_z>[A-Za-z_]\w*)\.xyzw \* "
    r"(?P<sign>-?)(?P<normal>[A-Za-z_]\w*)\.(?P<lane>[xyzw]){4} "
    r"\+ (?P<delta_x>[A-Za-z_]\w*)\.xyzw\);$"
)
_BILATERAL_PRODUCT = re.compile(
    r"^\s*(?P<output>[A-Za-z_]\w*)\.xyzw = "
    r"(?P<distance_weight>[A-Za-z_]\w*)\.xyzw \* "
    r"(?P<plane_weight>[A-Za-z_]\w*)\.xyzw;$"
)


def _lift_bilateral_weights(source: str) -> str:
    """Recover the repeated distance/plane-aware four-sample rejection."""
    lines = source.splitlines()
    lifted: list[str] = []
    index = 0
    while index < len(lines):
        start = _BILATERAL_START.match(lines[index])
        if start is None or index + 21 >= len(lines):
            lifted.append(lines[index])
            index += 1
            continue
        distance = start.group("distance")
        delta_y = start.group("delta_y")
        delta_x_match = _BILATERAL_DELTA.match(lines[index + 1])
        delta_z_match = _BILATERAL_DELTA.match(lines[index + 2])
        accept_match = _BILATERAL_ACCEPT.match(lines[index + 4])
        if (
            delta_x_match is None
            or delta_z_match is None
            or accept_match is None
            or delta_x_match.group("distance") != distance
            or delta_z_match.group("distance") != distance
            or accept_match.group("distance") != distance
            or lines[index + 3].strip()
            != f"{distance}.xyzw = sqrt({distance}.xyzw);"
        ):
            lifted.append(lines[index])
            index += 1
            continue
        delta_x = delta_x_match.group("delta")
        delta_z = delta_z_match.group("delta")
        accepted = accept_match.group("accepted")
        normalized_x = _NORMALIZED_DELTA.match(lines[index + 8])
        normalized_y = _NORMALIZED_DELTA.match(lines[index + 9])
        plane_y = _PLANE_SCALE.match(lines[index + 10])
        plane_x = _PLANE_COMBINE.match(lines[index + 11])
        normalized_z = _NORMALIZED_DELTA.match(lines[index + 12])
        plane_z = _PLANE_SATURATE.match(lines[index + 13])
        falloff = re.match(
            rf"^\s*(?P<distance_weight>[A-Za-z_]\w*)\.xyzw = "
            rf"{re.escape(distance)}\.xyzw \* "
            r"(?P<register>[A-Za-z_]\w*)\.(?P<lane>[xyzw]){4};$",
            lines[index + 15],
        )
        product = _BILATERAL_PRODUCT.match(lines[index + 20])
        if (
            normalized_x is None
            or normalized_y is None
            or normalized_z is None
            or plane_y is None
            or plane_x is None
            or plane_z is None
            or falloff is None
            or normalized_x.group("delta") != delta_x
            or normalized_y.group("delta") != delta_y
            or normalized_z.group("delta") != delta_z
            or plane_y.group("delta") != delta_y
            or plane_x.group("delta_x") != delta_x
            or plane_x.group("delta_y") != delta_y
            or plane_z.group("delta_x") != delta_x
            or plane_z.group("delta_z") != delta_z
            or plane_x.group("normal") != plane_y.group("normal")
            or plane_z.group("normal") != plane_y.group("normal")
            or product is None
            or product.group("plane_weight") != plane_z.group("plane_weight")
            or product.group("distance_weight") != falloff.group("distance_weight")
            or lines[index + 21].strip()
            != (
                f"{product.group('output')}.xyzw = "
                f"{product.group('output')}.xyzw * {accepted}.xyzw;"
            )
        ):
            lifted.append(lines[index])
            index += 1
            continue
        threshold = (
            f"{accept_match.group('threshold')}."
            f"{accept_match.group('threshold_lane')}"
        )
        normal = plane_y.group("normal")
        output = product.group("output")
        def plane_component(match: re.Match[str]) -> str:
            return f"{match.group('sign')}{normal}.{match.group('lane')}"
        indent = start.group("indent")
        lifted.append(f"{indent}// Plane- and distance-aware neighborhood rejection.")
        lifted.append(f"{indent}{output}.xyzw = ComputeCascadeBilateralWeights(")
        lifted.append(
            f"{indent}    {delta_x}.xyzw, {delta_y}.xyzw, {delta_z}.xyzw,"
        )
        lifted.append(
            f"{indent}    {plane_component(plane_x)}, "
            f"{plane_component(plane_y)}, {plane_component(plane_z)},"
        )
        lifted.append(
            f"{indent}    {threshold}, "
            f"{falloff.group('register')}.{falloff.group('lane')});"
        )
        index += 22
    return "\n".join(lifted) + "\n"


def _execution(blob: bytes) -> dict[str, Any]:
    abi = ShaderReflector().abi(blob)
    textures = [resource for resource in abi["resources"] if resource["type"] == 2]
    samplers = [resource for resource in abi["resources"] if resource["type"] == 3]
    profiles = {0: "index", 5: "projection", 9: "hdr"}
    return {
        "kind": "fullscreen_ssgi_cascade",
        "fixture": "ssgi-cascade",
        "vertex_harness": "fullscreen_uv",
        # Spatially varying channels exercise Gather lane ordering, cascade
        # offsets, normal rejection, and parent-level blending.
        "width": 8,
        "height": 8,
        "texture_slots": [resource["bind_point"] for resource in textures],
        "texture_kinds": ["2d"] * len(textures),
        "smooth_texture_slots": [resource["bind_point"] for resource in textures],
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
        source = source.replace("w1.xyzw", "w1.xyxy")
        # HLSL's Gather intrinsic and the native gather4 opcode expose the
        # middle two footprint lanes in the opposite order.
        source = source.replace(".wzxy * float4(65535", ".wzyx * float4(65535")
        source = source.replace(
            "    o0.xy = float2(0.00755321607,1);",
            "    // SM_COVERAGE_CANARY: far_depth_exit\n"
            "    o0.xy = float2(0.00755321607,1);",
            1,
        )
        source = _name_cascade_registers(source)
        shader_defines = definitions[selector]
        if "PS_FINAL" in shader_defines:
            marker = "// SM_COVERAGE_CANARY: final_resolve"
        elif "PS_DOWN_RES" in shader_defines:
            marker = "// SM_COVERAGE_CANARY: downsample"
        else:
            marker = "// SM_COVERAGE_CANARY: parent_upscale"
        source = source.replace(
            "  // Packed samples stay ordered to preserve the recovered lane map.",
            "  // Packed samples stay ordered to preserve the recovered lane map.\n"
            f"  {marker}",
            1,
        )
        variants[selector] = _lift_bilateral_weights(
            _lift_packed_indirect_encodes(
                _lift_packed_indirect_decodes(source)
            )
        )
    primitives = asset("ssgi_cascade_primitives.hlsl")
    bodies = {
        shader["selector"]: (
            SEMANTIC_PHASE_MAP + primitives + variants[shader["selector"]]
        )
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
