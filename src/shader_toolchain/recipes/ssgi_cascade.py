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
SSGI cascade phases
1. Reproject the center sample and build its filter plane.
2. Gather the eight depth-aware perimeter neighborhoods.
3. Resolve/downsample or blend the coarser parent cascade.
Recovered accumulation order is retained for Shader Model 5 rounding.
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


_CENTER_GATHER = re.compile(
    r"^(?P<indent>\s*)(?P<packed>[A-Za-z_]\w*)\.xyzw = "
    r"(?P<texture>[A-Za-z_]\w*)\.Gather\(LinearClampClamp_s, "
    r"(?P<uv>[A-Za-z_]\w*\.[xyzw]{2})\)\.xyzw;$"
)
_QUAD_SAMPLE = re.compile(
    r"^\s*(?P<destination>[A-Za-z_]\w*\.[xyzw]{3}) = "
    r"decodedQuad0\.sample(?P<sample>[0-3]);$"
)


def _sum_assignment(line: str) -> tuple[str, set[str]] | None:
    assignment = _SIMPLE_ASSIGNMENT.match(line)
    if assignment is None:
        return None
    terms = assignment.group("value").split(" + ")
    if len(terms) != 2:
        return None
    return assignment.group("destination"), set(terms)


def _lift_center_indirect_gathers(source: str) -> str:
    """Recover the four-lane center Gather and ordered indirect-light sum."""
    lines = source.splitlines()
    lifted: list[str] = []
    index = 0
    while index < len(lines):
        gather = _CENTER_GATHER.match(lines[index])
        if gather is None or index + 10 >= len(lines):
            lifted.append(lines[index])
            index += 1
            continue
        packed = gather.group("packed")
        if (
            lines[index + 1].strip()
            != (
                f"{packed}.xyzw = {packed}.wzyx * "
                "float4(65535,65535,65535,65535) + "
                "float4(0.5,0.5,0.5,0.5);"
            )
            or lines[index + 2].strip()
            != f"{packed}.xyzw = (uint4){packed}.xyzw;"
            or lines[index + 3].strip()
            != f"CascadeQuad decodedQuad0 = DecodeCascadeQuad((uint4){packed});"
        ):
            lifted.append(lines[index])
            index += 1
            continue
        samples = [_QUAD_SAMPLE.match(lines[index + offset]) for offset in range(4, 8)]
        if any(sample is None for sample in samples):
            lifted.append(lines[index])
            index += 1
            continue
        decoded = [sample for sample in samples if sample is not None]
        if [sample.group("sample") for sample in decoded] != list("0123"):
            lifted.append(lines[index])
            index += 1
            continue
        destinations = [sample.group("destination") for sample in decoded]
        additions = [_sum_assignment(lines[index + offset]) for offset in range(8, 11)]
        if any(addition is None for addition in additions):
            lifted.append(lines[index])
            index += 1
            continue
        first, second, third = [addition for addition in additions if addition is not None]
        if (
            first[1] != {destinations[0], destinations[1]}
            or second[1] != {first[0], destinations[2]}
            or third[1] != {second[0], destinations[3]}
        ):
            lifted.append(lines[index])
            index += 1
            continue
        indent = gather.group("indent")
        lifted.append(
            f"{indent}{third[0]} = GatherCascadeCenterIndirect("
            f"{gather.group('texture')}, LinearClampClamp_s, {gather.group('uv')});"
        )
        index += 11
    return "\n".join(lifted) + "\n"


_MINIMUM_DEPTH_GATHER = re.compile(
    r"^(?P<indent>\s*)(?P<depth>[A-Za-z_]\w*)\.xyzw = "
    r"(?P<texture>[A-Za-z_]\w*)\.GatherGreen\(PointClampClamp_s, "
    r"(?P<uv>[A-Za-z_]\w*\.[xyzw]{2})\)\.xyzw;$"
)


