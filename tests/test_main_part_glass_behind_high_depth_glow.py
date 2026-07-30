from shader_toolchain.recipes.main_part import (
    GLASS_BEHIND_HIGH_DEPTH_GLOW_DEFINES,
    is_main_part_glass_behind_high_depth_glow,
    lift_main_part_glass_behind_high_depth_glow,
)


def test_glass_behind_high_depth_glow_policy_is_exact() -> None:
    defines = sorted(GLASS_BEHIND_HIGH_DEPTH_GLOW_DEFINES)
    assert is_main_part_glass_behind_high_depth_glow(defines)
    assert not is_main_part_glass_behind_high_depth_glow(
        [define for define in defines if define != "PS_DEPTH_BLUR_DISTANCE"]
    )
    assert not is_main_part_glass_behind_high_depth_glow(
        defines + ["PS_TRANSPARENT_TINTED"]
    )


def test_glass_behind_high_depth_glow_reuses_shared_cascade_evaluator() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_GLASS { float4 glass; }
Texture2D<float4> tDepth : register(t7);
// 3Dmigoto declarations
#define cmp -
void commonPS(
  float4 v0 : SV_Position0, float3 v1 : VIEW_POSITION0,
  float2 v2 : UV0, float3 v3 : NORMAL0, float3 v4 : TANGENT0,
  float3 v5 : BITANGENT0, float4 v6 : VERTEXCOLOR0,
  linear noperspective centroid float3 v7 : SCREEN_UV0,
  float4 v8 : FOG_COLOR0, uint v9 : SV_IsFrontFace0,
  out float3 o0 : SV_Target0, out float2 o1 : SV_Target1) {}
'''
    lifted = lift_main_part_glass_behind_high_depth_glow(source)
    for filename in (
        "main_part_projection_abi.hlsl", "main_part_perframe_abi.hlsl",
        "main_part_glass_abi.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert '#include "include/main_part_legacy_glass_behind.hlsl"' in lifted
    assert "MAIN_PART_GLASS_BEHIND_TRANSMISSION_RANGE 1" in lifted
    assert "MAIN_PART_GLASS_BEHIND_EDGE_SCALE 0.5" in lifted
    assert "EvaluateMainPartLegacyGlassBehind" in lifted
    assert "partPositionState" not in lifted
