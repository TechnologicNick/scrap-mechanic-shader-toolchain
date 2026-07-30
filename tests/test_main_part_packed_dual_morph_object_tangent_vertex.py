from shader_toolchain.recipes.main_part import (
    PACKED_DUAL_MORPH_OBJECT_TANGENT_DEFINES,
    is_main_part_packed_dual_morph_object_tangent,
    lift_main_part_packed_dual_morph_object_tangent,
)


def test_packed_dual_morph_object_tangent_policy_is_exact() -> None:
    defines = sorted(PACKED_DUAL_MORPH_OBJECT_TANGENT_DEFINES)
    assert is_main_part_packed_dual_morph_object_tangent(defines)
    assert not is_main_part_packed_dual_morph_object_tangent(
        [define for define in defines if define != "TRANSFER_OBJECT_TANGENT"]
    )
    assert not is_main_part_packed_dual_morph_object_tangent(
        defines + ["TRANSFER_NORMAL"]
    )


def test_packed_dual_morph_object_tangent_lift_uses_shared_frame() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_TRANSFORMS : register(b7) { float4 transforms; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0, float2 v1 : TEXCOORD0,
  float3 v2 : NORMAL0, float4 v3 : TANGENT0,
  float3 v4 : POSITION1, float3 v5 : NORMAL1,
  float3 v6 : POSITION2, float3 v7 : NORMAL2,
  int4 v8 : LTWPACKED0, uint4 v9 : INSTANCE_DATA0,
  out float4 o0 : SV_Position0,
  out float3 o1 : OBJECT_TANGENT0) {}
'''
    lifted = lift_main_part_packed_dual_morph_object_tangent(source)
    for filename in (
        "main_part_projection_abi.hlsl",
        "main_part_perframe_abi.hlsl",
        "main_part_transforms_abi.hlsl",
        "main_part_packed_transform_vertex.hlsl",
        "main_part_packed_dual_morph_object_tangent_vertex.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert "EvaluateMainPartPackedDualMorphObjectTangentVertex" in lifted
    assert "out float3 o1 : OBJECT_TANGENT0" in lifted
    assert "partPositionState" not in lifted