def _lift_minimum_depth_gathers(source: str) -> str:
    """Name the minimum decoded depth in the center Gather footprint."""
    lines = source.splitlines()
    lifted: list[str] = []
    index = 0
    while index < len(lines):
        gather = _MINIMUM_DEPTH_GATHER.match(lines[index])
        if gather is None or index + 5 >= len(lines):
            lifted.append(lines[index])
            index += 1
            continue
        depth = gather.group("depth")
        scale_assignment = _SIMPLE_ASSIGNMENT.match(lines[index + 2])
        decoded = _DEPTH_SCALE.match(lines[index + 3])
        pair_minimum = _SIMPLE_ASSIGNMENT.match(lines[index + 4])
        minimum = _SIMPLE_ASSIGNMENT.match(lines[index + 5])
        pair_base = ""
        pair_lanes = ""
        if pair_minimum is not None:
            pair_base, pair_lanes = pair_minimum.group("destination").split(".")
        if (
            lines[index + 1].strip()
            != f"{depth}.xyzw = {depth}.xyzw * {depth}.xyzw;"
            or any(
                f"dot({depth}.xyzw" in line
                for line in lines[index + 6 : index + 26]
            )
            or scale_assignment is None
            or decoded is None
            or decoded.group("depth") != depth
            or decoded.group("scale") != scale_assignment.group("destination")
            or pair_minimum is None
            or pair_minimum.group("value") != f"min({depth}.xz, {depth}.yw)"
            or len(pair_lanes) != 2
            or minimum is None
            or minimum.group("value")
            != (
                f"min({pair_base}.{pair_lanes[0]}, "
                f"{pair_base}.{pair_lanes[1]})"
            )
        ):
            lifted.append(lines[index])
            index += 1
            continue
        indent = gather.group("indent")
        lifted.append(lines[index + 2])
        lifted.append(
            f"{indent}{minimum.group('destination')} = GatherMinimumCascadeDepth("
        )
        lifted.append(
            f"{indent}    {gather.group('texture')}, PointClampClamp_s, "
            f"{gather.group('uv')}, {decoded.group('scale')});"
        )
        index += 6
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


_VECTOR_NORTH_WEST = re.compile(
    r"^(?P<indent>\s*)[A-Za-z_]\w*\.xyzw = "
    r"(?P<pixel>[A-Za-z_]\w*)\.xyxy \* "
    r"float4\(-(?P<spacing>[0-9.]+),-(?P=spacing),[^)]+\) \+ "
    r"(?P<center>[A-Za-z_]\w*)\.xyxy;$"
)
_SCALAR_NORTH_WEST = re.compile(
    r"^(?P<indent>\s*)[A-Za-z_]\w*\.xy = "
    r"-(?P<spacing_x>[A-Za-z_]\w*\.[xyzw]{2}) \* "
    r"(?P<spacing_y>[A-Za-z_]\w*\.[xyzw]{2}) \+ "
    r"(?P<center>[A-Za-z_]\w*)\.xy;$"
)
_SIMPLE_ASSIGNMENT = re.compile(
    r"^\s*(?P<destination>[A-Za-z_]\w*\.[xyzw]{1,3}) = (?P<value>.+);$"
)


def _addition_base(line: str, contribution_term: str) -> tuple[str, str] | None:
    assignment = _SIMPLE_ASSIGNMENT.match(line)
    if assignment is None:
        return None
    terms = assignment.group("value").split(" + ")
    if len(terms) != 2 or terms.count(contribution_term) != 1:
        return None
    base = terms[1] if terms[0] == contribution_term else terms[0]
    return assignment.group("destination"), base


