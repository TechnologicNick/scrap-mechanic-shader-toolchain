from pathlib import Path

from shader_toolchain.main_part_permutation_graph import (
    CoverageMode,
    LightingModel,
    MainPartPermutationDescriptor,
    MaterialModel,
    NormalSource,
    OutputMode,
    Quality,
    ReflectionMode,
    RefractionMode,
    CompositionMode,
    describe_main_part_permutation,
    phase_registry,
    resolve_phase_graph,
)


SOURCE = '''
void commonPS(
  float4 p : SV_Position0,
  float3 viewPosition : VIEW_POSITION0,
  float2 uv : UV0,
  float3 normal : NORMAL0,
  float3 tangent : TANGENT0,
  float3 bitangent : BITANGENT0,
  float4 color : VERTEXCOLOR0,
  float3 screenUv : SCREEN_UV0,
  float4 fog : FOG_COLOR0,
  uint frontFace : SV_IsFrontFace0,
  out float4 target : SV_Target0,
  out float4 auxiliary : SV_Target1) {}
'''


def test_transparent_descriptor_is_selector_independent() -> None:
    defines = {
        "PIXEL_SHADER", "PS_PERM_TRANSPARANT_SURFACE",
        "PS_SHADER_QUALITY_MEDIUM", "PS_GLASS", "PS_ASG_TEX",
        "PS_NOR_TEX", "PS_ALPHA_CUTOFF", "PS_TRANSMISSION",
        "PS_REFRACTION", "PS_DEPTH_BLUR_DISTANCE",
        "PS_RESPONSIVE_GLOW", "PS_REFLECTION_MULTI",
        "PS_FLIP_BACKFACE_NORMALS", "TRANSFER_TANGENTS",
    }
    descriptor = describe_main_part_permutation("SM_SHADER_TEST", defines, SOURCE)
    assert descriptor.output == OutputMode.TRANSPARENT_SURFACE
    assert descriptor.quality == Quality.MEDIUM
    assert descriptor.material == MaterialModel.GLASS
    assert descriptor.normal == NormalSource.TANGENT_MAP
    assert descriptor.coverage == CoverageMode.ALPHA_CUTOUT
    assert descriptor.lighting == LightingModel.TRANSMISSION
    assert descriptor.reflection == ReflectionMode.MULTI
    assert descriptor.refraction == RefractionMode.DEPTH_BLUR
    assert descriptor.composition == CompositionMode.RESPONSIVE
    assert descriptor.features == ("PS_FLIP_BACKFACE_NORMALS",)
    assert "output.transparent_surface" in descriptor.shape()
    assert "feature.ps_flip_backface_normals" in descriptor.shape()
    graph = resolve_phase_graph(descriptor)
    assert graph.phase_inventory_complete
    assert not graph.missing


def test_registry_tracks_typed_phases_instead_of_shader_hashes() -> None:
    registry = phase_registry()
    assert registry["lighting.standard"].symbol == (
        "EvaluateMainPartStandardGlassDirectionalLighting"
    )
    assert registry["reflection.multi"].symbol == (
        "EvaluateMainPartGlassReflectionProbes"
    )
    assert all("SM_SHADER_" not in implementation.symbol
               for implementation in registry.values())
    asset_root = Path("src/shader_toolchain/recipes/assets")
    for implementation in registry.values():
        if not implementation.asset:
            continue
        source = (asset_root / implementation.asset).read_text(encoding="utf-8")
        assert implementation.symbol in source


def test_unknown_features_become_explicit_missing_phase_requirements() -> None:
    descriptor = describe_main_part_permutation(
        "SM_SHADER_TEST",
        {"PIXEL_SHADER", "PS_PERM_PREVIEW", "PS_HOLOGRAM"},
        SOURCE,
    )
    registry = phase_registry()
    missing = {
        requirement.key for requirement in descriptor.requirements()
        if requirement.key not in registry
    }
    assert "feature.ps_hologram" in missing
    assert "output.preview" not in missing
    assert "material.standard" not in missing


def test_skeleton_removes_only_cheap_permutation_axes() -> None:
    first = describe_main_part_permutation(
        "SM_SHADER_A",
        {"PIXEL_SHADER", "PS_PERM_TRANSPARANT_SURFACE", "PS_GLASS",
         "PS_ASG_TEX", "PS_REFLECTION_MULTI", "PS_SHADER_QUALITY_MEDIUM"},
        SOURCE,
    )
    second = describe_main_part_permutation(
        "SM_SHADER_B",
        {"PIXEL_SHADER", "PS_PERM_TRANSPARANT_SURFACE", "PS_GLASS",
         "PS_ASG_TEX", "PS_REFLECTION_OFF", "PS_SHADER_QUALITY_HIGH"},
        SOURCE,
    )
    assert first.shape() != second.shape()
    assert first.skeleton() == second.skeleton()
