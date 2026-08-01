from pathlib import Path

from shader_toolchain.recipes.common import asset
from shader_toolchain.recipes.indirect_cascade_upscale import (
    _emit_variant_snippets,
    _lift_coverage_weights,
    _lift_depth_gathers,
    _lift_gaussian_weights,
    _lift_linear_depth,
    _lift_material_responses,
    _lift_normal_decodes,
    _lift_bound_cascade_only_main,
    _lift_bound_cascade_no_history_main,
    _lift_bound_indirect_only_main,
    _lift_bound_sss_depth_cascade_main,
    _lift_bound_sss_only_main,
    _lift_bound_indirect_sss_main,
    _lift_bound_ao_only_main,
    _lift_bound_ao_sss_main,
    _lift_bound_cascade_indirect_main,
    _lift_bound_full_output_main,
    _lift_bound_ao_depth_cascade_main,
    _lift_bound_cascade_depth_only_main,
    _lift_bound_cascade_depth_no_history_main,
    _lift_bound_cascade_payload_no_history_main,
    _lift_bound_ao_cascade_no_history_main,
    _lift_bound_cascade_payload_main,
    _lift_bound_ao_cascade_main,
    _lift_bound_full_temporal_main,
    _lift_bound_full_depth_no_history_main,
    _lift_bound_ao_indirect_main,
    _lift_bound_ao_indirect_sss_main,
    _lift_bound_upscale_main,
)


def test_upscale_asset_exposes_recovered_filter_primitives() -> None:
    source = asset("indirect_cascade_upscale_primitives.hlsl")
    assert "struct UpscaleMaterialResponse" in source
    assert "UpscaleMaterialResponse EvaluateUpscaleMaterial" in source
    assert "float LinearizeUpscaleDepth" in source
    assert "float3 DecodeUpscaleNormal" in source
    assert "float4 GatherUpscaleDepthError" in source
    assert "float ComputeUpscaleGaussianWeight" in source
    assert "float ComputeUpscaleCoverageWeight" in source
    assert "UpscaledAoSss FilterAoSssCross" in source
    assert "UpscaleCascadeSelection SelectUpscaleCascade" in source
    assert "float3 TransformUpscalePosition" in source
    assert "float3 ProjectUpscalePosition" in source
    assert "float4 SwizzleUpscaleSss" in source
    assert "float ReadUpscaleVolatility" in source
    assert "UpscaleCascadeShadow SampleUpscaleMediumCascade" in source
    assert "UpscaleCascadeShadow SampleUpscaleLowCascade" in source
    assert "float EvaluateUpscaleMediumCascadeShadow" in source
    assert "float EvaluateUpscaleLowCascadeShadow" in source
    assert "float ApplyUpscaleDirectionalFacing" in source
    assert "float ComposeUpscaleAo" in source
    assert "UpscaleTemporalResult ResolveUpscaleTemporal" in source
    assert "ResolveUpscaleTemporalWithoutCascadeHistory" in source


def test_bound_asset_exposes_typed_upscale_pipeline() -> None:
    source = asset("indirect_cascade_upscale_bound.hlsl")
    assert "struct UpscaleSurface" in source
    assert "struct UpscaleCascadeLighting" in source
    assert "UpscalePosition ReconstructOrthoUpscalePosition" in source
    assert "UpscaleSurface GatherBoundUpscaleSurface" in source
    assert "GatherBoundPerspectiveUpscaleSurface" in source
    assert "EvaluateBoundUpscaleCascadeLighting" in source
    assert "EvaluateBoundLowUpscaleCascadeLighting" in source
    assert "ResolveBoundUpscaleTemporal" in source
    assert "ResolveBoundUpscaleTemporalWithoutCascadeHistory" in source


def test_cascade_bound_asset_exposes_quality_and_temporal_policies() -> None:
    source = asset("indirect_cascade_upscale_cascade_bound.hlsl")
    assert "struct UpscaleCascadeSurface" in source
    assert "GatherBoundPerspectiveCascadeSurface" in source
    assert "HasNegativeUpscaleVolatility" in source
    assert "EvaluateBoundLowCascadeOnlyLighting" in source
    assert "EvaluateBoundMediumCascadeOnlyLighting" in source
    assert "ResolveBoundLowMediumCascadeOnlyTemporal" in source
    assert "ResolveBoundHighCascadeOnlyTemporal" in source


