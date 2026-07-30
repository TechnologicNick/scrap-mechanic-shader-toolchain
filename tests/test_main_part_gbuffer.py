from shader_toolchain.recipes.main_part import (
    GBUFFER_ASG_NORMAL_DEFINES,
    is_main_part_gbuffer_asg_normal,
    lift_main_part_gbuffer_asg_normal,
)


def test_gbuffer_asg_normal_policy_is_exact() -> None:
    defines = sorted(GBUFFER_ASG_NORMAL_DEFINES)
    assert is_main_part_gbuffer_asg_normal(defines)
    assert not is_main_part_gbuffer_asg_normal(
        [define for define in defines if define != "PS_NOR_TEX"]
    )
    assert not is_main_part_gbuffer_asg_normal(
        defines + ["PS_ALPHA_CUTOFF"]
    )


def test_gbuffer_lift_uses_typed_surface_result() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
// 3Dmigoto declarations
#define cmp -
void commonPS(
  float4 v0 : SV_Position0, float3 v1 : VIEW_POSITION0,
  float2 v2 : UV0, float3 v3 : NORMAL0, float3 v4 : TANGENT0,
  float3 v5 : BITANGENT0, float4 v6 : VERTEXCOLOR0,
  uint v7 : SV_IsFrontFace0, out float4 o0 : SV_Target0,
  out float2 o1 : SV_Target1, out float4 o2 : SV_Target2) {}
'''
    lifted = lift_main_part_gbuffer_asg_normal(source)
    assert '#include "include/main_part_projection_abi.hlsl"' in lifted
    assert '#include "include/main_part_gbuffer.hlsl"' in lifted
    assert "MainPartGBuffer surface" in lifted
    assert "EvaluateMainPartGBuffer(" in lifted
    assert "v2, v3, v4, v5, v6);" in lifted
    assert "o0 = surface.albedo" in lifted
    assert "o1 = surface.encodedNormal" in lifted
    assert "o2 = surface.material" in lifted
    assert "partPositionState" not in lifted
