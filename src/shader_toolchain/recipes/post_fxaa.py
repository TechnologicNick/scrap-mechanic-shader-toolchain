"""Recognize and emit a readable semantic lift for post_fxaa."""

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


def apply_post_fxaa_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "post_fxaa"]
    if {shader["stage"] for shader in shaders} != {"vertex", "pixel"} or len(shaders) != 2:
        return None

    semantic_root = staging / "semantic"
    include_dir = semantic_root / "include"
    include_dir.mkdir(parents=True, exist_ok=True)
    (include_dir / "post_fxaa_abi.hlsl").write_text(
        _asset("post_fxaa_abi.hlsl"), encoding="utf-8", newline="\n"
    )

    variants = []
    bodies = {
        "vertex": _asset("post_fxaa_vertex.hlsl"),
        "pixel": _asset("post_fxaa_pixel.hlsl"),
    }
    for shader in shaders:
        variants.append(
            {
                **shader,
                "hlsl": '#include "include/post_fxaa_abi.hlsl"\n\n'
                + bodies[shader["stage"]],
            }
        )
    module_path = semantic_root / "post_fxaa.hlsl"
    module_path.write_text(
        render_factored_module("post_fxaa", variants),
        encoding="utf-8",
        newline="\n",
    )

    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    vertex_selector = next(
        shader["selector"] for shader in shaders if shader["stage"] == "vertex"
    )
    expanded = module_variants(module_path.read_text(encoding="utf-8"), definitions)
    reflector = ShaderReflector()
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
            raise RuntimeError(f"post_fxaa semantic recipe changes runtime ABI: {changed}")
        shader.update(
            {
                "semantic_recipe": "post_fxaa",
                "semantic_hlsl_path": "semantic/post_fxaa.hlsl",
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
                "sampler_slot": 6,
                "constant_buffer_slot": 5,
                "filter": "linear",
            }
    return {"name": "post_fxaa", "shader_count": len(shaders)}
