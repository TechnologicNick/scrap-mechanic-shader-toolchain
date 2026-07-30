from shader_toolchain.recipes.main_part import (
    VISUALIZATION_DEPTH_GLASS_PARAMS_DEFINES,
    is_main_part_visualization_depth_glass_params,
    lift_main_part_visualization_depth_glass_params,
)


def test_visualization_depth_policy_is_exact() -> None:
    defines = sorted(VISUALIZATION_DEPTH_GLASS_PARAMS_DEFINES)
    assert is_main_part_visualization_depth_glass_params(defines)
    assert not is_main_part_visualization_depth_glass_params(
        [define for define in defines if define != "PS_SET_PARAMS"]
    )
    assert not is_main_part_visualization_depth_glass_params(
        defines + ["PS_ASG_TEX"]
    )


def test_visualization_depth_lift_factors_ordered_overlay() -> None:
    source = '''cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_VISUALIZATION_COLOR : register(b6) { float4 visualization; }
Texture2D<float4> tDepth : register(t7);
// 3Dmigoto declarations
#define cmp -
void commonPS(
  float4 v0 : SV_Position0, float3 v1 : VIEW_POSITION0,
  float2 v2 : UV0, float3 v3 : NORMAL0, float4 v4 : VERTEXCOLOR0,
  linear noperspective centroid float3 v5 : SCREEN_UV0,
  uint v6 : SV_IsFrontFace0, out float4 o0 : SV_Target0) {}
'''
    lifted = lift_main_part_visualization_depth_glass_params(source)
    for filename in (
        "main_part_projection_abi.hlsl", "main_part_perframe_abi.hlsl",
        "main_part_visualization_abi.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert '#include "include/main_part_visualization_depth.hlsl"' in lifted
    assert "Texture2D<float4> tDepth" in lifted
    assert "partPositionState" not in lifted
