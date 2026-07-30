from pathlib import Path

from shader_toolchain.recipes.main_part_pixel_families import (
    classify_main_part_pixel_family,
    lift_main_part_pixel_family,
)
from shader_toolchain.hlsl import module_variants


CORPUS = Path("output/semantic/include/main_part")
ORIGINALS = Path("output/reports/gbuffer-family-originals")


def _source(selector: str) -> str:
    original = ORIGINALS / f"{selector}.hlsl"
    if original.exists():
        return original.read_text(encoding="utf-8")
    semantic = (CORPUS / f"{selector}.hlsl").read_text(encoding="utf-8")
    if "cbuffer CB_PROJECTION" in semantic:
        return semantic
    raw_module = Path("output/hlsl/main_part.hlsl").read_text(encoding="utf-8")
    return module_variants(raw_module)[selector]


def test_classifies_basic_gbuffer_by_features_and_signature():
    source = _source("SM_SHADER_58A90B8A1217EB03")
    defines = {
        "PIXEL_SHADER", "PS_PERM_GBUFFER", "TRANSFER_COLOR",
        "TRANSFER_NORMAL", "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
    }
    family = classify_main_part_pixel_family(defines, source)
    assert family is not None
    assert family.name == "gbuffer_diffuse"


def test_lift_uses_typed_material_phases_not_text_fragments():
    source = _source("SM_SHADER_978E5C9D11471D7E")
    defines = {
        "PIXEL_SHADER", "PS_NOR_TEX", "PS_PERM_GBUFFER",
        "TRANSFER_COLOR", "TRANSFER_NORMAL", "TRANSFER_TANGENTS",
        "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
    }
    result = lift_main_part_pixel_family(defines, source)
    assert result is not None
    name, lifted = result
    assert name == "gbuffer_diffuse_normal"
    assert "EvaluateMainPartGBufferDiffuse" in lifted
    assert "EvaluateMainPartGBufferNormalMap" in lifted
    assert "WriteMainPartGBuffer" in lifted
    assert "3Dmigoto declarations" not in lifted
    assert "../phases/" not in lifted


def test_lift_composes_alpha_cutoff_and_face_orientation_policies():
    source = _source("SM_SHADER_E17D4A3401F8E4EC")
    defines = {
        "ALPHA", "PIXEL_SHADER", "PS_ALPHA_CUTOFF",
        "PS_FLIP_BACKFACE_NORMALS", "PS_PERM_GBUFFER",
        "TRANSFER_COLOR", "TRANSFER_NORMAL", "TRANSFER_UV0",
        "TRANSFER_VIEW_POSITION",
    }
    result = lift_main_part_pixel_family(defines, source)
    assert result is not None
    name, lifted = result
    assert name == "gbuffer_diffuse_alpha_cutoff_flip_backface"
    assert "SampleMainPartGBufferDiffuse" in lifted
    assert "ApplyMainPartGBufferAlphaCutoff" in lifted
    assert "OrientMainPartGBufferNormal" in lifted


def test_lift_composes_ao_policy_using_semantic_uv_mapping():
    source = _source("SM_SHADER_3CDB91514B4EDAAC")
    defines = {
        "PIXEL_SHADER", "PS_AO_TEX", "PS_PERM_GBUFFER",
        "TRANSFER_COLOR", "TRANSFER_NORMAL", "TRANSFER_UV0",
        "TRANSFER_UV1", "TRANSFER_VIEW_POSITION",
    }
    result = lift_main_part_pixel_family(defines, source)
    assert result is not None
    name, lifted = result
    assert name == "gbuffer_diffuse_ao"
    assert "ApplyMainPartGBufferAo(w2, surface)" in lifted


