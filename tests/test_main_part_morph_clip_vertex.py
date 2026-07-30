from shader_toolchain.recipes.main_part import (
    MORPH_CLIP_VERTEX_DEFINES,
    is_main_part_morph_clip_vertex,
    lift_main_part_morph_clip_vertex,
)


def test_morph_clip_vertex_policy_is_exact() -> None:
    defines = sorted(MORPH_CLIP_VERTEX_DEFINES)
    assert is_main_part_morph_clip_vertex(defines)
    assert not is_main_part_morph_clip_vertex(
        [define for define in defines if define != "VS_POSE_0_ANIM"]
    )
    assert not is_main_part_morph_clip_vertex(defines + ["TRANSFER_UV0"])


def test_morph_clip_vertex_lift_preserves_minimal_signature() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0, float2 v1 : TEXCOORD0,
  float3 v2 : NORMAL0, float3 v3 : POSITION1,
  float3 v4 : NORMAL1, float4 v5 : LTW0,
  float4 v6 : LTW1, float4 v7 : LTW2,
  uint4 v8 : INSTANCE_DATA0, out float4 o0 : SV_Position0) {}
'''
    lifted = lift_main_part_morph_clip_vertex(source)
    for filename in (
        "main_part_projection_abi.hlsl",
        "main_part_perframe_abi.hlsl",
        "main_part_morph_clip_vertex.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert "EvaluateMainPartMorphClipVertex" in lifted
    assert "out float4 o0 : SV_Position0" in lifted
    assert "partPositionState" not in lifted

