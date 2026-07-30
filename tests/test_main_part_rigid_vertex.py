from shader_toolchain.recipes.main_part import (
    RIGID_TANGENT_UV1_CUTOFF_DEFINES,
    is_main_part_rigid_tangent_uv1_cutoff,
    lift_main_part_rigid_tangent_uv1_cutoff,
)


def test_rigid_tangent_uv1_cutoff_policy_is_exact() -> None:
    defines = sorted(RIGID_TANGENT_UV1_CUTOFF_DEFINES)
    assert is_main_part_rigid_tangent_uv1_cutoff(defines)
    assert not is_main_part_rigid_tangent_uv1_cutoff(
        [define for define in defines if define != "TRANSFER_CUTOFF"]
    )
    assert not is_main_part_rigid_tangent_uv1_cutoff(
        defines + ["VS_POSE_0_ANIM"]
    )


def test_rigid_vertex_lift_reuses_explicit_ltw_model() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0, float4 v1 : TEXCOORD0,
  float2 v2 : TEXCOORD1, float3 v3 : NORMAL0,
  float4 v4 : TANGENT0, float4 v5 : LTW0,
  float4 v6 : LTW1, float4 v7 : LTW2, uint4 v8 : INSTANCE_DATA0,
  out float4 o0 : SV_Position0, out float3 o1 : VIEW_POSITION0,
  out float2 o2 : UV0, out float2 p2 : UV1,
  out float3 o3 : NORMAL0, out float3 o4 : TANGENT0,
  out float3 o5 : BITANGENT0, out float4 o6 : VERTEXCOLOR0,
  out noperspective float o7 : CUTOFF0) {}
'''
    lifted = lift_main_part_rigid_tangent_uv1_cutoff(source)
    assert '#include "include/main_part_projection_abi.hlsl"' in lifted
    assert '#include "include/main_part_perframe_abi.hlsl"' in lifted
    assert '#include "include/main_part_morph_vertex.hlsl"' in lifted
    assert '#include "include/main_part_rigid_vertex.hlsl"' in lifted
    assert "float2 v1 : TEXCOORD0" in lifted
    assert "EvaluateMainPartRigidSurfaceVertex" in lifted
    for assignment in (
        "o0 =", "o1 =", "o2 =", "p2 =", "o3 =", "o4 =", "o5 =",
        "o6 =", "o7 =",
    ):
        assert assignment in lifted
    assert "partPositionState" not in lifted