def test_cascade_depth_bound_asset_separates_hzb_and_scene_surfaces() -> None:
    source = asset("indirect_cascade_upscale_cascade_depth_bound.hlsl")
    assert '#include "indirect_cascade_upscale_cascade_bound.hlsl"' in source
    assert "GatherBoundOrthoCascadeSurface" in source
    assert "ReconstructBoundPerspectiveCascadePosition" in source
    assert "ReconstructBoundOrthoCascadePosition" in source
    assert "EvaluateBoundLowDepthCascadeOnlyLighting" in source
    assert "EvaluateBoundMediumDepthCascadeOnlyLighting" in source


def test_full_depth_bound_asset_exposes_current_cascade_pipeline() -> None:
    source = asset("indirect_cascade_upscale_full_depth_bound.hlsl")
    assert '#include "indirect_cascade_upscale_full_bound.hlsl"' in source
    assert "EvaluateBoundLowFullDepthCascade" in source
    assert "EvaluateBoundMediumFullDepthCascade" in source
    assert "ResolveBoundFullDepthAoSssTemporal" in source
    assert "ResolveBoundFullDepthTemporalWithoutCascadeHistory" in source


def test_ao_indirect_bound_asset_exposes_packed_pipeline() -> None:
    source = asset("indirect_cascade_upscale_ao_indirect_bound.hlsl")
    assert "struct UpscaleAoIndirectSurface" in source
    assert "AccumulateAoIndirectFootprint" in source
    assert "FilterBoundAoIndirectCross" in source
    assert "GatherBoundPerspectiveAoIndirectSurface" in source
    assert "GatherBoundOrthoAoIndirectSurface" in source
    assert "ResolveBoundAoIndirectTemporal" in source


def test_cascade_only_main_selects_quality_specific_policies() -> None:
    common = """// 0.330000013
// tTemporalAo.SampleLevel(
// tVolatile.Gather(
// o0.xy = cascadeAddressState.yx;
// 3Dmigoto declarations
#define cmp -


void mainPS() {
  float4 registerState;
}
"""
    low = _lift_bound_cascade_only_main(
        "// 0.142857149 int2(-1,-1) int2(1,1)\n" + common,
        quality="low",
    )
    medium = _lift_bound_cascade_only_main(
        "// 0.0588235296 int2(-2,-2) int2(2,2)\n" + common,
        quality="medium",
    )
    high = _lift_bound_cascade_only_main(
        "// 0.0588235296 int2(-2,-2) int2(2,2)\n" + common,
        quality="high",
    )
    low_ortho = _lift_bound_cascade_only_main(
        "// 0.142857149 int2(-1,-1) int2(1,1)\n" + common,
        quality="low",
        perspective=False,
    )

    assert "EvaluateBoundLowCascadeOnlyLighting" in low
    assert "EvaluateBoundMediumCascadeOnlyLighting" in medium
    assert "ResolveBoundLowMediumCascadeOnlyTemporal" in medium
    assert "EvaluateBoundMediumCascadeOnlyLighting" in high
    assert "ResolveBoundHighCascadeOnlyTemporal" in high
    assert "GatherBoundOrthoCascadeSurface" in low_ortho
    assert "indirect_cascade_upscale_cascade_depth_bound.hlsl" in low_ortho
    assert "registerState" not in low + medium + high + low_ortho


def test_cascade_depth_only_main_selects_projection_and_quality_policies() -> None:
    common = """// LinearizeUpscaleDepth(tDepth.Load(
// tTemporalAo.SampleLevel(
// tVolatile.Gather(
// 0.330000013
// o0.xy = cascadeAddressState.yx;
// 3Dmigoto declarations
#define cmp -


void mainPS() {
  float4 registerState;
}
"""
    low = _lift_bound_cascade_depth_only_main(
        "// 0.142857149 int2(-1,-1) int2(1,1)\n" + common,
        perspective=True,
        quality="low",
    )
    high_ortho = _lift_bound_cascade_depth_only_main(
        "// 0.0588235296 int2(-2,-2) int2(2,2)\n" + common,
        perspective=False,
        quality="high",
    )

    assert "GatherBoundPerspectiveCascadeSurface" in low
    assert "ReconstructBoundPerspectiveCascadePosition" in low
    assert "EvaluateBoundLowDepthCascadeOnlyLighting" in low
    assert "ResolveBoundLowMediumCascadeOnlyTemporal" in low
    assert "GatherBoundOrthoCascadeSurface" in high_ortho
    assert "ReconstructBoundOrthoCascadePosition" in high_ortho
    assert "EvaluateBoundMediumDepthCascadeOnlyLighting" in high_ortho
    assert "ResolveBoundHighCascadeOnlyTemporal" in high_ortho
    assert "registerState" not in low + high_ortho


