import pytest

from shader_toolchain.gpu_fuzz import select_shader_pair
from shader_toolchain.reconstruct import ToolchainError


def manifest_with_fxaa() -> dict:
    return {
        "shaders": [
            {
                "source_name": "post_fxaa",
                "stage": "vertex",
                "selector": "SM_SHADER_VERTEX",
            },
            {
                "source_name": "post_fxaa",
                "stage": "pixel",
                "selector": "SM_SHADER_PIXEL",
                "semantic_hlsl_path": "semantic/post_fxaa.hlsl",
            },
            {
                "source_name": "unrelated",
                "stage": "pixel",
                "selector": "SM_SHADER_OTHER",
            },
        ]
    }


def test_select_shader_pair_finds_semantic_pixel_and_vertex() -> None:
    vertex, pixel = select_shader_pair(manifest_with_fxaa(), "post_fxaa")

    assert vertex["selector"] == "SM_SHADER_VERTEX"
    assert pixel["selector"] == "SM_SHADER_PIXEL"


def test_select_shader_pair_rejects_missing_semantic_pixel() -> None:
    manifest = manifest_with_fxaa()
    del manifest["shaders"][1]["semantic_hlsl_path"]

    with pytest.raises(ToolchainError, match="exactly one semantic pixel"):
        select_shader_pair(manifest, "post_fxaa")