def _lift_cascade_perimeter(source: str) -> str:
    """Replace the explicit clockwise eight-tap traversal with one typed filter."""
    lines = source.splitlines()
    north_uv = next(
        (index for index, line in enumerate(lines) if "float2 northWestUv =" in line),
        None,
    )
    north = next(
        (
            index
            for index, line in enumerate(lines)
            if "CascadeContribution northWestContribution =" in line
        ),
        None,
    )
    south_east = next(
        (
            index
            for index, line in enumerate(lines)
            if "CascadeContribution southEastContribution =" in line
        ),
        None,
    )
    context = next(
        (
            index
            for index, line in enumerate(lines)
            if "CascadeFilterContext cascadeFilterContext;" in line
        ),
        None,
    )
    if None in (north_uv, north, south_east, context):
        return source
    assert north_uv is not None
    assert north is not None
    assert south_east is not None
    assert context is not None
    start = north_uv - 3
    if start < 0 or north + 4 >= len(lines) or south_east + 4 >= len(lines):
        return source

    vector_grid = _VECTOR_NORTH_WEST.match(lines[start])
    scalar_grid = _SCALAR_NORTH_WEST.match(lines[start])
    if vector_grid is not None:
        indent = vector_grid.group("indent")
        center_uv = f"{vector_grid.group('center')}.xy"
        spacing = vector_grid.group("spacing")
        tap_spacing = (
            f"{vector_grid.group('pixel')}.xy * float2({spacing},{spacing})"
        )
    elif scalar_grid is not None:
        indent = scalar_grid.group("indent")
        center_uv = f"{scalar_grid.group('center')}.xy"
        tap_spacing = (
            f"{scalar_grid.group('spacing_x')} * "
            f"{scalar_grid.group('spacing_y')}"
        )
    else:
        return source

    if not (north_uv < context < north < south_east):
        return source
    context_lines = lines[context : context + 6]
    if len(context_lines) != 6 or any(
        f"cascadeFilterContext.{field}" not in line
        for field, line in zip(
            (
                "centerPosition",
                "depthScale",
                "planeScale",
                "rejectionDistance",
                "inverseFalloffDistance",
            ),
            context_lines[1:],
            strict=True,
        )
    ):
        return source
    context_values = [
        line.split("=", 1)[1].strip().removesuffix(";")
        for line in context_lines[1:]
    ]

    initial_weight = _addition_base(
        lines[north + 3], "northWestContribution.weight"
    )
    initial_indirect = _addition_base(
        lines[north + 4], "northWestContribution.indirect"
    )
    final_weight = _addition_base(
        lines[south_east + 3], "southEastContribution.weight"
    )
    final_indirect = _addition_base(
        lines[south_east + 4], "southEastContribution.indirect"
    )
    if None in (initial_weight, initial_indirect, final_weight, final_indirect):
        return source
    assert initial_weight is not None
    assert initial_indirect is not None
    assert final_weight is not None
    assert final_indirect is not None
    if any(source.count(f"{direction}Contribution") == 0 for direction in _NEIGHBORHOOD_DIRECTIONS):
        return source

    prelude = [
        line
        for line in lines[north_uv + 1 : context]
        if "cb_hdr.fMaxDepth" in line
    ]
    replacement = [
        *prelude,
        f"{indent}CascadeFilterGrid cascadeFilterGrid = {{",
        f"{indent}    {center_uv}, {tap_spacing}, cb_vRenderScale.xy,",
        f"{indent}    cb_vUvLimitMipDown.xy, cb_vNearFarViewCorner.zw}};",
        f"{indent}CascadeFilterContext cascadeFilterContext = {{",
        f"{indent}    {context_values[0]}, {context_values[1]}, "
        f"{context_values[2]},",
        f"{indent}    {context_values[3]}, {context_values[4]}}};",
        f"{indent}CascadeAccumulator filteredCascade = FilterCascadePerimeter(",
        f"{indent}    tSsgi, PointClampClamp_s, cascadeFilterGrid, "
        "cascadeFilterContext,",
        f"{indent}    {initial_weight[1]}, {initial_indirect[1]});",
        f"{indent}{final_weight[0]} = filteredCascade.weight;",
        f"{indent}{final_indirect[0]} = filteredCascade.indirect;",
    ]
    return "\n".join([*lines[:start], *replacement, *lines[south_east + 5 :]]) + "\n"


def _lift_parent_range_encode(source: str) -> str:
    """Name parent-cascade range compression before the packed-light encoder."""
    lines = source.splitlines()
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if line.strip()
            == "packedIndirectState.w = max(packedIndirectState.x, packedIndirectState.y);"
        ),
        None,
    )
    if start is None:
        return source
    end = next(
        (
            index
            for index in range(start, min(start + 40, len(lines)))
            if lines[index].strip()
            == "o0.x = 1.52590219e-05 * packedIndirectState.x;"
        ),
        None,
    )
    required = (
        "packedIndirectState.w = cmp(1 < packedIndirectState.w);",
        "packedIndirectState.z = packedIndirectState.z * packedIndirectState.w;",
        "packedIndirectState.y = saturate(0.015625 * packedIndirectState.x);",
        "packedIndirectState.x = (uint)packedIndirectState.x << 5;",
    )
    if end is None or any(
        not any(marker in line for line in lines[start : end + 1])
        for marker in required
    ):
        return source
    indent = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
    replacement = [
        f"{indent}float cascadeRangeScale = ComputeCascadeRangeScale(",
        f"{indent}    packedIndirectState.xyz, sampleCoordinateState.y);",
        f"{indent}o0.x = EncodeCascadeIndirect("
        "packedIndirectState.xyz * cascadeRangeScale);",
    ]
    return "\n".join([*lines[:start], *replacement, *lines[end + 1 :]]) + "\n"


