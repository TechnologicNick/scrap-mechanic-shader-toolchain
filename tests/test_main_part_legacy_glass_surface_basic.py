from shader_toolchain.recipes.main_part import (
    LEGACY_GLASS_SURFACE_MULTI_ALPHA_DEFINES,
    LEGACY_GLASS_SURFACE_OFF_ALPHA_DEFINES,
    LEGACY_GLASS_SURFACE_SINGLE_ALPHA_DEFINES,
    LEGACY_GLASS_SURFACE_MULTI_PLAIN_DEFINES,
    LEGACY_GLASS_SURFACE_OFF_PLAIN_DEFINES,
    LEGACY_GLASS_SURFACE_SINGLE_PLAIN_DEFINES,
    is_main_part_legacy_glass_surface_multi_alpha,
    is_main_part_legacy_glass_surface_single_alpha,
    lift_main_part_legacy_glass_surface_multi_alpha,
    lift_main_part_legacy_glass_surface_single_alpha,
    lift_main_part_legacy_glass_surface_plain,
    main_part_legacy_glass_surface_plain_asset,
)


def test_legacy_glass_surface_multi_alpha_policy_is_exact() -> None:
    defines = sorted(LEGACY_GLASS_SURFACE_MULTI_ALPHA_DEFINES)
    assert is_main_part_legacy_glass_surface_multi_alpha(defines)
    assert is_main_part_legacy_glass_surface_multi_alpha(
        sorted(LEGACY_GLASS_SURFACE_OFF_ALPHA_DEFINES)
    )
    assert not is_main_part_legacy_glass_surface_multi_alpha(
        [define for define in defines if define != "PS_ALPHA_CUTOFF"]
    )
    assert not is_main_part_legacy_glass_surface_multi_alpha(
        defines + ["PS_SHADER_QUALITY_MEDIUM"]
    )


def test_legacy_glass_surface_basic_lift_preserves_runtime_abi() -> None:
    source = '''cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_GLASS { float4 glass; }
// 3Dmigoto declarations
#define cmp -
void commonPS(
  float4 v0 : SV_Position0, float3 v1 : VIEW_POSITION0,
  float2 v2 : UV0, float3 v3 : NORMAL0, float3 v4 : TANGENT0,
  float3 v5 : BITANGENT0, float4 v6 : VERTEXCOLOR0,
  linear noperspective centroid float3 v7 : SCREEN_UV0,
  float4 v8 : FOG_COLOR0, uint v9 : SV_IsFrontFace0,
  out float4 o0 : SV_Target0, out float4 o1 : SV_Target1) {}
'''
    lifted = lift_main_part_legacy_glass_surface_multi_alpha(source)
    for filename in (
        "main_part_projection_abi.hlsl", "main_part_perframe_abi.hlsl",
        "main_part_glass_abi.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert '#include "include/main_part_legacy_glass_surface_basic.hlsl"' in lifted
    assert "EvaluateMainPartLegacyGlassSurfaceBasic" in lifted
    assert '#include "include/main_part_legacy_glass_surface_basic.hlsl"\n}' not in lifted
    assert "void commonPS(" in lifted
    assert "partPositionState" not in lifted


def test_legacy_glass_surface_single_policy_uses_typed_composition() -> None:
    assert is_main_part_legacy_glass_surface_single_alpha(
        sorted(LEGACY_GLASS_SURFACE_SINGLE_ALPHA_DEFINES)
    )
    source = '''cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_GLASS { float4 glass; }
// 3Dmigoto declarations
#define cmp -
void commonPS(
  float4 v0 : SV_Position0, float3 v1 : VIEW_POSITION0,
  float2 v2 : UV0, float3 v3 : NORMAL0, float3 v4 : TANGENT0,
  float3 v5 : BITANGENT0, float4 v6 : VERTEXCOLOR0,
  linear noperspective centroid float3 v7 : SCREEN_UV0,
  float4 v8 : FOG_COLOR0, uint v9 : SV_IsFrontFace0,
  out float4 o0 : SV_Target0, out float4 o1 : SV_Target1) {}
'''
    lifted = lift_main_part_legacy_glass_surface_single_alpha(source)
    assert 'main_part_legacy_glass_surface_single.hlsl' in lifted
    assert "EvaluateMainPartLegacyGlassSurfaceBasic" in lifted
    assert "partPositionState" not in lifted


def test_legacy_glass_surface_plain_policies_select_semantic_assets() -> None:
    expected = (
        (LEGACY_GLASS_SURFACE_MULTI_PLAIN_DEFINES, "plain_multi"),
        (LEGACY_GLASS_SURFACE_OFF_PLAIN_DEFINES, "plain_off"),
        (LEGACY_GLASS_SURFACE_SINGLE_PLAIN_DEFINES, "plain_single"),
    )
    for defines, suffix in expected:
        asset = main_part_legacy_glass_surface_plain_asset(sorted(defines))
        assert asset == f"main_part_legacy_glass_surface_{suffix}.hlsl"
        lifted = lift_main_part_legacy_glass_surface_plain(
            '''cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_GLASS { float4 glass; }
// 3Dmigoto declarations
void commonPS(float4 v0 : SV_Position0) {}
''', asset
        )
        assert f'include/{asset}' in lifted
        assert "EvaluateMainPartLegacyGlassSurfaceBasic" in lifted
