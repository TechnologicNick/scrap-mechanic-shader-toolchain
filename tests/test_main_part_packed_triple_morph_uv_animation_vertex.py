from shader_toolchain.recipes.main_part import (
    PACKED_TRIPLE_MORPH_UV_ANIMATION_SURFACE_DEFINES,
    is_main_part_packed_triple_morph_uv_animation_surface,
    lift_main_part_packed_triple_morph_uv_animation_surface,
)


def test_packed_triple_morph_uv_animation_policy_is_exact() -> None:
    defines = sorted(PACKED_TRIPLE_MORPH_UV_ANIMATION_SURFACE_DEFINES)
    assert is_main_part_packed_triple_morph_uv_animation_surface(defines)
    assert not is_main_part_packed_triple_morph_uv_animation_surface(
        [define for define in defines if define != "VS_UV_ANIM"]
    )
    assert not is_main_part_packed_triple_morph_uv_animation_surface(
        defines + ["TRANSFER_TANGENTS"]
    )


def test_packed_triple_morph_uv_animation_lift_is_thin() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_TRANSFORMS : register(b7) { float4 transforms; }
cbuffer CB_UVFRAME { float4 frame; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0, float2 v1 : TEXCOORD0,
  float3 v2 : NORMAL0, float3 v3 : POSITION1,
  float3 v4 : NORMAL1, float3 v5 : POSITION2,
  float3 v6 : NORMAL2, float3 v7 : POSITION3,
  float3 v8 : NORMAL3, int4 v9 : LTWPACKED0,
  uint4 v10 : INSTANCE_DATA0, out float4 o0 : SV_Position0,
  out float3 o1 : VIEW_POSITION0, out float2 o2 : UV0,
  out float3 o3 : NORMAL0, out float4 o4 : VERTEXCOLOR0,
  out float3 o5 : SCREEN_UV0) {}
'''
    lifted = lift_main_part_packed_triple_morph_uv_animation_surface(source)
    for filename in (
        "main_part_projection_abi.hlsl",
        "main_part_perframe_abi.hlsl",
        "main_part_transforms_abi.hlsl",
        "main_part_uvframe_abi.hlsl",
        "main_part_packed_transform_vertex.hlsl",
        "main_part_packed_triple_morph_uv_animation_vertex.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert "EvaluateMainPartPackedTripleMorphUvAnimationVertex" in lifted
    assert "partPositionState" not in lifted

