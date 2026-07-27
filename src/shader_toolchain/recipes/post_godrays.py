"""Recognize and validate the two god-ray integration modes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..hlsl import module_variants
from .common import emit_validated_module


SEMANTIC_PHASE_MAP = """
/*
Semantic phase map
------------------
1. Reconstruct a normalized view ray from HZB depth and transform it to world.
2. March 42 fixed-distance samples from the camera through the visible volume.
3. Transform each sample into cascade 1 and evaluate a manually filtered 7x7
   comparison-shadow footprint.  Accumulate only samples inside the cascade.
4. Underwater mode intersects the ray with the water plane and modulates each
   accepted shadow sample with two scrolling water-normal/caustic frequencies.
5. Divide accumulated visibility by the accepted-sample count (minimum 10).
6. Reproject the final world sample into the previous frame, then blend the
   temporal and volatility histories with the new integration result.
7. Shape the light-facing term and map the configured god-ray/light color
   through the current HDR power/base/range before writing color and history.

The executable block below remains instruction-ordered because changing FMA
attachment inside the PCF and temporal reductions changes observable output.
*/
"""


def apply_post_godrays_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "post_godrays"]
    if len(shaders) != 2 or any(shader["stage"] != "pixel" for shader in shaders):
        return None
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    expanded = module_variants(
        (staging / "hlsl" / "post_godrays.hlsl").read_text(encoding="utf-8"),
        definitions,
    )
    bodies = {
        shader["selector"]: (
            SEMANTIC_PHASE_MAP
            + expanded[shader["selector"]]
        )
        for shader in shaders
    }
    executions = {}
    for shader in shaders:
        underwater = "PS_UNDER_WATER" in shader["defines"]
        slots = [0, 1, 3, 4] + ([5] if underwater else [])
        samplers = [
            {"slot": 1, "filter": "point"},
            {"slot": 6, "filter": "linear"},
            {"slot": 12, "filter": "linear", "comparison": True},
        ]
        if underwater:
            samplers.insert(1, {"slot": 3, "filter": "linear"})
        executions[shader["selector"]] = {
            "kind": "fullscreen_uv",
            "vertex_harness": "fullscreen_uv",
            "texture_slots": slots,
            "texture_kinds": ["2d", "2darray", "2d", "2d"]
                             + (["2d"] if underwater else []),
            "samplers": samplers,
            "constant_buffers": [
                {"slot": 5, "profile": "projection"},
                {"slot": 9, "profile": "hdr"},
                {"slot": 12, "profile": "random"},
            ],
            "output": "color",
            "output_components": 4,
            "output_targets": 2,
        }
        if not underwater:
            executions[shader["selector"]]["ulp_tolerance"] = 1
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="post_godrays", bodies=bodies, executions=executions,
    )
