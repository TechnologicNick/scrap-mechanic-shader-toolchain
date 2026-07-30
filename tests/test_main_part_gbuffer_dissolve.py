from shader_toolchain.recipes.main_part import (
    GBUFFER_DISSOLVE_UV0_DEFINES,
    is_main_part_gbuffer_dissolve_uv0,
    lift_main_part_gbuffer_dissolve_uv0,
)


def test_gbuffer_dissolve_policy_is_exact() -> None:
    defines = sorted(GBUFFER_DISSOLVE_UV0_DEFINES)
    assert is_main_part_gbuffer_dissolve_uv0(defines)
    assert not is_main_part_gbuffer_dissolve_uv0(
        [define for define in defines if define != "PS_DISSOLVE_UV0"]
    )
    assert not is_main_part_gbuffer_dissolve_uv0(
        defines + ["PS_NOR_TEX"]
    )


def test_gbuffer_dissolve_lift_preserves_contract() -> None:
    source = '''cbuffer CB_PERFRAME : register(b12) { float4 frame; }
cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_DISSOLVE { float4 dissolve; }
SamplerState LinearWrapWrap_s : register(s3);
Texture2D<float4> tDif : register(t0);
Texture2D<float4> tAsg : register(t1);
Texture2D<float> tCutoff : register(t5);
// 3Dmigoto declarations
#define cmp -
void commonPS(
  float4 v0 : SV_Position0, float3 v1 : VIEW_POSITION0,
  float2 v2 : UV0, float3 v3 : NORMAL0, float4 v4 : VERTEXCOLOR0,
  nointerpolation float v5 : CUTOFF0, uint v6 : SV_IsFrontFace0,
  out float4 o0 : SV_Target0, out float2 o1 : SV_Target1,
  out float4 o2 : SV_Target2) {}
'''
    lifted = lift_main_part_gbuffer_dissolve_uv0(source)
    for filename in (
        "main_part_perframe_abi.hlsl", "main_part_projection_abi.hlsl",
        "main_part_dissolve_b0_abi.hlsl", "main_part_octahedral_normal.hlsl",
        "main_part_gbuffer_dissolve.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert '#include "include/main_part_gbuffer_dissolve.hlsl"' in lifted
    assert "EvaluateMainPartDissolveBand(" in lifted
    assert "EvaluateMainPartDissolveGBuffer(" in lifted
    assert "WriteMainPartDissolveGBuffer(" in lifted
    assert "partPositionState" not in lifted
    function_body = lifted[lifted.index("void commonPS(") :]
    assert '#include "include/' not in function_body
