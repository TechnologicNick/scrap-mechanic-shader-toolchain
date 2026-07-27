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


_DECODE_CALL = re.compile(
    r"^(?P<indent>\s*)(?P<destination>[A-Za-z_]\w*\.[xyzw]{3}) = "
    r"DecodeCascadeIndirect\(\(uint\)(?P<packed>[A-Za-z_]\w*)\."
    r"(?P<lane>[xyzw])\);$"
)
_QUARTER_WEIGHTS = re.compile(
    r"^\s*(?P<scaled>[A-Za-z_]\w*)\.xyzw = "
    r"float4\(0\.25,0\.25,0\.25,0\.25\) \* "
    r"(?P<raw>[A-Za-z_]\w*)\.xyzw;$"
)


def _replace_assignment_rhs(line: str, old: str, new: str) -> str:
    left, separator, right = line.partition("=")
    return left + separator + right.replace(old, new)


def _lift_cascade_quad_contributions(source: str) -> str:
    """Combine four decoded Gather lanes and their repeated weighted sum."""
    lines = source.splitlines()
    lifted: list[str] = []
    quad_index = 0
    index = 0
    marker = "// Decode the gathered 6:5:5 indirect-light words."
    while index < len(lines):
        if lines[index].strip() != marker or index + 4 >= len(lines):
            lifted.append(lines[index])
            index += 1
            continue
        calls = [_DECODE_CALL.match(lines[index + offset]) for offset in range(1, 5)]
        if any(call is None for call in calls):
            lifted.append(lines[index])
            index += 1
            continue
        decoded = [call for call in calls if call is not None]
        packed = decoded[0].group("packed")
        if (
            any(call.group("packed") != packed for call in decoded)
            or [call.group("lane") for call in decoded] != list("xyzw")
        ):
            lifted.append(lines[index])
            index += 1
            continue

        indent = decoded[0].group("indent")
        destinations = [call.group("destination") for call in decoded]
        weight_match = (
            _QUARTER_WEIGHTS.match(lines[index + 5])
            if index + 14 < len(lines)
            else None
        )
        if weight_match is not None:
            scaled = weight_match.group("scaled")
            raw = weight_match.group("raw")
            scalar_match = re.match(
                rf"^\s*(?P<scalar>[A-Za-z_]\w*\.[xyzw]) = "
                rf"{re.escape(scaled)}\.x \+ {re.escape(scaled)}\.y;$",
                lines[index + 6],
            )
            if scalar_match is not None:
                scalar = scalar_match.group("scalar")
                expected_weight_lines = (
                    f"{scalar} = {raw}.z * 0.25 + {scalar};",
                    f"{scalar} = {raw}.w * 0.25 + {scalar};",
                )
                sum_match = re.match(
                    rf"^\s*(?P<sum>[A-Za-z_]\w*\.[xyzw]{{3}}) = "
                    rf"{re.escape(scaled)}\.yyy \* "
                    rf"{re.escape(destinations[1])};$",
                    lines[index + 10],
                )
                if (
                    lines[index + 7].strip() == expected_weight_lines[0]
                    and lines[index + 8].strip() == expected_weight_lines[1]
                    and sum_match is not None
                ):
                    color_sum = sum_match.group("sum")
                    accumulation = color_sum
                    valid_accumulation = True
                    for offset, sample_index, weight_lane in (
                        (11, 0, "x"), (12, 2, "z"), (13, 3, "w")
                    ):
                        addition = re.match(
                            rf"^\s*(?P<sum>[A-Za-z_]\w*\.[xyzw]{{3}}) = "
                            rf"{re.escape(destinations[sample_index])} \* "
                            rf"{re.escape(scaled)}\.{weight_lane}{{3}} \+ "
                            rf"{re.escape(accumulation)};$",
                            lines[index + offset],
                        )
                        if addition is None:
                            valid_accumulation = False
                            break
                        accumulation = addition.group("sum")
                    if valid_accumulation:
                        contribution = f"filteredNeighborhood{quad_index}"
                        outer_weight = _replace_assignment_rhs(
                            lines[index + 9], scalar,
                            f"{contribution}.weight",
                        )
                        outer_color = _replace_assignment_rhs(
                            lines[index + 14], accumulation,
                            f"{contribution}.indirect",
                        )
                        if outer_weight != lines[index + 9] and outer_color != lines[index + 14]:
                            lifted.append(
                                f"{indent}CascadeContribution {contribution} = "
                                "ResolveCascadeContribution("
                            )
                            lifted.append(
                                f"{indent}    (uint4){packed}, {raw}.xyzw);"
                            )
                            lifted.append(outer_weight)
                            lifted.append(outer_color)
                            quad_index += 1
                            index += 15
                            continue

        quad = f"decodedQuad{quad_index}"
        lifted.append(
            f"{indent}CascadeQuad {quad} = DecodeCascadeQuad((uint4){packed});"
        )
        for lane_index, destination in enumerate(destinations):
            lifted.append(
                f"{indent}{destination} = {quad}.sample{lane_index};"
            )
        quad_index += 1
        index += 5
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
    r"(?P<threshold>[A-Za-z_]\w*)\.(?P<threshold_lane>[xyzw])"
    r"(?P=threshold_lane){3} "
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
    r"^\s*(?P<combined>[A-Za-z_]\w*)\.xyzw = "
    r"(?P<delta_x>[A-Za-z_]\w*)\.xyzw \* "
    r"(?P<sign>-?)(?P<normal>[A-Za-z_]\w*)\."
    r"(?P<lane>[xyzw]){4} \+ (?P<delta_y>[A-Za-z_]\w*)\.xyzw;$"
)
_PLANE_SATURATE = re.compile(
    r"^\s*(?P<plane_weight>[A-Za-z_]\w*)\.xyzw = saturate\("
    r"(?P<delta_z>[A-Za-z_]\w*)\.xyzw \* "
    r"(?P<sign>-?)(?P<normal>[A-Za-z_]\w*)\.(?P<lane>[xyzw]){4} "
    r"\+ (?P<combined>[A-Za-z_]\w*)\.xyzw\);$"
)
_BILATERAL_PRODUCT = re.compile(
    r"^\s*(?P<output>[A-Za-z_]\w*)\.xyzw = "
    r"(?P<left>[A-Za-z_]\w*)\.xyzw \* "
    r"(?P<right>[A-Za-z_]\w*)\.xyzw;$"
)
_BILATERAL_ACCEPTED_PRODUCT = re.compile(
    r"^\s*(?P<output>[A-Za-z_]\w*)\.xyzw = "
    r"(?P<weights>[A-Za-z_]\w*)\.xyzw \* "
    r"(?P<accepted>[A-Za-z_]\w*)\.xyzw;$"
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
        accepted_product = _BILATERAL_ACCEPTED_PRODUCT.match(lines[index + 21])
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
            or plane_z.group("combined") != plane_x.group("combined")
            or plane_z.group("delta_z") != delta_z
            or plane_x.group("normal") != plane_y.group("normal")
            or plane_z.group("normal") != plane_y.group("normal")
            or product is None
            or accepted_product is None
            or {
                product.group("left"), product.group("right")
            } != {
                plane_z.group("plane_weight"),
                falloff.group("distance_weight"),
            }
            or accepted_product.group("weights") != product.group("output")
            or accepted_product.group("accepted") != accepted
        ):
            lifted.append(lines[index])
            index += 1
            continue
        threshold = (
            f"{accept_match.group('threshold')}."
            f"{accept_match.group('threshold_lane')}"
        )
        normal = plane_y.group("normal")
        output = accepted_product.group("output")
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


