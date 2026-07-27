"""Recognize and emit readable horizontal and vertical Gaussian blur shaders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..compare import compare_bytecodes
from ..hlsl import (
    hlsl_token_sha256,
    module_variants,
    render_factored_module,
    resolve_local_includes,
)
from ..reflect import ShaderReflector


PROFILES = {"vertex": "vs_5_0", "pixel": "ps_5_0"}


def _asset(name: str) -> str:
    return (Path(__file__).parent / "assets" / name).read_text(encoding="utf-8")


def apply_post_blur_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "post_blur"]
    entry_points = {shader["entry_point"] for shader in shaders}
    expected = {"triangleVS", "mainHorizontalPS", "mainVerticalPS"}
    if entry_points != expected or len(shaders) != 3:
        return None

    semantic_root = staging / "semantic"
    include_dir = semantic_root / "include"
    include_dir.mkdir(parents=True, exist_ok=True)
    projection_include = include_dir / "post_fxaa_abi.hlsl"
    if not projection_include.exists():
        projection_include.write_text(
            _asset("post_fxaa_abi.hlsl"), encoding="utf-8", newline="\n"
        )

    assets = {
        "triangleVS": "post_blur_vertex.hlsl",
        "mainHorizontalPS": "post_blur_horizontal.hlsl",
        "mainVerticalPS": "post_blur_vertical.hlsl",
    }
    variants = [
        {**shader, "hlsl": _asset(assets[shader["entry_point"]])}
        for shader in shaders
    ]
    module_path = semantic_root / "post_blur.hlsl"
    module_path.write_text(
        render_factored_module("post_blur", variants),
        encoding="utf-8",
        newline="\n",
    )

    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    expanded = module_variants(module_path.read_text(encoding="utf-8"), definitions)
    reflector = ShaderReflector()
    vertex_selector = next(
        shader["selector"] for shader in shaders if shader["stage"] == "vertex"
    )
    assembly_exact = 0
    for shader in shaders:
        source = resolve_local_includes(
            expanded[shader["selector"]], module_path, semantic_root
        )
        candidate = compiler.compile(
            source, shader["entry_point"], PROFILES[shader["stage"]]
        )
        comparison, _baseline_assembly, _candidate_assembly = compare_bytecodes(
            blobs[shader["bundle_index"]], candidate, compiler, reflector
        )
        if not comparison["abi_compatible"]:
            changed = ", ".join(comparison["abi_differences"])
            raise RuntimeError(f"post_blur semantic recipe changes runtime ABI: {changed}")
        assembly_exact += int(comparison["assembly_exact"])
        shader.update(
            {
                "semantic_recipe": "post_blur",
                "semantic_hlsl_path": "semantic/post_blur.hlsl",
                "semantic_hlsl_token_sha256": hlsl_token_sha256(source),
                "semantic_assembly_exact": comparison["assembly_exact"],
                "semantic_abi_compatible": True,
            }
        )
        if shader["stage"] == "pixel":
            shader["semantic_execution"] = {
                "kind": "fullscreen_texture2d",
                "vertex_selector": vertex_selector,
                "texture_slot": 0,
                "sampler_slot": 1,
                "constant_buffer_slot": 5,
                "filter": "point",
            }
    return {
        "name": "post_blur",
        "shader_count": len(shaders),
        "assembly_exact_count": assembly_exact,
    }
