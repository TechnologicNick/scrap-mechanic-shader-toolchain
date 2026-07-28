"""Recognize deferred direct-light and shadow permutations."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..hlsl import module_variants
from ..reflect import ShaderReflector
from .common import (
    emit_validated_module,
    asset,
    ensure_recovered_cbuffer_include,
    rename_register_state,
    replace_cbuffer_with_include,
)


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


REGISTER_NAMES = {
    0: "gbufferAddressState", 1: "surfaceMaterialState",
    2: "normalDecodeState", 3: "viewPositionState",
    4: "clusterMaskState", 5: "lightIteratorState",
    6: "lightGeometryState", 7: "lightDirectionState",
    8: "distanceAttenuationState", 9: "coneAttenuationState",
    10: "cookieProjectionState", 11: "cookieSampleState",
    12: "cascadeSelectionState", 13: "shadowProjectionState",
    14: "shadowGatherStateA", 15: "shadowGatherStateB",
    16: "shadowFilterState", 17: "brdfDiffuseState",
    18: "brdfSpecularState", 19: "anisotropyState",
    20: "subsurfaceState", 21: "ambientOcclusionState",
    22: "cloudShadowState", 23: "directionalLightState",
    24: "horizonLightState", 25: "cameraLightState",
    26: "localLightState", 27: "profileLookupState",
    28: "materialResponseState", 29: "visibilityState",
    30: "directLightAccumulator", 31: "lightOutputState",
    32: "lightingScratchA", 33: "lightingScratchB",
    34: "lightingScratchC",
}


MAIN_LIGHT_ABI = {
    "CB_PROJECTION": "main_light_projection_abi.hlsl",
    "CB_PERFRAME": "main_light_perframe_abi.hlsl",
    "Cluster": "main_light_cluster_abi.hlsl",
    "LightProps": "main_light_lightprops_abi.hlsl",
}


def _lift_main_light_abi(source: str) -> str:
    """Replace the four invariant reflected buffers with named ABI includes."""
    for cbuffer_name, filename in MAIN_LIGHT_ABI.items():
        source = replace_cbuffer_with_include(source, cbuffer_name, filename)
    return source


def _is_clustered_local_compact(defines: list[str]) -> bool:
    selected = set(defines)
    return (
        selected <= {
            "ORTHO",
            "PIXEL_SHADER",
            "PS_SHADER_QUALITY_LOW",
            "PS_SHADER_QUALITY_MEDIUM",
            "PS_SHADER_QUALITY_HIGH",
            "PS_SHADOW_QUALITY_OFF",
            "PS_HORIZON_LIGHT",
            "PS_CAMERA_LIGHT",
            "PS_FLOW_COOKIE",
            "PS_TEMPORAL_AO_CASCADE",
            "PS_DIRECTIONAL_LIGHT",
            "PS_SSS",
        }
        and bool(
            selected
            & {
                "PS_SHADER_QUALITY_LOW",
                "PS_SHADER_QUALITY_MEDIUM",
                "PS_SHADER_QUALITY_HIGH",
            }
        )
    )


def _lift_clustered_local_compact(
    source: str,
    *,
    medium_quality: bool = False,
    shadows: bool = False,
    horizon: bool = False,
    camera: bool = False,
    flow_cookie: bool = False,
    temporal_ao: bool = False,
    directional: bool = False,
    sss: bool = False,
    high_quality: bool = False,
    orthographic: bool = False,
) -> str:
    """Replace compact-quality local lighting with recovered typed phases."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    return (
        declarations
        + f"\n\n#define MAIN_LIGHT_COMPACT_MEDIUM {int(medium_quality)}\n"
        + f"#define MAIN_LIGHT_COMPACT_SHADOWS {int(shadows)}\n"
        + f"#define MAIN_LIGHT_COMPACT_HORIZON {int(horizon)}\n"
        + f"#define MAIN_LIGHT_COMPACT_CAMERA {int(camera)}\n"
        + f"#define MAIN_LIGHT_COMPACT_FLOW_COOKIE {int(flow_cookie)}\n"
        + f"#define MAIN_LIGHT_COMPACT_TEMPORAL_AO {int(temporal_ao)}\n"
        + f"#define MAIN_LIGHT_COMPACT_DIRECTIONAL {int(directional)}\n"
        + "#define MAIN_LIGHT_COMPACT_DIRECTIONAL_SHADOWS "
        + f"{int(directional and shadows)}\n"
        + f"#define MAIN_LIGHT_COMPACT_SSS {int(sss)}\n"
        + f"#define MAIN_LIGHT_COMPACT_HIGH {int(high_quality)}\n"
        + f"#define MAIN_LIGHT_COMPACT_ORTHO {int(orthographic)}\n"
        + '#include "../main_light_clustered_local.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UNSCALED_UV0,\n"
        + "  out float3 o0 : SV_Target0)\n"
        + "{\n"
        + "  o0 = EvaluateMainLightClusteredLocal(v1);\n"
        + "}\n"
    )