_GATHER_INDIRECT = re.compile(
    r"^(?P<indent>\s*)(?P<indirect>[A-Za-z_]\w*)\.xyzw = "
    r"tSsgi\.Gather\(PointClampClamp_s, "
    r"(?P<uv>[A-Za-z_]\w*\.[xyzw]{2})\)\.xyzw;$"
)
_GATHER_DEPTH = re.compile(
    r"^\s*(?P<depth>[A-Za-z_]\w*)\.xyzw = "
    r"tSsgi\.GatherGreen\(PointClampClamp_s, "
    r"(?P<uv>[A-Za-z_]\w*\.[xyzw]{2})\)\.xyzw;$"
)
_DEPTH_SCALE = re.compile(
    r"^\s*(?P<depth>[A-Za-z_]\w*)\.xyzw = (?P=depth)\.xyzw \* "
    r"(?P<scale>[A-Za-z_]\w*\.(?P<lane>[xyzw]))(?P=lane){3} \+ "
    r"float4\(0\.100000001,0\.100000001,0\.100000001,0\.100000001\);$"
)
_POSITION_DELTA = re.compile(
    r"^\s*(?P<output>[A-Za-z_]\w*)\.xyzw = "
    r"(?P<ray>[A-Za-z_]\w*\.(?P<ray_lane>[xyzw]))(?P=ray_lane){3} \* "
    r"(?P<depth>[A-Za-z_]\w*)\.xyzw \+ "
    r"-(?P<center>[A-Za-z_]\w*\.(?P<center_lane>[xyzw]))"
    r"(?P=center_lane){3};$"
)
_DEPTH_DELTA = re.compile(
    r"^\s*(?P<output>[A-Za-z_]\w*)\.xyzw = "
    r"-(?P<depth>[A-Za-z_]\w*)\.xyzw \+ "
    r"-(?P<center>[A-Za-z_]\w*\.(?P<center_lane>[xyzw]))"
    r"(?P=center_lane){3};$"
)
_BILATERAL_CALL = re.compile(
    r"^\s*(?P<weights>[A-Za-z_]\w*)\.xyzw = "
    r"ComputeCascadeBilateralWeights\(\n"
    r"\s*(?P<delta_x>[A-Za-z_]\w*)\.xyzw, "
    r"(?P<delta_y>[A-Za-z_]\w*)\.xyzw, "
    r"(?P<delta_z>[A-Za-z_]\w*)\.xyzw,\n"
    r"\s*(?P<plane_x>-?[A-Za-z_]\w*\.[xyzw]), "
    r"(?P<plane_y>-?[A-Za-z_]\w*\.[xyzw]), "
    r"(?P<plane_z>-?[A-Za-z_]\w*\.[xyzw]),\n"
    r"\s*(?P<rejection>[A-Za-z_]\w*\.[xyzw]), "
    r"(?P<falloff>[A-Za-z_]\w*\.[xyzw])\);$"
)
_PACK_GATHER = re.compile(
    r"^\s*(?P<packed>[A-Za-z_]\w*)\.xyzw = "
    r"(?P<indirect>[A-Za-z_]\w*)\.xyzw \* "
    r"float4\(65535,65535,65535,65535\) \+ "
    r"float4\(0\.5,0\.5,0\.5,0\.5\);$"
)
_CAST_PACKED_GATHER = re.compile(
    r"^\s*(?P<packed>[A-Za-z_]\w*)\.xyzw = "
    r"\(uint4\)(?P=packed)\.xyzw;$"
)
_RESOLVE_NEIGHBORHOOD = re.compile(
    r"^\s*CascadeContribution (?P<contribution>[A-Za-z_]\w*) = "
    r"ResolveCascadeContribution\(\n"
    r"\s*\(uint4\)(?P<packed>[A-Za-z_]\w*), "
    r"(?P<weights>[A-Za-z_]\w*)\.xyzw\);$"
)


