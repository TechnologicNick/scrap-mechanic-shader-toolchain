from shader_toolchain.recipes.main_part import (
    GLASS_SET_PARAMS_BEHIND_SINGLE_LOW_DEFINES,
    is_main_part_glass_set_params_behind_single_low,
    lift_main_part_glass_set_params_behind_single_low,
)


def test_glass_set_params_behind_single_low_policy_is_exact() -> None:
    defines = sorted(GLASS_SET_PARAMS_BEHIND_SINGLE_LOW_DEFINES)
    assert is_main_part_glass_set_params_behind_single_low(defines)
    assert not is_main_part_glass_set_params_behind_single_low(
        [define for define in defines if define != "PS_REFLECTION_SINGLE"]
    )
    assert not is_main_part_glass_set_params_behind_single_low(
        defines + ["PS_SHADER_QUALITY_HIGH"]
    )


def test_glass_set_params_behind_single_low_uses_shared_family_assets() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_GLASS { float4 glass; }
cbuffer CB_OFFSET_PARAMS { float4 offsetParams; }
Texture2D<float4> tDepth : register(t7);
// 3Dmigoto declarations
#define cmp -
void commonPS(
  float4 v0 : SV_Position0, float3 v1 : VIEW_POSITION0,
  float2 v2 : UV0, float3 v3 : NORMAL0, float4 v4 : VERTEXCOLOR0,
  linear noperspective centroid float3 v5 : SCREEN_UV0,
  float4 v6 : FOG_COLOR0, uint v7 : SV_IsFrontFace0,
  out float3 o0 : SV_Target0, out float2 o1 : SV_Target1) {}
'''
    lifted = lift_main_part_glass_set_params_behind_single_low(source)
    for filename in (
        "main_part_projection_abi.hlsl",
        "main_part_perframe_abi.hlsl",
        "main_part_glass_abi.hlsl",
        "main_part_offset_params_abi.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert (
        '#include "include/main_part_glass_set_params_behind_single.hlsl"'
        in lifted
    )
    assert "EvaluateMainPartSetParamsBehindSingle(" in lifted
    assert "partPositionState" not in lifted
    function_body = lifted[lifted.index("void commonPS(") :]
    assert '#include "include/' not in function_body
