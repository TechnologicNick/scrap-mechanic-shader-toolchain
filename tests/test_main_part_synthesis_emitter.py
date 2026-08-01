from shader_toolchain.main_part_synthesis_emitter import (
    emit_family_source,
    expand_emitted_wrapper,
    parse_source_preserving_body,
)


def _source(reflection: str) -> str:
    return f"""
Texture2D<float4> tDif : register(t0);
// 3Dmigoto declarations
#define cmp -
void commonPS(
  float2 v0 : UV0,
  out float4 o0 : SV_Target0)
{{
  float4 surfaceState;
  surfaceState = tDif.Load(int3(v0, 0));
  surfaceState.xyz += {reflection};
  o0 = surfaceState;
  return;
}}
"""


def test_source_preserving_body_tracks_exact_spans_and_executable_tokens() -> None:
    source = _source("float3(0.0, 0.0, 0.0)")
    body = parse_source_preserving_body(source)
    assert source[body.tokens[0].start:body.tokens[0].end] == "float4"
    assert "smtemporary0" in body.executable_tokens
    assert "smin_uv0" in body.executable_tokens
    assert "smout_sv_target0" in body.executable_tokens


def test_emitter_writes_one_semantic_asset_and_thin_policy_wrappers() -> None:
    sources = {
        "SM_SHADER_A": _source("float3(0.0, 0.0, 0.0)"),
        "SM_SHADER_B": _source("float3(1.0, 1.0, 1.0)"),
    }
    emitted = emit_family_source(
        "transparent_water_surface",
        sources,
        {
            "SM_SHADER_A": ("default", "off"),
            "SM_SHADER_B": ("high", "multi"),
        },
        minimum_common_tokens=3,
    )
    assert emitted.asset_filename == "main_part_transparent_water_surface.hlsl"
    assert emitted.evaluator == "EvaluateTransparentWaterSurface"
    assert all("SM_SHADER_A" not in source for source in emitted.assets.values())
    assert all("SM_SHADER_B" not in source for source in emitted.assets.values())
    assert "#define SM_SYNTH" not in "\n".join(emitted.assets.values())
    assert "void EvaluateTransparentWaterSurface" in emitted.asset_source
    policy_asset = emitted.assets[
        "main_part_transparent_water_surface_default_off.hlsl"
    ]
    assert "void EvaluateTransparentWaterSurfacePolicy0" in policy_asset
    assert "inout float4 smLocalFloat40" in policy_asset
    assert "smLocalFloat40.xyz += float3 (0.0, 0.0, 0.0);" in policy_asset
    assert "struct TransparentWaterSurfaceState" not in policy_asset
    assert "EvaluateTransparentWaterSurfacePolicy1(smLocalFloat40);" in (
        emitted.asset_source
    )

    wrapper = emitted.wrappers["SM_SHADER_A"]
    assert "// 3Dmigoto declarations" not in wrapper
    assert "EvaluateTransparentWaterSurface" in wrapper
    assert "surfaceState" not in wrapper
    expanded = expand_emitted_wrapper(wrapper, emitted)
    assert emitted.asset_filename not in expanded
    assert "#include" not in expanded
    assert "0.0, 0.0, 0.0" in expanded