def _lift_cascade_neighborhood_gathers(source: str) -> str:
    """Recover each Gather/depth/bilateral/decode operation as one call."""
    lines = source.splitlines()
    lifted: list[str] = []
    context_signature: tuple[str, ...] | None = None
    context_name = "cascadeFilterContext"
    neighborhood_index = 0
    index = 0
    while index < len(lines):
        gather = _GATHER_INDIRECT.match(lines[index])
        depth_gather = (
            _GATHER_DEPTH.match(lines[index + 1])
            if gather is not None and index + 1 < len(lines)
            else None
        )
        if (
            gather is None
            or depth_gather is None
            or depth_gather.group("uv") != gather.group("uv")
        ):
            lifted.append(lines[index])
            index += 1
            continue

        depth = depth_gather.group("depth")
        if (
            index + 3 >= len(lines)
            or lines[index + 2].strip()
            != f"{depth}.xyzw = {depth}.xyzw * {depth}.xyzw;"
        ):
            lifted.append(lines[index])
            index += 1
            continue

        marker = next(
            (
                candidate
                for candidate in range(index + 4, min(index + 16, len(lines)))
                if lines[candidate].strip()
                == "// Plane- and distance-aware neighborhood rejection."
            ),
            None,
        )
        if marker is None or marker < index + 7:
            lifted.append(lines[index])
            index += 1
            continue

        scale_line = next(
            (
                candidate
                for candidate in range(index + 3, marker - 2)
                if _DEPTH_SCALE.match(lines[candidate]) is not None
            ),
            None,
        )
        if scale_line is None:
            lifted.append(lines[index])
            index += 1
            continue
        scale = _DEPTH_SCALE.match(lines[scale_line])
        delta_x = _POSITION_DELTA.match(lines[marker - 3])
        delta_y = _POSITION_DELTA.match(lines[marker - 2])
        delta_z = _DEPTH_DELTA.match(lines[marker - 1])
        if (
            scale is None
            or delta_x is None
            or delta_y is None
            or delta_z is None
            or scale.group("depth") != depth
            or any(
                delta.group("depth") != depth
                for delta in (delta_x, delta_y, delta_z)
            )
        ):
            lifted.append(lines[index])
            index += 1
            continue

        call_end = marker + 4
        if call_end + 4 >= len(lines):
            lifted.append(lines[index])
            index += 1
            continue
        bilateral = _BILATERAL_CALL.match("\n".join(lines[marker + 1 : call_end + 1]))
        packed = _PACK_GATHER.match(lines[call_end + 1])
        cast = _CAST_PACKED_GATHER.match(lines[call_end + 2])
        resolve = _RESOLVE_NEIGHBORHOOD.match(
            "\n".join(lines[call_end + 3 : call_end + 5])
        )
        if (
            bilateral is None
            or packed is None
            or cast is None
            or resolve is None
            or packed.group("indirect") != gather.group("indirect")
            or cast.group("packed") != packed.group("packed")
            or resolve.group("packed") != packed.group("packed")
            or resolve.group("weights") != bilateral.group("weights")
            or bilateral.group("delta_x") != delta_x.group("output")
            or bilateral.group("delta_y") != delta_y.group("output")
            or bilateral.group("delta_z") != delta_z.group("output")
        ):
            lifted.append(lines[index])
            index += 1
            continue

        centers = (
            delta_x.group("center"),
            delta_y.group("center"),
            delta_z.group("center"),
        )
        signature = (
            *centers,
            scale.group("scale"),
            bilateral.group("plane_x"),
            bilateral.group("plane_y"),
            bilateral.group("plane_z"),
            bilateral.group("rejection"),
            bilateral.group("falloff"),
        )
        if context_signature is not None and signature != context_signature:
            lifted.append(lines[index])
            index += 1
            continue
        indent = gather.group("indent")
        setup = [
            *lines[index + 3 : scale_line],
            *lines[scale_line + 1 : marker - 3],
        ]
        uv = gather.group("uv")
        if setup:
            saved_uv = f"cascadeNeighborhoodUv{neighborhood_index}"
            lifted.append(f"{indent}float2 {saved_uv} = {uv};")
            uv = saved_uv
            lifted.extend(setup)

        if context_signature is None:
            context_signature = signature
            lifted.append(f"{indent}CascadeFilterContext {context_name};")
            lifted.append(
                f"{indent}{context_name}.centerPosition = float3("
                f"{centers[0]}, {centers[1]}, {centers[2]});"
            )
            lifted.append(
                f"{indent}{context_name}.depthScale = {scale.group('scale')};"
            )
            lifted.append(
                f"{indent}{context_name}.planeScale = float3("
                f"{bilateral.group('plane_x')}, {bilateral.group('plane_y')}, "
                f"{bilateral.group('plane_z')});"
            )
            lifted.append(
                f"{indent}{context_name}.rejectionDistance = "
                f"{bilateral.group('rejection')};"
            )
            lifted.append(
                f"{indent}{context_name}.inverseFalloffDistance = "
                f"{bilateral.group('falloff')};"
            )
        contribution = resolve.group("contribution")
        lifted.append(
            f"{indent}CascadeContribution {contribution} = "
            "GatherCascadeNeighborhood("
        )
        lifted.append(
            f"{indent}    tSsgi, PointClampClamp_s, {uv},"
        )
        lifted.append(
            f"{indent}    {delta_x.group('ray')}"
            f"{delta_x.group('ray_lane') * 3}, "
            f"{delta_y.group('ray')}"
            f"{delta_y.group('ray_lane') * 3}, {context_name});"
        )
        neighborhood_index += 1
        index = call_end + 5
    return "\n".join(lifted) + "\n"


