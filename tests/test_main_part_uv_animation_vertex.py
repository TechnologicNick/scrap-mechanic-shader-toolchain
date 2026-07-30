from shader_toolchain.recipes.main_part import (
    UV_ANIMATION_POSE0_CUTOFF_DEFINES,
    is_main_part_uv_animation_pose0_cutoff,
    lift_main_part_uv_animation_pose0_cutoff,
)


def test_uv_animation_pose0_cutoff_policy_is_exact() -> None:
    defines = sorted(UV_ANIMATION_POSE0_CUTOFF_DEFINES)
    assert is_main_part_uv_animation_pose0_cutoff(defines)
    assert not is_main_part_uv_animation_pose0_cutoff(
        [define for define in defines if define != "TRANSFER_CUTOFF"]
    )
    assert not is_main_part_uv_animation_pose0_cutoff(
        defines + ["VS_POSE_1_ANIM"]
    )


def test_uv_animation_lift_uses_typed_vertex_result() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_UVFRAME { float4 uvAnimationFrame; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0, float2 v1 : TEXCOORD0,
  float3 v2 : NORMAL0, float4 v3 : TANGENT0,
  float3 v4 : POSITION1, float3 v5 : NORMAL1,
  float4 v6 : LTW0, float4 v7 : LTW1, float4 v8 : LTW2,
  uint4 v9 : INSTANCE_DATA0, out float4 o0 : SV_Position0,
  out float2 o1 : UV0, out noperspective float o2 : CUTOFF0) {}
'''
    lifted = lift_main_part_uv_animation_pose0_cutoff(source)
    assert '#include "include/main_part_uv_animation_vertex.hlsl"' in lifted
    assert "EvaluateMainPartUvAnimationVertex" in lifted
    assert "o0 = vertex.clipPosition" in lifted
    assert "o1 = vertex.uv" in lifted
    assert "o2 = vertex.cutoff" in lifted
    assert "partPositionState" not in lifted
