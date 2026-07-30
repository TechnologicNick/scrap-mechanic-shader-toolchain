"""Typed early-GForward material and normal policies."""

from __future__ import annotations

from typing import Iterable

from .common import replace_cbuffer_with_include
from .main_part_families import SemanticKey, parse_entry_signature


def lift_main_part_early_gforward_family(
    defines: Iterable[str], source: str
) -> tuple[str, str] | None:
    values = frozenset(defines)
    if not {"PIXEL_SHADER", "PS_PERM_EARLY_GFORWARD"} <= values:
        return None
    if "PS_REFLECTION_AS_DIFFUSE" in values:
        mode = "reflection_as_diffuse"
    elif {"PS_GLASS_OPAQUE", "PS_ASG_TEX", "PS_NOR_TEX"} <= values:
        mode = "opaque_glass"
    else:
        return None
    signature, parameters = parse_entry_signature(source, "commonPS")
    variables = {parameter.semantic: parameter.variable for parameter in parameters}
    if "cbuffer CB_PROJECTION" in source:
        source = replace_cbuffer_with_include(
            source, "CB_PROJECTION", "main_part_projection_abi.hlsl"
        )
    prefix = source[:source.find("// 3Dmigoto declarations")].rstrip()
    if mode == "reflection_as_diffuse":
        lines = [
            "  MainPartEarlyGForward result =",
            "      EvaluateMainPartReflectionAsDiffuseEarlyGForward(",
            f"          {variables[SemanticKey('NORMAL', 0)]});",
        ]
    else:
        lines = [
            "  MainPartEarlyGForward result =",
            "      EvaluateMainPartOpaqueGlassEarlyGForward(",
            f"          {variables[SemanticKey('UV', 0)]},",
            f"          {variables[SemanticKey('NORMAL', 0)]},",
            f"          {variables[SemanticKey('TANGENT', 0)]},",
            f"          {variables[SemanticKey('BITANGENT', 0)]},",
            f"          {variables[SemanticKey('SV_ISFRONTFACE', 0)]} != 0);",
        ]
    lines.extend((
        "  WriteMainPartEarlyGForward(",
        f"      result, {variables[SemanticKey('SV_TARGET', 0)]},",
        f"      {variables[SemanticKey('SV_TARGET', 1)]});",
    ))
    phase = f"#define MAIN_PART_EARLY_GFORWARD_{mode.upper()}_PHASE 1"
    return (
        f"early_gforward_{mode}",
        prefix + "\n\n" + phase
        + '\n#include "include/main_part_early_gforward.hlsl"\n\n'
        + signature + "\n{\n" + "\n".join(lines) + "\n}\n",
    )
