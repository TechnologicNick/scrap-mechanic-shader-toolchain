from shader_toolchain.recipes.main_part import (
    LASER_BEHIND_FULL_DEFINES,
    is_main_part_laser_behind_full,
    lift_main_part_laser_behind_full,
)


def test_laser_behind_full_policy_is_exact() -> None:
    defines = sorted(LASER_BEHIND_FULL_DEFINES)
    assert is_main_part_laser_behind_full(defines)
    assert not is_main_part_laser_behind_full(
        [define for define in defines if define != "PS_LASER_FOG"]
    )
    assert not is_main_part_laser_behind_full(
        defines + ["PS_RESPONSIVE_GLOW"]
    )


def test_laser_behind_full_lift_has_named_evaluator() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_LASER { float4 laser; }
SamplerState PointClampClamp_s : register(s1);
SamplerState LinearWrapWrap_s : register(s3);
Texture2D<float4> tLaser : register(t0);
Texture2D<float4> tLaserMask : register(t1);
Texture3D<float> tLaserFog : register(t4);
Texture2D<float4> tDepth : register(t7);
// 3Dmigoto declarations
#define cmp -
void commonPS(
  float4 v0 : SV_Position0, float3 v1 : VIEW_POSITION0,
  float2 v2 : UV0, float3 v3 : NORMAL0, float4 v4 : VERTEXCOLOR0,
  linear noperspective centroid float3 v5 : SCREEN_UV0,
  float4 v6 : FOG_COLOR0, uint v7 : SV_IsFrontFace0,
  out float3 o0 : SV_Target0, out float2 o1 : SV_Target1) {}
'''
    lifted = lift_main_part_laser_behind_full(source)
    for filename in (
        "main_part_projection_abi.hlsl", "main_part_perframe_abi.hlsl",
        "main_part_laser_abi.hlsl", "main_part_laser_behind.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert "EvaluateMainPartLaserBehind" in lifted
    assert "laser.color" in lifted
    assert "laser.glowAndAlpha" in lifted
    assert "partPositionState" not in lifted
