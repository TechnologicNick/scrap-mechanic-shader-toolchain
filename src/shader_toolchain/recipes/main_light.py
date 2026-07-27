"""Recognize deferred direct-light and shadow permutations."""

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
1. Reconstruct the G-buffer surface and resolve its clustered light list.
2. Evaluate directional, horizon, camera and local light BRDF terms.
3. Apply cascade/spot shadows, cookies, clouds, AO and subsurface response.
4. Accumulate the selected light contribution into the deferred RGB target.

The permutation bodies retain instruction ordering for packed cluster masks,
shadow comparisons, cookie transforms and quality-dependent BRDF contraction.
*/
"""


def _execution(blob: bytes) -> dict[str, Any]:
    abi = ShaderReflector().abi(blob)
    textures = [resource for resource in abi["resources"] if resource["type"] == 2]
    samplers = [resource for resource in abi["resources"] if resource["type"] == 3]
    buffers = [resource for resource in abi["resources"] if resource["type"] == 5]
    profiles = {0: "cluster", 1: "index", 5: "projection", 12: "index"}
    return {
        "kind": "fullscreen_main_light",
        "vertex_harness": "fullscreen_unscaled",
        "width": 1,
        "height": 1,
        "texture_slots": [resource["bind_point"] for resource in textures],
        "texture_kinds": [
            "2darray" if resource["dimension"] == 5 else "2d"
            for resource in textures
        ],
        "smooth_texture_slots": [resource["bind_point"] for resource in textures],
        "structured_inputs": [
            {
                "slot": resource["bind_point"],
                "elements": 4096,
                "stride": 4,
                "profile": "zero",
            }
            for resource in buffers
        ],
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
            if buffer["bind_point"] >= 0
        ],
        "output": "color",
        "output_components": 3,
    }


def apply_main_light_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "main_light"]
    if len(shaders) != 224 or any(shader["stage"] != "pixel" for shader in shaders):
        return None
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    variants = module_variants(
        (staging / "hlsl" / "main_light.hlsl").read_text(encoding="utf-8"),
        definitions,
    )
    for selector, source in variants.items():
        source = re.sub(
            r"cb_arrSpot\[([^\]]+)/4\]\.(_m[0-9_]+)",
            r"cb_arrSpot[\1].xClip.\2",
            source,
        )
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
        recipe_name="main_light",
        bodies={
            shader["selector"]: SEMANTIC_PHASE_MAP + variants[shader["selector"]]
            for shader in shaders
        },
        executions={
            shader["selector"]: _execution(blobs[shader["bundle_index"]])
            for shader in shaders
        },
    )
