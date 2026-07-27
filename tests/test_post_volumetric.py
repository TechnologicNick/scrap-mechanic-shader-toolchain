from shader_toolchain.gpu_fuzz import VERTEX_HARNESSES
from shader_toolchain.recipes.post_volumetric import _replace_quality_step


def test_volumetric_quality_modes_converge_to_one_shared_call() -> None:
    high = """    temporalAndNoiseState.xy = viewRayAndDepthState.yy * float2(0.300000012,0.800000012) + float2(0.200000003,0.200000003);
    viewRayAndDepthState.y = temporalAndNoiseState.y + -temporalAndNoiseState.x;
    viewRayAndDepthState.y = pixelAndClusterState.w * viewRayAndDepthState.y + temporalAndNoiseState.x;"""
    medium = """    viewRayAndDepthState.y = viewRayAndDepthState.y * 0.600000024 + 0.200000003;
    reprojectionState.w = 1 + -viewRayAndDepthState.y;
    viewRayAndDepthState.y = pixelAndClusterState.w * reprojectionState.w + viewRayAndDepthState.y;"""

    assert _replace_quality_step(high) == _replace_quality_step(medium)
    assert "SelectVolumetricMarchStep" in _replace_quality_step(high)


def test_packed_uv_harness_populates_consumed_components() -> None:
    source = VERTEX_HARNESSES["fullscreen_packed_uv"]
    assert "float4(0.0, 0.0, coordinates[vertexId])" in source
