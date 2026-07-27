"""Recognize the clustered-light culling grid permutations."""

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
1. Map each compute lane to one cluster cell; the 94 variants specialize only
   the rectangular thread-grid dimensions and perspective/orthographic bounds.
2. Decode four packed light-index ranges for the current depth slice.
3. Construct the cell AABB in view space, including the nonlinear perspective
   depth interval when ORTHO is absent.
4. Test sphere, reflection, cone and frustum records against that AABB.
5. Accumulate accepted IDs into eight 32-bit lane masks and write the masks to
   the cell's 33-word clustered-light record.

The executable body remains instruction-ordered because its packed bitfields,
dynamic constant-buffer records and mask compaction must preserve integer DXBC.
*/
"""


def _group_size(defines: list[str], axis: str) -> int:
    prefix = f"GROUP_SIZE_{axis}="
    return int(next(
        value.removeprefix(prefix)
        for value in defines
        if value.startswith(prefix)
    ))


def apply_cmp_cluster_culling_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records
        if record["source_name"] == "cmp_cluster_culling"
    ]
    if len(shaders) != 94 or any(
        shader["stage"] != "compute" for shader in shaders
    ):
        return None
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    expanded = module_variants(
        (staging / "hlsl" / "cmp_cluster_culling.hlsl").read_text(
            encoding="utf-8"
        ),
        definitions,
    )
    expanded = {
        selector: re.sub(r"<< (r\d+\.[xyzw])", r"<< (int)\1", source)
        for selector, source in expanded.items()
    }
    bodies = {
        shader["selector"]: SEMANTIC_PHASE_MAP + expanded[shader["selector"]]
        for shader in shaders
    }
    executions = {}
    for shader in shaders:
        group_x = _group_size(shader["defines"], "X")
        group_y = _group_size(shader["defines"], "Y")
        thread_count = group_x * group_y
        executions[shader["selector"]] = {
            "kind": "compute_structured_u32",
            "width": group_x * 3,
            "height": group_y,
            "dispatch_width": group_x * 3,
            "dispatch_height": group_y,
            "thread_group": [group_x, group_y, 1],
            "texture_slots": [],
            "samplers": [],
            "constant_buffers": [
                {"slot": 0, "profile": "cluster"},
                {"slot": 1, "profile": "cluster-culling"},
            ],
            "structured_output_elements": thread_count * 3 * 33,
            "output": "color",
            "output_components": 1,
        }
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="cmp_cluster_culling", bodies=bodies, executions=executions,
    )