def test_infers_policy_combinations_without_a_permutation_registry():
    source = _source("SM_SHADER_9A9A68C500E1C656")
    defines = {
        "ALPHA", "PIXEL_SHADER", "PS_ALPHA_CUTOFF", "PS_AO_TEX",
        "PS_ASG_TEX", "PS_FLIP_BACKFACE_NORMALS", "PS_NOR_TEX",
        "PS_PERM_GBUFFER", "TRANSFER_COLOR", "TRANSFER_NORMAL",
        "TRANSFER_TANGENTS", "TRANSFER_UV0", "TRANSFER_UV1",
        "TRANSFER_VIEW_POSITION",
    }
    result = lift_main_part_pixel_family(defines, source)
    assert result is not None
    name, lifted = result
    assert name == (
        "gbuffer_diffuse_alpha_cutoff_ao_asg_normal_flip_backface"
    )
    assert "ApplyMainPartGBufferAlphaCutoff(asgSample.x)" in lifted
    assert "mappedNormal = OrientMainPartGBufferNormal" in lifted
    assert "ApplyMainPartGBufferAo(w2, surface)" in lifted


def test_rejects_unrecovered_policy_defines():
    source = _source("SM_SHADER_58A90B8A1217EB03")
    defines = {
        "PIXEL_SHADER", "PS_PERM_GBUFFER", "PS_UNKNOWN_LAYER",
        "TRANSFER_COLOR", "TRANSFER_NORMAL", "TRANSFER_UV0",
        "TRANSFER_VIEW_POSITION",
    }
    assert classify_main_part_pixel_family(defines, source) is None


def test_lift_composes_light_cap_as_a_reusable_material_policy():
    source = _source("SM_SHADER_43B39ECC95452254")
    defines = {
        "PIXEL_SHADER", "PS_ASG_TEX", "PS_LIGHT_CAP", "PS_NOR_TEX",
        "PS_PERM_GBUFFER", "TRANSFER_COLOR", "TRANSFER_NORMAL",
        "TRANSFER_TANGENTS", "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
    }
    result = lift_main_part_pixel_family(defines, source)
    assert result is not None
    name, lifted = result
    assert name == "gbuffer_diffuse_asg_normal_light_cap"
    assert "#define MAIN_PART_GBUFFER_LIGHT_CAP_PHASE 1" in lifted
    assert "ApplyMainPartGBufferLightCap(" in lifted
    assert "v1, mappedNormal, false, surface" in lifted


def test_lift_composes_masked_light_cap_with_cutout():
    source = _source("SM_SHADER_E7C9977B7FB9A76A")
    defines = {
        "PIXEL_SHADER", "PS_ALPHA_CUTOFF", "PS_ASG_TEX",
        "PS_LIGHT_CAP_MASKED", "PS_NOR_TEX", "PS_PERM_GBUFFER",
        "TRANSFER_COLOR", "TRANSFER_NORMAL", "TRANSFER_TANGENTS",
        "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
    }
    result = lift_main_part_pixel_family(defines, source)
    assert result is not None
    name, lifted = result
    assert name == (
        "gbuffer_diffuse_alpha_cutoff_asg_normal_light_cap_masked"
    )
    assert "ApplyMainPartGBufferAlphaCutoff(asgSample.x)" in lifted
    assert "v1, mappedNormal, true, surface" in lifted


def test_lift_reuses_mat_cap_coordinates_as_a_diffuse_sampling_policy():
    source = _source("SM_SHADER_0C0CAA30A2C4AABB")
    defines = {
        "PIXEL_SHADER", "PS_ALPHA_CUTOFF", "PS_ASG_TEX",
        "PS_FLIP_BACKFACE_NORMALS", "PS_MAT_CAP_DIF", "PS_NOR_TEX",
        "PS_PERM_GBUFFER", "TRANSFER_COLOR", "TRANSFER_NORMAL",
        "TRANSFER_TANGENTS", "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
    }
    result = lift_main_part_pixel_family(defines, source)
    assert result is not None
    name, lifted = result
    assert name.endswith("mat_cap_diffuse")
    assert "#define MAIN_PART_GBUFFER_MAT_CAP_DIFFUSE_PHASE 1" in lifted
    assert "ApplyMainPartGBufferMatCapDiffuse(" in lifted
    assert "v1, mappedNormal, v6, surface" in lifted


