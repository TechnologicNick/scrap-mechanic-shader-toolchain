from shader_toolchain.recipes.main_part import (
    TRIPLE_MORPH_UV_ANIMATION_DEFINES,
    is_main_part_triple_morph_uv_animation,
    lift_main_part_triple_morph_uv_animation,
)


def test_triple_morph_uv_animation_policy_is_exact() -> None:
    defines = sorted(TRIPLE_MORPH_UV_ANIMATION_DEFINES)
    assert is_main_part_triple_morph_uv_animation(defines)
    assert not is_main_part_triple_morph_uv_animation(
        [define for define in defines if define != "VS_POSE_2_ANIM"]
    )
    assert not is_main_part_triple_morph_uv_animation(
        defines + ["TRANSFER_COLOR"]
    )


def test_triple_morph_uv_animation_lift_uses_typed_family_core() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_UVFRAME { float4 uvAnimationFrame; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0, float2 v1 : TEXCOORD0,
  float3 v2 : NORMAL0, float4 v3 : TANGENT0,
  float3 v4 : POSITION1, float3 v5 : NORMAL1,
  float3 v6 : POSITION2, float3 v7 : NORMAL2,
  float3 v8 : POSITION3, float3 v9 : NORMAL3,
  float4 v10 : LTW0, float4 v11 : LTW1, float4 v12 : LTW2,
  uint4 v13 : INSTANCE_DATA0, out float4 o0 : SV_Position0,
  out float2 o1 : UV0) {}
'''
    lifted = lift_main_part_triple_morph_uv_animation(source)
    for filename in (
        "main_part_projection_abi.hlsl",
        "main_part_perframe_abi.hlsl",
        "main_part_uvframe_abi.hlsl",
        "main_part_triple_morph_uv_animation_vertex.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert "EvaluateMainPartTripleMorphUvAnimationVertex" in lifted
    assert "o0 = vertex.clipPosition" in lifted
    assert "o1 = vertex.uv0" in lifted
    assert "partPositionState" not in lifted
