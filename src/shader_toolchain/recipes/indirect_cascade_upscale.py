"""Recognize indirect-light cascade reconstruction and upscale variants."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..hlsl import module_variants
from ..reflect import ShaderReflector
from .common import emit_validated_module


SEMANTIC_PHASE_MAP = """
/*
Semantic phase map
------------------
1. Reconstruct view depth/normal and choose the active indirect-light cascade.
2. Gather depth-aware AO, indirect, subsurface and temporal neighborhoods.
3. Reject discontinuities and combine the selected quality/temporal path.
4. Emit AO, indirect RGB and/or SSS targets requested by the permutation.

The 162 feature permutations retain instruction ordering for gather lanes,
cascade transforms, packed material tests and temporal rejection thresholds.
*/
"""


def _execution(blob: bytes) -> dict[str, Any]:
    abi = ShaderReflector().abi(blob)
    textures = [resource for resource in abi["resources"] if resource["type"] == 2]
    samplers = [resource for resource in abi["resources"] if resource["type"] == 3]
    outputs = abi["outputs"]
    target_count = max((output["index"] for output in outputs), default=0) + 1
    components = [4] * target_count
    for output in outputs:
        components[output["index"]] = max(1, output["mask"].bit_count())
    profiles = {0: "index", 5: "projection", 12: "index"}
    return {
        "kind": "fullscreen_indirect_cascade",
        "vertex_harness": "fullscreen_uv",
        "width": 1,
        "height": 1,
        "texture_slots": [resource["bind_point"] for resource in textures],
        "texture_kinds": [
            "2darray" if resource["dimension"] == 5 else "2d"
            for resource in textures
        ],
        "smooth_texture_slots": [resource["bind_point"] for resource in textures],
        "samplers": [
            {
                "slot": resource["bind_point"],
                "filter": "linear",
                "comparison": resource["bind_point"] == 12,
            }
            for resource in samplers
        ],
        "constant_buffers": [
            {"slot": buffer["bind_point"], "profile": profiles[buffer["bind_point"]]}
            for buffer in abi["constant_buffers"]
        ],
        "output": "color",
        "output_components": 4,
        "output_targets": target_count,
        "output_target_components": components,
    }


def apply_indirect_cascade_upscale_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record
        for record in records
        if record["source_name"] == "indirect_cascade_upscale"
    ]
    if len(shaders) != 163 or any(shader["stage"] != "pixel" for shader in shaders):
        return None
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    variants = module_variants(
        (staging / "hlsl" / "indirect_cascade_upscale.hlsl").read_text(
            encoding="utf-8"
        ),
        definitions,
    )
    for selector, source in variants.items():
        source = re.sub(
            r"cb_arrCascades\[([^\]]+)/4\]\.(_m[0-9_]+)",
            r"cb_arrCascades[\1].\2",
            source,
        )
        variants[selector] = source
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="indirect_cascade_upscale",
        bodies={
            shader["selector"]: SEMANTIC_PHASE_MAP + variants[shader["selector"]]
            for shader in shaders
        },
        executions={
            shader["selector"]: _execution(blobs[shader["bundle_index"]])
            for shader in shaders
        },
    )
