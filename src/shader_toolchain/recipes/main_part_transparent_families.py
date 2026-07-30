"""Typed transparent pixel families for ``main_part`` permutations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .common import replace_cbuffer_with_include
from .main_part_families import SemanticKey, parse_entry_signature


TRANSPARENT_BEHIND_BASE_DEFINES = frozenset({
    "PIXEL_SHADER",
    "PS_ASG_TEX",
    "PS_GLASS",
    "PS_PERM_TRANSPARANT_BEHIND",
    "TRANSFER_COLOR",
    "TRANSFER_FOG_COLOR",
    "TRANSFER_NORMAL",
    "TRANSFER_SCREEN_UV",
    "TRANSFER_UV0",
    "TRANSFER_VIEW_POSITION",
})


@dataclass(frozen=True)
class MainPartTransparentBehindFamily:
    material_model: str
    reflection_model: str

    @property
    def name(self) -> str:
        return (
            f"transparent_behind_{self.material_model}_"
            f"reflection_{self.reflection_model}"
        )

    @property
    def defines(self) -> frozenset[str]:
        values = set(TRANSPARENT_BEHIND_BASE_DEFINES)
        if self.material_model == "light_cap":
            values.add("PS_LIGHT_CAP")
        if self.reflection_model == "off":
            values.add("PS_REFLECTION_OFF")
        return frozenset(values)


def classify_main_part_transparent_family(
    defines: Iterable[str], source: str
) -> MainPartTransparentBehindFamily | None:
    values = frozenset(defines)
    if not TRANSPARENT_BEHIND_BASE_DEFINES <= values:
        return None
    family = MainPartTransparentBehindFamily(
        material_model="light_cap" if "PS_LIGHT_CAP" in values else "",
        reflection_model="off" if "PS_REFLECTION_OFF" in values else "",
    )
    if family.defines != values:
        return None
    _signature, parameters = parse_entry_signature(source, "commonPS")
    semantics = {parameter.semantic for parameter in parameters}
    required = {
        SemanticKey("VIEW_POSITION", 0),
        SemanticKey("UV", 0),
        SemanticKey("NORMAL", 0),
        SemanticKey("VERTEXCOLOR", 0),
        SemanticKey("SCREEN_UV", 0),
        SemanticKey("FOG_COLOR", 0),
        SemanticKey("SV_ISFRONTFACE", 0),
        SemanticKey("SV_TARGET", 0),
        SemanticKey("SV_TARGET", 1),
    }
    return family if required <= semantics else None


def lift_main_part_transparent_family(
    defines: Iterable[str], source: str
) -> tuple[str, str] | None:
    family = classify_main_part_transparent_family(defines, source)
    if family is None:
        return None
    signature, parameters = parse_entry_signature(source, "commonPS")
    variables = {parameter.semantic: parameter.variable for parameter in parameters}
    for cbuffer, filename in (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_GLASS", "main_part_glass_abi.hlsl"),
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)
    marker = source.find("// 3Dmigoto declarations")
    prefix = source[:marker].rstrip()

    view_position = variables[SemanticKey("VIEW_POSITION", 0)]
    uv = variables[SemanticKey("UV", 0)]
    normal = variables[SemanticKey("NORMAL", 0)]
    color = variables[SemanticKey("VERTEXCOLOR", 0)]
    screen_uv = variables[SemanticKey("SCREEN_UV", 0)]
    front_face = variables[SemanticKey("SV_ISFRONTFACE", 0)]
    output0 = variables[SemanticKey("SV_TARGET", 0)]
    output1 = variables[SemanticKey("SV_TARGET", 1)]
    body = f'''{{
  RejectMainPartBehindOpaqueDepth({screen_uv});
  MainPartBehindGlassMaterial material =
      EvaluateMainPartBehindLightCapMaterial(
          {view_position}, {uv}, {normal}, {color});
  MainPartBehindDirectionalLighting lighting =
      EvaluateMainPartBehindDirectionalLighting(
          {view_position}, material);
  MainPartBehindGlassComposite composite = ComposeMainPartBehindGlass(
      {screen_uv}.z, {front_face} != 0, material, lighting);
  WriteMainPartBehindGlass(composite, {output0}, {output1});
}}
'''
    lifted = (
        prefix
        + '\n\n#include "include/main_part_glass_behind_light_cap.hlsl"\n\n'
        + signature
        + "\n"
        + body
    )
    return family.name, lifted
