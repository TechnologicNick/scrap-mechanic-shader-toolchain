from shader_toolchain.recipes.main_part import (
    TRIPLE_MORPH_OCCLUSION_SURFACE_DEFINES,
    is_main_part_triple_morph_occlusion_surface,
    lift_main_part_triple_morph_occlusion_surface,
)


def test_triple_morph_occlusion_surface_policy_is_exact() -> None:
    defines = sorted(TRIPLE_MORPH_OCCLUSION_SURFACE_DEFINES)
    assert is_main_part_triple_morph_occlusion_surface(defines)
    assert not is_main_part_triple_morph_occlusion_surface(
        [define for define in defines if define != "VS_POSE_2_ANIM"]
    )
    assert not is_main_part_triple_morph_occlusion_surface(
        defines + ["TRANSFER_UV1"]
    )


def test_triple_morph_lift_reuses_explicit_ltw_model() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0, float2 v1 : TEXCOORD0, float4 v2 : COLOR0,
  float3 v3 : NORMAL0, float4 v4 : TANGENT0,
  float3 v5 : POSITION1, float3 v6 : NORMAL1,
  float3 v7 : POSITION2, float3 v8 : NORMAL2,
  float3 v9 : POSITION3, float3 v10 : NORMAL3,
  float4 v11 : LTW0, float4 v12 : LTW1, float4 v13 : LTW2,
  uint4 v14 : INSTANCE_DATA0,
  out float4 o0 : SV_Position0, out float3 o1 : VIEW_POSITION0,
  out float2 o2 : UV0, out float p2 : OCCLUSION0,
  out float3 o3 : NORMAL0, out float3 o4 : TANGENT0,
  out float3 o5 : BITANGENT0, out float4 o6 : VERTEXCOLOR0,
  out float3 o7 : SCREEN_UV0) {}
'''
    lifted = lift_main_part_triple_morph_occlusion_surface(source)
    assert '#include "include/main_part_projection_abi.hlsl"' in lifted
    assert '#include "include/main_part_perframe_abi.hlsl"' in lifted
    assert '#include "include/main_part_morph_vertex.hlsl"' in lifted
    assert '#include "include/main_part_triple_morph_vertex.hlsl"' in lifted
    assert "EvaluateMainPartTripleMorphSurfaceVertex" in lifted
    for assignment in (
        "o0 =", "o1 =", "o2 =", "p2 =", "o3 =", "o4 =", "o5 =",
        "o6 =", "o7 =",
    ):
        assert assignment in lifted
    assert "partPositionState" not in lifted
