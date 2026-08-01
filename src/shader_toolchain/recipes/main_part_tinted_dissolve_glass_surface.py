"""Tinted UV1-dissolve glass as one quality x reflection graph family."""

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
    "PIXEL_SHADER", "PS_ALPHA_CUTOFF", "PS_ASG_TEX",
    "PS_DISSOLVE_UV1", "PS_FLIP_BACKFACE_NORMALS", "PS_GLASS",
    "PS_LEGACY_GLASS", "PS_NOR_TEX", "PS_PERM_TRANSPARANT_SURFACE",
    "PS_REFRACTION", "PS_TRANSPARENT_TINTED", "TRANSFER_COLOR",
    "TRANSFER_CUTOFF", "TRANSFER_FOG_COLOR", "TRANSFER_NORMAL",
    "TRANSFER_SCREEN_UV", "TRANSFER_TANGENTS", "TRANSFER_UV0",
    "TRANSFER_UV1", "TRANSFER_VIEW_POSITION",
})


@dataclass(frozen=True)
class MainPartTintedDissolveGlassSurface:
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
        return f"tinted_dissolve_glass_{self.quality}_{self.reflection}"


TINTED_DISSOLVE_GLASS_SURFACES = tuple(
    MainPartTintedDissolveGlassSurface(quality, reflection)
    for quality in ("default", "medium", "high")
    for reflection in ("multi", "off", "single")
)


TINTED_DISSOLVE_GLASS_ENTRY = GraphEntrySpecification(
    name="tinted_dissolve_glass_surface",
    include_asset="main_part_tinted_dissolve_glass_surface.hlsl",
    evaluator="EvaluateMainPartTintedDissolveGlassSurfaceGraph",
    semantics=(
        SemanticKey("SV_POSITION", 0), SemanticKey("VIEW_POSITION", 0),
        SemanticKey("UV", 0), SemanticKey("UV", 1),
        SemanticKey("NORMAL", 0), SemanticKey("TANGENT", 0),
        SemanticKey("BITANGENT", 0), SemanticKey("VERTEXCOLOR", 0),
        SemanticKey("SCREEN_UV", 0), SemanticKey("FOG_COLOR", 0),
        SemanticKey("CUTOFF", 0), SemanticKey("SV_ISFRONTFACE", 0),
        SemanticKey("SV_TARGET", 0), SemanticKey("SV_TARGET", 1),
    ),
    axes=(
        PolicyAxis("quality", {
            "default": None,
            "medium": "MAIN_PART_TINTED_DISSOLVE_QUALITY_MEDIUM",
            "high": "MAIN_PART_TINTED_DISSOLVE_QUALITY_HIGH",
        }),
        PolicyAxis("reflection", {
            "multi": "MAIN_PART_TINTED_DISSOLVE_REFLECTION_MULTI",
            "off": "MAIN_PART_TINTED_DISSOLVE_REFLECTION_OFF",
            "single": "MAIN_PART_TINTED_DISSOLVE_REFLECTION_SINGLE",
        }),
    ),
    abi_includes=(
        AbiIncludeRule("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        AbiIncludeRule("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        AbiIncludeRule("CB_GLASS", "main_part_glass_abi.hlsl"),
        AbiIncludeRule("CB_DISSOLVE", "main_part_dissolve_abi.hlsl"),
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


def classify_main_part_tinted_dissolve_glass_surface(
    defines: Iterable[str], source: str,
) -> MainPartTintedDissolveGlassSurface | None:
    values = frozenset(defines)
    family = next((
        candidate for candidate in TINTED_DISSOLVE_GLASS_SURFACES
        if candidate.defines == values
    ), None)
    if family is None:
        return None
    _signature, parameters = parse_entry_signature(source, "commonPS")
    available = {parameter.semantic for parameter in parameters}
    required = set(TINTED_DISSOLVE_GLASS_ENTRY.semantics)
    return family if required <= available else None


def lift_main_part_tinted_dissolve_glass_surface(
    defines: Iterable[str], source: str,
) -> tuple[str, str] | None:
    family = classify_main_part_tinted_dissolve_glass_surface(defines, source)
    if family is None:
        return None
    lifted = render_main_part_graph_entry(
        TINTED_DISSOLVE_GLASS_ENTRY,
        {"quality": family.quality, "reflection": family.reflection},
        source,
    )
    return family.name, lifted
