from pathlib import Path

from shader_toolchain.recipes.common import asset
from shader_toolchain.recipes.indirect_light import (
    _append_runtime_abi_sentinel,
    _emit_variant_snippets,
    _is_cascade_medium_reference,
    _is_medium_sss_reference,
    _is_ortho_medium_ssgi_three_reference,
    _is_ortho_medium_reflection_two_reference,
    _is_medium_probe_four_reference,
    _is_ortho_high_cascade_probe_reference,
    _is_ortho_high_ssgi_three_reference,
    _is_ortho_high_ultra_reference,
    _is_ortho_low_ultra_reference,
    _is_ortho_medium_ultra_reference,
    _is_probe_cascade_reference,
    _lift_cascade_medium_reference,
    _lift_indirect_light_abi,
    _lift_medium_sss_reference,
    _lift_ortho_medium_ssgi_three_reference,
    _lift_ortho_medium_reflection_two_reference,
    _lift_medium_probe_four_reference,
    _lift_ortho_high_cascade_probe_reference,
    _lift_ortho_high_ssgi_three_reference,
    _lift_ortho_high_ultra_reference,
    _lift_ortho_low_ultra_reference,
    _lift_ortho_medium_ultra_reference,
    _lift_probe_cascade_reference,
    _lift_perspective_cascade_ssgi_reference,
    _lift_perspective_probe_quality_reference,
    _lift_perspective_ao_sss_reference,
    _lift_perspective_cascade_only_reference,
    _lift_ortho_ssgi_quality_reference,
    _ortho_ssgi_quality_policy,
    _lift_perspective_probe_cascade_reference,
    _perspective_probe_cascade_policy,
    _lift_perspective_ultra_quality_reference,
    _perspective_ultra_quality_policy,
    _lift_perspective_ssgi_probe_reference,
    _perspective_ssgi_probe_policy,
    _lift_perspective_ultra_no_ao_reference,
    _perspective_ultra_no_ao_policy,
    _lift_perspective_ultra_cascade_reference,
    _perspective_ultra_cascade_policy,
    _lift_ortho_ultra_cascade_reference,
    _ortho_ultra_cascade_policy,
    _lift_ortho_ultra_policy_reference,
    _ortho_ultra_policy,
    _lift_perspective_reflection_reference,
    _perspective_reflection_policy,
    _lift_ortho_probe_reference,
    _ortho_probe_policy,
    _lift_ortho_probe_cascade_reference,
    _ortho_probe_cascade_policy,
    _lift_ortho_cascade_ssgi_reference,
    _ortho_cascade_ssgi_policy,
    _lift_perspective_cascade_reflection_reference,
    _perspective_cascade_reflection_policy,
    _lift_ortho_ao_sss_reference,
    _ortho_ao_sss_policy,
    _lift_ortho_cascade_reference,
    _ortho_cascade_policy,
    _lift_ortho_reflection_reference,
    _ortho_reflection_policy,
    _lift_ortho_cascade_reflection_reference,
    _ortho_cascade_reflection_policy,
    _perspective_ao_sss_policy,
    _perspective_cascade_only_policy,
    _perspective_cascade_ssgi_policy,
    _perspective_probe_quality_policy,
)


def test_indirect_light_abi_lift_names_recovered_buffers() -> None:
    source = """cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_REFLECTIONS : register(b11) { float4 reflections; }
cbuffer Cluster : register(b6) { float4 cluster; }
cbuffer CB_AO_SETTINGS : register(b0) { float4 settings; }
void mainPS() {}
"""
    lifted = _lift_indirect_light_abi(source)
    assert "cbuffer " not in lifted
    assert "indirect_light_projection_abi.hlsl" in lifted
    assert "indirect_light_perframe_abi.hlsl" in lifted
    assert "indirect_light_reflections_abi.hlsl" in lifted
    assert "indirect_light_cluster_abi.hlsl" in lifted
    assert "indirect_light_ao_settings_abi.hlsl" in lifted


def test_runtime_abi_sentinel_is_appended_to_replaced_main() -> None:
    source = "void mainPS(float2 w1 : UV0, out float4 o0 : SV_Target0)\n{\n}\n"
    lifted = _append_runtime_abi_sentinel(
        source,
        ["o0.x += tDepth.Load(int3((int2)w1.xy, 0));"],
        {5},
    )
    assert "cb_vNearFarViewCorner.x == -3.402823e+38" in lifted
    assert "tDepth.Load(int3((int2)w1.xy, 0))" in lifted
    assert lifted.rstrip().endswith("}")


def test_probe_cascade_reference_lift_is_typed_entry_point() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    lifted = _lift_probe_cascade_reference(source)
    assert '#include "../indirect_light_probe_cascade.hlsl"' in lifted
    assert "EvaluateIndirectLightProbeCascade(w1)" in lifted
    assert "3Dmigoto" not in lifted


def test_probe_cascade_reference_policy_is_exact() -> None:
    assert _is_probe_cascade_reference([
        "PIXEL_SHADER",
        "PS_CASCADE",
        "PS_PROBE_GI",
        "PS_REFLECTION",
        "PS_SSS_COUNT=1",
    ])
    assert not _is_probe_cascade_reference([
        "PIXEL_SHADER",
        "PS_CASCADE",
        "PS_PROBE_GI",
        "PS_REFLECTION",
        "PS_SSS_COUNT=2",
    ])


def test_cascade_medium_lift_reuses_typed_quality_phases() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    lifted = _lift_cascade_medium_reference(source)
    assert "#define INDIRECT_LIGHT_ENABLE_PROBE_GI 0" in lifted
    assert "EvaluateIndirectLightCascadeMedium(w1)" in lifted
    assert "out float2 o2 : SV_Target2" in lifted
    assert "3Dmigoto" not in lifted


