from pathlib import Path

from shader_toolchain.recipes.main_part_glass_surface_families import (
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
    classify_main_part_glass_surface_family,
    lift_main_part_glass_surface_family,
)


SOURCE = '''cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_REFLECTIONS : register(b11) { float4 reflections; }
cbuffer CB_GLASS { float4 glass; }
cbuffer CB_DISSOLVE { float4 dissolve; }
cbuffer Cluster : register(b6) { float4 cluster; }
cbuffer LightProps : register(b8) { float4 lights; }
Texture2D<float4> tDif : register(t0);
// 3Dmigoto declarations
#define cmp -
void commonPS(
  float4 v0 : SV_Position0, float3 v1 : VIEW_POSITION0,
  float2 v2 : UV0, float3 v3 : NORMAL0, float3 v4 : TANGENT0,
  float3 v5 : BITANGENT0, float4 v6 : VERTEXCOLOR0,
  linear noperspective centroid float3 v7 : SCREEN_UV0,
  float4 v8 : FOG_COLOR0, nointerpolation float v9 : CUTOFF0,
  uint v10 : SV_IsFrontFace0,
  out float4 o0 : SV_Target0, out float4 o1 : SV_Target1) {}
'''


def test_glass_surface_family_is_classified_by_complete_policy() -> None:
    family = classify_main_part_glass_surface_family(
        MEDIUM_MULTI_DISSOLVE.defines, SOURCE
    )
    assert family == MEDIUM_MULTI_DISSOLVE
    assert family.name == "glass_surface_medium_multi_dissolve_uv0"
    assert classify_main_part_glass_surface_family(
        MEDIUM_MULTI_DISSOLVE.defines - {"PS_REFLECTION_MULTI"}
        | {"PS_REFLECTION_SINGLE"},
        SOURCE,
    ) == MEDIUM_SINGLE_DISSOLVE
    assert classify_main_part_glass_surface_family(
        LOW_MULTI_DISSOLVE.defines, SOURCE
    ) == LOW_MULTI_DISSOLVE
    plain_source = SOURCE.replace(
        "cbuffer CB_DISSOLVE { float4 dissolve; }\n", ""
    ).replace(" nointerpolation float v9 : CUTOFF0,\n", "")
    assert classify_main_part_glass_surface_family(
        LOW_MULTI_PLAIN.defines, plain_source
    ) == LOW_MULTI_PLAIN
    assert classify_main_part_glass_surface_family(
        MEDIUM_MULTI_PLAIN.defines, plain_source
    ) == MEDIUM_MULTI_PLAIN
    assert classify_main_part_glass_surface_family(
        LOW_OFF_DISSOLVE.defines, SOURCE
    ) == LOW_OFF_DISSOLVE
    assert classify_main_part_glass_surface_family(
        LOW_OFF_PLAIN.defines, plain_source
    ) == LOW_OFF_PLAIN
    assert classify_main_part_glass_surface_family(
        LOW_SINGLE_DISSOLVE.defines, SOURCE
    ) == LOW_SINGLE_DISSOLVE
    assert classify_main_part_glass_surface_family(
        LOW_SINGLE_PLAIN.defines, plain_source
    ) == LOW_SINGLE_PLAIN
    assert classify_main_part_glass_surface_family(
        MEDIUM_OFF_DISSOLVE.defines, SOURCE
    ) == MEDIUM_OFF_DISSOLVE
    assert classify_main_part_glass_surface_family(
        MEDIUM_OFF_PLAIN.defines, plain_source
    ) == MEDIUM_OFF_PLAIN
    assert classify_main_part_glass_surface_family(
        MEDIUM_SINGLE_DISSOLVE.defines, SOURCE
    ) == MEDIUM_SINGLE_DISSOLVE
    assert classify_main_part_glass_surface_family(
        MEDIUM_SINGLE_PLAIN.defines, plain_source
    ) == MEDIUM_SINGLE_PLAIN
    for family in (
        LOW_MULTI_NO_CUTOUT, LOW_OFF_NO_CUTOUT, LOW_SINGLE_NO_CUTOUT,
        MEDIUM_MULTI_NO_CUTOUT, MEDIUM_OFF_NO_CUTOUT,
        MEDIUM_SINGLE_NO_CUTOUT,
    ):
        assert classify_main_part_glass_surface_family(
            family.defines, plain_source
        ) == family


def test_glass_surface_wrapper_is_semantic_and_small() -> None:
    result = lift_main_part_glass_surface_family(
        MEDIUM_MULTI_DISSOLVE.defines, SOURCE
    )
    assert result is not None
    _name, lifted = result
    assert "EvaluateMainPartGlassSurfaceMedium" in lifted
    assert "v0, v1, v2, v3, v4, v5, v6, v7, v8, v9, v10, o0, o1" in lifted
    assert "partPositionState" not in lifted
    assert "../phases/" not in lifted


def test_glass_surface_asset_has_typed_phase_helpers() -> None:
    asset = Path(
        "src/shader_toolchain/recipes/assets/"
        "main_part_glass_surface_shared.hlsl"
    ).read_text(encoding="utf-8")
    for helper in (
        "EvaluateMainPartUvDissolve",
        "DecodeMainPartTwoSidedNormal",
        "EvaluateMainPartDissolveGlassMaterial",
        "EvaluateMainPartGlassDirectionalLighting",
        "ComposeMainPartDissolveGlassSurface",
    ):
        assert helper in asset
    assert "…" not in asset
