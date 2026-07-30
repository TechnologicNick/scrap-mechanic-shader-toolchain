from shader_toolchain.recipes.main_part import (
    GLASS_DISSOLVE_BEHIND_SINGLE_DEFINES,
    is_main_part_glass_dissolve_behind_single,
    lift_main_part_glass_dissolve_behind_single,
)


def test_glass_dissolve_behind_single_policy_is_exact() -> None:
    defines = sorted(GLASS_DISSOLVE_BEHIND_SINGLE_DEFINES)
    assert is_main_part_glass_dissolve_behind_single(defines)
    assert not is_main_part_glass_dissolve_behind_single(
        [define for define in defines if define != "PS_DISSOLVE_UV0"]
    )
    assert not is_main_part_glass_dissolve_behind_single(
        defines + ["PS_SHADER_QUALITY_HIGH"]
    )


def test_glass_dissolve_behind_single_lift_is_a_thin_abi_wrapper() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_GLASS { float4 glass; }
cbuffer CB_DISSOLVE { float4 dissolve; }
Texture2D<float4> tDepth : register(t7);
// 3Dmigoto declarations
#define cmp -
void commonPS(
  float4 v0 : SV_Position0, float3 v1 : VIEW_POSITION0,
  float2 v2 : UV0, float3 v3 : NORMAL0, float3 v4 : TANGENT0,
  float3 v5 : BITANGENT0, float4 v6 : VERTEXCOLOR0,
  linear noperspective centroid float3 v7 : SCREEN_UV0,
  float4 v8 : FOG_COLOR0, nointerpolation float v9 : CUTOFF0,
  uint v10 : SV_IsFrontFace0, out float3 o0 : SV_Target0,
  out float2 o1 : SV_Target1) {}
'''
    lifted = lift_main_part_glass_dissolve_behind_single(source)
    for filename in (
        "main_part_projection_abi.hlsl",
        "main_part_perframe_abi.hlsl",
        "main_part_glass_abi.hlsl",
        "main_part_dissolve_abi.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert (
        '#include "include/main_part_glass_dissolve_behind_single.hlsl"'
        in lifted
    )
    assert "partPositionState" not in lifted
    assert "nointerpolation float v9 : CUTOFF0" in lifted
    assert "EvaluateMainPartDissolveBehindSingle(" in lifted
    function_body = lifted[lifted.index("void commonPS(") :]
    assert '#include "include/' not in function_body