def test_cascade_medium_reference_policy_is_exact() -> None:
    assert _is_cascade_medium_reference([
        "PIXEL_SHADER",
        "PS_CASCADE",
        "PS_REFLECTION",
        "PS_SSAO_QUALITY_MEDIUM",
        "PS_SSS_COUNT=2",
    ])


def test_medium_sss_lift_reuses_ao_and_clustered_visibility() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    lifted = _lift_medium_sss_reference(source)
    assert "#define INDIRECT_LIGHT_ENABLE_REFLECTION 0" in lifted
    assert "#define INDIRECT_LIGHT_ENABLE_DIFFUSE 0" in lifted
    assert "EvaluateIndirectLightMediumSss(w1)" in lifted
    assert "out float o2 : SV_Target2" in lifted
    assert "3Dmigoto" not in lifted


def test_medium_sss_reference_policy_is_exact() -> None:
    assert _is_medium_sss_reference([
        "PIXEL_SHADER",
        "PS_SSAO_QUALITY_MEDIUM",
        "PS_SSS_COUNT=1",
    ])


def test_ortho_medium_ssgi_three_lift_uses_counted_policy() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    lifted = _lift_ortho_medium_ssgi_three_reference(source)
    assert '#include "../indirect_light_ortho_ssgi.hlsl"' in lifted
    assert "EvaluateIndirectLightOrthoSsgi(w1, 3u)" in lifted
    assert "out float3 o2 : SV_Target2" in lifted
    assert "3Dmigoto" not in lifted


def test_ortho_medium_ssgi_three_policy_is_exact() -> None:
    assert _is_ortho_medium_ssgi_three_reference([
        "ORTHO", "PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION",
        "PS_SSAO_QUALITY_MEDIUM", "PS_SSGI", "PS_SSS_COUNT=3",
    ])


def test_ortho_medium_reflection_two_lift_disables_temporal_gi() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    lifted = _lift_ortho_medium_reflection_two_reference(source)
    assert "#define INDIRECT_LIGHT_ENABLE_PROBE_GI 0" in lifted
    assert "#define INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI 0" in lifted
    assert "EvaluateIndirectLightOrthoMediumReflection(w1, 2u)" in lifted
    assert "out float2 o2 : SV_Target2" in lifted


def test_ortho_medium_reflection_two_policy_is_exact() -> None:
    assert _is_ortho_medium_reflection_two_reference([
        "ORTHO", "PIXEL_SHADER", "PS_REFLECTION",
        "PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=2",
    ])


def test_medium_probe_four_lift_uses_counted_probe_policy() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    lifted = _lift_medium_probe_four_reference(source)
    assert "#define INDIRECT_LIGHT_ENABLE_PROBE_AO 1" in lifted
    assert '#include "../indirect_light_medium_probe.hlsl"' in lifted
    assert "EvaluateIndirectLightMediumProbe(w1, 4u)" in lifted
    assert "out float4 o2 : SV_Target2" in lifted


def test_medium_probe_four_policy_is_exact() -> None:
    assert _is_medium_probe_four_reference([
        "PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION",
        "PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=4",
    ])


def test_ortho_high_cascade_probe_lift_uses_single_cascade_channel() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    lifted = _lift_ortho_high_cascade_probe_reference(source)
    assert "EvaluateIndirectLightOrthoHighCascadeProbe(w1)" in lifted
    assert "o2 = result.occlusion.x" in lifted
    assert "out float o2 : SV_Target2" in lifted


def test_ortho_high_cascade_probe_policy_is_exact() -> None:
    assert _is_ortho_high_cascade_probe_reference([
        "ORTHO", "PIXEL_SHADER", "PS_CASCADE", "PS_PROBE_GI",
        "PS_REFLECTION", "PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=1",
    ])


def test_ortho_high_ssgi_three_policy_reuses_temporal_structure() -> None:
    defines = [
        "ORTHO", "PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION",
        "PS_SSAO_QUALITY_HIGH", "PS_SSGI", "PS_SSS_COUNT=3",
    ]
    assert _is_ortho_high_ssgi_three_reference(defines)
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    lifted = _lift_ortho_high_ssgi_three_reference(source)
    assert "EvaluateIndirectLightOrthoSsgi(w1, 3u)" in lifted
    assert "out float3 o2 : SV_Target2" in lifted
    assert not _is_ortho_high_cascade_probe_reference([
        "ORTHO", "PIXEL_SHADER", "PS_CASCADE", "PS_PROBE_GI",
        "PS_REFLECTION", "PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=1",
    ])
    assert not _is_medium_probe_four_reference([
        "PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION",
        "PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=3",
    ])
    assert not _is_ortho_medium_reflection_two_reference([
        "ORTHO", "PIXEL_SHADER", "PS_REFLECTION",
        "PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=1",
    ])
    assert not _is_ortho_medium_ssgi_three_reference([
        "ORTHO", "PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION",
        "PS_SSAO_QUALITY_MEDIUM", "PS_SSGI", "PS_SSS_COUNT=2",
    ])
    assert not _is_medium_sss_reference([
        "PIXEL_SHADER",
        "PS_SSAO_QUALITY_HIGH",
        "PS_SSS_COUNT=1",
    ])
    assert not _is_cascade_medium_reference([
        "PIXEL_SHADER",
        "PS_CASCADE",
        "PS_REFLECTION",
        "PS_SSAO_QUALITY_HIGH",
        "PS_SSS_COUNT=2",
    ])


def test_ortho_high_ultra_lift_uses_quality_parameterized_resolver() -> None:
    defines = [
        "ORTHO", "PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION",
        "PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=0", "PS_ULTRA",
    ]
    assert _is_ortho_high_ultra_reference(defines)
    assert not _is_ortho_high_ultra_reference([
        "ORTHO", "PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION",
        "PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=0", "PS_ULTRA",
    ])
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    lifted = _lift_ortho_high_ultra_reference(source)
    assert '#include "../indirect_light_ultra.hlsl"' in lifted
    assert "EvaluateIndirectLightOrthoUltra(w1, 2.0)" in lifted
    assert "out float o1 : SV_Target1" in lifted
    assert "SV_Target2" not in lifted
    assert "3Dmigoto" not in lifted


