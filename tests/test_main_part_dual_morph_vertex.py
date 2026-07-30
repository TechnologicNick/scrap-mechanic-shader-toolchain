from shader_toolchain.recipes.main_part import (
    DUAL_MORPH_PARALLAX_PLANE_DEFINES,
    is_main_part_dual_morph_parallax_plane,
    lift_main_part_dual_morph_parallax_plane,
)


def test_dual_morph_parallax_plane_policy_is_exact() -> None:
    defines = sorted(DUAL_MORPH_PARALLAX_PLANE_DEFINES)
    assert is_main_part_dual_morph_parallax_plane(defines)
    assert not is_main_part_dual_morph_parallax_plane(
        [define for define in defines if define != "PARALLAX_PLANE"]
    )
    assert not is_main_part_dual_morph_parallax_plane(
        defines + ["VS_POSE_2_ANIM"]
    )


def test_dual_morph_lift_reuses_explicit_ltw_model() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0, float2 v1 : TEXCOORD0,
  float3 v2 : NORMAL0, float4 v3 : TANGENT0,
  float3 v4 : POSITION1, float3 v5 : NORMAL1,
  float3 v6 : POSITION2, float3 v7 : NORMAL2,
  float4 v8 : LTW0, float4 v9 : LTW1, float4 v10 : LTW2,
  uint4 v11 : INSTANCE_DATA0,
  out float4 o0 : SV_Position0, out float3 o1 : VIEW_POSITION0,
  out float2 o2 : UV0, out float3 o3 : NORMAL0,
  out float3 o4 : TANGENT0, out float3 o5 : BITANGENT0,
  out float4 o6 : VERTEXCOLOR0, out float3 o7 : SCREEN_UV0,
  out float4 o8 : PLANE_VIEW_POS0) {}
'''
    lifted = lift_main_part_dual_morph_parallax_plane(source)
    assert '#include "include/main_part_projection_abi.hlsl"' in lifted
    assert '#include "include/main_part_perframe_abi.hlsl"' in lifted
    assert '#include "include/main_part_morph_vertex.hlsl"' in lifted
    assert '#include "include/main_part_dual_morph_vertex.hlsl"' in lifted
    assert "EvaluateMainPartDualMorphVertex" in lifted
    for assignment in ("o0 =", "o1 =", "o2 =", "o3 =", "o4 =", "o5 =", "o6 =", "o7 =", "o8 ="):
        assert assignment in lifted
    assert "partPositionState" not in lifted
