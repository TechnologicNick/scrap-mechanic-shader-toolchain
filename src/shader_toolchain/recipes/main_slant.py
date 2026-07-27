"""Recognize the slanted-block material and transform permutations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..hlsl import module_variants
from .common import emit_validated_module, rename_register_state


SEMANTIC_PHASE_MAP = """
/*
Semantic phase map
------------------
Vertex paths
1. Decode the slant/block index and construct the selected beveled transform.
2. Apply instance/full transforms, view projection and optional back-face depth
   push while forwarding only the varyings requested by the permutation.
3. Transform the normal/tangent frame and generate screen/fog coordinates for
   material, visualization and picking consumers.

Pixel paths
4. Apply optional per-channel texture tiling and reconstruct the tangent-space
   normal from the two-channel normal map.
5. G-buffer modes blend diffuse vertex tint, pack opacity/ASG and octahedrally
   encode the view normal into three render targets.
6. Preview modes evaluate the directional palette and optional reflection map;
   visualization modes combine depth occlusion, rim fade and pulse coloring.

The executable blocks remain instruction-ordered where transform contraction,
normal packing, derivatives and preview lighting affect observable GPU output.
*/
"""


REGISTER_NAMES = {
    0: "slantPositionState", 1: "bevelTransformState",
    2: "instanceTransformState", 3: "viewProjectionState",
    4: "normalAndTangentState", 5: "materialSampleState",
    6: "previewLightingState", 7: "reflectionState",
    8: "gbufferAndVisualizationState", 9: "slantScratch",
}


def apply_main_slant_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "main_slant"]
    if len(shaders) != 48 or sum(s["stage"] == "pixel" for s in shaders) != 8:
        return None
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    expanded = module_variants(
        (staging / "hlsl" / "main_slant.hlsl").read_text(encoding="utf-8"),
        definitions,
    )
    # The original compiler assigned CB_SLANT/CB_TILING to b0 implicitly.
    # 3Dmigoto prints an explicit register, which changes the reflected
    # D3D_SIF_USERPACKED flag even though the runtime slot is identical.
    expanded = {
        selector: rename_register_state(
            source.replace(" : register(b0)", ""), REGISTER_NAMES,
            note="Bevel transforms and packed material outputs retain DXBC order.",
        )
        for selector, source in expanded.items()
    }
    bodies = {
        shader["selector"]: SEMANTIC_PHASE_MAP + expanded[shader["selector"]]
        for shader in shaders
    }
    executions = {}
    for shader in shaders:
        if shader["stage"] != "pixel":
            continue
        defines = set(shader["defines"])
        visualization = "PS_PERM_VISUALIZATION" in defines
        preview = "PS_PERM_PREVIEW" in defines
        asg = "PS_ASG_TEX" in defines
        texture_slots = [2, 7] if visualization else [0, 2]
        texture_kinds = ["2d"] * len(texture_slots)
        samplers = ([{"slot": 1, "filter": "point"}]
                    if visualization else [])
        samplers.append({"slot": 3, "filter": "linear"})
        if asg and not visualization:
            texture_slots.insert(1, 1)
            texture_kinds.insert(1, "2d")
        if preview:
            texture_slots.append(9)
            texture_kinds.append("2d")
            samplers.append({"slot": 4, "filter": "linear"})
            if asg:
                texture_slots.append(14)
                texture_kinds.append("2darray")
                samplers.append({"slot": 11, "filter": "linear"})
        constant_buffers = [{"slot": 5, "profile": "projection"}]
        if "PS_CUSTOM_TILING" in defines:
            constant_buffers.insert(0, {"slot": 0, "profile": "random"})
        if visualization:
            constant_buffers.extend([
                {"slot": 6, "profile": "random"},
                {"slot": 12, "profile": "random"},
            ])
        elif preview:
            constant_buffers.append({"slot": 12, "profile": "random"})
        executions[shader["selector"]] = {
            "kind": "fullscreen_slant",
            "vertex_harness": "fullscreen_slant",
            "texture_slots": texture_slots,
            "texture_kinds": texture_kinds,
            "samplers": samplers,
            "constant_buffers": constant_buffers,
            "output": "color",
            "output_components": 4,
            "output_targets": 3 if "PS_PERM_GBUFFER" in defines else 1,
        }
        if "PS_PERM_GBUFFER" in defines:
            executions[shader["selector"]]["output_target_components"] = [4, 2, 4]
        if "PS_PERM_GBUFFER" in defines and "PS_FLIP_BACKFACE_NORMALS" in defines:
            executions[shader["selector"]]["ulp_tolerance"] = 8
        elif "PS_PERM_GBUFFER" in defines and asg:
            executions[shader["selector"]]["ulp_tolerance"] = 2
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="main_slant", bodies=bodies, executions=executions,
    )