def test_lift_reuses_directional_map_diffuse_policy():
    source = _source("SM_SHADER_F78FCA1191A456E9")
    defines = {
        "PIXEL_SHADER", "PS_ALPHA_CUTOFF", "PS_ASG_TEX",
        "PS_FBDRF_DIF", "PS_FLIP_BACKFACE_NORMALS", "PS_NOR_TEX",
        "PS_PERM_GBUFFER", "TRANSFER_COLOR", "TRANSFER_NORMAL",
        "TRANSFER_TANGENTS", "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
    }
    result = lift_main_part_pixel_family(defines, source)
    assert result is not None
    name, lifted = result
    assert name.endswith("directional_map_diffuse")
    assert '#include "include/main_part_perframe_abi.hlsl"' in lifted
    assert "ApplyMainPartGBufferDirectionalMapDiffuse(" in lifted
    assert "v1, mappedNormal, v6, surface" in lifted


def test_lift_composes_secondary_uv_occlusion_and_pulse_policies():
    uv1 = lift_main_part_pixel_family({
        "PIXEL_SHADER", "PS_ASG_TEX", "PS_DIF_UV1", "PS_NOR_TEX",
        "PS_PERM_GBUFFER", "TRANSFER_COLOR", "TRANSFER_NORMAL",
        "TRANSFER_TANGENTS", "TRANSFER_UV0", "TRANSFER_UV1",
        "TRANSFER_VIEW_POSITION",
    }, _source("SM_SHADER_939D4824B1D4A401"))
    assert uv1 is not None
    assert "EvaluateMainPartGBufferDiffuse(\n      w2" in uv1[1]

    occlusion = lift_main_part_pixel_family({
        "PIXEL_SHADER", "PS_ASG_TEX", "PS_NOR_TEX", "PS_PERM_GBUFFER",
        "TRANSFER_COLOR", "TRANSFER_NORMAL", "TRANSFER_OCCLUSION",
        "TRANSFER_TANGENTS", "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
    }, _source("SM_SHADER_BE2127F84D856530"))
    assert occlusion is not None
    assert "ApplyMainPartGBufferVertexOcclusion(w2, surface)" in occlusion[1]

    pulse = lift_main_part_pixel_family({
        "PIXEL_SHADER", "PS_ASG_TEX", "PS_GLOBAL_PULSE",
        "PS_PERM_GBUFFER", "TRANSFER_COLOR", "TRANSFER_NORMAL",
        "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
    }, _source("SM_SHADER_08FAE174544FD6FB"))
    assert pulse is not None
    assert "ApplyMainPartGBufferGlobalPulse(surface)" in pulse[1]


def test_lift_composes_masked_mat_cap_policy():
    result = lift_main_part_pixel_family({
        "PIXEL_SHADER", "PS_ASG_TEX", "PS_MAT_CAP_MASKED_GLOW",
        "PS_NOR_TEX", "PS_PERM_GBUFFER", "TRANSFER_COLOR",
        "TRANSFER_NORMAL", "TRANSFER_TANGENTS", "TRANSFER_UV0",
        "TRANSFER_VIEW_POSITION",
    }, _source("SM_SHADER_727229881BE60FA8"))
    assert result is not None
    assert "ApplyMainPartGBufferMaskedMatCap(" in result[1]
    assert "v1, mappedNormal, true, surface" in result[1]


def test_lift_composes_dissolve_with_existing_material_policies():
    result = lift_main_part_pixel_family({
        "PIXEL_SHADER", "PS_ALPHA_CUTOFF", "PS_ASG_TEX",
        "PS_DISSOLVE_UV0", "PS_FBDRF_DIF", "PS_FLIP_BACKFACE_NORMALS",
        "PS_NOR_TEX", "PS_PERM_GBUFFER", "TRANSFER_COLOR",
        "TRANSFER_CUTOFF", "TRANSFER_NORMAL", "TRANSFER_TANGENTS",
        "TRANSFER_UV0", "TRANSFER_VIEW_POSITION",
    }, _source("SM_SHADER_AF0CD00D786DDCC6"))
    assert result is not None
    lifted = result[1]
    assert '#include "include/main_part_dissolve_b0_abi.hlsl"' in lifted
    assert "EvaluateMainPartSurfaceDissolveBand(v2, v7)" in lifted
    assert "ApplyMainPartGBufferDirectionalMapDiffuse(" in lifted
    assert "ApplyMainPartGBufferDissolve(dissolve.fade, surface)" in lifted
