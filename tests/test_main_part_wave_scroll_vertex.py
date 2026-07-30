from shader_toolchain.recipes.main_part import (
    FULL_TRANSFORM_WAVE_SCROLL_SCREEN_DEFINES,
    is_main_part_full_transform_wave_scroll_screen,
    lift_main_part_full_transform_wave_scroll_screen,
)


def test_wave_scroll_screen_policy_is_exact() -> None:
    defines = sorted(FULL_TRANSFORM_WAVE_SCROLL_SCREEN_DEFINES)
    assert is_main_part_full_transform_wave_scroll_screen(defines)
    assert not is_main_part_full_transform_wave_scroll_screen(
        [define for define in defines if define != "VS_WAVE_NO_SCALE"]
    )
    assert not is_main_part_full_transform_wave_scroll_screen(
        defines + ["TRANSFER_COLOR"]
    )


def test_wave_scroll_screen_lift_preserves_contract() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 frame; }
cbuffer CB_UV_SCROLL { float4 scroll; }
cbuffer CB_WAVE { float4 wave; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
 float3 v0 : POSITION0, float2 v1 : TEXCOORD0,
 float3 v2 : NORMAL0, float4 v3 : TANGENT0,
 float4 v4 : LTW0, float4 v5 : LTW1, float4 v6 : LTW2,
 uint4 v7 : INSTANCE_DATA0, out float4 o0 : SV_Position0,
 out float2 o1 : UV0, out float3 o2 : SCREEN_UV0) {}
'''
    lifted = lift_main_part_full_transform_wave_scroll_screen(source)
    for filename in (
        "main_part_projection_abi.hlsl", "main_part_perframe_abi.hlsl",
        "main_part_uv_scroll_abi.hlsl", "main_part_wave_abi.hlsl",
        "main_part_wave_common.hlsl", "main_part_wave_scroll_vertex.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert "EvaluateMainPartWaveScrollVertex" in lifted
    assert "o0 = vertex.clipPosition" in lifted
    assert "o1 = vertex.uv0" in lifted
    assert "o2 = vertex.screenUv" in lifted
    assert "partPositionState" not in lifted