def test_full_depth_main_selects_projection_and_quality_policies() -> None:
    common = """// tIndirect_Ao.SampleLevel(
// tSSS.SampleLevel(
// tTemporalIndirect.SampleLevel(
// tTemporalAo.SampleLevel(
// tTemporalSSS.SampleLevel(
// LinearizeUpscaleDepth(tDepth.Load(
// GatherUpscaleDepthError(
// SwizzleUpscaleSss(
// o1.xyz = cascadeAddressState.zzz * viewDepthState.xyz
// o0.y = min(normalDecodeState.x, cascadeAddressState.y);
// 3Dmigoto declarations
#define cmp -


void mainPS() {
  float4 registerState;
}
"""
    low = _lift_bound_full_depth_no_history_main(
        "// 0.142857149 int2(-1,-1) int2(1,1)\n" + common,
        perspective=True,
        quality="low",
    )
    medium_ortho = _lift_bound_full_depth_no_history_main(
        "// 0.0588235296 int2(-2,-2) int2(2,2)\n" + common,
        perspective=False,
        quality="medium",
    )
    assert "GatherBoundPerspectiveFullSurface" in low
    assert "ReconstructBoundPerspectiveCascadePosition" in low
    assert "EvaluateBoundLowFullDepthCascade" in low
    assert "GatherBoundOrthoFullSurface" in medium_ortho
    assert "ReconstructBoundOrthoCascadePosition" in medium_ortho
    assert "EvaluateBoundMediumFullDepthCascade" in medium_ortho
    assert "ResolveBoundFullDepthTemporalWithoutCascadeHistory" in low
    assert "registerState" not in low + medium_ortho


def test_ao_indirect_main_selects_projection_policy() -> None:
    common = """// tIndirect_Ao.SampleLevel(
// tTemporalIndirect.SampleLevel(
// tTemporalAo.SampleLevel(
// GatherUpscaleDepthError(
// ComputeUpscaleGaussianWeight(
// ComputeUpscaleCoverageWeight(
// out float2 o0 : SV_Target0
// out float3 o1 : SV_Target1
// o0.y = 1;
// 3Dmigoto declarations
#define cmp -


void mainPS() {
  float4 registerState;
}
"""
    perspective = _lift_bound_ao_indirect_main(
        common, perspective=True, quality="low"
    )
    ortho = _lift_bound_ao_indirect_main(
        common, perspective=False, quality="high"
    )
    assert "GatherBoundPerspectiveAoIndirectSurface" in perspective
    assert "GatherBoundOrthoAoIndirectSurface" in ortho
    assert "ResolveBoundAoIndirectTemporal" in perspective
    assert "ResolveBoundIndirectTemporal" in perspective
    assert "0.819999993" in perspective
    assert "0.649999976" in ortho
    assert "registerState" not in perspective + ortho


def test_indirect_bound_asset_exposes_spatial_and_temporal_pipeline() -> None:
    source = asset("indirect_cascade_upscale_indirect_bound.hlsl")
    assert "struct UpscaledIndirect" in source
    assert "struct IndirectAccumulator" in source
    assert "AccumulateIndirectFootprint" in source
    assert "FilterBoundIndirectCross" in source
    assert "ReconstructBoundPerspectiveIndirectPosition" in source
    assert "ReconstructBoundOrthoIndirectPosition" in source
    assert "ResolveBoundIndirectTemporal" in source


def test_indirect_only_main_selects_projection_reconstruction() -> None:
    source = """// tMaterial.Load( 3.5999999 1.42857146
// GatherUpscaleDepthError(
// ComputeUpscaleGaussianWeight(
// ComputeUpscaleCoverageWeight(
// tTemporalIndirect.SampleLevel(
// tVolatile.Gather(
// o1.xyz = cascadeAddressState.zzz * viewDepthState.xyz
// 3Dmigoto declarations
#define cmp -


void mainPS() {
  float4 registerState;
}
"""
    perspective = _lift_bound_indirect_only_main(source, perspective=True)
    ortho = _lift_bound_indirect_only_main(source, perspective=False)

    assert "ReconstructBoundPerspectiveIndirectPosition" in perspective
    assert "ReconstructBoundOrthoIndirectPosition" in ortho
    assert "FilterBoundIndirectCross" in perspective
    assert "ResolveBoundIndirectTemporal" in perspective
    assert "registerState" not in perspective + ortho


