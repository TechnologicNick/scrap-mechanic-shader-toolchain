"""Typed picking-output policies for ``main_part`` pixel permutations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .common import replace_cbuffer_with_include
from .main_part_families import SemanticKey, parse_entry_signature


@dataclass(frozen=True)
class MainPartPickingFamily:
    cutout: str

    @property
    def name(self) -> str:
        return f"picking_{self.cutout}"


def classify_main_part_picking_family(
    defines: Iterable[str], source: str
) -> MainPartPickingFamily | None:
    values = frozenset(defines)
    if not {"PIXEL_SHADER", "PS_PERM_PICKING"} <= values:
        return None
    signature, parameters = parse_entry_signature(source, "commonPS")
    del signature
    variables = {parameter.semantic: parameter.variable for parameter in parameters}
    if not {
        SemanticKey("VERTEXCOLOR", 0), SemanticKey("SV_TARGET", 0)
    } <= variables.keys():
        return None
    body = source[source.index("void commonPS("):]
    output = variables[SemanticKey("SV_TARGET", 0)]
    color = variables[SemanticKey("VERTEXCOLOR", 0)]
    if f"{output}.xyzw = {color}.xyzw" not in body:
        return None
    if "tFlowMap.Sample" in body:
        cutout = "flow"
    elif "tAsg.SampleBias(LinearWrapWrap_s" in body:
        cutout = "linear"
    elif "tAsg.SampleBias(PointWrapWrap_s" in body:
        cutout = "point"
    elif "tAsg.Sample" not in body and "discard" not in body:
        cutout = "none"
    else:
        return None
    if cutout != "none" and SemanticKey("UV", 0) not in variables:
        return None
    return MainPartPickingFamily(cutout)


def lift_main_part_picking_family(
    defines: Iterable[str], source: str
) -> tuple[str, str] | None:
    family = classify_main_part_picking_family(defines, source)
    if family is None:
        return None
    signature, parameters = parse_entry_signature(source, "commonPS")
    variables = {parameter.semantic: parameter.variable for parameter in parameters}
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_FLOW_MAP", "main_part_flow_map_abi.hlsl"),
    ):
        if f"cbuffer {cbuffer}" in source and (
            family.cutout == "flow" or cbuffer == "CB_PROJECTION"
        ):
            source = replace_cbuffer_with_include(source, cbuffer, filename)
    marker = source.find("// 3Dmigoto declarations")
    prefix = source[:marker].rstrip()
    lines: list[str] = []
    if family.cutout != "none":
        uv = variables[SemanticKey("UV", 0)]
        function = {
            "point": "ApplyMainPartPickingPointCutout",
            "linear": "ApplyMainPartPickingLinearCutout",
            "flow": "ApplyMainPartPickingFlowCutout",
        }[family.cutout]
        lines.append(f"  {function}({uv});")
    lines.append(
        "  WriteMainPartPickingColor("
        f"{variables[SemanticKey('VERTEXCOLOR', 0)]}, "
        f"{variables[SemanticKey('SV_TARGET', 0)]});"
    )
    phase = f"#define MAIN_PART_PICKING_{family.cutout.upper()}_PHASE 1"
    lifted = (
        prefix + "\n\n" + phase
        + '\n#include "include/main_part_picking_pixel.hlsl"\n\n'
        + signature + "\n{\n" + "\n".join(lines) + "\n}\n"
    )
    return family.name, lifted
