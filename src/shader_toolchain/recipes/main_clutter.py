"""Recognize the procedural clutter material permutations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..hlsl import module_variants
from .common import emit_validated_module


SEMANTIC_PHASE_MAP = """
/*
Semantic phase map
------------------
Vertex paths
1. Decode the clutter instance, align it to the ground normal and apply the
   selected slope rotation/skew and authored tangent frame.
2. Add wind and pusher deformation, including optional per-vertex push, then
   transform the position and requested material varyings into view space.
3. Forward foliage occlusion/filter channels and normalized normal/tangents.

Pixel paths
4. Alpha/depth modes reject transparent diffuse texels and optionally apply
   the screen-space dither/filter threshold.
5. Material modes combine diffuse tint, optional ASG/foliage occlusion and
   tangent-space normal mapping into the three-target G-buffer contract.
6. Light-cap modes project the reconstructed view normal into the cap texture
   and blend its color/opacity before octahedral normal encoding.

The executable blocks remain instruction-ordered because deformation, texture
derivatives, approximate normalization and packed G-buffer output are sensitive
to compiler scheduling and contraction.
*/
"""


def apply_main_clutter_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "main_clutter"]
    if len(shaders) != 41 or sum(s["stage"] == "pixel" for s in shaders) != 13:
        return None
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    expanded = module_variants(
        (staging / "hlsl" / "main_clutter.hlsl").read_text(encoding="utf-8"),
        definitions,
    )
    bodies = {
        shader["selector"]: SEMANTIC_PHASE_MAP + expanded[shader["selector"]]
        for shader in shaders
    }
    executions = {}
    asg_selectors = {
        "SM_SHADER_04F1DAF2EE2ED694", "SM_SHADER_1365E48EA8711FCF",
        "SM_SHADER_138CE38F246E26F3", "SM_SHADER_195623F5704738A2",
        "SM_SHADER_47F5982C3AB8BD06", "SM_SHADER_4EB22A598D072CD9",
        "SM_SHADER_DF23A712CC25A09C",
    }
    for shader in shaders:
        if shader["stage"] != "pixel":
            continue
        defines = set(shader["defines"])
        selector = shader["selector"]
        depth = "PS_PERM_DEPTH" in defines
        texture_slots = [0]
        if selector in asg_selectors:
            texture_slots.append(1)
        if "PS_NOR_TEX" in defines:
            texture_slots.append(2)
        if "PS_LIGHT_CAP" in defines or "PS_LIGHT_CAP_MASKED" in defines:
            texture_slots.append(3)
        if "TRANSFER_FILTER" in defines:
            texture_slots.append(14)
        execution = {
            "kind": "fullscreen_clutter",
            "vertex_harness": "fullscreen_clutter",
            "texture_slots": texture_slots,
            "texture_kinds": ["2d"] * len(texture_slots),
            "samplers": [{"slot": 6, "filter": "linear"}],
            "constant_buffers": [{"slot": 5, "profile": "projection"}],
            "output": "depth" if depth else "color",
            "output_components": 1 if depth else 4,
            "output_targets": 1 if depth else 3,
        }
        if not depth:
            execution["output_target_components"] = [4, 2, 4]
        if "PS_NOR_TEX" in defines:
            execution["ulp_tolerance"] = 2
        executions[selector] = execution
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="main_clutter", bodies=bodies, executions=executions,
    )
