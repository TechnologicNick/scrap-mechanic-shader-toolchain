from shader_toolchain.gpu_fuzz import VERTEX_HARNESSES
from shader_toolchain.recipes.common import asset
from shader_toolchain.recipes.post_volumetric import ABI_INCLUDES


def test_volumetric_asset_is_structural_shared_hlsl() -> None:
    source = asset("post_volumetric_pixel.hlsl")
    assert "#if defined(PS_SHADER_QUALITY_HIGH)" in source
    assert "IntegrateClusteredVolumes" in source
    assert "IntersectConeVolume" in source
    assert "float4 pixelAndClusterState" not in source
    assert "SM_SELECT" not in source
    assert len(ABI_INCLUDES) == 5
    for branch in (
        "cone_mask",
        "cone_intersection",
        "cone_march",
        "cone_cookie",
        "cone_shadow",
    ):
        assert source.count(f"// SM_COVERAGE_CANARY: {branch}") == 1


def test_packed_uv_harness_populates_consumed_components() -> None:
    source = VERTEX_HARNESSES["fullscreen_packed_uv"]
    assert "float4(0.0, 0.0, coordinates[vertexId])" in source
