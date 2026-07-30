from shader_toolchain.recipes.main_part import (
    PACKED_TRANSFORM_MORPH_UV1_CUTOFF_DEFINES,
    is_main_part_packed_transform_morph_uv1_cutoff,
    lift_main_part_packed_transform_morph_uv1_cutoff,
)


def test_packed_transform_morph_policy_is_exact() -> None:
    defines = sorted(PACKED_TRANSFORM_MORPH_UV1_CUTOFF_DEFINES)
    assert is_main_part_packed_transform_morph_uv1_cutoff(defines)
    assert not is_main_part_packed_transform_morph_uv1_cutoff(
        [define for define in defines if define != "TRANSFER_CUTOFF"]
    )
    assert not is_main_part_packed_transform_morph_uv1_cutoff(
        defines + ["VS_FULL_TRANSFORM"]
    )


def test_packed_transform_lift_preserves_vertex_contract() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_TRANSFORMS : register(b7) { float4 transforms; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0, float4 v1 : TEXCOORD0,
  float2 v2 : TEXCOORD1, float3 v3 : NORMAL0,
  float3 v4 : POSITION1, float3 v5 : NORMAL1,
  int4 v6 : LTWPACKED0, uint4 v7 : INSTANCE_DATA0,
  out float4 o0 : SV_Position0, out float3 o1 : VIEW_POSITION0,
  out float2 o2 : UV0, out float2 p2 : UV1,
  out float3 o3 : NORMAL0, out float4 o4 : VERTEXCOLOR0,
  out noperspective float o5 : CUTOFF0) {}
'''
    lifted = lift_main_part_packed_transform_morph_uv1_cutoff(source)
    for filename in (
        "main_part_projection_abi.hlsl", "main_part_perframe_abi.hlsl",
        "main_part_transforms_abi.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert '#include "include/main_part_packed_transform_vertex.hlsl"' in lifted
    assert "EvaluateMainPartPackedTransformVertex" in lifted
    assert "float2 v1 : TEXCOORD0" in lifted
    for assignment in ("o0 =", "o1 =", "o2 =", "p2 =", "o3 =", "o4 =", "o5 ="):
        assert assignment in lifted
    assert "partPositionState" not in lifted
