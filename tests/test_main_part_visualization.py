from shader_toolchain.recipes.main_part import (
    VISUALIZATION_ALPHA_ASG_NORMAL_DEFINES,
    is_main_part_visualization_alpha_asg_normal,
    lift_main_part_visualization_alpha_asg_normal,
)


def test_visualization_alpha_asg_normal_policy_is_exact() -> None:
    defines = sorted(VISUALIZATION_ALPHA_ASG_NORMAL_DEFINES)
    assert is_main_part_visualization_alpha_asg_normal(defines)
    assert not is_main_part_visualization_alpha_asg_normal(
        [define for define in defines if define != "PS_NOR_TEX"]
    )
    assert not is_main_part_visualization_alpha_asg_normal(
        defines + ["PS_SHADER_QUALITY_LOW"]
    )


def test_visualization_lift_separates_material_frontend_from_core() -> None:
    source = '''cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_VISUALIZATION_COLOR : register(b6) { float4 visualization; }
// 3Dmigoto declarations
#define cmp -
void commonPS(
  float4 v0 : SV_Position0, float3 v1 : VIEW_POSITION0,
  float2 v2 : UV0, float3 v3 : NORMAL0, float3 v4 : TANGENT0,
  float3 v5 : BITANGENT0, float4 v6 : VERTEXCOLOR0,
  linear noperspective centroid float3 v7 : SCREEN_UV0,
  uint v8 : SV_IsFrontFace0, out float4 o0 : SV_Target0) {}
'''
    lifted = lift_main_part_visualization_alpha_asg_normal(source)
    for filename in (
        "main_part_projection_abi.hlsl", "main_part_perframe_abi.hlsl",
        "main_part_visualization_abi.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert '#include "include/main_part_visualization.hlsl"' in lifted
    assert "DecodeMainPartVisualizationNormal" in lifted
    assert "EvaluateMainPartVisualization" in lifted
    assert "partPositionState" not in lifted
