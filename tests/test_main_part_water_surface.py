from shader_toolchain.recipes.main_part import (
    WATER_SURFACE_SINGLE_DEFINES,
    is_main_part_water_surface_single,
    lift_main_part_water_surface_single,
)


def test_water_surface_single_policy_is_exact() -> None:
    defines = sorted(WATER_SURFACE_SINGLE_DEFINES)
    assert is_main_part_water_surface_single(defines)
    assert not is_main_part_water_surface_single(
        [define for define in defines if define != "PS_WATER"]
    )
    assert not is_main_part_water_surface_single(
        defines + ["PS_SHADER_QUALITY_HIGH"]
    )


def test_water_surface_lift_uses_shared_abis_and_instruction_body() -> None:
    source = '''cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer Cluster : register(b6) { float4 cluster; }
cbuffer LightProps : register(b8) { float4 lights; }
// 3Dmigoto declarations
#define cmp -
void commonPS(
  float4 v0 : SV_Position0, float3 v1 : VIEW_POSITION0,
  float2 v2 : UV0, float3 v3 : NORMAL0, float4 v4 : VERTEXCOLOR0,
  linear noperspective centroid float3 v5 : SCREEN_UV0,
  float3 v6 : TANGENT0, float2 v7 : UV1, float4 v8 : FOG_COLOR0,
  out float4 o0 : SV_Target0, out float4 o1 : SV_Target1) {}
'''
    lifted = lift_main_part_water_surface_single(source)
    for filename in (
        "main_part_projection_abi.hlsl", "main_part_perframe_abi.hlsl",
        "main_part_cluster_abi.hlsl", "main_part_lightprops_abi.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert '#include "include/main_part_water_surface_single.hlsl"' in lifted
    assert "#define cmp -" in lifted
    assert "void commonPS(" in lifted
    assert "partPositionState" not in lifted
    assert "EvaluateMainPartSingleWaterSurface" in lifted
    function_body = lifted[lifted.index("void commonPS(") :]
    assert '#include "include/main_part_water_surface_single.hlsl"' not in function_body