def test_sss_depth_bound_asset_exposes_composed_pipeline() -> None:
    source = asset("indirect_cascade_upscale_sss_depth_bound.hlsl")
    assert "struct UpscaledSss" in source
    assert "struct SssAccumulator" in source
    assert "AccumulateSssFootprint" in source
    assert "FilterBoundSssCross" in source
    assert "ReconstructBoundPerspectiveSssPosition" in source
    assert "ReconstructBoundOrthoSssPosition" in source
    assert "EvaluateBoundDepthCascadeImpl" in source
    assert "ResolveBoundSssTemporal" in source
    assert "ResolveBoundSssOnlyTemporal" in source


def test_sss_depth_main_selects_projection_and_shadow_quality() -> None:
    common = """// tSSS.SampleLevel(
// tTemporalSSS.SampleLevel(
// LinearizeUpscaleDepth(tDepth.Load(
// GatherUpscaleDepthError(
// ComputeUpscaleCoverageWeight(
// SwizzleUpscaleSss(
// o0.y = min(normalDecodeState.x, cascadeAddressState.x);
// 3Dmigoto declarations
#define cmp -


void mainPS() {
  float4 registerState;
}
"""
    low = _lift_bound_sss_depth_cascade_main(
        "// 0.142857149 int2(-1,-1) int2(1,1)\n" + common,
        perspective=True,
        quality="low",
    )
    medium_ortho = _lift_bound_sss_depth_cascade_main(
        "// 0.0588235296 int2(-2,-2) int2(2,2)\n" + common,
        perspective=False,
        quality="medium",
    )

    assert "ReconstructBoundPerspectiveSssPosition" in low
    assert "sceneSurface, false" in low
    assert "ReconstructBoundOrthoSssPosition" in medium_ortho
    assert "sceneSurface, true" in medium_ortho
    assert "ResolveBoundSssTemporal" in low + medium_ortho
    assert "registerState" not in low + medium_ortho


def test_sss_only_main_reuses_spatial_and_temporal_pipeline() -> None:
    source = """// tSSS.SampleLevel(
// tTemporalSSS.SampleLevel(
// GatherUpscaleDepthError(
// ComputeUpscaleGaussianWeight(
// ComputeUpscaleCoverageWeight(
// SwizzleUpscaleSss(
// out float4 o2 : SV_Target2
// 3Dmigoto declarations
#define cmp -


void mainPS() {
  float4 registerState;
}
"""
    perspective = _lift_bound_sss_only_main(source, perspective=True)
    ortho = _lift_bound_sss_only_main(source, perspective=False)
    assert "FilterBoundSssCross" in perspective
    assert "ReconstructBoundPerspectiveSssPosition" in perspective
    assert "ReconstructBoundOrthoSssPosition" in ortho
    assert "ResolveBoundSssOnlyTemporal" in perspective + ortho
    assert "registerState" not in perspective + ortho


def test_indirect_sss_main_composes_shared_output_pipelines() -> None:
    source = """// tSSS.SampleLevel(
// tTemporalSSS.SampleLevel(
// tTemporalIndirect.SampleLevel(
// GatherUpscaleDepthError(
// ComputeUpscaleGaussianWeight(
// ComputeUpscaleCoverageWeight(
// out float3 o1 : SV_Target1
// out float4 o2 : SV_Target2
// 3Dmigoto declarations
#define cmp -


void mainPS() {
  float4 registerState;
}
"""
    perspective = _lift_bound_indirect_sss_main(
        source, perspective=True
    )
    ortho = _lift_bound_indirect_sss_main(source, perspective=False)
    assert "FilterBoundIndirectCross" in perspective
    assert "FilterBoundSssCross" in perspective
    assert "ReconstructBoundPerspectiveSssPosition" in perspective
    assert "ReconstructBoundOrthoSssPosition" in ortho
    assert "ResolveBoundIndirectTemporal" in perspective + ortho
    assert "ResolveBoundSssOnlyTemporal" in perspective + ortho
    assert "registerState" not in perspective + ortho


