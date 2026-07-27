"""Recognize cube and octahedral reflection-probe conversion variants."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..hlsl import module_variants
from ..reflect import ShaderReflector
from .common import emit_validated_module


SEMANTIC_PHASE_MAP = """
/*
Semantic phase map
------------------
1. Convert the destination UV to an octahedral direction or cube-face ray.
2. Select the requested probe array element when array mode is enabled.
3. Sample the cube/octahedral source and emit its four-channel probe value.

The branch-free coordinate fold remains instruction ordered to preserve the
edge convention and floating-point behavior used by the original cache.
*/
"""


def _execution(blob: bytes) -> dict[str, Any]:
    abi = ShaderReflector().abi(blob)
    texture = next(resource for resource in abi["resources"] if resource["type"] == 2)
    dimensions = {4: "2d", 5: "2darray", 9: "cube", 10: "cubearray"}
    samplers = [resource for resource in abi["resources"] if resource["type"] == 3]
    return {
        "kind": "fullscreen_reflection_probe",
        "vertex_harness": "fullscreen_unscaled",
        "width": 8,
        "height": 8,
        "texture_slots": [texture["bind_point"]],
        "texture_kinds": [dimensions[texture["dimension"]]],
        "smooth_texture_slots": [texture["bind_point"]],
        "samplers": [
            {
                "slot": sampler["bind_point"],
                "filter": "point" if sampler["bind_point"] in (1, 2) else "linear",
            }
            for sampler in samplers
        ],
        "constant_buffers": [{"slot": 0, "profile": "index"}],
        "output": "color",
        "output_components": 4,
    }


def apply_gen_reflection_probe_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record for record in records if record["source_name"] == "gen_reflection_probe"
    ]
    if len(shaders) != 4 or any(shader["stage"] != "pixel" for shader in shaders):
        return None
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    variants = module_variants(
        (staging / "hlsl" / "gen_reflection_probe.hlsl").read_text(encoding="utf-8"),
        definitions,
    )
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="gen_reflection_probe",
        bodies={
            shader["selector"]: SEMANTIC_PHASE_MAP + variants[shader["selector"]]
            for shader in shaders
        },
        executions={
            shader["selector"]: _execution(blobs[shader["bundle_index"]])
            for shader in shaders
        },
    )
