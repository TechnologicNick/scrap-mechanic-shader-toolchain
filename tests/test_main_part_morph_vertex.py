from shader_toolchain.recipes.main_part import (
    is_main_part_morph_vertex,
    lift_main_part_morph_vertex,
)


MORPH_DEFINES = [
    "TRANSFER_COLOR", "TRANSFER_NORMAL", "TRANSFER_SCREEN_UV",
    "TRANSFER_TANGENTS", "TRANSFER_UV0", "TRANSFER_UV1",
    "TRANSFER_VIEW_POSITION", "VERTEX_SHADER", "VS_FULL_TRANSFORM",
    "VS_INPUT_TANGENTS", "VS_INPUT_UV1", "VS_POSE_0_ANIM",
]


def test_main_part_morph_vertex_policy_is_exact() -> None:
    assert is_main_part_morph_vertex(MORPH_DEFINES)
    assert not is_main_part_morph_vertex(MORPH_DEFINES + ["VS_WAVE"])
    assert is_main_part_morph_vertex(
        [define for define in MORPH_DEFINES if define != "TRANSFER_UV1"]
    )
    assert is_main_part_morph_vertex([
        "VERTEX_SHADER", "VS_FULL_TRANSFORM", "VS_INPUT_TANGENTS",
        "VS_INPUT_UV1", "VS_POSE_0_ANIM",
    ])


def test_main_part_morph_vertex_lift_has_typed_phases() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5)
{
  float4 projection;
}
cbuffer CB_PERFRAME : register(b12)
{
  float4 perFrame;
}
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0,
  float4 v1 : TEXCOORD0,
  float2 v2 : TEXCOORD1,
  float3 v3 : NORMAL0,
  float4 v4 : TANGENT0,
  float3 v5 : POSITION1,
  float3 v6 : NORMAL1,
  float4 v7 : LTW0,
  float4 v8 : LTW1,
  float4 v9 : LTW2,
  uint4 v10 : INSTANCE_DATA0,
  out float4 o0 : SV_Position0,
  out float4 o1 : VERTEXCOLOR0) {}
'''
    lifted = lift_main_part_morph_vertex(source)
    assert '#include "include/main_part_projection_abi.hlsl"' in lifted
    assert '#include "include/main_part_perframe_abi.hlsl"' in lifted
    assert '#include "include/main_part_morph_vertex.hlsl"' in lifted
    assert "EvaluateMainPartMorphVertex" in lifted
    assert "o0 = vertex.clipPosition" in lifted
    assert "o1 = vertex.color" in lifted
    assert "vertex.normalView" not in lifted
    assert "partPositionState" not in lifted
    assert "3Dmigoto" not in lifted