def _lift_view_positions_and_normals(source: str) -> str:
    """Name repeated view-position reconstruction and octahedral normal decode."""
    radial_view = """  sampleCoordinateState.yz = w1.xy * float2(1,-1) + float2(0,1);
  sampleCoordinateState.yz = sampleCoordinateState.yz * float2(2,2) + float2(-1,-1);
  sampleCoordinateState.yz = cb_vNearFarViewCorner.zw * sampleCoordinateState.yz;
  centerDepthState.xy = sampleCoordinateState.yz * packedIndirectState.xx;
  centerDepthState.z = -packedIndirectState.x;"""
    final_view = """  sampleCoordinateState.xy = w1.xy * float2(1,-1) + float2(0,1);
  sampleCoordinateState.xy = sampleCoordinateState.xy * float2(2,2) + float2(-1,-1);
  sampleCoordinateState.xy = cb_vNearFarViewCorner.zw * sampleCoordinateState.xy;
  sampleCoordinateState.xy = sampleCoordinateState.xy * packedIndirectState.xx;
  sampleCoordinateState.z = -packedIndirectState.x;"""
    parent_view = """  packedIndirectState.zw = w1.xy * float2(1,-1) + float2(0,1);
  packedIndirectState.zw = packedIndirectState.zw * float2(2,2) + float2(-1,-1);
  packedIndirectState.zw = cb_vNearFarViewCorner.zw * packedIndirectState.zw;
  neighborhoodDepthA.xy = packedIndirectState.zw * sampleCoordinateState.yy;
  neighborhoodDepthA.z = -sampleCoordinateState.y;"""
    source = source.replace(
        radial_view,
        "  centerDepthState.xyz = ReconstructCascadeViewPosition(\n"
        "      w1.xy, packedIndirectState.x, cb_vNearFarViewCorner.zw);",
    )
    source = source.replace(
        final_view,
        "  sampleCoordinateState.xyz = ReconstructCascadeViewPosition(\n"
        "      w1.xy, packedIndirectState.x, cb_vNearFarViewCorner.zw);",
    )
    source = source.replace(
        parent_view,
        "  neighborhoodDepthA.xyz = ReconstructCascadeViewPosition(\n"
        "      w1.xy, sampleCoordinateState.y, cb_vNearFarViewCorner.zw);",
    )

    final_normal = """  centerDepthState.xy = tNormal.SampleLevel(PointClampClamp_s, v1.xy, 0).xy;
  centerDepthState.xy = centerDepthState.xy * float2(2,2) + float2(-1,-1);
  sampleCoordinateState.w = 1 + -abs(centerDepthState.x);
  normalDecodeState.z = sampleCoordinateState.w + -abs(centerDepthState.y);
  sampleCoordinateState.w = saturate(-normalDecodeState.z);
  centerDepthState.zw = cmp(centerDepthState.xy >= float2(0,0));
  centerDepthState.zw = centerDepthState.zw ? -sampleCoordinateState.ww : sampleCoordinateState.ww;
  normalDecodeState.xy = centerDepthState.xy + centerDepthState.zw;
  sampleCoordinateState.w = dot(normalDecodeState.xyz, normalDecodeState.xyz);
  sampleCoordinateState.w = rsqrt(sampleCoordinateState.w);
  centerDepthState.xyz = normalDecodeState.xyz * sampleCoordinateState.www;"""
    downsample_normal = """  sampleCoordinateState.yz = tNormal.SampleLevel(PointClampClamp_s, v1.xy, 0).xy;
  sampleCoordinateState.yz = sampleCoordinateState.yz * float2(2,2) + float2(-1,-1);
  sampleCoordinateState.w = 1 + -abs(sampleCoordinateState.y);
  normalDecodeState.z = sampleCoordinateState.w + -abs(sampleCoordinateState.z);
  sampleCoordinateState.w = saturate(-normalDecodeState.z);
  neighborhoodDepthA.xy = cmp(sampleCoordinateState.yz >= float2(0,0));
  neighborhoodDepthA.xy = neighborhoodDepthA.xy ? -sampleCoordinateState.ww : sampleCoordinateState.ww;
  normalDecodeState.xy = neighborhoodDepthA.xy + sampleCoordinateState.yz;
  sampleCoordinateState.y = dot(normalDecodeState.xyz, normalDecodeState.xyz);
  sampleCoordinateState.y = rsqrt(sampleCoordinateState.y);
  sampleCoordinateState.yzw = normalDecodeState.xyz * sampleCoordinateState.yyy;"""
    source = source.replace(
        final_normal,
        "  centerDepthState.xyz = DecodeCascadeNormal(\n"
        "      tNormal.SampleLevel(PointClampClamp_s, v1.xy, 0).xy);",
    )
    return source.replace(
        downsample_normal,
        "  sampleCoordinateState.yzw = DecodeCascadeNormal(\n"
        "      tNormal.SampleLevel(PointClampClamp_s, v1.xy, 0).xy);",
    )


