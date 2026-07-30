from shader_toolchain.recipes.main_part import (
    VISUALIZATION_LOW_METAL_NORMAL_DEFINES,
    is_main_part_visualization_low_metal_normal,
    lift_main_part_visualization_low_metal_normal,
)


def test_low_visualization_policy_is_exact() -> None:
    defines = sorted(VISUALIZATION_LOW_METAL_NORMAL_DEFINES)
    assert is_main_part_visualization_low_metal_normal(defines)
    assert not is_main_part_visualization_low_metal_normal(
        [define for define in defines if define != "PS_SHADER_QUALITY_LOW"]
    )
    assert not is_main_part_visualization_low_metal_normal(
        defines + ["PS_ALPHA_CUTOFF"]
    )


def test_low_visualization_lift_preserves_contract() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_VISUALIZATION_COLOR : register(b6) { float4 visual; }
SamplerState PointClampClamp_s : register(s1);
SamplerState LinearWrapWrap_s : register(s3);
Texture2D<float4> tNor : register(t2);
Texture2D<float4> tDepth : register(t7);
// 3Dmigoto declarations
#define cmp -
void commonPS(
 float4 v0 : SV_Position0, float3 v1 : VIEW_POSITION0,
 float2 v2 : UV0, float2 w2 : UV1, float3 v3 : NORMAL0,
 float3 v4 : TANGENT0, float3 v5 : BITANGENT0,
 float4 v6 : VERTEXCOLOR0,
 linear noperspective centroid float3 v7 : SCREEN_UV0,
 float3 v8 : OBJECT_TANGENT0, uint v9 : SV_IsFrontFace0,
 out float4 o0 : SV_Target0) {}
'''
    lifted = lift_main_part_visualization_low_metal_normal(source)
    for filename in (
        "main_part_projection_abi.hlsl", "main_part_visualization_abi.hlsl",
        "main_part_visualization_low.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert "EvaluateMainPartLowVisualization" in lifted
    assert "DecodeMainPartLowVisualizationNormal" in lifted
    assert "partPositionState" not in lifted
