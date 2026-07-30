from shader_toolchain.recipes.main_part import (
    GLASS_CUSTOM_TILING_BEHIND_LOW_DEFINES,
    is_main_part_glass_custom_tiling_behind_low,
    lift_main_part_glass_custom_tiling_behind_low,
)


def test_glass_custom_tiling_behind_low_policy_is_exact() -> None:
    defines = sorted(GLASS_CUSTOM_TILING_BEHIND_LOW_DEFINES)
    assert is_main_part_glass_custom_tiling_behind_low(defines)
    assert not is_main_part_glass_custom_tiling_behind_low(
        [define for define in defines if define != "PS_NOR_D_TEX"]
    )
    assert not is_main_part_glass_custom_tiling_behind_low(
        defines + ["PS_SHADER_QUALITY_HIGH"]
    )


def test_custom_tiling_glass_lift_uses_shared_abis_and_typed_policy() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_TILING { float4 tiling; }
cbuffer CB_GLASS { float4 glass; }
Texture2D<float4> tDif : register(t0);
// 3Dmigoto declarations
#define cmp -
void commonPS(
  float4 v0 : SV_Position0, float3 v1 : VIEW_POSITION0,
  float w1 : OCCLUSION0, float2 v2 : UV0, float2 w2 : UV1,
  float3 v3 : NORMAL0, float3 v4 : TANGENT0, float3 v5 : BITANGENT0,
  float4 v6 : VERTEXCOLOR0,
  linear noperspective centroid float3 v7 : SCREEN_UV0,
  float4 v8 : FOG_COLOR0, uint v9 : SV_IsFrontFace0,
  out float3 o0 : SV_Target0, out float2 o1 : SV_Target1) {}
'''
    lifted = lift_main_part_glass_custom_tiling_behind_low(source)
    for filename in (
        "main_part_projection_abi.hlsl",
        "main_part_perframe_abi.hlsl",
        "main_part_tiling_abi.hlsl",
        "main_part_glass_abi.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert (
        '#include "include/main_part_glass_custom_tiling_behind_low.hlsl"'
        in lifted
    )
    assert "partPositionState" not in lifted
    assert "EvaluateMainPartCustomTilingBehindLow(" in lifted
    function_body = lifted[lifted.index("void commonPS(") :]
    assert '#include "include/' not in function_body
