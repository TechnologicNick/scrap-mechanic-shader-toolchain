"""Recognize the medium/high volumetric-light integration shaders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..hlsl import module_variants
from .common import emit_validated_module


SEMANTIC_PHASE_MAP = """
/*
Semantic phase map
------------------
1. Resolve the screen tile's clustered-volumetric ID masks.
2. Reconstruct current world position and reproject it into the previous frame.
3. Validate temporal history with previous depth, camera motion and volatility.
4. Jitter a view ray with screen noise; quality controls the temporal/ray budget.
5. Walk clustered sphere/cone light IDs, integrating attenuation, cookies,
   shadow-atlas comparisons and 3D density noise along each light volume.
6. Blend new in-scattering with valid history and write radiance plus history.

The executable block remains instruction-ordered because nested bit scans,
shadow comparisons and long accumulation chains are contraction-sensitive.
*/
"""


def apply_post_volumetric_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "post_volumetric"]
    if len(shaders) != 2 or any(shader["stage"] != "pixel" for shader in shaders):
        return None
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    expanded = module_variants(
        (staging / "hlsl" / "post_volumetric.hlsl").read_text(encoding="utf-8"),
        definitions,
    )
    # 3Dmigoto resolves the constant-register offset of this nested matrix as
    # an array stride. Restore the source-level struct member and light index.
    expanded = {
        selector: source.replace(
            "cb_arrCone[r4.w/4]._m", "cb_arrCone[r4.w].xClip._m"
        )
        for selector, source in expanded.items()
    }
    bodies = {
        shader["selector"]: SEMANTIC_PHASE_MAP + expanded[shader["selector"]]
        for shader in shaders
    }
    execution = {
        "kind": "fullscreen_uv",
        "vertex_harness": "fullscreen_uv",
        "texture_slots": [0, 2, 3, 4, 5, 6, 7, 8],
        "texture_kinds": ["2d", "3d", "2darray", "2darray", "2d", "2d", "2d", "2d"],
        "structured_inputs": [
            {"slot": 1, "elements": 17, "stride": 4, "profile": "zero"},
        ],
        "samplers": [
            {"slot": 1, "filter": "point"},
            {"slot": 3, "filter": "linear"},
            {"slot": 6, "filter": "linear"},
            {"slot": 13, "filter": "point", "comparison": True},
        ],
        "constant_buffers": [
            {"slot": 0, "profile": "cluster"},
            {"slot": 1, "profile": "random"},
            {"slot": 5, "profile": "projection"},
            {"slot": 9, "profile": "hdr"},
            {"slot": 12, "profile": "random"},
        ],
        "output": "color",
        "output_components": 4,
        "output_targets": 2,
    }
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="post_volumetric", bodies=bodies,
        executions={shader["selector"]: execution for shader in shaders},
    )
