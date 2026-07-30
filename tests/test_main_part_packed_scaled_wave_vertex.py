from shader_toolchain.recipes.main_part import (
    PACKED_SCALED_WAVE_UV_DEFINES,
    is_main_part_packed_scaled_wave_uv,
    lift_main_part_packed_scaled_wave_uv,
)


def test_packed_scaled_wave_uv_policy_is_exact() -> None:
    defines = sorted(PACKED_SCALED_WAVE_UV_DEFINES)
    assert is_main_part_packed_scaled_wave_uv(defines)
    assert not is_main_part_packed_scaled_wave_uv(
        [define for define in defines if define != "VS_WAVE"]
    )
    assert not is_main_part_packed_scaled_wave_uv(
        defines + ["VS_UV0_SCROLL"]
    )


def test_packed_scaled_wave_uv_lift_is_thin() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_TRANSFORMS : register(b7) { float4 transforms; }
cbuffer CB_WAVE { float4 wave; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0, float2 v1 : TEXCOORD0, float3 v2 : NORMAL0,
  float4 v3 : TANGENT0, int4 v4 : LTWPACKED0, uint4 v5 : INSTANCE_DATA0,
  out float4 o0 : SV_Position0, out float2 o1 : UV0) {}
'''
    lifted = lift_main_part_packed_scaled_wave_uv(source)
    for filename in (
        "main_part_projection_abi.hlsl", "main_part_perframe_abi.hlsl",
        "main_part_transforms_abi.hlsl", "main_part_wave_abi.hlsl",
        "main_part_packed_transform_vertex.hlsl",
        "main_part_scaled_wave_by_scale_common.hlsl",
        "main_part_packed_scaled_wave_vertex.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert "EvaluateMainPartPackedScaledWaveClipPosition" in lifted
    assert "o1 = v1;" in lifted
    assert "partPositionState" not in lifted
