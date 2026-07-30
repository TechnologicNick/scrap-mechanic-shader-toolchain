from shader_toolchain.recipes.main_part import (
    PACKED_SCALED_WAVE_PICKING_SCROLL_DEFINES,
    is_main_part_packed_scaled_wave_picking_scroll,
    lift_main_part_packed_scaled_wave_picking_scroll,
)


def test_packed_scaled_wave_picking_policy_is_exact() -> None:
    defines = sorted(PACKED_SCALED_WAVE_PICKING_SCROLL_DEFINES)
    assert is_main_part_packed_scaled_wave_picking_scroll(defines)
    assert not is_main_part_packed_scaled_wave_picking_scroll(
        [define for define in defines if define != "VS_WAVE"]
    )
    assert not is_main_part_packed_scaled_wave_picking_scroll(
        defines + ["TRANSFER_SCREEN_UV"]
    )


def test_packed_scaled_wave_picking_lift_has_policy_wrapper() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_TRANSFORMS : register(b7) { float4 transforms; }
cbuffer CB_PICKING : register(b13) { float4 picking; }
cbuffer CB_UV_SCROLL { float4 scroll; }
cbuffer CB_WAVE { float4 wave; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0, float2 v1 : TEXCOORD0, float3 v2 : NORMAL0,
  float4 v3 : TANGENT0, int4 v4 : LTWPACKED0, uint4 v5 : INSTANCE_DATA0,
  out float4 o0 : SV_Position0, out float2 o1 : UV0,
  out float4 o2 : VERTEXCOLOR0) {}
'''
    lifted = lift_main_part_packed_scaled_wave_picking_scroll(source)
    for filename in (
        "main_part_projection_abi.hlsl", "main_part_perframe_abi.hlsl",
        "main_part_transforms_abi.hlsl", "main_part_picking_abi.hlsl",
        "main_part_uv_scroll_abi.hlsl", "main_part_wave_abi.hlsl",
        "main_part_packed_transform_vertex.hlsl",
        "main_part_scaled_wave_by_scale_common.hlsl",
        "main_part_picking_common.hlsl",
        "main_part_packed_scaled_wave_vertex.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert "EvaluateMainPartPackedScaledWaveClipPosition" in lifted
    assert "MainPartDecodePickingColor" in lifted
    assert "partPositionState" not in lifted
