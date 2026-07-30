"""Typed, composable pixel families for ``main_part`` permutations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .common import replace_cbuffer_with_include
from .main_part_families import SemanticKey, parse_entry_signature


GBUFFER_BASE_DEFINES = frozenset({
    "PIXEL_SHADER",
    "PS_PERM_GBUFFER",
    "TRANSFER_COLOR",
    "TRANSFER_NORMAL",
    "TRANSFER_UV0",
    "TRANSFER_VIEW_POSITION",
})


@dataclass(frozen=True)
class MainPartGBufferFamily:
    asg: bool = False
    normal_map: bool = False
    alpha_cutoff: bool = False
    alpha_marker: bool = False
    ao_texture: bool = False
    flip_backface: bool = False
    light_cap: str | None = None
    mat_cap_diffuse: bool = False
    directional_map_diffuse: bool = False
    diffuse_uv1: bool = False
    vertex_occlusion: bool = False
    accent_color_passthrough: bool = False
    global_pulse: bool = False
    mat_cap_masked: str | None = None
    dissolve_uv: int | None = None

    @property
    def name(self) -> str:
        suffixes = []
        if self.alpha_cutoff:
            suffixes.append("alpha_cutoff")
        if self.ao_texture:
            suffixes.append("ao")
        if self.asg:
            suffixes.append("asg")
        if self.normal_map:
            suffixes.append("normal")
        if self.flip_backface:
            suffixes.append("flip_backface")
        if self.light_cap is not None:
            suffixes.append(self.light_cap)
        if self.mat_cap_diffuse:
            suffixes.append("mat_cap_diffuse")
        if self.directional_map_diffuse:
            suffixes.append("directional_map_diffuse")
        if self.diffuse_uv1:
            suffixes.append("diffuse_uv1")
        if self.vertex_occlusion:
            suffixes.append("vertex_occlusion")
        if self.accent_color_passthrough:
            suffixes.append("accent_color_passthrough")
        if self.global_pulse:
            suffixes.append("global_pulse")
        if self.mat_cap_masked is not None:
            suffixes.append(self.mat_cap_masked)
        if self.dissolve_uv is not None:
            suffixes.append(f"dissolve_uv{self.dissolve_uv}")
        return "gbuffer_diffuse" + (
            "_" + "_".join(suffixes) if suffixes else ""
        )

    @property
    def defines(self) -> frozenset[str]:
        values = set(GBUFFER_BASE_DEFINES)
        if self.asg:
            values.add("PS_ASG_TEX")
        if self.normal_map:
            values.update({"PS_NOR_TEX", "TRANSFER_TANGENTS"})
        if self.alpha_cutoff:
            values.add("PS_ALPHA_CUTOFF")
        if self.alpha_marker:
            values.add("ALPHA")
        if self.ao_texture:
            values.update({"PS_AO_TEX", "TRANSFER_UV1"})
        if self.flip_backface:
            values.add("PS_FLIP_BACKFACE_NORMALS")
        if self.light_cap == "light_cap":
            values.add("PS_LIGHT_CAP")
        elif self.light_cap == "light_cap_masked":
            values.add("PS_LIGHT_CAP_MASKED")
        if self.mat_cap_diffuse:
            values.add("PS_MAT_CAP_DIF")
        if self.directional_map_diffuse:
            values.add("PS_FBDRF_DIF")
        if self.diffuse_uv1:
            values.update({"PS_DIF_UV1", "TRANSFER_UV1"})
        if self.vertex_occlusion:
            values.add("TRANSFER_OCCLUSION")
        if self.accent_color_passthrough:
            values.add("TRANSFER_ACCENT_COLOR")
        if self.global_pulse:
            values.add("PS_GLOBAL_PULSE")
        if self.mat_cap_masked == "mat_cap_masked":
            values.add("PS_MAT_CAP_MASKED")
        elif self.mat_cap_masked == "mat_cap_masked_glow":
            values.add("PS_MAT_CAP_MASKED_GLOW")
        if self.dissolve_uv is not None:
            values.update({
                f"PS_DISSOLVE_UV{self.dissolve_uv}", "TRANSFER_CUTOFF"
            })
            if self.dissolve_uv == 1:
                values.add("TRANSFER_UV1")
        return frozenset(values)


def classify_main_part_pixel_family(
    defines: Iterable[str], source: str
) -> MainPartGBufferFamily | None:
    values = frozenset(defines)
    if not GBUFFER_BASE_DEFINES <= values:
        return None
    family = MainPartGBufferFamily(
        asg="PS_ASG_TEX" in values,
        normal_map="PS_NOR_TEX" in values,
        alpha_cutoff="PS_ALPHA_CUTOFF" in values,
        alpha_marker="ALPHA" in values,
        ao_texture="PS_AO_TEX" in values,
        flip_backface="PS_FLIP_BACKFACE_NORMALS" in values,
        light_cap=(
            "light_cap_masked" if "PS_LIGHT_CAP_MASKED" in values
            else "light_cap" if "PS_LIGHT_CAP" in values
            else None
        ),
        mat_cap_diffuse="PS_MAT_CAP_DIF" in values,
        directional_map_diffuse="PS_FBDRF_DIF" in values,
        diffuse_uv1="PS_DIF_UV1" in values,
        vertex_occlusion="TRANSFER_OCCLUSION" in values,
        accent_color_passthrough="TRANSFER_ACCENT_COLOR" in values,
        global_pulse="PS_GLOBAL_PULSE" in values,
        mat_cap_masked=(
            "mat_cap_masked_glow" if "PS_MAT_CAP_MASKED_GLOW" in values
            else "mat_cap_masked" if "PS_MAT_CAP_MASKED" in values
            else None
        ),
        dissolve_uv=(
            1 if "PS_DISSOLVE_UV1" in values
            else 0 if "PS_DISSOLVE_UV0" in values
            else None
        ),
    )
    # Every define must be consumed by a known policy. Paired transfer defines
    # are part of their policy's contract, so incomplete or novel feature sets
    # remain mechanical until their semantics are recovered.
    if family.defines != values:
        return None
    if family.alpha_marker and not family.alpha_cutoff:
        return None
    _signature, parameters = parse_entry_signature(source, "commonPS")
    semantics = {parameter.semantic for parameter in parameters}
    required = {
        SemanticKey("UV", 0),
        SemanticKey("NORMAL", 0),
        SemanticKey("VERTEXCOLOR", 0),
        SemanticKey("SV_TARGET", 0),
        SemanticKey("SV_TARGET", 1),
        SemanticKey("SV_TARGET", 2),
    }
    if family.normal_map:
        required.update({SemanticKey("TANGENT", 0), SemanticKey("BITANGENT", 0)})
    if family.ao_texture:
        required.add(SemanticKey("UV", 1))
    if family.diffuse_uv1:
        required.add(SemanticKey("UV", 1))
    if family.vertex_occlusion:
        required.add(SemanticKey("OCCLUSION", 0))
    if family.accent_color_passthrough:
        required.add(SemanticKey("ACCSENTCOLOR", 0))
    if family.dissolve_uv is not None:
        required.add(SemanticKey("CUTOFF", 0))
        if family.dissolve_uv == 1:
            required.add(SemanticKey("UV", 1))
    if family.flip_backface:
        required.add(SemanticKey("SV_ISFRONTFACE", 0))
    if (family.light_cap is not None or family.mat_cap_diffuse
            or family.mat_cap_masked is not None
            or family.directional_map_diffuse):
        required.add(SemanticKey("VIEW_POSITION", 0))
    return family if required <= semantics else None


def lift_main_part_pixel_family(
    defines: Iterable[str], source: str
) -> tuple[str, str] | None:
    family = classify_main_part_pixel_family(defines, source)
    if family is None:
        return None
    signature, parameters = parse_entry_signature(source, "commonPS")
    variables = {parameter.semantic: parameter.variable for parameter in parameters}
    if (family.directional_map_diffuse or family.global_pulse
            or family.dissolve_uv is not None):
        source = replace_cbuffer_with_include(
            source, "CB_PERFRAME", "main_part_perframe_abi.hlsl"
        )
    if family.dissolve_uv is not None:
        source = replace_cbuffer_with_include(
            source, "CB_DISSOLVE", "main_part_dissolve_b0_abi.hlsl"
        )
    source = replace_cbuffer_with_include(
        source, "CB_PROJECTION", "main_part_projection_abi.hlsl"
    )
    signature_start = source.index("void commonPS(")
    marker = source.find("// 3Dmigoto declarations")
    if marker >= 0:
        prefix = source[:marker].rstrip()
    else:
        prefix = source[:signature_start].rstrip()

    uv = variables[SemanticKey("UV", 0)]
    diffuse_uv = (
        variables[SemanticKey("UV", 1)] if family.diffuse_uv1 else uv
    )
    normal = variables[SemanticKey("NORMAL", 0)]
    color = variables[SemanticKey("VERTEXCOLOR", 0)]
    normal_expression = normal
    lighting_normal_expression = normal
    lines: list[str] = []
    # ASG-enabled cutouts use the ASG red channel; diffuse-only cutouts use
    # diffuse alpha. Keep each sampled value alive so no texture is read twice.
    if family.asg:
        lines.append(f"  float4 asgSample = SampleMainPartGBufferAsg({uv});")
    if family.alpha_cutoff and family.asg:
        lines.append("  ApplyMainPartGBufferAlphaCutoff(asgSample.x);")
    if family.dissolve_uv is not None:
        dissolve_uv = variables[SemanticKey("UV", family.dissolve_uv)]
        cutoff = variables[SemanticKey("CUTOFF", 0)]
        lines.extend((
            "  MainPartSurfaceDissolveBand dissolve =",
            f"      EvaluateMainPartSurfaceDissolveBand({dissolve_uv}, {cutoff});",
            "  ApplyMainPartSurfaceDissolveWindow(dissolve);",
        ))
    if family.flip_backface and not family.normal_map:
        front_face = variables[SemanticKey("SV_ISFRONTFACE", 0)]
        lines.extend((
            "  float3 orientedNormal = OrientMainPartGBufferNormal(",
            f"      {normal}, {front_face} != 0);",
        ))
        normal_expression = "orientedNormal"
    if family.alpha_cutoff and not family.asg:
        lines.extend((
            f"  float4 diffuseSample = SampleMainPartGBufferDiffuse({diffuse_uv});",
            "  ApplyMainPartGBufferAlphaCutoff(diffuseSample.w);",
            "  MainPartGBuffer surface = EvaluateMainPartGBufferDiffuseSample(",
            f"      diffuseSample, {normal_expression}, {color});",
        ))
    else:
        lines.extend((
            "  MainPartGBuffer surface = EvaluateMainPartGBufferDiffuse(",
            f"      {diffuse_uv}, {normal_expression}, {color});",
        ))
    if family.ao_texture:
        uv1 = variables[SemanticKey("UV", 1)]
        lines.append(f"  ApplyMainPartGBufferAo({uv1}, surface);")
    if family.asg:
        lines.extend((
            "  ApplyMainPartGBufferAsgSample(",
            f"      asgSample, {color}.w, surface);",
        ))
    if family.normal_map:
        tangent = variables[SemanticKey("TANGENT", 0)]
        bitangent = variables[SemanticKey("BITANGENT", 0)]
        lines.extend((
            "  float3 mappedNormal = EvaluateMainPartGBufferNormalMap(",
            f"      {uv}, {normal}, {tangent}, {bitangent});",
        ))
        if family.flip_backface:
            front_face = variables[SemanticKey("SV_ISFRONTFACE", 0)]
            lines.extend((
                "  mappedNormal = OrientMainPartGBufferNormal(",
                f"      mappedNormal, {front_face} != 0);",
            ))
        lines.extend((
            "  surface.encodedNormal =",
            "      EncodeMainPartOctahedralNormal(mappedNormal);",
        ))
        lighting_normal_expression = "mappedNormal"
    if family.light_cap is not None:
        view_position = variables[SemanticKey("VIEW_POSITION", 0)]
        masked = "true" if family.light_cap == "light_cap_masked" else "false"
        lines.extend((
            "  ApplyMainPartGBufferLightCap(",
            f"      {view_position}, {lighting_normal_expression}, {masked}, surface);",
        ))
    if family.mat_cap_diffuse:
        view_position = variables[SemanticKey("VIEW_POSITION", 0)]
        lines.extend((
            "  ApplyMainPartGBufferMatCapDiffuse(",
            f"      {view_position}, {lighting_normal_expression}, {color}, surface);",
        ))
    if family.directional_map_diffuse:
        view_position = variables[SemanticKey("VIEW_POSITION", 0)]
        lines.extend((
            "  ApplyMainPartGBufferDirectionalMapDiffuse(",
            f"      {view_position}, {lighting_normal_expression}, {color}, surface);",
        ))
    if family.mat_cap_masked is not None:
        view_position = variables[SemanticKey("VIEW_POSITION", 0)]
        preserve_glow = (
            "true" if family.mat_cap_masked == "mat_cap_masked_glow"
            else "false"
        )
        lines.extend((
            "  ApplyMainPartGBufferMaskedMatCap(",
            f"      {view_position}, {lighting_normal_expression}, {preserve_glow}, surface);",
        ))
    if family.dissolve_uv is not None:
        lines.append("  ApplyMainPartGBufferDissolve(dissolve.fade, surface);")
    if family.vertex_occlusion:
        occlusion = variables[SemanticKey("OCCLUSION", 0)]
        lines.append(f"  ApplyMainPartGBufferVertexOcclusion({occlusion}, surface);")
    if family.global_pulse:
        lines.append("  ApplyMainPartGBufferGlobalPulse(surface);")
    lines.extend((
        "  WriteMainPartGBuffer(",
        "      surface,",
        f"      {variables[SemanticKey('SV_TARGET', 0)]},",
        f"      {variables[SemanticKey('SV_TARGET', 1)]},",
        f"      {variables[SemanticKey('SV_TARGET', 2)]});",
    ))
    phase_defines = ["#define MAIN_PART_GBUFFER_PHASED 1"]
    if family.asg:
        phase_defines.append("#define MAIN_PART_GBUFFER_ASG_PHASE 1")
    if family.normal_map:
        phase_defines.append("#define MAIN_PART_GBUFFER_NORMAL_PHASE 1")
    if family.alpha_cutoff:
        phase_defines.append("#define MAIN_PART_GBUFFER_ALPHA_CUTOFF_PHASE 1")
    if family.ao_texture:
        phase_defines.append("#define MAIN_PART_GBUFFER_AO_PHASE 1")
    if family.flip_backface:
        phase_defines.append(
            "#define MAIN_PART_GBUFFER_FACE_ORIENTATION_PHASE 1"
        )
    if family.light_cap is not None:
        phase_defines.append("#define MAIN_PART_GBUFFER_LIGHT_CAP_PHASE 1")
    if family.mat_cap_diffuse:
        phase_defines.append("#define MAIN_PART_GBUFFER_MAT_CAP_DIFFUSE_PHASE 1")
    if family.directional_map_diffuse:
        phase_defines.append(
            "#define MAIN_PART_GBUFFER_DIRECTIONAL_MAP_DIFFUSE_PHASE 1"
        )
    if family.mat_cap_masked is not None:
        phase_defines.append("#define MAIN_PART_GBUFFER_MASKED_MAT_CAP_PHASE 1")
    if family.vertex_occlusion:
        phase_defines.append("#define MAIN_PART_GBUFFER_VERTEX_OCCLUSION_PHASE 1")
    if family.global_pulse:
        phase_defines.append("#define MAIN_PART_GBUFFER_GLOBAL_PULSE_PHASE 1")
    if family.dissolve_uv is not None:
        phase_defines.append("#define MAIN_PART_GBUFFER_DISSOLVE_PHASE 1")
    lifted = (
        prefix
        + "\n\n"
        + "\n".join(phase_defines)
        + '\n#include "include/main_part_gbuffer.hlsl"\n\n'
        + signature
        + "\n{\n"
        + "\n".join(lines)
        + "\n}\n"
    )
    return family.name, lifted
