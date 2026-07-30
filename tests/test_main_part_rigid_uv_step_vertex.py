from shader_toolchain.recipes.main_part import (
    RIGID_UV_STEP_SURFACE_DEFINES,
    is_main_part_rigid_uv_step_surface,
    lift_main_part_rigid_uv_step_surface,
)


def test_rigid_uv_step_surface_policy_is_exact() -> None:
    defines = sorted(RIGID_UV_STEP_SURFACE_DEFINES)
    assert is_main_part_rigid_uv_step_surface(defines)
    assert not is_main_part_rigid_uv_step_surface(
        [define for define in defines if define != "VS_UV0_STEP"]
    )
    assert not is_main_part_rigid_uv_step_surface(
        defines + ["TRANSFER_TANGENTS"]
    )


def test_rigid_uv_step_surface_lift_is_thin() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_UV_STEP { float4 uvStep; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0, float2 v1 : TEXCOORD0,
  float3 v2 : NORMAL0, float4 v3 : LTW0,
  float4 v4 : LTW1, float4 v5 : LTW2,
  uint4 v6 : INSTANCE_DATA0, out float4 o0 : SV_Position0,
  out float3 o1 : VIEW_POSITION0, out float2 o2 : UV0,
  out float3 o3 : NORMAL0, out float4 o4 : VERTEXCOLOR0,
  out float3 o5 : SCREEN_UV0) {}
'''
    lifted = lift_main_part_rigid_uv_step_surface(source)
    for filename in (
        "main_part_projection_abi.hlsl",
        "main_part_perframe_abi.hlsl",
        "main_part_uv_step_abi.hlsl",
        "main_part_morph_vertex.hlsl",
        "main_part_uv_step.hlsl",
        "main_part_rigid_uv_step_vertex.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert "EvaluateMainPartRigidUvStepVertex" in lifted
    assert "partPositionState" not in lifted
