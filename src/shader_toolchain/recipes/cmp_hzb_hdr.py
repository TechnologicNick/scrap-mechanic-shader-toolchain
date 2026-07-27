"""Recover the hierarchical depth, AO-depth, and HDR feedback reduction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import asset, emit_validated_module, ensure_projection_include


SEMANTIC_PHASE_MAP = """
/*
Semantic phase map
------------------
1. Convert a 2x2 hardware-depth quad to view depth, optionally merging the
   separately exported depth surface, and write the full-resolution HZB level.
2. Reduce maximum view depth through 2x2, 4x4 and 8x8 levels in group-shared
   memory while producing the three AO depth encodings.
3. HDR variants reduce average RGB plus scalar min/max intensity and atomically
   accumulate the eight-frame feedback summary.
4. Shadow-feedback variants retain the packed clustered-light/spotlight ABI;
   clusters without lights exit before reading a spotlight record.
*/
"""


def apply_cmp_hzb_hdr_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "cmp_hzb_hdr"]
    if len(shaders) != 16 or any(shader["stage"] != "compute" for shader in shaders):
        return None
    ensure_projection_include(staging)
    source = SEMANTIC_PHASE_MAP + asset("cmp_hzb_hdr.hlsl")
    bodies = {}
    for shader in shaders:
        prefix = "".join(
            f"#define {name} {value if separator else '1'}\n"
            for definition in shader["defines"]
            for name, separator, value in [definition.partition("=")]
        )
        bodies[shader["selector"]] = prefix + source
    executions = {}
    for shader in shaders:
        defines = set(shader["defines"])
        hdr = "HDR" in defines
        shadow = "SHADOW_FEEDBACK" in defines
        depth_export = "DEPTH_EXPORT" in defines
        texture_slots = [0]
        if hdr:
            texture_slots.append(1)
        if depth_export:
            texture_slots.append(2)
        constants = [
            {"slot": 0, "profile": "hzb"},
            {"slot": 5, "profile": "projection"},
        ]
        if shadow:
            constants.extend((
                {"slot": 1, "profile": "cluster"},
                {"slot": 2, "profile": "index"},
            ))
        execution = {
            "kind": "compute_mixed_hzb",
            "width": 32,
            "height": 32,
            "dispatch_width": 16,
            "dispatch_height": 16,
            "texture_slots": texture_slots,
            "texture_kinds": ["2d"] * len(texture_slots),
            "smooth_texture_slots": [slot for slot in texture_slots if slot != 0],
            "structured_inputs": (
                [{"slot": 3, "elements": 33, "stride": 4, "profile": "zero"}]
                if shadow else []
            ),
            "structured_outputs": (
                [{"slot": 7, "elements": 1024, "stride": 4}]
                if hdr or shadow else []
            ),
            "samplers": [],
            "constant_buffers": constants,
            "output": "color",
            "output_components": 1,
            "output_targets": 7,
            "output_target_components": [1] * 7,
            "texture_outputs": True,
            "thread_group": [16, 16, 1],
            "ulp_tolerance": 0,
        }
        executions[shader["selector"]] = execution
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="cmp_hzb_hdr", bodies=bodies, executions=executions,
    )