def test_ao_only_main_selects_projection_and_quality_response() -> None:
    source = """// tIndirect_Ao.SampleLevel(
// tTemporalAo.SampleLevel(
// GatherUpscaleDepthError(
// ComputeUpscaleGaussianWeight(
// ComputeUpscaleCoverageWeight(
// out float2 o0 : SV_Target0
// o0.y = 1;
// 3Dmigoto declarations
#define cmp -


void mainPS() {
  float4 registerState;
}
"""
    low = _lift_bound_ao_only_main(
        source, perspective=True, quality="low"
    )
    high_ortho = _lift_bound_ao_only_main(
        source, perspective=False, quality="high"
    )
    assert "FilterBoundAoCross" in low
    assert "ReconstructBoundPerspectiveAoPosition" in low
    assert "ReconstructBoundOrthoAoPosition" in high_ortho
    assert "0.819999993" in low
    assert "0.649999976" in high_ortho
    assert "registerState" not in low + high_ortho


def test_ao_sss_main_composes_both_temporal_outputs() -> None:
    source = """// tIndirect_Ao.SampleLevel(
// tTemporalAo.SampleLevel(
// tSSS.SampleLevel(
// tTemporalSSS.SampleLevel(
// GatherUpscaleDepthError(
// ComputeUpscaleCoverageWeight(
// out float2 o0 : SV_Target0
// out float4 o2 : SV_Target2
// 3Dmigoto declarations
#define cmp -


void mainPS() {
  float4 registerState;
}
"""
    low = _lift_bound_ao_sss_main(
        source, perspective=True, quality="low"
    )
    high_ortho = _lift_bound_ao_sss_main(
        source, perspective=False, quality="high"
    )
    assert "FilterBoundAoCross" in low
    assert "FilterBoundSssCross" in low
    assert "ReconstructBoundPerspectiveAoPosition" in low
    assert "ReconstructBoundOrthoSssPosition" in high_ortho
    assert "ResolveBoundAoCascadeTemporal" in low + high_ortho
    assert "ResolveBoundSssOnlyTemporal" in low + high_ortho
    assert "0.819999993" in low
    assert "0.649999976" in high_ortho
    assert "registerState" not in low + high_ortho


def test_ao_indirect_sss_main_composes_three_temporal_outputs() -> None:
    source = """// tIndirect_Ao.SampleLevel(
// tTemporalIndirect.SampleLevel(
// tTemporalAo.SampleLevel(
// tSSS.SampleLevel(
// tTemporalSSS.SampleLevel(
// GatherUpscaleDepthError(
// ComputeUpscaleGaussianWeight(
// ComputeUpscaleCoverageWeight(
// SwizzleUpscaleSss(
// out float2 o0 : SV_Target0
// out float3 o1 : SV_Target1
// out float4 o2 : SV_Target2
// o0.y = 1;
// 3Dmigoto declarations
#define cmp -


void mainPS() {
  float4 registerState;
}
"""
    low = _lift_bound_ao_indirect_sss_main(
        source, perspective=True, quality="low"
    )
    high_ortho = _lift_bound_ao_indirect_sss_main(
        source, perspective=False, quality="high"
    )
    assert "GatherBoundPerspectiveAoIndirectSurface" in low
    assert "GatherBoundOrthoAoIndirectSurface" in high_ortho
    assert "ReconstructBoundPerspectiveSssPosition" in low
    assert "ReconstructBoundOrthoSssPosition" in high_ortho
    assert "ResolveBoundAoIndirectTemporal" in low + high_ortho
    assert "ResolveBoundIndirectTemporal" in low + high_ortho
    assert "ResolveBoundSssOnlyTemporal" in low + high_ortho
    assert "0.819999993" in low
    assert "0.649999976" in high_ortho
    assert "registerState" not in low + high_ortho


def test_cascade_indirect_main_selects_all_family_policies() -> None:
    source = """// tTemporalAo.SampleLevel(
// tTemporalIndirect.SampleLevel(
// tIndirect_Ao.SampleLevel(
// GatherUpscaleDepthError(
// out float2 o0 : SV_Target0
// out float3 o1 : SV_Target1
// 3Dmigoto declarations
#define cmp -


void mainPS() {
  float4 registerState;
}
"""
    low = _lift_bound_cascade_indirect_main(
        "// 0.142857149 int2(-1,-1) int2(1,1)\n" + source,
        perspective=True,
        quality="low",
    )
    high_ortho = _lift_bound_cascade_indirect_main(
        "// 0.0588235296 int2(-2,-2) int2(2,2)\n" + source,
        perspective=False,
        quality="high",
    )
    assert "GatherBoundPerspectiveCascadeSurface" in low
    assert "EvaluateBoundLowCascadeOnlyLighting" in low
    assert "ResolveBoundLowMediumCascadeOnlyTemporal" in low
    assert "GatherBoundOrthoCascadeSurface" in high_ortho
    assert "EvaluateBoundMediumCascadeOnlyLighting" in high_ortho
    assert "ResolveBoundHighCascadeOnlyTemporal" in high_ortho
    assert "FilterBoundIndirectCross" in low + high_ortho
    assert "ResolveBoundIndirectTemporal" in low + high_ortho
    assert "registerState" not in low + high_ortho