_CONTRIBUTION_ASSIGNMENT = re.compile(
    r"^(?P<indent>\s*)(?P<destination>[A-Za-z_]\w*\.[xyzw]{1,3}) = "
    r"(?P<left>[^;]+) \+ (?P<right>[^;]+);$"
)


def _lift_cascade_accumulations(source: str) -> str:
    """Name the repeated weight/indirect accumulation between neighborhood taps."""
    lines = source.splitlines()
    lifted: list[str] = []
    index = 0
    while index < len(lines):
        weight = _CONTRIBUTION_ASSIGNMENT.match(lines[index])
        indirect = (
            _CONTRIBUTION_ASSIGNMENT.match(lines[index + 1])
            if weight is not None and index + 1 < len(lines)
            else None
        )
        if weight is None or indirect is None:
            lifted.append(lines[index])
            index += 1
            continue

        weight_destination = weight.group("destination")
        indirect_destination = indirect.group("destination")
        weight_terms = {weight.group("left"), weight.group("right")}
        indirect_terms = {indirect.group("left"), indirect.group("right")}
        contribution_terms = [
            term.removesuffix(".weight")
            for term in weight_terms
            if term.endswith(".weight")
        ]
        if len(contribution_terms) != 1:
            lifted.append(lines[index])
            index += 1
            continue
        contribution = contribution_terms[0]
        if (
            weight_destination not in weight_terms
            or indirect_destination not in indirect_terms
            or f"{contribution}.indirect" not in indirect_terms
        ):
            lifted.append(lines[index])
            index += 1
            continue

        indent = weight.group("indent")
        lifted.append(f"{indent}AccumulateCascadeContribution(")
        lifted.append(
            f"{indent}    {weight_destination}, {indirect_destination}, "
            f"{contribution});"
        )
        index += 2
    return "\n".join(lifted) + "\n"


_NEIGHBORHOOD_DIRECTIONS = (
    "northWest",
    "north",
    "northEast",
    "west",
    "east",
    "southWest",
    "south",
    "southEast",
)


def _name_cascade_neighborhoods(source: str) -> str:
    """Expose the recovered clockwise 3x3 perimeter traversal."""
    for index, direction in enumerate(_NEIGHBORHOOD_DIRECTIONS):
        source = re.sub(
            rf"\bfilteredNeighborhood{index + 1}\b",
            f"{direction}Contribution",
            source,
        )
        source = re.sub(
            rf"\bcascadeNeighborhoodUv{index}\b",
            f"{direction}Uv",
            source,
        )
    return source


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
        variants[selector] = _name_cascade_neighborhoods(
            _lift_cascade_accumulations(
                _lift_cascade_neighborhood_gathers(
                    _lift_bilateral_weights(
                        _lift_packed_indirect_encodes(
                            _lift_cascade_quad_contributions(
                                _lift_packed_indirect_decodes(source)
                            )
                        )
                    )
                )
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