def test_ortho_ultra_quality_policies_share_one_resolver() -> None:
    common = [
        "ORTHO", "PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION",
        "PS_SSS_COUNT=0", "PS_ULTRA",
    ]
    medium = common + ["PS_SSAO_QUALITY_MEDIUM"]
    low = common + ["PS_SSAO_QUALITY_LOW"]
    assert _is_ortho_medium_ultra_reference(medium)
    assert _is_ortho_low_ultra_reference(low)
    assert not _is_ortho_medium_ultra_reference(low)
    assert not _is_ortho_low_ultra_reference(medium)
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    medium_lift = _lift_ortho_medium_ultra_reference(source)
    low_lift = _lift_ortho_low_ultra_reference(source)
    assert "EvaluateIndirectLightOrthoUltra(w1, 1.0)" in medium_lift
    assert "EvaluateIndirectLightOrthoUltra(w1, 0.5)" in low_lift
    assert '#include "../indirect_light_ultra.hlsl"' in medium_lift
    assert '#include "../indirect_light_ultra.hlsl"' in low_lift


def test_ortho_ultra_policy_covers_optional_ao_and_counted_sss() -> None:
    common = [
        "ORTHO", "PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION",
        "PS_ULTRA",
    ]
    assert _ortho_ultra_policy(
        common + ["PS_SSS_COUNT=0"]
    ) == (1.0, False, 0)
    assert _ortho_ultra_policy(
        common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) == (2.0, True, 4)
    assert _ortho_ultra_policy(
        common + ["PS_CASCADE", "PS_SSS_COUNT=2"]
    ) is None


def test_ortho_ultra_policy_lift_routes_optional_sss_target() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    zero = _lift_ortho_ultra_policy_reference(source, 1.0, False, 0)
    four = _lift_ortho_ultra_policy_reference(source, 2.0, True, 4)
    assert '#include "../indirect_light_ultra.hlsl"' in zero
    assert "w1, 1.0, false, 0u" in zero
    assert "Texture2DArray<float> taAo" in zero
    assert "SV_Target2" not in zero
    assert "w1, 2.0, true, 4u" in four
    assert "out float4 o2 : SV_Target2" in four
    assert "o2 = result.occlusion.xyzw" in four


def test_perspective_cascade_ssgi_policy_is_quality_and_counted() -> None:
    common = [
        "PIXEL_SHADER", "PS_CASCADE", "PS_PROBE_GI", "PS_REFLECTION",
        "PS_SSGI",
    ]
    assert _perspective_cascade_ssgi_policy(
        common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=2"]
    ) == (2.0, True, 2)
    assert _perspective_cascade_ssgi_policy(
        common + ["PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=3"]
    ) == (1.0, True, 3)
    assert _perspective_cascade_ssgi_policy(
        common + ["PS_SSAO_QUALITY_LOW", "PS_SSS_COUNT=4"]
    ) == (0.5, True, 4)
    assert _perspective_cascade_ssgi_policy(
        common + ["PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=0"]
    ) == (1.0, True, 0)
    assert _perspective_cascade_ssgi_policy(
        common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=1"]
    ) == (2.0, True, 1)
    assert _perspective_cascade_ssgi_policy(
        common + ["PS_SSS_COUNT=4"]
    ) == (1.0, False, 4)
    assert _perspective_cascade_ssgi_policy(
        ["ORTHO"] + common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=2"]
    ) is None


def test_perspective_cascade_ssgi_lift_routes_counted_outputs() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    lifted = _lift_perspective_cascade_ssgi_reference(
        source, 2.0, True, 2
    )
    assert '#include "../indirect_light_ssgi_cascade.hlsl"' in lifted
    assert "EvaluateIndirectLightPerspectiveSsgiCascade" in lifted
    assert "w1, 2.0, true, 2u" in lifted
    assert "out float2 o2 : SV_Target2" in lifted
    assert "o2 = result.occlusion.xy" in lifted
    no_output = _lift_perspective_cascade_ssgi_reference(
        source, 1.0, False, 0
    )
    assert "w1, 1.0, false, 0u" in no_output
    assert "Texture2DArray<float> taAo" in no_output
    assert "SV_Target2" not in no_output


