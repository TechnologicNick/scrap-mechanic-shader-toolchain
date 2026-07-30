"""Policy-driven transparent-surface families for ``main_part`` shaders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .common import replace_cbuffer_with_include
from .main_part_families import SemanticKey, parse_entry_signature


GLASS_SURFACE_BASE_DEFINES = frozenset({
    "PIXEL_SHADER",
    "PS_ASG_TEX",
    "PS_GLASS",
    "PS_PERM_TRANSPARANT_SURFACE",
    "PS_REFRACTION",
    "TRANSFER_COLOR",
    "TRANSFER_FOG_COLOR",
    "TRANSFER_NORMAL",
    "TRANSFER_SCREEN_UV",
    "TRANSFER_UV0",
    "TRANSFER_VIEW_POSITION",
})


@dataclass(frozen=True)
class MainPartGlassSurfaceFamily:
    quality: str
    reflection: str
    dissolve_uv: int | None
    alpha_cutoff: bool
    depth_blur: bool
    flip_backface_normals: bool
    normal_map: bool
    responsive_glow: bool
    transmission: bool
    tangent_frame: bool
    cutoff_transfer: bool

    @property
    def name(self) -> str:
        dissolve = (
            "plain" if self.dissolve_uv is None
            else f"dissolve_uv{self.dissolve_uv}"
        )
        cutout = "" if self.alpha_cutoff else "_no_cutout"
        return (
            f"glass_surface_{self.quality}_{self.reflection}_{dissolve}"
            f"{cutout}"
        )

    @property
    def defines(self) -> frozenset[str]:
        values = set(GLASS_SURFACE_BASE_DEFINES)
        if self.quality != "low":
            values.add(f"PS_SHADER_QUALITY_{self.quality.upper()}")
        values.add(f"PS_REFLECTION_{self.reflection.upper()}")
        if self.dissolve_uv is not None:
            values.add(f"PS_DISSOLVE_UV{self.dissolve_uv}")
        if self.alpha_cutoff:
            values.add("PS_ALPHA_CUTOFF")
        if self.depth_blur:
            values.add("PS_DEPTH_BLUR_DISTANCE")
        if self.flip_backface_normals:
            values.add("PS_FLIP_BACKFACE_NORMALS")
        if self.normal_map:
            values.add("PS_NOR_TEX")
        if self.responsive_glow:
            values.add("PS_RESPONSIVE_GLOW")
        if self.transmission:
            values.add("PS_TRANSMISSION")
        if self.tangent_frame:
            values.add("TRANSFER_TANGENTS")
        if self.cutoff_transfer:
            values.add("TRANSFER_CUTOFF")
        return frozenset(values)


MEDIUM_MULTI_DISSOLVE = MainPartGlassSurfaceFamily(
    quality="medium",
    reflection="multi",
    dissolve_uv=0,
    alpha_cutoff=True,
    depth_blur=True,
    flip_backface_normals=True,
    normal_map=True,
    responsive_glow=True,
    transmission=True,
    tangent_frame=True,
    cutoff_transfer=True,
)

LOW_MULTI_DISSOLVE = MainPartGlassSurfaceFamily(
    quality="low",
    reflection="multi",
    dissolve_uv=0,
    alpha_cutoff=True,
    depth_blur=True,
    flip_backface_normals=True,
    normal_map=True,
    responsive_glow=True,
    transmission=True,
    tangent_frame=True,
    cutoff_transfer=True,
)

LOW_MULTI_PLAIN = MainPartGlassSurfaceFamily(
    quality="low",
    reflection="multi",
    dissolve_uv=None,
    alpha_cutoff=True,
    depth_blur=True,
    flip_backface_normals=True,
    normal_map=True,
    responsive_glow=True,
    transmission=True,
    tangent_frame=True,
    cutoff_transfer=False,
)

MEDIUM_MULTI_PLAIN = MainPartGlassSurfaceFamily(
    quality="medium",
    reflection="multi",
    dissolve_uv=None,
    alpha_cutoff=True,
    depth_blur=True,
    flip_backface_normals=True,
    normal_map=True,
    responsive_glow=True,
    transmission=True,
    tangent_frame=True,
    cutoff_transfer=False,
)

LOW_OFF_DISSOLVE = MainPartGlassSurfaceFamily(
    quality="low",
    reflection="off",
    dissolve_uv=0,
    alpha_cutoff=True,
    depth_blur=True,
    flip_backface_normals=True,
    normal_map=True,
    responsive_glow=True,
    transmission=True,
    tangent_frame=True,
    cutoff_transfer=True,
)

LOW_OFF_PLAIN = MainPartGlassSurfaceFamily(
    quality="low",
    reflection="off",
    dissolve_uv=None,
    alpha_cutoff=True,
    depth_blur=True,
    flip_backface_normals=True,
    normal_map=True,
    responsive_glow=True,
    transmission=True,
    tangent_frame=True,
    cutoff_transfer=False,
)

LOW_SINGLE_DISSOLVE = MainPartGlassSurfaceFamily(
    quality="low", reflection="single", dissolve_uv=0,
    alpha_cutoff=True, depth_blur=True, flip_backface_normals=True,
    normal_map=True, responsive_glow=True, transmission=True,
    tangent_frame=True, cutoff_transfer=True,
)

LOW_SINGLE_PLAIN = MainPartGlassSurfaceFamily(
    quality="low", reflection="single", dissolve_uv=None,
    alpha_cutoff=True, depth_blur=True, flip_backface_normals=True,
    normal_map=True, responsive_glow=True, transmission=True,
    tangent_frame=True, cutoff_transfer=False,
)

MEDIUM_OFF_DISSOLVE = MainPartGlassSurfaceFamily(
    quality="medium", reflection="off", dissolve_uv=0,
    alpha_cutoff=True, depth_blur=True, flip_backface_normals=True,
    normal_map=True, responsive_glow=True, transmission=True,
    tangent_frame=True, cutoff_transfer=True,
)

MEDIUM_OFF_PLAIN = MainPartGlassSurfaceFamily(
    quality="medium", reflection="off", dissolve_uv=None,
    alpha_cutoff=True, depth_blur=True, flip_backface_normals=True,
    normal_map=True, responsive_glow=True, transmission=True,
    tangent_frame=True, cutoff_transfer=False,
)

MEDIUM_SINGLE_DISSOLVE = MainPartGlassSurfaceFamily(
    quality="medium", reflection="single", dissolve_uv=0,
    alpha_cutoff=True, depth_blur=True, flip_backface_normals=True,
    normal_map=True, responsive_glow=True, transmission=True,
    tangent_frame=True, cutoff_transfer=True,
)

MEDIUM_SINGLE_PLAIN = MainPartGlassSurfaceFamily(
    quality="medium", reflection="single", dissolve_uv=None,
    alpha_cutoff=True, depth_blur=True, flip_backface_normals=True,
    normal_map=True, responsive_glow=True, transmission=True,
    tangent_frame=True, cutoff_transfer=False,
)

LOW_MULTI_NO_CUTOUT = MainPartGlassSurfaceFamily(
    quality="low", reflection="multi", dissolve_uv=None,
    alpha_cutoff=False, depth_blur=True, flip_backface_normals=True,
    normal_map=True, responsive_glow=True, transmission=True,
    tangent_frame=True, cutoff_transfer=False,
)
LOW_OFF_NO_CUTOUT = MainPartGlassSurfaceFamily(
    quality="low", reflection="off", dissolve_uv=None,
    alpha_cutoff=False, depth_blur=True, flip_backface_normals=True,
    normal_map=True, responsive_glow=True, transmission=True,
    tangent_frame=True, cutoff_transfer=False,
)
LOW_SINGLE_NO_CUTOUT = MainPartGlassSurfaceFamily(
    quality="low", reflection="single", dissolve_uv=None,
    alpha_cutoff=False, depth_blur=True, flip_backface_normals=True,
    normal_map=True, responsive_glow=True, transmission=True,
    tangent_frame=True, cutoff_transfer=False,
)
MEDIUM_MULTI_NO_CUTOUT = MainPartGlassSurfaceFamily(
    quality="medium", reflection="multi", dissolve_uv=None,
    alpha_cutoff=False, depth_blur=True, flip_backface_normals=True,
    normal_map=True, responsive_glow=True, transmission=True,
    tangent_frame=True, cutoff_transfer=False,
)
MEDIUM_OFF_NO_CUTOUT = MainPartGlassSurfaceFamily(
    quality="medium", reflection="off", dissolve_uv=None,
    alpha_cutoff=False, depth_blur=True, flip_backface_normals=True,
    normal_map=True, responsive_glow=True, transmission=True,
    tangent_frame=True, cutoff_transfer=False,
)
MEDIUM_SINGLE_NO_CUTOUT = MainPartGlassSurfaceFamily(
    quality="medium", reflection="single", dissolve_uv=None,
    alpha_cutoff=False, depth_blur=True, flip_backface_normals=True,
    normal_map=True, responsive_glow=True, transmission=True,
    tangent_frame=True, cutoff_transfer=False,
)

GLASS_SURFACE_FAMILIES = (
    MEDIUM_MULTI_DISSOLVE,
    LOW_MULTI_DISSOLVE,
    LOW_MULTI_PLAIN,
    MEDIUM_MULTI_PLAIN,
    LOW_OFF_DISSOLVE,
    LOW_OFF_PLAIN,
    LOW_SINGLE_DISSOLVE,
    LOW_SINGLE_PLAIN,
    MEDIUM_OFF_DISSOLVE,
    MEDIUM_OFF_PLAIN,
    MEDIUM_SINGLE_DISSOLVE,
    MEDIUM_SINGLE_PLAIN,
    LOW_MULTI_NO_CUTOUT,
    LOW_OFF_NO_CUTOUT,
    LOW_SINGLE_NO_CUTOUT,
    MEDIUM_MULTI_NO_CUTOUT,
    MEDIUM_OFF_NO_CUTOUT,
    MEDIUM_SINGLE_NO_CUTOUT,
)


def classify_main_part_glass_surface_family(
    defines: Iterable[str], source: str
) -> MainPartGlassSurfaceFamily | None:
    values = frozenset(defines)
    # Only policies with a recovered backend are admitted. Adding another
    # permutation means adding its policy and evaluator, not a shader hash.
    family = next(
        (candidate for candidate in GLASS_SURFACE_FAMILIES
         if values == candidate.defines),
        None,
    )
    if family is None:
        return None

    _signature, parameters = parse_entry_signature(source, "commonPS")
    semantics = {parameter.semantic for parameter in parameters}
    required = {
        SemanticKey("SV_POSITION", 0),
        SemanticKey("VIEW_POSITION", 0),
        SemanticKey("UV", 0),
        SemanticKey("NORMAL", 0),
        SemanticKey("TANGENT", 0),
        SemanticKey("BITANGENT", 0),
        SemanticKey("VERTEXCOLOR", 0),
        SemanticKey("SCREEN_UV", 0),
        SemanticKey("FOG_COLOR", 0),
        SemanticKey("SV_ISFRONTFACE", 0),
        SemanticKey("SV_TARGET", 0),
        SemanticKey("SV_TARGET", 1),
    }
    if family.cutoff_transfer:
        required.add(SemanticKey("CUTOFF", 0))
    return family if required <= semantics else None


def lift_main_part_glass_surface_family(
    defines: Iterable[str], source: str
) -> tuple[str, str] | None:
    family = classify_main_part_glass_surface_family(defines, source)
    if family is None:
        return None

    signature, parameters = parse_entry_signature(source, "commonPS")
    variables = {parameter.semantic: parameter.variable for parameter in parameters}
    common_cbuffers = (
        ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
        ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ("CB_GLASS", "main_part_glass_abi.hlsl"),
    )
    dissolve_cbuffers = (
        (("CB_DISSOLVE", "main_part_dissolve_abi.hlsl"),)
        if family.dissolve_uv is not None else ()
    )
    reflection_cbuffers = (
        (("CB_REFLECTIONS", "main_part_reflections_abi.hlsl"),)
        if family.quality == "medium" and family.reflection == "multi"
        else ()
    )
    medium_cbuffers = (
        ("Cluster", "main_part_cluster_abi.hlsl"),
        ("LightProps", "main_part_lightprops_abi.hlsl"),
    ) if family.quality == "medium" else ()
    for cbuffer, filename in (
        *common_cbuffers, *dissolve_cbuffers,
        *reflection_cbuffers, *medium_cbuffers
    ):
        source = replace_cbuffer_with_include(source, cbuffer, filename)

    marker = source.find("// 3Dmigoto declarations")
    prefix = source[:marker].rstrip()
    argument_semantics = [
        SemanticKey("SV_POSITION", 0),
        SemanticKey("VIEW_POSITION", 0),
        SemanticKey("UV", 0),
        SemanticKey("NORMAL", 0),
        SemanticKey("TANGENT", 0),
        SemanticKey("BITANGENT", 0),
        SemanticKey("VERTEXCOLOR", 0),
        SemanticKey("SCREEN_UV", 0),
        SemanticKey("FOG_COLOR", 0),
    ]
    if family.cutoff_transfer:
        argument_semantics.append(SemanticKey("CUTOFF", 0))
    argument_semantics.extend((
        SemanticKey("SV_ISFRONTFACE", 0),
        SemanticKey("SV_TARGET", 0),
        SemanticKey("SV_TARGET", 1),
    ))
    argument_values = [variables[key] for key in argument_semantics]
    if family.quality == "medium" and not family.cutoff_transfer:
        # The shared medium backend keeps a stable call ABI; the cutoff value
        # is compile-time dead when the plain material frontend is selected.
        argument_values.insert(9, "0.0")
    arguments = ", ".join(argument_values)
    if not family.alpha_cutoff and family.quality == "medium":
        evaluator = "EvaluateMainPartGlassSurfaceMedium"
        reflection_suffix = (
            "" if family.reflection == "multi"
            else f"_{family.reflection}"
        )
        asset = (
            "main_part_glass_surface_medium"
            f"{reflection_suffix}_no_cutout.hlsl"
        )
    elif not family.alpha_cutoff:
        evaluator_suffix = {
            "multi": "",
            "off": "Off",
            "single": "Single",
        }[family.reflection]
        evaluator = f"EvaluateMainPartGlassSurfaceLow{evaluator_suffix}NoCutout"
        reflection_suffix = (
            "" if family.reflection == "multi"
            else f"_{family.reflection}"
        )
        asset = (
            "main_part_glass_surface_low"
            f"{reflection_suffix}_no_cutout.hlsl"
        )
    elif family.quality == "medium":
        evaluator = "EvaluateMainPartGlassSurfaceMedium"
        suffix = (
            "_dissolve" if family.dissolve_uv is not None else ""
        )
        reflection_suffix = (
            "" if family.reflection == "multi"
            else f"_{family.reflection}"
        )
        asset = (
            "main_part_glass_surface_medium"
            f"{reflection_suffix}{suffix}.hlsl"
        )
    elif family.reflection == "single":
        evaluator = "EvaluateMainPartGlassSurfaceLowSingle"
        asset = (
            "main_part_glass_surface_low_single_dissolve.hlsl"
            if family.dissolve_uv is not None
            else "main_part_glass_surface_low_single.hlsl"
        )
    elif family.dissolve_uv is not None:
        evaluator = "EvaluateMainPartDissolveGlassSurfaceLow"
        asset = "main_part_glass_surface_low_dissolve.hlsl"
    else:
        evaluator = "EvaluateMainPartGlassSurfaceLow"
        asset = "main_part_glass_surface_low.hlsl"
    body = (
        "{\n"
        f"  {evaluator}(\n"
        f"      {arguments});\n"
        "}\n"
    )
    lifted = (
        prefix
        + f'\n\n#include "include/{asset}"\n\n'
        + signature
        + "\n"
        + body
    )
    return family.name, lifted
