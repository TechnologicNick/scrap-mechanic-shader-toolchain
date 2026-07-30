from shader_toolchain.recipes.main_part import (
    LEGACY_GLASS_BEHIND_HIGH_DEFINES,
    is_main_part_legacy_glass_behind_high,
    lift_main_part_legacy_glass_behind_high,
)


def test_legacy_glass_behind_high_policy_is_exact() -> None:
    defines = sorted(LEGACY_GLASS_BEHIND_HIGH_DEFINES)
    assert is_main_part_legacy_glass_behind_high(defines)
    assert not is_main_part_legacy_glass_behind_high(
        [define for define in defines if define != "PS_SHADER_QUALITY_HIGH"]
    )
    assert not is_main_part_legacy_glass_behind_high(
        defines + ["PS_REFLECTION_SINGLE"]
    )


def test_legacy_glass_lift_preserves_signature_and_uses_shared_evaluator() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_GLASS { float4 glass; }
// 3Dmigoto declarations
#define cmp -
void commonPS(
  float4 v0 : SV_Position0,
  float3 v1 : VIEW_POSITION0,
  float2 v2 : UV0,
  float3 v3 : NORMAL0,
  float3 v4 : TANGENT0,
  float3 v5 : BITANGENT0,
  float4 v6 : VERTEXCOLOR0,
  linear noperspective centroid float3 v7 : SCREEN_UV0,
  float4 v8 : FOG_COLOR0,
  uint v9 : SV_IsFrontFace0,
  out float3 o0 : SV_Target0,
  out float2 o1 : SV_Target1) {}
'''
    lifted = lift_main_part_legacy_glass_behind_high(source)
    assert '#include "include/main_part_projection_abi.hlsl"' in lifted
    assert '#include "include/main_part_perframe_abi.hlsl"' in lifted
    assert '#include "include/main_part_legacy_glass_behind.hlsl"' in lifted
    assert "EvaluateMainPartLegacyGlassBehind" in lifted
    assert "v0, v1, v2, v3, v4, v5, v6, v7, v8, v9, o0, o1" in lifted
    assert "partPositionState" not in lifted