def test_perspective_probe_quality_policy_covers_quality_count_matrix() -> None:
    common = ["PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION"]
    assert _perspective_probe_quality_policy(
        common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) == (2.0, True, 4)
    assert _perspective_probe_quality_policy(
        common + ["PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=2"]
    ) == (1.0, True, 2)
    assert _perspective_probe_quality_policy(
        common + ["PS_SSAO_QUALITY_LOW", "PS_SSS_COUNT=0"]
    ) == (0.5, True, 0)
    assert _perspective_probe_quality_policy(
        common + ["PS_SSS_COUNT=3"]
    ) == (1.0, False, 3)
    assert _perspective_probe_quality_policy(
        common + ["PS_CASCADE", "PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) is None


def test_perspective_probe_quality_lift_omits_absent_occlusion_target() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    no_sss = _lift_perspective_probe_quality_reference(
        source, 1.0, False, 0
    )
    four_sss = _lift_perspective_probe_quality_reference(
        source, 2.0, True, 4
    )
    assert "EvaluateIndirectLightProbePolicy" in no_sss
    assert "Texture2D<float> tAoDepth" in no_sss
    assert "w1, 1.0, false, 0u" in no_sss
    assert "SV_Target2" not in no_sss
    assert "w1, 2.0, true, 4u" in four_sss
    assert "out float4 o2 : SV_Target2" in four_sss
    assert "o2 = result.occlusion.xyzw" in four_sss


def test_perspective_ao_sss_policy_covers_quality_count_matrix() -> None:
    assert _perspective_ao_sss_policy([
        "PIXEL_SHADER", "PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=0",
    ]) == (2.0, True, 0)
    assert _perspective_ao_sss_policy([
        "PIXEL_SHADER", "PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=2",
    ]) == (1.0, True, 2)
    assert _perspective_ao_sss_policy([
        "PIXEL_SHADER", "PS_SSAO_QUALITY_LOW", "PS_SSS_COUNT=4",
    ]) == (0.5, True, 4)
    assert _perspective_ao_sss_policy([
        "PIXEL_SHADER", "PS_SSS_COUNT=3",
    ]) == (1.0, False, 3)
    assert _perspective_ao_sss_policy([
        "PIXEL_SHADER", "PS_REFLECTION", "PS_SSAO_QUALITY_HIGH",
        "PS_SSS_COUNT=0",
    ]) is None


def test_indirect_light_helpers_keep_recovered_sampling_paths() -> None:
    perspective = asset("indirect_light_ao_sss.hlsl")
    ortho = asset("indirect_light_ortho_ssgi.hlsl")
    shared = asset("indirect_light_probe_cascade.hlsl")
    assert "tMaterial.Gather(" in perspective
    assert "PointClampClamp_s" in perspective
    assert "tScreenNoise.Load(" in perspective
    assert "tAoDepth.SampleLevel(" in perspective
    assert "LinearClampClamp_s, clampedUv" in perspective
    assert "tAoDepth.SampleLevel(" in ortho
    assert "LinearClampClamp_s, clampedUv" in ortho
    assert "tScreenNoise.Load(" in shared
    assert "stepUv * (0.5 + rayJitter)" in shared
    assert "tAoDepth.SampleLevel(" in shared


def test_perspective_ao_sss_lift_routes_optional_target() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    no_sss = _lift_perspective_ao_sss_reference(source, 1.0, False, 0)
    four_sss = _lift_perspective_ao_sss_reference(source, 0.5, True, 4)
    assert '#include "../indirect_light_ao_sss.hlsl"' in no_sss
    assert "EvaluateIndirectLightPerspectiveAoSssPolicy" in no_sss
    assert "Texture2D<float2> tNormal" in no_sss
    assert "#define INDIRECT_LIGHT_AO_SSS_COUNT 0" in no_sss
    assert "w1, 1.0, false" in no_sss
    assert "SV_Target2" not in no_sss
    assert "#define INDIRECT_LIGHT_AO_SSS_COUNT 4" in four_sss
    assert "w1, 0.5, true" in four_sss
    assert "out float4 o2 : SV_Target2" in four_sss


def test_perspective_cascade_only_policy_covers_output_counts() -> None:
    assert _perspective_cascade_only_policy([
        "PIXEL_SHADER", "PS_CASCADE", "PS_SSS_COUNT=1",
    ]) == (1.0, False, 1)
    assert _perspective_cascade_only_policy([
        "PIXEL_SHADER", "PS_CASCADE", "PS_SSAO_QUALITY_HIGH",
        "PS_SSS_COUNT=4",
    ]) == (2.0, True, 4)
    assert _perspective_cascade_only_policy([
        "PIXEL_SHADER", "PS_CASCADE", "PS_REFLECTION", "PS_SSS_COUNT=4",
    ]) is None
    assert _perspective_cascade_only_policy([
        "ORTHO", "PIXEL_SHADER", "PS_CASCADE", "PS_SSS_COUNT=2",
    ]) is None


def test_perspective_cascade_only_lift_routes_counted_visibility() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    one = _lift_perspective_cascade_only_reference(source, 1.0, False, 1)
    four = _lift_perspective_cascade_only_reference(source, 2.0, True, 4)
    assert '#include "../indirect_light_cascade.hlsl"' in one
    assert "EvaluateIndirectLightCascadeVisibilityPolicy" in one
    assert "w1, 1.0, false" in one
    assert "#define INDIRECT_LIGHT_CASCADE_OUTPUT_COUNT 1" in one
    assert "out float o2 : SV_Target2" in one
    assert "o2 = result.visibility.x" in one
    assert "#define INDIRECT_LIGHT_CASCADE_OUTPUT_COUNT 4" in four
    assert "w1, 2.0, true" in four
    assert "out float4 o2 : SV_Target2" in four
    assert "o2 = result.visibility.xyzw" in four


def test_ortho_ssgi_quality_policy_covers_quality_count_matrix() -> None:
    common = [
        "ORTHO", "PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION", "PS_SSGI",
    ]
    assert _ortho_ssgi_quality_policy(
        common + ["PS_SSAO_QUALITY_LOW", "PS_SSS_COUNT=0"]
    ) == (0.5, True, 0)
    assert _ortho_ssgi_quality_policy(
        common + ["PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=3"]
    ) == (1.0, True, 3)
    assert _ortho_ssgi_quality_policy(
        common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) == (2.0, True, 4)
    assert _ortho_ssgi_quality_policy(
        common + ["PS_SSS_COUNT=2"]
    ) == (1.0, False, 2)
    assert _ortho_ssgi_quality_policy(
        common + ["PS_CASCADE", "PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) is None


def test_ortho_ssgi_quality_lift_routes_optional_sss_target() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    no_sss = _lift_ortho_ssgi_quality_reference(source, 1.0, False, 0)
    four_sss = _lift_ortho_ssgi_quality_reference(source, 2.0, True, 4)
    assert '#include "../indirect_light_ortho_ssgi.hlsl"' in no_sss
    assert "w1, 0u, 1.0, false" in no_sss
    assert "Texture2DArray<float> taAo" in no_sss
    assert "SV_Target2" not in no_sss
    assert "w1, 4u, 2.0, true" in four_sss
    assert "out float4 o2 : SV_Target2" in four_sss
    assert "o2 = result.subsurfaceOcclusion.xyzw" in four_sss


def test_perspective_probe_cascade_policy_covers_output_counts() -> None:
    common = ["PIXEL_SHADER", "PS_CASCADE", "PS_PROBE_GI", "PS_REFLECTION"]
    assert _perspective_probe_cascade_policy(
        common + ["PS_SSS_COUNT=0"]
    ) == (1.0, False, 0)
    assert _perspective_probe_cascade_policy(
        common + ["PS_SSS_COUNT=4"]
    ) == (1.0, False, 4)
    assert _perspective_probe_cascade_policy(
        common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=2"]
    ) == (2.0, True, 2)
    assert _perspective_probe_cascade_policy(
        common + ["PS_SSGI", "PS_SSS_COUNT=2"]
    ) is None


def test_perspective_probe_cascade_lift_routes_optional_visibility() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    zero = _lift_perspective_probe_cascade_reference(
        source, 1.0, False, 0
    )
    four = _lift_perspective_probe_cascade_reference(
        source, 2.0, True, 4
    )
    assert '#include "../indirect_light_probe_cascade_counted.hlsl"' in zero
    assert "#define INDIRECT_LIGHT_PROBE_CASCADE_COUNT 0" in zero
    assert "w1, 1.0, false" in zero
    assert "SV_Target2" not in zero
    assert "#define INDIRECT_LIGHT_PROBE_CASCADE_COUNT 4" in four
    assert "w1, 2.0, true" in four
    assert "out float4 o2 : SV_Target2" in four
    assert "o2 = result.visibility.xyzw" in four


def test_perspective_ultra_policy_covers_quality_count_matrix() -> None:
    common = ["PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION", "PS_ULTRA"]
    assert _perspective_ultra_quality_policy(
        common + ["PS_SSAO_QUALITY_LOW", "PS_SSS_COUNT=0"]
    ) == (0.5, 0)
    assert _perspective_ultra_quality_policy(
        common + ["PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=2"]
    ) == (1.0, 2)
    assert _perspective_ultra_quality_policy(
        common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) == (2.0, 4)
    assert _perspective_ultra_quality_policy(
        ["ORTHO"] + common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=0"]
    ) is None


def test_perspective_ultra_lift_routes_optional_sss_target() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    zero = _lift_perspective_ultra_quality_reference(source, 0.5, 0)
    four = _lift_perspective_ultra_quality_reference(source, 2.0, 4)
    assert '#include "../indirect_light_ultra.hlsl"' in zero
    assert "w1, 0.5, 0u" in zero
    assert "SV_Target2" not in zero
    assert "w1, 2.0, 4u" in four
    assert "out float4 o2 : SV_Target2" in four
    assert "o2 = result.occlusion.xyzw" in four


def test_perspective_ssgi_probe_policy_covers_count_matrix() -> None:
    common = ["PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION", "PS_SSGI"]
    assert _perspective_ssgi_probe_policy(
        common + ["PS_SSS_COUNT=0"]
    ) == (1.0, False, 0)
    assert _perspective_ssgi_probe_policy(
        common + ["PS_SSS_COUNT=4"]
    ) == (1.0, False, 4)
    assert _perspective_ssgi_probe_policy(
        common + ["PS_SSAO_QUALITY_LOW", "PS_SSS_COUNT=1"]
    ) == (0.5, True, 1)
    assert _perspective_ssgi_probe_policy(
        common + ["PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=2"]
    ) == (1.0, True, 2)
    assert _perspective_ssgi_probe_policy(
        common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=3"]
    ) == (2.0, True, 3)


def test_perspective_ssgi_probe_lift_routes_optional_sss_target() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    zero = _lift_perspective_ssgi_probe_reference(
        source, 1.0, False, 0
    )
    four = _lift_perspective_ssgi_probe_reference(
        source, 2.0, True, 4
    )
    assert '#include "../indirect_light_ssgi_probe.hlsl"' in zero
    assert "Texture2DArray<float> taAo" in zero
    assert "w1, 1.0, false, 0u" in zero
    assert "SV_Target2" not in zero
    assert "w1, 2.0, true, 4u" in four
    assert "out float4 o2 : SV_Target2" in four
    assert "o2 = result.occlusion.xyzw" in four


def test_perspective_ultra_no_ao_policy_covers_count_matrix() -> None:
    common = ["PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION", "PS_ULTRA"]
    assert _perspective_ultra_no_ao_policy(
        common + ["PS_SSS_COUNT=0"]
    ) == 0
    assert _perspective_ultra_no_ao_policy(
        common + ["PS_SSS_COUNT=4"]
    ) == 4
    assert _perspective_ultra_no_ao_policy(
        common + ["PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=2"]
    ) is None


def test_perspective_ultra_no_ao_lift_routes_optional_sss_target() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    zero = _lift_perspective_ultra_no_ao_reference(source, 0)
    four = _lift_perspective_ultra_no_ao_reference(source, 4)
    assert '#include "../indirect_light_ultra.hlsl"' in zero
    assert "w1, 0u" in zero
    assert "SV_Target2" not in zero
    assert "w1, 4u" in four
    assert "out float4 o2 : SV_Target2" in four
    assert "o2 = result.occlusion.xyzw" in four


def test_perspective_ultra_cascade_policy_covers_quality_count_matrix() -> None:
    common = [
        "PIXEL_SHADER", "PS_CASCADE", "PS_PROBE_GI", "PS_REFLECTION",
        "PS_ULTRA",
    ]
    assert _perspective_ultra_cascade_policy(
        common + ["PS_SSAO_QUALITY_LOW", "PS_SSS_COUNT=0"]
    ) == (0.5, True, 0)
    assert _perspective_ultra_cascade_policy(
        common + ["PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=2"]
    ) == (1.0, True, 2)
    assert _perspective_ultra_cascade_policy(
        common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) == (2.0, True, 4)
    assert _perspective_ultra_cascade_policy(
        common + ["PS_SSS_COUNT=3"]
    ) == (1.0, False, 3)
    assert _perspective_ultra_cascade_policy(
        ["ORTHO"] + common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) is None
    assert _perspective_ultra_cascade_policy(
        common + ["PS_SSGI", "PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) is None


def test_perspective_ultra_cascade_lift_routes_optional_visibility() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    zero = _lift_perspective_ultra_cascade_reference(
        source, 0.5, True, 0
    )
    four = _lift_perspective_ultra_cascade_reference(
        source, 2.0, True, 4
    )
    assert '#include "../indirect_light_ultra.hlsl"' in zero
    assert "w1, 0.5, true, 0u" in zero
    assert "SV_Target2" not in zero
    assert "w1, 2.0, true, 4u" in four
    assert "out float4 o2 : SV_Target2" in four
    assert "o2 = result.occlusion.xyzw" in four


def test_ortho_ultra_cascade_policy_covers_ao_and_count_matrix() -> None:
    common = [
        "ORTHO", "PIXEL_SHADER", "PS_CASCADE", "PS_PROBE_GI",
        "PS_REFLECTION", "PS_ULTRA",
    ]
    assert _ortho_ultra_cascade_policy(
        common + ["PS_SSS_COUNT=0"]
    ) == (1.0, False, 0)
    assert _ortho_ultra_cascade_policy(
        common + ["PS_SSAO_QUALITY_LOW", "PS_SSS_COUNT=1"]
    ) == (0.5, True, 1)
    assert _ortho_ultra_cascade_policy(
        common + ["PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=2"]
    ) == (1.0, True, 2)
    assert _ortho_ultra_cascade_policy(
        common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) == (2.0, True, 4)
    assert _ortho_ultra_cascade_policy(
        common + ["PS_SSGI", "PS_SSS_COUNT=3"]
    ) is None


def test_ortho_ultra_cascade_lift_routes_optional_visibility() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    zero = _lift_ortho_ultra_cascade_reference(
        source, 1.0, False, 0
    )
    four = _lift_ortho_ultra_cascade_reference(
        source, 2.0, True, 4
    )
    assert '#include "../indirect_light_ultra.hlsl"' in zero
    assert "Texture2DArray<float> taAo" in zero
    assert "w1, 1.0, false, 0u" in zero
    assert "SV_Target2" not in zero
    assert "w1, 2.0, true, 4u" in four
    assert "out float4 o2 : SV_Target2" in four
    assert "o2 = result.occlusion.xyzw" in four


def test_perspective_reflection_policy_covers_ao_and_count_matrix() -> None:
    common = ["PIXEL_SHADER", "PS_REFLECTION"]
    assert _perspective_reflection_policy(
        common + ["PS_SSS_COUNT=0"]
    ) == (1.0, False, 0)
    assert _perspective_reflection_policy(
        common + ["PS_SSAO_QUALITY_LOW", "PS_SSS_COUNT=1"]
    ) == (0.5, True, 1)
    assert _perspective_reflection_policy(
        common + ["PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=2"]
    ) == (1.0, True, 2)
    assert _perspective_reflection_policy(
        common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) == (2.0, True, 4)
    assert _perspective_reflection_policy(
        ["ORTHO"] + common + ["PS_SSS_COUNT=0"]
    ) is None


def test_perspective_reflection_lift_routes_optional_sss_target() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    zero = _lift_perspective_reflection_reference(
        source, 1.0, False, 0
    )
    four = _lift_perspective_reflection_reference(
        source, 2.0, True, 4
    )
    assert '#include "../indirect_light_reflection.hlsl"' in zero
    assert "Texture2D<float> tAoDepth" in zero
    assert "w1, 1.0, false, 0u" in zero
    assert "SV_Target2" not in zero
    assert "w1, 2.0, true, 4u" in four
    assert "out float4 o2 : SV_Target2" in four
    assert "o2 = result.occlusion.xyzw" in four


def test_ortho_probe_policy_covers_ao_and_count_matrix() -> None:
    common = ["ORTHO", "PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION"]
    assert _ortho_probe_policy(
        common + ["PS_SSS_COUNT=0"]
    ) == (1.0, False, 0)
    assert _ortho_probe_policy(
        common + ["PS_SSAO_QUALITY_LOW", "PS_SSS_COUNT=1"]
    ) == (0.5, True, 1)
    assert _ortho_probe_policy(
        common + ["PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=2"]
    ) == (1.0, True, 2)
    assert _ortho_probe_policy(
        common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) == (2.0, True, 4)
    assert _ortho_probe_policy(
        common + ["PS_CASCADE", "PS_SSS_COUNT=0"]
    ) is None


def test_ortho_probe_cascade_policy_covers_optional_ao_matrix() -> None:
    common = [
        "ORTHO", "PIXEL_SHADER", "PS_CASCADE", "PS_PROBE_GI",
        "PS_REFLECTION",
    ]
    assert _ortho_probe_cascade_policy(
        common + ["PS_SSS_COUNT=0"]
    ) == (1.0, False, 0)
    assert _ortho_probe_cascade_policy(
        common + ["PS_SSAO_QUALITY_LOW", "PS_SSS_COUNT=1"]
    ) == (0.5, True, 1)
    assert _ortho_probe_cascade_policy(
        common + ["PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=3"]
    ) == (1.0, True, 3)
    assert _ortho_probe_cascade_policy(
        common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) == (2.0, True, 4)
    assert _ortho_probe_cascade_policy(
        common + ["PS_SSGI", "PS_SSS_COUNT=0"]
    ) is None


def test_ortho_probe_cascade_lift_routes_counted_visibility() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    zero = _lift_ortho_probe_cascade_reference(source, 1.0, False, 0)
    four = _lift_ortho_probe_cascade_reference(source, 2.0, True, 4)
    assert "EvaluateIndirectLightOrthoProbeCascadePolicy" in zero
    assert "Texture2D<float> tAoDepth" in zero
    assert "w1, 1.0, false, 0u" in zero
    assert "SV_Target2" not in zero
    assert "w1, 2.0, true, 4u" in four
    assert "out float4 o2 : SV_Target2" in four
    assert "o2 = result.occlusion.xyzw" in four


def test_ortho_probe_lift_routes_optional_sss_target() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    zero = _lift_ortho_probe_reference(source, 1.0, False, 0)
    four = _lift_ortho_probe_reference(source, 2.0, True, 4)
    assert '#include "../indirect_light_medium_probe.hlsl"' in zero
    assert "INDIRECT_LIGHT_ENABLE_PROBE_AO 0" in zero
    assert "Texture2D<float> tAoDepth" in zero
    assert "w1, 1.0, false, 0u" in zero
    assert "SV_Target2" not in zero
    assert "INDIRECT_LIGHT_ENABLE_PROBE_AO 1" in four
    assert "w1, 2.0, true, 4u" in four
    assert "out float4 o2 : SV_Target2" in four
    assert "o2 = result.occlusion.xyzw" in four


def test_ortho_cascade_ssgi_policy_covers_ao_and_count_matrix() -> None:
    common = [
        "ORTHO", "PIXEL_SHADER", "PS_CASCADE", "PS_PROBE_GI",
        "PS_REFLECTION", "PS_SSGI",
    ]
    assert _ortho_cascade_ssgi_policy(
        common + ["PS_SSS_COUNT=0"]
    ) == (1.0, False, 0)
    assert _ortho_cascade_ssgi_policy(
        common + ["PS_SSAO_QUALITY_LOW", "PS_SSS_COUNT=2"]
    ) == (0.5, True, 2)
    assert _ortho_cascade_ssgi_policy(
        common + ["PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=3"]
    ) == (1.0, True, 3)
    assert _ortho_cascade_ssgi_policy(
        common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) == (2.0, True, 4)
    assert _ortho_cascade_ssgi_policy(
        common + ["PS_ULTRA", "PS_SSS_COUNT=1"]
    ) is None


def test_ortho_cascade_policy_covers_quality_and_count_matrix() -> None:
    common = ["ORTHO", "PIXEL_SHADER", "PS_CASCADE"]
    assert _ortho_cascade_policy(
        common + ["PS_SSAO_QUALITY_LOW", "PS_SSS_COUNT=1"]
    ) == (0.5, 1)
    assert _ortho_cascade_policy(
        common + ["PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=3"]
    ) == (1.0, 3)
    assert _ortho_cascade_policy(
        common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) == (2.0, 4)
    assert _ortho_cascade_policy(
        common + ["PS_PROBE_GI", "PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) is None


def test_ortho_cascade_lift_routes_counted_visibility() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    one = _lift_ortho_cascade_reference(source, 0.5, 1)
    four = _lift_ortho_cascade_reference(source, 2.0, 4)
    assert '#include "../indirect_light_ortho_cascade.hlsl"' in one
    assert "indirect_light_cluster_abi.hlsl" in one
    assert "StructuredBuffer<uint> sbVoxelLightIds" in one
    assert "w1, 0.5, 1u" in one
    assert "out float o2 : SV_Target2" in one
    assert "o2 = result.visibility.x" in one
    assert "w1, 2.0, 4u" in four
    assert "out float4 o2 : SV_Target2" in four
    assert "o2 = result.visibility.xyzw" in four


def test_ortho_cascade_ssgi_lift_routes_optional_visibility() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    zero = _lift_ortho_cascade_ssgi_reference(source, 1.0, False, 0)
    four = _lift_ortho_cascade_ssgi_reference(source, 2.0, True, 4)
    assert '#include "../indirect_light_ortho_ssgi_cascade.hlsl"' in zero
    assert "w1, 1.0, false, 0u" in zero
    assert "SV_Target2" not in zero
    assert "w1, 2.0, true, 4u" in four
    assert "out float4 o2 : SV_Target2" in four
    assert "o2 = result.occlusion.xyzw" in four


def test_perspective_cascade_reflection_policy_covers_matrix() -> None:
    common = ["PIXEL_SHADER", "PS_CASCADE", "PS_REFLECTION"]
    assert _perspective_cascade_reflection_policy(
        common + ["PS_SSS_COUNT=1"]
    ) == (1.0, False, 1)
    assert _perspective_cascade_reflection_policy(
        common + ["PS_SSAO_QUALITY_LOW", "PS_SSS_COUNT=2"]
    ) == (0.5, True, 2)
    assert _perspective_cascade_reflection_policy(
        common + ["PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=3"]
    ) == (1.0, True, 3)
    assert _perspective_cascade_reflection_policy(
        common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) == (2.0, True, 4)
    assert _perspective_cascade_reflection_policy(
        common + ["PS_PROBE_GI", "PS_SSS_COUNT=1"]
    ) is None


def test_ortho_cascade_reflection_policy_covers_matrix() -> None:
    common = ["ORTHO", "PIXEL_SHADER", "PS_CASCADE", "PS_REFLECTION"]
    assert _ortho_cascade_reflection_policy(
        common + ["PS_SSS_COUNT=1"]
    ) == (1.0, False, 1)
    assert _ortho_cascade_reflection_policy(
        common + ["PS_SSAO_QUALITY_LOW", "PS_SSS_COUNT=2"]
    ) == (0.5, True, 2)
    assert _ortho_cascade_reflection_policy(
        common + ["PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=3"]
    ) == (1.0, True, 3)
    assert _ortho_cascade_reflection_policy(
        common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) == (2.0, True, 4)
    assert _ortho_cascade_reflection_policy(
        common + ["PS_PROBE_GI", "PS_SSS_COUNT=1"]
    ) is None


def test_ortho_cascade_reflection_lift_routes_visibility() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    one = _lift_ortho_cascade_reflection_reference(
        source, 1.0, False, 1
    )
    four = _lift_ortho_cascade_reflection_reference(
        source, 2.0, True, 4
    )
    assert "indirect_light_ortho_reflection_cascade.hlsl" in one
    assert "Texture2D<float> tAoDepth" in one
    assert "w1, 1.0, false, 1u" in one
    assert "out float o2 : SV_Target2" in one
    assert "o2 = result.occlusion.x" in one
    assert "w1, 2.0, true, 4u" in four
    assert "out float4 o2 : SV_Target2" in four


def test_perspective_cascade_reflection_lift_routes_counted_visibility() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    one = _lift_perspective_cascade_reflection_reference(
        source, 1.0, False, 1
    )
    four = _lift_perspective_cascade_reflection_reference(
        source, 2.0, True, 4
    )
    assert '#include "../indirect_light_probe_cascade.hlsl"' in one
    assert "w1, 1.0, false, 1u" in one
    assert "out float o2 : SV_Target2" in one
    assert "w1, 2.0, true, 4u" in four
    assert "out float4 o2 : SV_Target2" in four
    assert "o2 = result.occlusion.xyzw" in four


def test_ortho_ao_sss_policy_covers_quality_count_matrix() -> None:
    common = ["ORTHO", "PIXEL_SHADER"]
    assert _ortho_ao_sss_policy(
        common + ["PS_SSAO_QUALITY_LOW", "PS_SSS_COUNT=0"]
    ) == (0.5, 0)
    assert _ortho_ao_sss_policy(
        common + ["PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=2"]
    ) == (1.0, 2)
    assert _ortho_ao_sss_policy(
        common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) == (2.0, 4)
    assert _ortho_ao_sss_policy(
        common + ["PS_REFLECTION", "PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) is None


def test_ortho_ao_sss_lift_routes_optional_target() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    zero = _lift_ortho_ao_sss_reference(source, 0.5, 0)
    four = _lift_ortho_ao_sss_reference(source, 2.0, 4)
    assert '#include "../indirect_light_ortho_ao_sss.hlsl"' in zero
    assert "w1, 0.5, 0u" in zero
    assert "SV_Target2" not in zero
    assert "w1, 2.0, 4u" in four
    assert "out float4 o2 : SV_Target2" in four
    assert "o2 = result.occlusion.xyzw" in four


def test_ortho_reflection_policy_covers_ao_and_count_matrix() -> None:
    common = ["ORTHO", "PIXEL_SHADER", "PS_REFLECTION"]
    assert _ortho_reflection_policy(
        common + ["PS_SSS_COUNT=0"]
    ) == (1.0, False, 0)
    assert _ortho_reflection_policy(
        common + ["PS_SSAO_QUALITY_LOW", "PS_SSS_COUNT=1"]
    ) == (0.5, True, 1)
    assert _ortho_reflection_policy(
        common + ["PS_SSAO_QUALITY_MEDIUM", "PS_SSS_COUNT=2"]
    ) == (1.0, True, 2)
    assert _ortho_reflection_policy(
        common + ["PS_SSAO_QUALITY_HIGH", "PS_SSS_COUNT=4"]
    ) == (2.0, True, 4)
    assert _ortho_reflection_policy(
        common + ["PS_PROBE_GI", "PS_SSS_COUNT=0"]
    ) is None


def test_ortho_reflection_lift_routes_optional_target() -> None:
    source = """Texture2D<float4> tMaterial : register(t3);
// 3Dmigoto declarations
#define cmp -
void mainPS() {}
"""
    zero = _lift_ortho_reflection_reference(source, 1.0, False, 0)
    four = _lift_ortho_reflection_reference(source, 2.0, True, 4)
    assert "INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI 0" in zero
    assert "Texture2D<float> tScreenNoise" in zero
    assert "w1, 1.0, false, 0u" in zero
    assert "SV_Target2" not in zero
    assert "w1, 2.0, true, 4u" in four
    assert "out float4 o2 : SV_Target2" in four
    assert "o2 = result.occlusion.xyzw" in four


def test_indirect_light_variants_are_emitted_as_independent_snippets(
    tmp_path: Path,
) -> None:
    bodies = _emit_variant_snippets(
        tmp_path,
        {
            "SM_SHADER_A": """#include "include/shared_abi.hlsl"
Texture2D<float4> textureA : register(t0);
void mainPS(float4 v0, float2 w1, out float4 o0) { o0 = textureA.Load(0); }
""",
            "SM_SHADER_B": """Texture2D<float4> textureB : register(t1);
void mainPS(float4 v0, float2 w1, out float4 o0) { o0 = textureB.Load(0); }
""",
        },
    )

    root = tmp_path / "semantic" / "include" / "indirect_light"
    first = (root / "SM_SHADER_A.hlsl").read_text(encoding="utf-8")
    second = (root / "SM_SHADER_B.hlsl").read_text(encoding="utf-8")
    assert "Semantic phase map" in first
    assert '#include "../shared_abi.hlsl"' in first
    assert "textureA" in first and "textureB" not in first
    assert "textureB" in second and "textureA" not in second
    assert bodies == {
        "SM_SHADER_A": '#include "include/indirect_light/SM_SHADER_A.hlsl"\n',
        "SM_SHADER_B": '#include "include/indirect_light/SM_SHADER_B.hlsl"\n',
    }
