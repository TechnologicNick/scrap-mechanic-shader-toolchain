from shader_toolchain.recipes.main_part import (
    TRANSLUCENT_PREVIEW_FLOW_DEFINES,
    is_main_part_translucent_preview_flow,
    lift_main_part_translucent_preview_flow,
)


def test_translucent_preview_flow_policy_is_exact() -> None:
    defines = sorted(TRANSLUCENT_PREVIEW_FLOW_DEFINES)
    assert is_main_part_translucent_preview_flow(defines)
    assert not is_main_part_translucent_preview_flow(defines + ["PS_NOR_TEX"])
    assert not is_main_part_translucent_preview_flow(
        [define for define in defines if define != "PS_FLOW_MAP_UV0"]
    )


def test_translucent_preview_flow_lift_has_typed_phases() -> None:
    source = '''cbuffer CB_PERFRAME : register(b12)
{
  float4 perFrame;
}
cbuffer CB_PROJECTION : register(b5)
{
  float4 projection;
}
Texture2D<float4> tDif : register(t0);
// 3Dmigoto declarations
#define cmp -
void commonPS(
  float4 v0 : SV_Position0,
  float3 v1 : VIEW_POSITION0,
  float2 v2 : UV0,
  float3 v3 : NORMAL0,
  float4 v4 : VERTEXCOLOR0,
  linear noperspective centroid float3 v5 : SCREEN_UV0,
  uint v6 : SV_IsFrontFace0,
  out float4 o0 : SV_Target0) {}
'''
    lifted = lift_main_part_translucent_preview_flow(source)
    assert '#include "include/main_part_projection_abi.hlsl"' in lifted
    assert '#include "include/main_part_perframe_abi.hlsl"' in lifted
    assert '#include "include/main_part_translucent_preview.hlsl"' in lifted
    assert "EvaluateMainPartTranslucentPreview" in lifted
    assert "o0 = EvaluateMainPartTranslucentPreview" in lifted
    assert "partPositionState" not in lifted
    assert "3Dmigoto" not in lifted