_FAR_DEPTH_COMPARE = re.compile(
    r"^(?P<indent>\s*)(?P<condition>[A-Za-z_]\w*\.[xyzw]) = "
    r"cmp\(800 < (?P<depth>[A-Za-z_]\w*\.[xyzw])\);\n"
    r"(?P=indent)if \((?P=condition) != 0\) \{$",
    re.MULTILINE,
)


def _lift_far_depth_checks(source: str) -> str:
    """Express the far-depth early exit as ordinary HLSL control flow."""
    source = _FAR_DEPTH_COMPARE.sub(
        lambda match: (
            f"{match.group('indent')}if (800 < {match.group('depth')}) {{"
        ),
        source,
    )
    source = source.replace("\n// 3Dmigoto declarations\n#define cmp -\n", "\n")
    return source


def _compact_cascade_entrypoint(source: str) -> str:
    signature = """void mainPS(
  float4 v0 : SV_Position0,
  float2 v1 : UV0,
  float2 w1 : UNSCALED_UV0,
  out float2 o0 : SV_Target0)
{"""
    compact = """void mainPS(
  float4 v0 : SV_Position0, float2 v1 : UV0, float2 w1 : UNSCALED_UV0,
  out float2 o0 : SV_Target0) {"""
    source = source.replace(signature, compact)
    return re.sub(r"\n{3,}", "\n\n", source)


_CASCADE_STATE_DECLARATION = re.compile(
    r"^(?P<indent>\s*)float4 (?P<names>[A-Za-z_,]+);$",
    re.MULTILINE,
)


def _prune_unused_cascade_state(source: str) -> str:
    """Remove recovered scratch registers made obsolete by structural lifts."""
    match = _CASCADE_STATE_DECLARATION.search(source)
    if match is None:
        return source
    names = match.group("names").split(",")
    used = [name for name in names if len(re.findall(rf"\b{name}\b", source)) > 1]
    declaration = f"{match.group('indent')}float4 {','.join(used)};"
    return source[: match.start()] + declaration + source[match.end() :]


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
        variants[selector] = _prune_unused_cascade_state(
            _compact_cascade_entrypoint(
                _lift_far_depth_checks(
                    _lift_view_positions_and_normals(
                        _lift_parent_range_encode(
                            _lift_cascade_perimeter(
                                _name_cascade_neighborhoods(
                                    _lift_cascade_accumulations(
                                        _lift_cascade_neighborhood_gathers(
                                            _lift_bilateral_weights(
                                                _lift_packed_indirect_encodes(
                                                    _lift_minimum_depth_gathers(
                                                        _lift_center_indirect_gathers(
                                                            _lift_cascade_quad_contributions(
                                                                _lift_packed_indirect_decodes(source)
                                                            )
                                                        )
                                                    )
                                                )
                                            )
                                        )
                                    )
                                )
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
