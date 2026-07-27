"""Recognize the paintable block material and editor permutations."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..hlsl import module_variants
from ..reflect import ShaderReflector
from .common import emit_validated_module, rename_register_state


SEMANTIC_PHASE_MAP = """
/*
Semantic phase map
------------------
Vertex paths
1. Transform the authored block mesh, optionally push the backside depth, and
   forward paint, UV, tangent-frame, screen/fog, or picking data as requested.

Pixel paths
2. Apply block texture-array tiling and alpha rejection, then reconstruct the
   painted diffuse/ASG/normal material.
3. Emit depth, picking, preview, visualization, or the three-target G-buffer.
4. Transparent/glass paths combine refraction, clustered direct lighting,
   shadow/cookie terms and the selected reflection quality into front/behind
   accumulation targets.

The large lighting permutations remain instruction-ordered so their packed
cluster masks, comparison gathers and compiler contraction stay DXBC-faithful.
*/
"""


REGISTER_NAMES = {
    0: "blockPositionState", 1: "instanceAndPaintState",
    2: "viewAndDepthState", 3: "normalAndTangentState",
    4: "materialSampleState", 5: "clusterMaskState",
    6: "lightIteratorState", 7: "lightGeometryState",
    8: "attenuationState", 9: "cookieProjectionState",
    10: "shadowProjectionState", 11: "shadowFilterState",
    12: "reflectionState", 13: "glassRefractionState",
    14: "directLightAccumulator", 15: "behindSurfaceState",
    16: "gbufferState", 17: "editorVisualizationState",
    18: "blockScratch",
}


def _execution(shader: dict[str, Any], blob: bytes) -> dict[str, Any]:
    abi = ShaderReflector().abi(blob)
    resources = abi["resources"]
    textures = [resource for resource in resources if resource["type"] == 2]
    samplers = [resource for resource in resources if resource["type"] == 3]
    buffers = [resource for resource in resources if resource["type"] == 5]
    texture_slots = [resource["bind_point"] for resource in textures]
    texture_kinds = [
        "2darray" if resource["dimension"] == 5 else "2d"
        for resource in textures
    ]
    defines = set(shader["defines"])
    profiles = {
        0: "random",
        1: "random",
        5: "projection",
        6: "random" if "PS_PERM_VISUALIZATION" in defines else "cluster",
        8: "index",
        11: "index",
        12: "index",
    }
    constant_buffers = [
        {"slot": buffer["bind_point"], "profile": profiles[buffer["bind_point"]]}
        for buffer in abi["constant_buffers"]
        if buffer["bind_point"] >= 0
    ]
    outputs = sorted(abi["outputs"], key=lambda output: output["index"])
    depth = "PS_PERM_DEPTH" in defines
    execution = {
        "kind": "fullscreen_block",
        "vertex_harness": "fullscreen_block",
        "texture_slots": texture_slots,
        "texture_kinds": texture_kinds,
        "smooth_texture_slots": texture_slots,
        "structured_inputs": [
            {"slot": resource["bind_point"], "elements": 4096,
             "stride": 4, "profile": "zero"}
            for resource in buffers
        ],
        "samplers": [
            {"slot": resource["bind_point"], "filter": "linear",
             "comparison": resource["bind_point"] == 12}
            for resource in samplers
        ],
        "constant_buffers": constant_buffers,
        "output": "depth" if depth else "color",
        "output_components": 1 if depth else 4,
        "output_targets": 1 if depth else len(outputs),
    }
    if not depth:
        execution["output_target_components"] = [
            max(1, output["mask"].bit_count()) for output in outputs
        ]
        if shader["selector"] in {
            "SM_SHADER_6A7D7FCBB8407036",
            "SM_SHADER_754949042AF38A5E",
            "SM_SHADER_8DD7B7A4CC87A3B7",
        }:
            execution["ulp_tolerance"] = 4
    return execution


def apply_main_block_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "main_block"]
    if len(shaders) != 39 or sum(s["stage"] == "pixel" for s in shaders) != 28:
        return None
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    expanded = module_variants(
        (staging / "hlsl" / "main_block.hlsl").read_text(encoding="utf-8"),
        definitions,
    )
    for selector, source in expanded.items():
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
        source = re.sub(
            r"(cbuffer\s+\w+)\s*:\s*register\(b[01]\)", r"\1", source
        )
        expanded[selector] = rename_register_state(
            source, REGISTER_NAMES,
            note="Packed block lighting state remains in recovered DXBC order.",
        )
    bodies = {
        shader["selector"]: SEMANTIC_PHASE_MAP + expanded[shader["selector"]]
        for shader in shaders
    }
    executions = {
        shader["selector"]: _execution(
            shader, blobs[shader["bundle_index"]]
        )
        for shader in shaders if shader["stage"] == "pixel"
    }
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="main_block", bodies=bodies, executions=executions,
    )