def test_cascade_no_history_mains_omit_temporal_resolution() -> None:
    cascade_source = """// 0.330000013
// 0.142857149
// int2(-1,-1)
// int2(1,1)
// out float2 o0 : SV_Target0
// o0.xy = cascadeAddressState.yx;
// 3Dmigoto declarations
#define cmp -


void mainPS()
{
  float4 registerState;
}
"""
    depth_source = cascade_source.replace(
        "// 0.330000013",
        "// 0.330000013\n// LinearizeUpscaleDepth(tDepth.Load(",
    )
    cascade = _lift_bound_cascade_no_history_main(
        cascade_source, perspective=True, quality="low"
    )
    depth = _lift_bound_cascade_depth_no_history_main(
        depth_source, perspective=False, quality="low"
    )
    assert "GatherBoundPerspectiveCascadeSurface" in cascade
    assert "EvaluateBoundLowCascadeOnlyLighting" in cascade
    assert "ReconstructBoundOrthoCascadePosition" in depth
    assert "EvaluateBoundLowDepthCascadeOnlyLighting" in depth
    assert "ResolveBound" not in cascade + depth
    assert "registerState" not in cascade + depth


def test_cascade_payload_no_history_composes_optional_outputs() -> None:
    source = """// 0.330000013 0.0588235296
// int2(-2,-2) int2(2,2)
// LinearizeUpscaleDepth(tDepth.Load(
// tIndirect_Ao.SampleLevel(
// tTemporalAo.SampleLevel(
// tTemporalIndirect.SampleLevel(
// tSSS.SampleLevel(
// tTemporalSSS.SampleLevel(
// SwizzleUpscaleSss(
// out float2 o0 : SV_Target0
// out float3 o1 : SV_Target1
// out float4 o2 : SV_Target2
// 0.959999979
// 3Dmigoto declarations
#define cmp -


void mainPS()
{
  float4 registerState;
}
"""
    lifted = _lift_bound_cascade_payload_no_history_main(
        source,
        perspective=False,
        quality="medium",
        from_depth=True,
        indirect=True,
        sss=True,
    )
    assert "EvaluateBoundMediumDepthCascadeOnlyLighting" in lifted
    assert "GatherBoundOrthoAoIndirectSurface" in lifted
    assert "ResolveBoundAoIndirectTemporal" in lifted
    assert "ResolveBoundIndirectTemporal" in lifted
    assert "ResolveBoundSssTemporal" in lifted
    assert "float2(resolvedAo.x, min(resolvedSss.x, visibility))" in lifted
    assert "registerState" not in lifted


def test_full_bound_asset_composes_all_output_pipelines() -> None:
    source = asset("indirect_cascade_upscale_full_bound.hlsl")
    assert "struct UpscaleFullSurface" in source
    assert "struct UpscaleFullTemporalResult" in source
    assert "GatherBoundPerspectiveFullSurface" in source
    assert "GatherBoundOrthoFullSurface" in source
    assert "EvaluateBoundFullCascade" in source
    assert "ResolveBoundFullTemporalWithoutCascadeHistory" in source
    assert "ResolveBoundIndirectTemporal" in source


def test_full_output_main_selects_projection_and_shadow_quality() -> None:
    common = """// tIndirect_Ao.SampleLevel(
// tSSS.SampleLevel(
// tTemporalIndirect.SampleLevel(
// tTemporalAo.SampleLevel(
// tTemporalSSS.SampleLevel(
// GatherUpscaleDepthError(
// SwizzleUpscaleSss(
// o1.xyz = cascadeAddressState.zzz * viewDepthState.xyz
// o0.y = min(normalDecodeState.x, cascadeAddressState.y);
// 3Dmigoto declarations
#define cmp -


void mainPS() {
  float4 registerState;
}
"""
    low = _lift_bound_full_output_main(
        "// 0.142857149 int2(-1,-1) int2(1,1)\n" + common,
        perspective=True,
        quality="low",
    )
    medium_ortho = _lift_bound_full_output_main(
        "// 0.0588235296 int2(-2,-2) int2(2,2)\n" + common,
        perspective=False,
        quality="medium",
    )

    assert "GatherBoundPerspectiveFullSurface" in low
    assert "EvaluateBoundLowUpscaleCascadeLighting" in low
    assert "GatherBoundOrthoFullSurface" in medium_ortho
    assert "EvaluateBoundUpscaleCascadeLighting" in medium_ortho
    assert "ResolveBoundFullTemporalWithoutCascadeHistory" in low
    assert "registerState" not in low + medium_ortho


