"""Directional-map standard-glass transparent-surface graph template."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..main_part_graph_codegen import (
    AbiIncludeRule,
    GraphEntrySpecification,
    PolicyAxis,
    render_main_part_graph_entry,
)
from .main_part_families import SemanticKey, parse_entry_signature


BASE_DEFINES = frozenset({
    "PIXEL_SHADER", "PS_ASG_TEX", "PS_FBDRF_DIF", "PS_GLASS",
    "PS_PERM_TRANSPARANT_SURFACE", "TRANSFER_COLOR",
    "TRANSFER_FOG_COLOR", "TRANSFER_NORMAL", "TRANSFER_SCREEN_UV",
    "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
})


@dataclass(frozen=True)
class MainPartDirectionalGlassSurface:
    quality: str
    reflection: str

    @property
    def defines(self) -> frozenset[str]:
        values = set(BASE_DEFINES)
        if self.quality != "default":
            values.add(f"PS_SHADER_QUALITY_{self.quality.upper()}")
        values.add(f"PS_REFLECTION_{self.reflection.upper()}")
        return frozenset(values)

    @property
    def name(self) -> str:
        return f"directional_glass_surface_{self.quality}_{self.reflection}"


DIRECTIONAL_GLASS_SURFACES = tuple(
    MainPartDirectionalGlassSurface(quality, reflection)
    for quality in ("default", "medium", "high")
    for reflection in ("multi", "off", "single")
)


DIRECTIONAL_GLASS_ENTRY = GraphEntrySpecification(
    name="directional_glass_surface",
    include_asset="main_part_directional_glass_surface.hlsl",
    evaluator="EvaluateMainPartDirectionalGlassSurface",
    semantics=(
        SemanticKey("SV_POSITION", 0), SemanticKey("VIEW_POSITION", 0),
        SemanticKey("UV", 0), SemanticKey("NORMAL", 0),
        SemanticKey("VERTEXCOLOR", 0), SemanticKey("SCREEN_UV", 0),
        SemanticKey("FOG_COLOR", 0), SemanticKey("SV_ISFRONTFACE", 0),
        SemanticKey("SV_TARGET", 0), SemanticKey("SV_TARGET", 1),
    ),
    axes=(
        PolicyAxis("quality", {
            "default": None,
            "medium": "MAIN_PART_DIRECTIONAL_GLASS_QUALITY_MEDIUM",
            "high": "MAIN_PART_DIRECTIONAL_GLASS_QUALITY_HIGH",
        }),
        PolicyAxis("reflection", {
            "multi": "MAIN_PART_DIRECTIONAL_GLASS_REFLECTION_MULTI",
            "off": "MAIN_PART_DIRECTIONAL_GLASS_REFLECTION_OFF",
            "single": "MAIN_PART_DIRECTIONAL_GLASS_REFLECTION_SINGLE",
        }),
    ),
    abi_includes=(
        AbiIncludeRule("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        AbiIncludeRule("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        AbiIncludeRule("CB_GLASS", "main_part_glass_abi.hlsl"),
        AbiIncludeRule(
            "Cluster", "main_part_cluster_abi.hlsl",
            (("quality", frozenset({"medium", "high"})),),
        ),
        AbiIncludeRule(
            "LightProps", "main_part_lightprops_abi.hlsl",
            (("quality", frozenset({"medium", "high"})),),
        ),
        AbiIncludeRule(
            "CB_REFLECTIONS", "main_part_reflections_abi.hlsl",
            (
                ("quality", frozenset({"medium", "high"})),
                ("reflection", frozenset({"multi"})),
            ),
        ),
    ),
)


def classify_main_part_directional_glass_surface(
    defines: Iterable[str], source: str,
) -> MainPartDirectionalGlassSurface | None:
    values = frozenset(defines)
    family = next(
        (candidate for candidate in DIRECTIONAL_GLASS_SURFACES
         if candidate.defines == values),
        None,
    )
    if family is None:
        return None
    _signature, parameters = parse_entry_signature(source, "commonPS")
    semantics = {parameter.semantic for parameter in parameters}
    required = {
        SemanticKey("SV_POSITION", 0), SemanticKey("VIEW_POSITION", 0),
        SemanticKey("UV", 0), SemanticKey("NORMAL", 0),
        SemanticKey("VERTEXCOLOR", 0), SemanticKey("SCREEN_UV", 0),
        SemanticKey("FOG_COLOR", 0), SemanticKey("SV_ISFRONTFACE", 0),
        SemanticKey("SV_TARGET", 0), SemanticKey("SV_TARGET", 1),
    }
    return family if required <= semantics else None


def lift_main_part_directional_glass_surface(
    defines: Iterable[str], source: str,
) -> tuple[str, str] | None:
    family = classify_main_part_directional_glass_surface(defines, source)
    if family is None:
        return None

    lifted = render_main_part_graph_entry(
        DIRECTIONAL_GLASS_ENTRY,
        {"quality": family.quality, "reflection": family.reflection},
        source,
    )
    return family.name, lifted
