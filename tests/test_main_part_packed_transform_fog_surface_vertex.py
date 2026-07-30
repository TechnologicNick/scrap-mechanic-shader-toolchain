from shader_toolchain.recipes.main_part import (
    PACKED_TRANSFORM_FOG_SURFACE_DEFINES,
    is_main_part_packed_transform_fog_surface,
    lift_main_part_packed_transform_fog_surface,
)


def test_packed_transform_fog_surface_policy_is_exact() -> None:
    defines = sorted(PACKED_TRANSFORM_FOG_SURFACE_DEFINES)
    assert is_main_part_packed_transform_fog_surface(defines)
    assert not is_main_part_packed_transform_fog_surface(
        [define for define in defines if define != "TRANSFER_FOG_COLOR"]
    )
    assert not is_main_part_packed_transform_fog_surface(
        defines + ["VS_POSE_0_ANIM"]
    )


def test_packed_transform_fog_surface_lift_preserves_contract() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_TRANSFORMS : register(b7) { float4 transforms; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0, float2 v1 : TEXCOORD0,
  float3 v2 : NORMAL0, float4 v3 : TANGENT0,
  int4 v4 : LTWPACKED0, uint4 v5 : INSTANCE_DATA0,
  out float4 o0 : SV_Position0, out float3 o1 : VIEW_POSITION0,
  out float2 o2 : UV0, out float3 o3 : NORMAL0,
  out float3 o4 : TANGENT0, out float3 o5 : BITANGENT0,
  out float4 o6 : VERTEXCOLOR0, out float3 o7 : SCREEN_UV0,
  out float4 o8 : FOG_COLOR0) {}
'''
    lifted = lift_main_part_packed_transform_fog_surface(source)
    for filename in (
        "main_part_projection_abi.hlsl",
        "main_part_perframe_abi.hlsl",
        "main_part_transforms_abi.hlsl",
        "main_part_vertex_fog.hlsl",
        "main_part_packed_transform_vertex.hlsl",
        "main_part_packed_transform_fog_vertex.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert "EvaluateMainPartPackedTransformFogSurfaceVertex" in lifted
    for assignment in (
        "o0 =", "o1 =", "o2 =", "o3 =", "o4 =", "o5 =",
        "o6 =", "o7 =", "o8 =",
    ):
        assert assignment in lifted
    assert "partPositionState" not in lifted