def test_ao_depth_bound_asset_exposes_two_surface_pipeline() -> None:
    source = asset("indirect_cascade_upscale_ao_depth_bound.hlsl")
    assert "struct UpscaledAo" in source
    assert "struct AoAccumulator" in source
    assert "AccumulateAoFootprint" in source
    assert "FilterBoundAoCross" in source
    assert "ReconstructBoundPerspectiveAoPosition" in source
    assert "ReconstructBoundOrthoAoPosition" in source
    assert "EvaluateBoundAoDepthCascade" in source
    assert "ResolveBoundAoCascadeTemporal" in source


def test_ao_depth_main_selects_projection_quality_and_history_policy() -> None:
    common = """// tIndirect_Ao.SampleLevel(
// tTemporalAo.SampleLevel(
// LinearizeUpscaleDepth(tDepth.Load(
// GatherUpscaleDepthError(
// 0.330000013
// o0.xy = cascadeSelectionState.xy * cascadeAddressState.xy
// 3Dmigoto declarations
#define cmp -


void mainPS() {
  float4 registerState;
}
"""
    low = _lift_bound_ao_depth_cascade_main(
        "// 0.142857149 int2(-1,-1) int2(1,1)\n" + common,
        perspective=True,
        quality="low",
    )
    high_ortho = _lift_bound_ao_depth_cascade_main(
        "// 0.0588235296 int2(-2,-2) int2(2,2)\n" + common,
        perspective=False,
        quality="high",
    )

    assert "ReconstructBoundPerspectiveAoPosition" in low
    assert "sceneDepth, false" in low
    assert "-0.180000007, 0.819999993" in low
    assert "ReconstructBoundOrthoAoPosition" in high_ortho
    assert "sceneDepth, true" in high_ortho
    assert "-0.350000024, 0.649999976" in high_ortho
    assert "registerState" not in low + high_ortho


def test_bound_main_removes_decompiler_register_shell() -> None:
    source = """// UpscaledAoSss spatialAoSss = FilterAoSssCross(
// tTemporalAo.SampleLevel(
// tTemporalSSS.SampleLevel(
// o0.y = min(normalDecodeState.x, cascadeAddressState.y);
// 3Dmigoto declarations
#define cmp -


void mainPS() {
  float4 registerState;
}
"""
    lifted = _lift_bound_upscale_main(source)
    assert '#include "../indirect_cascade_upscale_bound.hlsl"' in lifted
    assert "GatherBoundUpscaleSurface" in lifted
    assert "EvaluateBoundUpscaleCascadeLighting" in lifted
    assert "ResolveBoundUpscaleTemporal" in lifted
    assert "#define cmp" not in lifted
    assert "registerState" not in lifted


def test_depth_filter_sequence_becomes_named_helpers() -> None:
    source = """  error.xyzw = tAoDepth.Gather(LinearClampClamp_s, uv.xy).xyzw;
  error.xyzw = error.xyzw * error.xyzw;
  error.xyzw = error.xyzw * float4(499.899994,499.899994,499.899994,499.899994) + float4(0.100000001,0.100000001,0.100000001,0.100000001);
  error.xyzw = error.xyzw + -center.xxxx;
  error.xyzw = error.xyzw * error.xyzw;
  gaussian.x = dot(error.xyzw, float4(0.25,0.25,0.25,0.25));
  gaussian.x = -gaussian.x * inverseThreshold.y;
  gaussian.x = 1.44269502 * gaussian.x;
  gaussian.x = exp2(gaussian.x);
  error.xyzw = error.xyzw / threshold.zzzz;
  error.xyzw = float4(1,1,1,1) + -error.xyzw;
  error.xyzw = max(float4(0,0,0,0), error.xyzw);
  coverage.w = dot(error.xyzw, float4(0.25,0.25,0.25,0.25));
  coverage.w = log2(coverage.w);
  coverage.w = exponent.x * coverage.w;
  coverage.w = exp2(coverage.w);"""

    lifted = _lift_coverage_weights(
        _lift_gaussian_weights(_lift_depth_gathers(source))
    )

    assert "GatherUpscaleDepthError(" in lifted
    assert "ComputeUpscaleGaussianWeight(" in lifted
    assert "ComputeUpscaleCoverageWeight(" in lifted
    assert "499.899994" not in lifted