def _emit_variant_snippets(
    staging: Path,
    variants: dict[str, str],
) -> dict[str, str]:
    """Emit each recovered permutation as an independently liftable snippet."""
    snippet_root = staging / "semantic" / "include" / "main_light"
    snippet_root.mkdir(parents=True, exist_ok=True)
    bodies: dict[str, str] = {}
    for selector, source in variants.items():
        filename = f"{selector}.hlsl"
        source = source.replace('#include "include/', '#include "../')
        replacement = SEMANTIC_PHASE_MAP + source
        (snippet_root / filename).write_text(
            replacement,
            encoding="utf-8",
            newline="\n",
        )
        bodies[selector] = f'#include "include/main_light/{filename}"\n'
    return bodies


def _execution(blob: bytes) -> dict[str, Any]:
    abi = ShaderReflector().abi(blob)
    textures = [resource for resource in abi["resources"] if resource["type"] == 2]
    samplers = [resource for resource in abi["resources"] if resource["type"] == 3]
    buffers = [resource for resource in abi["resources"] if resource["type"] == 5]
    profiles = {
        0: "main-light-cluster",
        1: "main-light-lights",
        5: "projection",
        12: "index",
    }
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
                "profile": "main-light",
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
    for cbuffer_name, filename in MAIN_LIGHT_ABI.items():
        ensure_recovered_cbuffer_include(
            staging, "main_light", cbuffer_name, filename
        )
    helper_path = (
        staging / "semantic" / "include" / "main_light_clustered_local.hlsl"
    )
    helper_path.write_text(
        asset("main_light_clustered_local.hlsl"),
        encoding="utf-8",
        newline="\n",
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
        source = rename_register_state(
            source, REGISTER_NAMES,
            note="BRDF, cookie, and shadow accumulation retain DXBC order.",
        )
        source = _lift_main_light_abi(source)
        if _is_clustered_local_compact(definitions[selector]):
            source = _lift_clustered_local_compact(
                source,
                medium_quality=(
                    "PS_SHADER_QUALITY_MEDIUM" in definitions[selector]
                ),
                shadows=(
                    "PS_SHADOW_QUALITY_OFF" not in definitions[selector]
                ),
                horizon=("PS_HORIZON_LIGHT" in definitions[selector]),
                camera=("PS_CAMERA_LIGHT" in definitions[selector]),
                flow_cookie=("PS_FLOW_COOKIE" in definitions[selector]),
                temporal_ao=(
                    "PS_TEMPORAL_AO_CASCADE" in definitions[selector]
                ),
                directional=("PS_DIRECTIONAL_LIGHT" in definitions[selector]),
                sss=("PS_SSS" in definitions[selector]),
                high_quality=(
                    "PS_SHADER_QUALITY_HIGH" in definitions[selector]
                ),
                orthographic=("ORTHO" in definitions[selector]),
            )
        variants[selector] = source
    bodies = _emit_variant_snippets(staging, variants)
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="main_light",
        bodies=bodies,
        executions={
            shader["selector"]: _execution(blobs[shader["bundle_index"]])
            for shader in shaders
        },
    )
