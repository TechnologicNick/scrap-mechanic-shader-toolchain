"""Typed alpha/depth-only policies for ``main_part`` pixel permutations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .common import replace_cbuffer_with_include
from .main_part_families import SemanticKey, parse_entry_signature


@dataclass(frozen=True)
class MainPartDepthFamily:
    cutout: str
    dissolve: str | None

    @property
    def name(self) -> str:
        suffix = f"_dissolve_{self.dissolve}" if self.dissolve else ""
        return f"depth_{self.cutout}{suffix}"


def classify_main_part_depth_family(
    defines: Iterable[str], source: str
) -> MainPartDepthFamily | None:
    values = frozenset(defines)
    if not {"PIXEL_SHADER", "PS_PERM_DEPTH"} <= values:
        return None
    # Detail-normal declarations are deliberately retained in the exact
    # shader ABI even though the depth body does not sample them. Recover that
    # resource-retention policy before admitting this variant.
    if "PS_NOR_D_TEX" in values:
        return None
    _signature, parameters = parse_entry_signature(source, "commonPS")
    semantics = {parameter.semantic for parameter in parameters}
    body = source[source.index("void commonPS("):]
    if "tFlowMap.Sample" in body:
        cutout = "flow_asg"
    elif "taAsg.SampleBias" in body:
        cutout = "array_asg"
    elif "tLaserMask.Sample" in body:
        cutout = "laser_mask"
    elif "tDif.SampleBias" in body:
        cutout = "point_diffuse"
    elif "tAsg.SampleBias(LinearWrapWrap_s" in body:
        cutout = "linear_asg"
    elif "tAsg.SampleBias(PointWrapWrap_s" in body:
        cutout = "point_asg"
    elif "discard" not in body:
        cutout = "none"
    else:
        return None
    dissolve = (
        "3d" if "PS_DISSOLVE_3D" in values
        else "uv1" if "PS_DISSOLVE_UV1" in values
        else "uv0" if "PS_DISSOLVE_UV0" in values
        else None
    )
    if cutout != "none" and SemanticKey("UV", 0) not in semantics:
        return None
    if dissolve is not None and SemanticKey("CUTOFF", 0) not in semantics:
        return None
    if dissolve == "uv1" and SemanticKey("UV", 1) not in semantics:
        return None
    return MainPartDepthFamily(cutout, dissolve)


def lift_main_part_depth_family(
    defines: Iterable[str], source: str
) -> tuple[str, str] | None:
    family = classify_main_part_depth_family(defines, source)
    if family is None:
        return None
    signature, parameters = parse_entry_signature(source, "commonPS")
    variables = {parameter.semantic: parameter.variable for parameter in parameters}
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_FLOW_MAP", "main_part_flow_map_abi.hlsl"),
        ("CB_DISSOLVE", "main_part_dissolve_b0_abi.hlsl"),
    ):
        needed = (
            cbuffer == "CB_PROJECTION"
            or (cbuffer in {"CB_PERFRAME", "CB_FLOW_MAP"}
                and family.cutout == "flow_asg")
            or (cbuffer in {"CB_PERFRAME", "CB_DISSOLVE"}
                and family.dissolve is not None)
        )
        if needed and f"cbuffer {cbuffer}" in source:
            source = replace_cbuffer_with_include(source, cbuffer, filename)
    marker = source.find("// 3Dmigoto declarations")
    prefix = source[:marker].rstrip()
    uv0 = variables.get(SemanticKey("UV", 0), "float2(0.0, 0.0)")
    lines = [f"  ApplyMainPartDepth{family.cutout.title().replace('_', '')}({uv0});"]
    if family.cutout == "none":
        lines = []
    if family.dissolve in {"uv0", "uv1"}:
        uv_index = 1 if family.dissolve == "uv1" else 0
        dissolve_uv = variables[SemanticKey("UV", uv_index)]
        cutoff = variables[SemanticKey("CUTOFF", 0)]
        lines.extend((
            "  MainPartSurfaceDissolveBand dissolve =",
            f"      EvaluateMainPartSurfaceDissolveBand({dissolve_uv}, {cutoff});",
            "  ApplyMainPartSurfaceDissolveWindow(dissolve);",
        ))
    elif family.dissolve == "3d":
        cutoff = variables[SemanticKey("CUTOFF", 0)]
        lines.append(f"  ApplyMainPartDepthDissolve3D({cutoff});")
    defines_text = [f"#define MAIN_PART_DEPTH_{family.cutout.upper()}_PHASE 1"]
    if family.dissolve in {"uv0", "uv1"}:
        defines_text.append("#define MAIN_PART_DEPTH_DISSOLVE_2D_PHASE 1")
    elif family.dissolve == "3d":
        defines_text.append("#define MAIN_PART_DEPTH_DISSOLVE_3D_PHASE 1")
    return (
        family.name,
        prefix + "\n\n" + "\n".join(defines_text)
        + '\n#include "include/main_part_depth_pixel.hlsl"\n\n'
        + signature + "\n{\n" + "\n".join(lines) + "\n}\n",
    )