def test_projection_depth_sequence_becomes_linearization_call() -> None:
    source = """  depth.x = tDepth.Load(pixel.xyw).x;
  depth.x = cb_xViewToProjection._m22 + depth.x;
  depth.x = cb_xViewToProjection._m23 / depth.x;"""
    lifted = _lift_linear_depth(source)
    assert "depth.x = LinearizeUpscaleDepth(" in lifted
    assert "tDepth.Load(pixel.xyw).x" in lifted


def test_octahedral_normal_sequence_becomes_decode_call() -> None:
    source = """  encoded.xy = tNormal.Load(pixel.xyz).xy;
  encoded.xy = encoded.xy * float2(2,2) + float2(-1,-1);
  encoded.z = 1 + -abs(encoded.x);
  scratch.z = encoded.z + -abs(encoded.y);
  encoded.z = saturate(-scratch.z);
  signs.xy = cmp(encoded.xy >= float2(0,0));
  encoded.zw = signs.xy ? -encoded.zz : encoded.zz;
  normal.xy = encoded.xy + encoded.zw;
  length.x = dot(normal.xyz, normal.xyz);
  length.x = rsqrt(length.x);
  decoded.xyz = normal.xyz * length.xxx;"""
    lifted = _lift_normal_decodes(source)
    assert lifted == "  decoded.xyz = DecodeUpscaleNormal(tNormal.Load(pixel.xyz).xy);"


def test_material_response_sequence_becomes_typed_state() -> None:
    source = """  state.yz = tMaterial.Load(pixel.xyw).xy;
  state.z = 1 + -state.z;
  state.z = log2(abs(state.z));
  state.z = 0.75 * state.z;
  state.z = exp2(state.z);
  state.z = 1 + -state.z;
  state.y = state.z * state.y;
  state.y = saturate(3.5999999 * state.y);
  state.y = -0.150000006 + state.y;
  state.y = max(0, state.y);
  state.y = 1.42857146 * state.y;
  state.y = min(1, state.y);
  state.z = 1 + -state.y;
  state.w = state.z * state.z;
  state.w = state.w * state.w;"""
    lifted = _lift_material_responses(source)
    assert "UpscaleMaterialResponse materialResponse" in lifted
    assert "materialResponse.edgeResponse" in lifted
    assert "materialResponse.tapRadiusScale" in lifted


def test_variants_are_emitted_as_independent_semantic_snippets(
    tmp_path: Path,
) -> None:
    bodies = _emit_variant_snippets(
        tmp_path,
        {
            "SM_SHADER_0000000000000001": "float mainPS() { return 1.0; }\n",
            "SM_SHADER_0000000000000002": "float mainPS() { return 2.0; }\n",
        },
    )

    first = tmp_path / "semantic/include/indirect_cascade_upscale/SM_SHADER_0000000000000001.hlsl"
    assert first.is_file()
    assert '#include "../indirect_cascade_upscale_primitives.hlsl"' in first.read_text()
    assert (
        tmp_path / "semantic/include/indirect_cascade_upscale_bound.hlsl"
    ).is_file()
    assert (
        tmp_path
        / "semantic/include/indirect_cascade_upscale_cascade_bound.hlsl"
    ).is_file()
    assert (
        tmp_path
        / "semantic/include/indirect_cascade_upscale_indirect_bound.hlsl"
    ).is_file()
    assert (
        tmp_path
        / "semantic/include/indirect_cascade_upscale_sss_depth_bound.hlsl"
    ).is_file()
    assert (
        tmp_path
        / "semantic/include/indirect_cascade_upscale_full_bound.hlsl"
    ).is_file()
    assert (
        tmp_path
        / "semantic/include/indirect_cascade_upscale_ao_depth_bound.hlsl"
    ).is_file()
    assert (
        tmp_path
        / "semantic/include/indirect_cascade_upscale_cascade_depth_bound.hlsl"
    ).is_file()
    assert (
        tmp_path
        / "semantic/include/indirect_cascade_upscale_full_depth_bound.hlsl"
    ).is_file()
    assert (
        tmp_path
        / "semantic/include/indirect_cascade_upscale_ao_indirect_bound.hlsl"
    ).is_file()
    assert bodies["SM_SHADER_0000000000000001"] == (
        '#include "include/indirect_cascade_upscale/'
        'SM_SHADER_0000000000000001.hlsl"\n'
    )
