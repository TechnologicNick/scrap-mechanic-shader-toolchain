from shader_toolchain.recipes.main_part import (
    WATER_SURFACE_SINGLE_HIGH_DEFINES,
    is_main_part_water_surface_single_high,
    lift_main_part_water_surface_single_high,
)


def test_water_surface_single_high_policy_is_exact() -> None:
    defines = sorted(WATER_SURFACE_SINGLE_HIGH_DEFINES)
    assert is_main_part_water_surface_single_high(defines)
    assert not is_main_part_water_surface_single_high(
        [define for define in defines if define != "PS_FBDRF_DIF"]
    )
    assert not is_main_part_water_surface_single_high(
        defines + ["PS_NOR_TEX"]
    )


def test_high_water_lift_uses_shared_abis_and_fidelity_body() -> None:
    source = '''cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer Cluster : register(b6) { float4 cluster; }
cbuffer LightProps : register(b8) { float4 lightProps; }
Texture2D<float4> tDif : register(t0);
// 3Dmigoto declarations
#define cmp -
void commonPS(
  float4 v0 : SV_Position0, float3 v1 : VIEW_POSITION0,
  float2 v2 : UV0, float3 v3 : NORMAL0, float3 v4 : TANGENT0,
  float3 v5 : BITANGENT0, float4 v6 : VERTEXCOLOR0,
  linear noperspective centroid float3 v7 : SCREEN_UV0,
  float4 v8 : FOG_COLOR0, uint v9 : SV_IsFrontFace0,
  out float4 o0 : SV_Target0, out float4 o1 : SV_Target1) {}
'''
    lifted = lift_main_part_water_surface_single_high(source)
    for filename in (
        "main_part_projection_abi.hlsl",
        "main_part_perframe_abi.hlsl",
        "main_part_cluster_abi.hlsl",
        "main_part_lightprops_abi.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert (
        '#include "include/main_part_water_surface_single_high.hlsl"'
        in lifted
    )
    assert "EvaluateMainPartWaterSurfaceSingleHigh" in lifted
    function_body = lifted[lifted.index("void commonPS(") :]
    assert '#include "include/main_part_water_surface_single_high.hlsl"' not in function_body
    assert "#define cmp -" in lifted
    assert "partPositionState" not in lifted
