"""Recognize the final deferred-lighting composition permutations."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..hlsl import module_variants
from .common import emit_validated_module


SEMANTIC_PHASE_MAP = """
/*
Semantic phase map
------------------
1. Load the diffuse, packed material, depth, and accumulated direct light.
2. Reconstruct view position and decode the octahedral G-buffer normal when a
   reflection mode needs it.
3. Add either the single-probe array reflection or multi-probe indirect buffer;
   PS_REFLECTION_OFF deliberately skips this stage.
4. Optionally apply cascade ambient occlusion from t10.
5. Underwater mode reconstructs the water intersection, samples animated water
   normals/height, and evaluates the selected distance/vertical fog record.
6. Composite lit diffuse, emissive/material contribution, reflection and fog;
   write RGB to target 0 and the recovered depth/history scalar to target 1.

The executable section is kept instruction-ordered because the reflection and
fog reductions expose legacy FXC contraction choices at render-target precision.
*/
"""


def apply_post_composition_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records if record["source_name"] == "post_composition"
    ]
    if len(shaders) != 24 or any(shader["stage"] != "pixel" for shader in shaders):
        return None
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    expanded = module_variants(
        (staging / "hlsl" / "post_composition.hlsl").read_text(encoding="utf-8"),
        definitions,
    )
    # 3Dmigoto prints the source pair (branch=true, fogIndex=1) as zeros after
    # FXC has folded the seven-register fog-struct stride into an integer AND.
    # Recover the source-level values; FXC then recreates masks (1, 7).
    for selector, source in expanded.items():
        expanded[selector] = re.sub(
            r"(r\d+\.(?:xy|yz|zw) = r\d+\.\w\w)"
            r" \? float2\(0,0\) : 0;",
            r"\1 ? float2(1, 1) : 0;",
            source,
        )
    bodies = {
        shader["selector"]: SEMANTIC_PHASE_MAP + expanded[shader["selector"]]
        for shader in shaders
    }
    executions = {}
    for shader in shaders:
        defines = set(shader["defines"])
        underwater = "PS_UNDER_WATER_FOG" in defines
        single = "PS_REFLECTION_SINGLE" in defines
        multi = "PS_REFLECTION_MULTI" in defines
        slots = [0]
        if single or multi or underwater:
            slots.append(1)
        slots.extend([2, 3, 4])
        if multi:
            slots.append(5)
        if single:
            slots.append(7)
        if underwater:
            slots.extend([8, 9])
        if "PS_CASCADE" in defines:
            slots.append(10)
        kinds = ["2darray" if slot == 7 else "2d" for slot in slots]
        samplers = []
        if underwater:
            samplers.extend([
                {"slot": 0, "filter": "point"},
                {"slot": 3, "filter": "linear"},
            ])
        if single:
            samplers.append({"slot": 11, "filter": "linear"})
        executions[shader["selector"]] = {
            "kind": "fullscreen_uv",
            "vertex_harness": "fullscreen_uv",
            "texture_slots": slots,
            "texture_kinds": kinds,
            "smooth_texture_slots": [7] if single else [],
            "samplers": samplers,
            "constant_buffers": [
                {"slot": 5, "profile": "projection"},
                {"slot": 12, "profile": (
                    "composition-fog" if underwater else "composition"
                )},
            ],
            "output": "color",
            "output_components": 4,
            "output_targets": 2,
        }
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="post_composition", bodies=bodies, executions=executions,
    )
