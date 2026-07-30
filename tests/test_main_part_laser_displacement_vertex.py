from shader_toolchain.recipes.main_part import (
    LASER_DISPLACEMENT_PACKED_POSE_PICKING_DEFINES,
    is_main_part_laser_displacement_packed_pose_picking,
    lift_main_part_laser_displacement_packed_pose_picking,
)


def test_laser_displacement_packed_pose_picking_policy_is_exact() -> None:
    defines = sorted(LASER_DISPLACEMENT_PACKED_POSE_PICKING_DEFINES)
    assert is_main_part_laser_displacement_packed_pose_picking(defines)
    assert not is_main_part_laser_displacement_packed_pose_picking(
        [define for define in defines if define != "VS_LASER_GLITCH"]
    )
    assert not is_main_part_laser_displacement_packed_pose_picking(
        defines + ["TRANSFER_SCREEN_UV"]
    )


def test_laser_displacement_lift_uses_shared_abis_and_phase_root() -> None:
    source = '''cbuffer CB_LASER_DISPLACEMENT { float4 laser; }
cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_TRANSFORMS : register(b7) { float4 transforms; }
cbuffer CB_PICKING : register(b13) { float4 picking; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0, float2 v1 : TEXCOORD0,
  float3 v2 : NORMAL0, float3 v3 : POSITION1, float3 v4 : NORMAL1,
  int4 v5 : LTWPACKED0, uint4 v6 : INSTANCE_DATA0,
  out float4 o0 : SV_Position0, out float2 o1 : UV0,
  out float4 o2 : VERTEXCOLOR0) {}
'''
    lifted = lift_main_part_laser_displacement_packed_pose_picking(source)
    for filename in (
        "main_part_laser_displacement_abi.hlsl",
        "main_part_projection_abi.hlsl",
        "main_part_perframe_abi.hlsl",
        "main_part_transforms_abi.hlsl",
        "main_part_picking_abi.hlsl",
        "main_part_laser_displacement_packed_pose_picking.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert "partPositionState" not in lifted
    assert "EvaluateMainPartPackedLaserVertex" in lifted
    function_body = lifted[lifted.index("void mainVS(") :]
    assert "#include" not in function_body
