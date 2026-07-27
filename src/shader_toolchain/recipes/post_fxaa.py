"""Recognize and emit a readable semantic lift for post_fxaa."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import emit_validated_module


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

    bodies = {
        "vertex": _asset("post_fxaa_vertex.hlsl"),
        "pixel": _asset("post_fxaa_pixel.hlsl"),
    }
    vertex_selector = next(
        shader["selector"] for shader in shaders if shader["stage"] == "vertex"
    )
    executions = {}
    for shader in shaders:
        if shader["stage"] == "pixel":
            executions[shader["selector"]] = {
                "kind": "fullscreen_texture2d",
                "vertex_selector": vertex_selector,
                "texture_slot": 0,
                "sampler_slot": 6,
                "constant_buffer_slot": 5,
                "filter": "linear",
            }
    include = '#include "include/post_fxaa_abi.hlsl"\n\n'
    shared_source = include + bodies["vertex"] + "\n" + bodies["pixel"]
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="post_fxaa",
        bodies={
            shader["selector"]: include + bodies[shader["stage"]]
            for shader in shaders
        },
        executions=executions,
        shared_source=shared_source,
    )
