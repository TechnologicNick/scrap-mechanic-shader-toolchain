"""Recognize deferred indirect-light, probe, reflection and SSGI variants."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..hlsl import module_variants
from ..reflect import ShaderReflector
from .common import (
    asset,
    emit_validated_module,
    ensure_recovered_cbuffer_include,
    rename_register_state,
    replace_cbuffer_with_include,
)


SEMANTIC_PHASE_MAP = """
/*
Semantic phase map
------------------
1. Reconstruct view position, material normal and roughness from the G-buffer.
2. Evaluate the selected cascade/probe AO and diffuse-GI sources.
3. Trace or sample SSGI/SSR and blend the chosen reflection probe quality.
4. Accumulate up to four subsurface layers and emit indirect, AO and SSS data.

The feature blocks remain instruction ordered because packed voxel masks,
probe-array addressing, ray steps and temporal confidence are DXBC-sensitive.
*/
"""


REGISTER_NAMES = {
    0: "gbufferAddressState", 1: "viewPositionState",
    2: "normalDecodeState", 3: "materialResponseState",
    4: "cascadeSelectionState", 5: "cascadeCoordinateState",
    6: "voxelMaskState", 7: "voxelIteratorState",
    8: "probeAddressState", 9: "probeWeightState",
    10: "probeDiffuseState", 11: "probeOcclusionState",
    12: "ssgiRayState", 13: "ssgiStepState",
    14: "ssgiHitState", 15: "ssgiConfidenceState",
    16: "ssrRayState", 17: "ssrStepState",
    18: "ssrHitState", 19: "reflectionDirectionState",
    20: "reflectionProbeState", 21: "reflectionBlendState",
    22: "ambientOcclusionState", 23: "diffuseGiState",
    24: "subsurfaceLayerZero", 25: "subsurfaceLayerOne",
    26: "subsurfaceLayerTwo", 27: "subsurfaceLayerThree",
    28: "subsurfaceWeightState", 29: "indirectAccumulator",
    30: "aoAccumulator", 31: "subsurfaceAccumulator",
    32: "indirectOutputState", 33: "indirectScratchA",
    34: "indirectScratchB", 35: "indirectScratchC",
    36: "indirectScratchD",
}


INDIRECT_LIGHT_ABI = {
    "CB_PROJECTION": "indirect_light_projection_abi.hlsl",
    "CB_PERFRAME": "indirect_light_perframe_abi.hlsl",
    "CB_REFLECTIONS": "indirect_light_reflections_abi.hlsl",
    "cb_hdr_settings": "indirect_light_hdr_abi.hlsl",
    "Cluster": "indirect_light_cluster_abi.hlsl",
    "CB_AO_SETTINGS": "indirect_light_ao_settings_abi.hlsl",
}


def _lift_indirect_light_abi(source: str) -> str:
    """Replace invariant reflected buffers with named ABI includes."""
    for cbuffer_name, filename in INDIRECT_LIGHT_ABI.items():
        if re.search(rf"\bcbuffer\s+{re.escape(cbuffer_name)}\b", source):
            source = replace_cbuffer_with_include(source, cbuffer_name, filename)
    return source


def _is_probe_cascade_reference(defines: list[str]) -> bool:
    return set(defines) == {
        "PIXEL_SHADER",
        "PS_CASCADE",
        "PS_PROBE_GI",
        "PS_REFLECTION",
        "PS_SSS_COUNT=1",
    }


def _is_cascade_medium_reference(defines: list[str]) -> bool:
    return set(defines) == {
        "PIXEL_SHADER",
        "PS_CASCADE",
        "PS_REFLECTION",
        "PS_SSAO_QUALITY_MEDIUM",
        "PS_SSS_COUNT=2",
    }


def _is_medium_sss_reference(defines: list[str]) -> bool:
    return set(defines) == {
        "PIXEL_SHADER",
        "PS_SSAO_QUALITY_MEDIUM",
        "PS_SSS_COUNT=1",
    }


def _is_ortho_medium_ssgi_three_reference(defines: list[str]) -> bool:
    return set(defines) == {
        "ORTHO",
        "PIXEL_SHADER",
        "PS_PROBE_GI",
        "PS_REFLECTION",
        "PS_SSAO_QUALITY_MEDIUM",
        "PS_SSGI",
        "PS_SSS_COUNT=3",
    }


def _is_ortho_medium_reflection_two_reference(defines: list[str]) -> bool:
    return set(defines) == {
        "ORTHO",
        "PIXEL_SHADER",
        "PS_REFLECTION",
        "PS_SSAO_QUALITY_MEDIUM",
        "PS_SSS_COUNT=2",
    }


def _is_medium_probe_four_reference(defines: list[str]) -> bool:
    return set(defines) == {
        "PIXEL_SHADER",
        "PS_PROBE_GI",
        "PS_REFLECTION",
        "PS_SSAO_QUALITY_MEDIUM",
        "PS_SSS_COUNT=4",
    }


def _is_ortho_high_cascade_probe_reference(defines: list[str]) -> bool:
    return set(defines) == {
        "ORTHO",
        "PIXEL_SHADER",
        "PS_CASCADE",
        "PS_PROBE_GI",
        "PS_REFLECTION",
        "PS_SSAO_QUALITY_HIGH",
        "PS_SSS_COUNT=1",
    }


def _is_ortho_high_ssgi_three_reference(defines: list[str]) -> bool:
    return set(defines) == {
        "ORTHO",
        "PIXEL_SHADER",
        "PS_PROBE_GI",
        "PS_REFLECTION",
        "PS_SSAO_QUALITY_HIGH",
        "PS_SSGI",
        "PS_SSS_COUNT=3",
    }


def _is_ortho_high_ultra_reference(defines: list[str]) -> bool:
    return set(defines) == {
        "ORTHO",
        "PIXEL_SHADER",
        "PS_PROBE_GI",
        "PS_REFLECTION",
        "PS_SSAO_QUALITY_HIGH",
        "PS_SSS_COUNT=0",
        "PS_ULTRA",
    }


def _is_ortho_medium_ultra_reference(defines: list[str]) -> bool:
    return set(defines) == {
        "ORTHO",
        "PIXEL_SHADER",
        "PS_PROBE_GI",
        "PS_REFLECTION",
        "PS_SSAO_QUALITY_MEDIUM",
        "PS_SSS_COUNT=0",
        "PS_ULTRA",
    }


def _is_ortho_low_ultra_reference(defines: list[str]) -> bool:
    return set(defines) == {
        "ORTHO",
        "PIXEL_SHADER",
        "PS_PROBE_GI",
        "PS_REFLECTION",
        "PS_SSAO_QUALITY_LOW",
        "PS_SSS_COUNT=0",
        "PS_ULTRA",
    }


def _perspective_cascade_ssgi_policy(
    defines: list[str],
) -> tuple[float, bool, int] | None:
    values = set(defines)
    common = {
        "PIXEL_SHADER",
        "PS_CASCADE",
        "PS_PROBE_GI",
        "PS_REFLECTION",
        "PS_SSGI",
    }
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(0, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) > 1 or len(counts) != 1:
        return None
    policy = {f"PS_SSS_COUNT={counts[0]}"}
    if qualities:
        policy.add(qualities[0])
    expected = common | policy
    if values != expected:
        return None
    quality = quality_scales[qualities[0]] if qualities else 1.0
    return quality, bool(qualities), counts[0]


def _perspective_probe_quality_policy(
    defines: list[str],
) -> tuple[float, bool, int] | None:
    values = set(defines)
    common = {"PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION"}
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(0, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) > 1 or len(counts) != 1:
        return None
    policy = {f"PS_SSS_COUNT={counts[0]}"}
    if qualities:
        policy.add(qualities[0])
    expected = common | policy
    if values != expected:
        return None
    quality = quality_scales[qualities[0]] if qualities else 1.0
    return quality, bool(qualities), counts[0]


def _perspective_ao_sss_policy(
    defines: list[str],
) -> tuple[float, bool, int] | None:
    values = set(defines)
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(0, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) > 1 or len(counts) != 1:
        return None
    policy = {f"PS_SSS_COUNT={counts[0]}"}
    if qualities:
        policy.add(qualities[0])
    expected = {"PIXEL_SHADER"} | policy
    if values != expected:
        return None
    quality = quality_scales[qualities[0]] if qualities else 1.0
    return quality, bool(qualities), counts[0]


def _perspective_cascade_only_policy(
    defines: list[str],
) -> tuple[float, bool, int] | None:
    """Recognize cascade-first visibility with optional screen AO."""
    values = set(defines)
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(1, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) > 1 or len(counts) != 1:
        return None
    policy = {f"PS_SSS_COUNT={counts[0]}"}
    if qualities:
        policy.add(qualities[0])
    expected = {"PIXEL_SHADER", "PS_CASCADE"} | policy
    if values != expected:
        return None
    quality = quality_scales[qualities[0]] if qualities else 1.0
    return quality, bool(qualities), counts[0]


def _perspective_cascade_reflection_policy(
    defines: list[str],
) -> tuple[float, bool, int] | None:
    """Recognize cascade/reflection with optional AO and trailing SSS."""
    values = set(defines)
    common = {"PIXEL_SHADER", "PS_CASCADE", "PS_REFLECTION"}
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(1, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) > 1 or len(counts) != 1:
        return None
    policy = {f"PS_SSS_COUNT={counts[0]}"}
    if qualities:
        policy.add(qualities[0])
    if values != common | policy:
        return None
    quality = quality_scales[qualities[0]] if qualities else 1.0
    return quality, bool(qualities), counts[0]


def _ortho_ssgi_quality_policy(
    defines: list[str],
) -> tuple[float, bool, int] | None:
    """Recognize orthographic temporal SSGI across AO quality and SSS count."""
    values = set(defines)
    common = {
        "ORTHO", "PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION", "PS_SSGI"
    }
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(0, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) > 1 or len(counts) != 1:
        return None
    policy = {f"PS_SSS_COUNT={counts[0]}"}
    if qualities:
        policy.add(qualities[0])
    expected = common | policy
    if values != expected:
        return None
    quality = quality_scales[qualities[0]] if qualities else 1.0
    return quality, bool(qualities), counts[0]


def _ortho_ao_sss_policy(
    defines: list[str],
) -> tuple[float, int] | None:
    """Recognize orthographic horizon AO with counted SSS visibility."""
    values = set(defines)
    common = {"ORTHO", "PIXEL_SHADER"}
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(0, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) != 1 or len(counts) != 1:
        return None
    expected = common | {qualities[0], f"PS_SSS_COUNT={counts[0]}"}
    if values != expected:
        return None
    return quality_scales[qualities[0]], counts[0]


def _ortho_cascade_policy(
    defines: list[str],
) -> tuple[float, int] | None:
    """Recognize orthographic AO with cascade-first visibility outputs."""
    values = set(defines)
    common = {"ORTHO", "PIXEL_SHADER", "PS_CASCADE"}
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(1, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) != 1 or len(counts) != 1:
        return None
    expected = common | {qualities[0], f"PS_SSS_COUNT={counts[0]}"}
    if values != expected:
        return None
    return quality_scales[qualities[0]], counts[0]


def _ortho_reflection_policy(
    defines: list[str],
) -> tuple[float, bool, int] | None:
    """Recognize orthographic reflection with optional AO and counted SSS."""
    values = set(defines)
    common = {"ORTHO", "PIXEL_SHADER", "PS_REFLECTION"}
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(0, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) > 1 or len(counts) != 1:
        return None
    policy = {f"PS_SSS_COUNT={counts[0]}"}
    if qualities:
        policy.add(qualities[0])
    if values != common | policy:
        return None
    quality = quality_scales[qualities[0]] if qualities else 1.0
    return quality, bool(qualities), counts[0]


def _ortho_cascade_reflection_policy(
    defines: list[str],
) -> tuple[float, bool, int] | None:
    """Recognize orthographic reflection with cascade-first visibility."""
    values = set(defines)
    common = {"ORTHO", "PIXEL_SHADER", "PS_CASCADE", "PS_REFLECTION"}
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(1, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) > 1 or len(counts) != 1:
        return None
    policy = {f"PS_SSS_COUNT={counts[0]}"}
    if qualities:
        policy.add(qualities[0])
    if values != common | policy:
        return None
    quality = quality_scales[qualities[0]] if qualities else 1.0
    return quality, bool(qualities), counts[0]


def _ortho_cascade_ssgi_policy(
    defines: list[str],
) -> tuple[float, bool, int] | None:
    """Recognize orthographic temporal SSGI with cascade-first outputs."""
    values = set(defines)
    common = {
        "ORTHO", "PIXEL_SHADER", "PS_CASCADE", "PS_PROBE_GI",
        "PS_REFLECTION", "PS_SSGI",
    }
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(0, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) > 1 or len(counts) != 1:
        return None
    policy = {f"PS_SSS_COUNT={counts[0]}"}
    if qualities:
        policy.add(qualities[0])
    if values != common | policy:
        return None
    quality = quality_scales[qualities[0]] if qualities else 1.0
    return quality, bool(qualities), counts[0]


def _perspective_probe_cascade_policy(
    defines: list[str],
) -> tuple[float, bool, int] | None:
    """Recognize probe lighting with AO and cascade-first visibility."""
    values = set(defines)
    common = {"PIXEL_SHADER", "PS_CASCADE", "PS_PROBE_GI", "PS_REFLECTION"}
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(0, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) > 1 or len(counts) != 1:
        return None
    policy = {f"PS_SSS_COUNT={counts[0]}"}
    if qualities:
        policy.add(qualities[0])
    if values != common | policy:
        return None
    quality = quality_scales[qualities[0]] if qualities else 1.0
    return quality, bool(qualities), counts[0]


def _perspective_ultra_quality_policy(
    defines: list[str],
) -> tuple[float, int] | None:
    """Recognize perspective ultra history across AO quality and SSS count."""
    values = set(defines)
    common = {"PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION", "PS_ULTRA"}
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(0, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) != 1 or len(counts) != 1:
        return None
    expected = common | {qualities[0], f"PS_SSS_COUNT={counts[0]}"}
    if values != expected:
        return None
    return quality_scales[qualities[0]], counts[0]


def _perspective_ssgi_probe_policy(
    defines: list[str],
) -> tuple[float, bool, int] | None:
    """Recognize temporal SSGI/probe lighting with optional quality AO."""
    values = set(defines)
    common = {"PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION", "PS_SSGI"}
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(0, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) > 1 or len(counts) != 1:
        return None
    policy = {f"PS_SSS_COUNT={counts[0]}"}
    if qualities:
        policy.add(qualities[0])
    if values != common | policy:
        return None
    quality = quality_scales[qualities[0]] if qualities else 1.0
    return quality, bool(qualities), counts[0]


def _perspective_ultra_no_ao_policy(defines: list[str]) -> int | None:
    """Recognize perspective ultra history without an SSAO-quality pass."""
    values = set(defines)
    common = {"PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION", "PS_ULTRA"}
    counts = [
        count for count in range(0, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(counts) != 1:
        return None
    expected = common | {f"PS_SSS_COUNT={counts[0]}"}
    return counts[0] if values == expected else None


def _perspective_ultra_cascade_policy(
    defines: list[str],
) -> tuple[float, bool, int] | None:
    """Recognize ultra history with cascade-first counted visibility."""
    values = set(defines)
    common = {
        "PIXEL_SHADER", "PS_CASCADE", "PS_PROBE_GI", "PS_REFLECTION",
        "PS_ULTRA",
    }
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(0, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) > 1 or len(counts) != 1:
        return None
    policy = {f"PS_SSS_COUNT={counts[0]}"}
    if qualities:
        policy.add(qualities[0])
    expected = common | policy
    if values != expected:
        return None
    quality = quality_scales[qualities[0]] if qualities else 1.0
    return quality, bool(qualities), counts[0]


def _ortho_ultra_cascade_policy(
    defines: list[str],
) -> tuple[float, bool, int] | None:
    """Recognize orthographic ultra history with cascade-first visibility."""
    values = set(defines)
    common = {
        "ORTHO", "PIXEL_SHADER", "PS_CASCADE", "PS_PROBE_GI",
        "PS_REFLECTION", "PS_ULTRA",
    }
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(0, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) > 1 or len(counts) != 1:
        return None
    policy = {f"PS_SSS_COUNT={counts[0]}"}
    if qualities:
        policy.add(qualities[0])
    if values != common | policy:
        return None
    quality = quality_scales[qualities[0]] if qualities else 1.0
    return quality, bool(qualities), counts[0]


def _ortho_ultra_policy(
    defines: list[str],
) -> tuple[float, bool, int] | None:
    """Recognize orthographic ultra history with optional AO and SSS."""
    values = set(defines)
    common = {
        "ORTHO", "PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION",
        "PS_ULTRA",
    }
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(0, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) > 1 or len(counts) != 1:
        return None
    policy = {f"PS_SSS_COUNT={counts[0]}"}
    if qualities:
        policy.add(qualities[0])
    if values != common | policy:
        return None
    quality = quality_scales[qualities[0]] if qualities else 1.0
    return quality, bool(qualities), counts[0]


def _perspective_reflection_policy(
    defines: list[str],
) -> tuple[float, bool, int] | None:
    """Recognize reflection-only lighting with optional AO and counted SSS."""
    values = set(defines)
    common = {"PIXEL_SHADER", "PS_REFLECTION"}
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(0, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) > 1 or len(counts) != 1:
        return None
    policy = {f"PS_SSS_COUNT={counts[0]}"}
    if qualities:
        policy.add(qualities[0])
    if values != common | policy:
        return None
    quality = quality_scales[qualities[0]] if qualities else 1.0
    return quality, bool(qualities), counts[0]


def _ortho_probe_policy(
    defines: list[str],
) -> tuple[float, bool, int] | None:
    """Recognize orthographic probe/GI lighting with optional AO and SSS."""
    values = set(defines)
    common = {"ORTHO", "PIXEL_SHADER", "PS_PROBE_GI", "PS_REFLECTION"}
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(0, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) > 1 or len(counts) != 1:
        return None
    policy = {f"PS_SSS_COUNT={counts[0]}"}
    if qualities:
        policy.add(qualities[0])
    if values != common | policy:
        return None
    quality = quality_scales[qualities[0]] if qualities else 1.0
    return quality, bool(qualities), counts[0]


def _ortho_probe_cascade_policy(
    defines: list[str],
) -> tuple[float, bool, int] | None:
    """Recognize orthographic probe lighting with cascade-first outputs."""
    values = set(defines)
    common = {
        "ORTHO", "PIXEL_SHADER", "PS_CASCADE", "PS_PROBE_GI",
        "PS_REFLECTION",
    }
    quality_scales = {
        "PS_SSAO_QUALITY_LOW": 0.5,
        "PS_SSAO_QUALITY_MEDIUM": 1.0,
        "PS_SSAO_QUALITY_HIGH": 2.0,
    }
    qualities = [name for name in quality_scales if name in values]
    counts = [
        count for count in range(0, 5)
        if f"PS_SSS_COUNT={count}" in values
    ]
    if len(qualities) > 1 or len(counts) != 1:
        return None
    policy = {f"PS_SSS_COUNT={counts[0]}"}
    if qualities:
        policy.add(qualities[0])
    if values != common | policy:
        return None
    quality = quality_scales[qualities[0]] if qualities else 1.0
    return quality, bool(qualities), counts[0]


def _lift_probe_cascade_reference(source: str) -> str:
    """Bind the recovered cascade/probe algorithm to this permutation ABI."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    return (
        declarations
        + '\n\n#include "../indirect_light_probe_cascade.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1,\n"
        + "  out float o2 : SV_Target2)\n"
        + "{\n"
        + "  IndirectLightResult result = "
          "EvaluateIndirectLightProbeCascade(w1);\n"
        + "  o0 = result.indirect;\n"
        + "  o1 = result.subsurface;\n"
        + "  o2 = result.cascadeOcclusion;\n"
        + "}\n"
    )


def _lift_cascade_medium_reference(source: str) -> str:
    """Bind medium GTAO, cascade, SSS and reflection phases to the ABI."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    return (
        declarations
        + "\n\n#define INDIRECT_LIGHT_ENABLE_PROBE_GI 0\n"
        + '#include "../indirect_light_probe_cascade.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1,\n"
        + "  out float2 o2 : SV_Target2)\n"
        + "{\n"
        + "  IndirectLightMediumResult result = "
          "EvaluateIndirectLightCascadeMedium(w1);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.subsurface;\n"
        + "  o2 = result.occlusion;\n"
        + "}\n"
    )


def _lift_medium_sss_reference(source: str) -> str:
    """Bind medium horizon AO and the first clustered SSS ray to the ABI."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    return (
        declarations
        + "\n\n#define INDIRECT_LIGHT_ENABLE_PROBE_GI 0\n"
        + "#define INDIRECT_LIGHT_ENABLE_REFLECTION 0\n"
        + "#define INDIRECT_LIGHT_ENABLE_DIFFUSE 0\n"
        + '#include "../indirect_light_probe_cascade.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1,\n"
        + "  out float o2 : SV_Target2)\n"
        + "{\n"
        + "  IndirectLightMediumSssResult result = "
          "EvaluateIndirectLightMediumSss(w1);\n"
        + "  o0 = result.ambientOcclusion;\n"
        + "  o1 = result.subsurface;\n"
        + "  o2 = result.occlusion;\n"
        + "}\n"
    )


def _lift_ortho_medium_ssgi_three_reference(source: str) -> str:
    """Bind the orthographic temporal-SSGI path with three SSS layers."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    return (
        declarations
        + '\n\n#include "../indirect_light_ortho_ssgi.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1,\n"
        + "  out float3 o2 : SV_Target2)\n"
        + "{\n"
        + "  IndirectLightOrthoSsgiResult result = "
          "EvaluateIndirectLightOrthoSsgi(w1, 3u);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.temporalConfidence;\n"
        + "  o2 = result.subsurfaceOcclusion;\n"
        + "}\n"
    )


def _lift_ortho_medium_reflection_two_reference(source: str) -> str:
    """Bind orthographic medium AO, reflection and two SSS layers."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    return (
        declarations
        + "\n\n#define INDIRECT_LIGHT_ENABLE_PROBE_GI 0\n"
        + "#define INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI 0\n"
        + '#include "../indirect_light_ortho_ssgi.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1,\n"
        + "  out float2 o2 : SV_Target2)\n"
        + "{\n"
        + "  IndirectLightOrthoMediumResult result = "
          "EvaluateIndirectLightOrthoMediumReflection(w1, 2u);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.subsurface;\n"
        + "  o2 = result.occlusion.xy;\n"
        + "}\n"
    )


def _lift_medium_probe_four_reference(source: str) -> str:
    """Bind perspective medium AO, probe GI/reflection and four SSS layers."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    return (
        declarations
        + "\n\n#define INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI 0\n"
        + "#define INDIRECT_LIGHT_ENABLE_PROBE_AO 1\n"
        + '#include "../indirect_light_medium_probe.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1,\n"
        + "  out float4 o2 : SV_Target2)\n"
        + "{\n"
        + "  IndirectLightMediumProbeResult result = "
          "EvaluateIndirectLightMediumProbe(w1, 4u);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.subsurface;\n"
        + "  o2 = result.occlusion;\n"
        + "}\n"
    )


def _lift_ortho_high_cascade_probe_reference(source: str) -> str:
    """Bind orthographic high AO, cascade and probe lighting."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    return (
        declarations
        + "\n\n#define INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI 0\n"
        + "#define INDIRECT_LIGHT_ENABLE_PROBE_AO 1\n"
        + '#include "../indirect_light_medium_probe.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1,\n"
        + "  out float o2 : SV_Target2)\n"
        + "{\n"
        + "  IndirectLightMediumProbeResult result = "
          "EvaluateIndirectLightOrthoHighCascadeProbe(w1);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.subsurface;\n"
        + "  o2 = result.occlusion.x;\n"
        + "}\n"
    )


def _lift_ortho_high_ssgi_three_reference(source: str) -> str:
    """Bind the high-quality orthographic temporal-SSGI policy."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    return (
        declarations
        + '\n\n#include "../indirect_light_ortho_ssgi.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1,\n"
        + "  out float3 o2 : SV_Target2)\n"
        + "{\n"
        + "  IndirectLightOrthoSsgiResult result = "
          "EvaluateIndirectLightOrthoSsgi(w1, 3u);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.temporalConfidence;\n"
        + "  o2 = result.subsurfaceOcclusion;\n"
        + "}\n"
    )


def _lift_ortho_ultra_reference(
    source: str,
    quality_radius_scale: float,
) -> str:
    """Bind quality-scaled AO and the ultra temporal/probe reconstruction."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    return (
        declarations
        + '\n\n#include "../indirect_light_ultra.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1)\n"
        + "{\n"
        + "  IndirectLightUltraResult result = "
          f"EvaluateIndirectLightOrthoUltra(w1, {quality_radius_scale:.1f});\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.temporalConfidence;\n"
        + "}\n"
    )


def _lift_ortho_ultra_policy_reference(
    source: str,
    quality_radius_scale: float,
    enable_screen_ao: bool,
    output_count: int,
) -> str:
    """Bind orthographic ultra history to optional AO and counted SSS."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_parameter = ""
    output_assignment = ""
    if output_count > 0:
        output_type = "float" if output_count == 1 else f"float{output_count}"
        swizzle = "xyzw"[:output_count]
        output_parameter = f",\n  out {output_type} o2 : SV_Target2"
        output_assignment = f"  o2 = result.occlusion.{swizzle};\n"
    enable_literal = "true" if enable_screen_ao else "false"
    dummy_probe_ao = ""
    if not enable_screen_ao and "taAo" not in declarations:
        dummy_probe_ao = (
            "\n\n// Parsed by the shared helper; removed by the no-AO policy.\n"
            "Texture2DArray<float> taAo : register(t7);"
        )
    return (
        declarations
        + dummy_probe_ao
        + '\n\n#include "../indirect_light_ultra.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1"
        + output_parameter
        + ")\n"
        + "{\n"
        + "  IndirectLightUltraResult result = "
          "EvaluateIndirectLightOrthoUltraPolicy(\n"
        + f"      w1, {quality_radius_scale:.1f}, {enable_literal}, "
          f"{output_count}u);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.temporalConfidence;\n"
        + output_assignment
        + "}\n"
    )


def _lift_ortho_high_ultra_reference(source: str) -> str:
    return _lift_ortho_ultra_reference(source, 2.0)


def _lift_ortho_medium_ultra_reference(source: str) -> str:
    return _lift_ortho_ultra_reference(source, 1.0)


def _lift_ortho_low_ultra_reference(source: str) -> str:
    return _lift_ortho_ultra_reference(source, 0.5)


def _lift_perspective_cascade_ssgi_reference(
    source: str,
    quality_radius_scale: float,
    enable_screen_ao: bool,
    output_count: int,
) -> str:
    """Bind temporal SSGI to cascade-first counted occlusion outputs."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_parameter = ""
    output_assignment = ""
    if output_count > 0:
        output_type = "float" if output_count == 1 else f"float{output_count}"
        swizzle = "xyzw"[:output_count]
        output_parameter = f",\n  out {output_type} o2 : SV_Target2"
        output_assignment = f"  o2 = result.occlusion.{swizzle};\n"
    enable_literal = "true" if enable_screen_ao else "false"
    dummy_probe_ao = ""
    if not enable_screen_ao and "taAo" not in declarations:
        dummy_probe_ao = (
            "\n\n// Parsed by the shared helper; removed by the no-AO policy.\n"
            "Texture2DArray<float> taAo : register(t7);"
        )
    return (
        declarations
        + dummy_probe_ao
        + '\n\n#include "../indirect_light_ssgi_cascade.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1"
        + output_parameter
        + ")\n"
        + "{\n"
        + "  IndirectLightSsgiCascadeResult result = "
          "EvaluateIndirectLightPerspectiveSsgiCascade(\n"
        + f"      w1, {quality_radius_scale:.1f}, {enable_literal}, "
          f"{output_count}u);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.temporalConfidence;\n"
        + output_assignment
        + "}\n"
    )


def _lift_perspective_probe_quality_reference(
    source: str,
    quality_radius_scale: float,
    enable_screen_ao: bool,
    output_count: int,
) -> str:
    """Bind probe lighting to optional screen AO and counted SSS."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_parameter = ""
    output_assignment = ""
    if output_count > 0:
        output_type = "float" if output_count == 1 else f"float{output_count}"
        swizzle = "xyzw"[:output_count]
        output_parameter = f",\n  out {output_type} o2 : SV_Target2"
        output_assignment = f"  o2 = result.occlusion.{swizzle};\n"
    dummy_ao_resources = ""
    if not enable_screen_ao:
        if "LinearClampClamp_s" not in declarations:
            dummy_ao_resources += (
                "\n// Parsed by the shared AO helper; removed by policy.\n"
                "SamplerState LinearClampClamp_s : register(s6);\n"
            )
        if "tAoDepth" not in declarations:
            dummy_ao_resources += (
                "Texture2D<float> tAoDepth : register(t1);\n"
            )
        if "tScreenNoise" not in declarations:
            dummy_ao_resources += (
                "Texture2D<float> tScreenNoise : register(t4);\n"
            )
    enable_literal = "true" if enable_screen_ao else "false"
    return (
        declarations
        + dummy_ao_resources
        + "\n\n#define INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI 0\n"
        + f"#define INDIRECT_LIGHT_ENABLE_PROBE_AO {int(enable_screen_ao)}\n"
        + '\n#include "../indirect_light_medium_probe.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1"
        + output_parameter
        + ")\n"
        + "{\n"
        + "  IndirectLightMediumProbeResult result = "
          "EvaluateIndirectLightProbePolicy(\n"
        + f"      w1, {quality_radius_scale:.1f}, {enable_literal}, "
          f"{output_count}u);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.subsurface;\n"
        + output_assignment
        + "}\n"
    )


def _lift_perspective_ao_sss_reference(
    source: str,
    quality_radius_scale: float,
    enable_screen_ao: bool,
    output_count: int,
) -> str:
    """Bind quality-scaled horizon AO and counted clustered SSS rays."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_parameter = ""
    output_assignment = ""
    if output_count > 0:
        output_type = "float" if output_count == 1 else f"float{output_count}"
        swizzle = "xyzw"[:output_count]
        output_parameter = f",\n  out {output_type} o2 : SV_Target2"
        output_assignment = f"  o2 = result.occlusion.{swizzle};\n"
    dummy_ao_resources = ""
    if not enable_screen_ao:
        if "CB_PERFRAME" not in declarations \
                and "indirect_light_perframe_abi.hlsl" not in declarations:
            dummy_ao_resources += (
                '\n#include "../indirect_light_perframe_abi.hlsl"\n'
            )
        if "LinearClampClamp_s" not in declarations:
            dummy_ao_resources += (
                "SamplerState LinearClampClamp_s : register(s6);\n"
            )
        for declaration in (
            "Texture2D<float2> tNormal : register(t0);",
            "Texture2D<float> tAoDepth : register(t1);",
            "Texture2D<float4> tMaterial : register(t3);",
            "Texture2D<float> tScreenNoise : register(t4);",
        ):
            name = declaration.split()[1].split(":")[0]
            if name not in declarations:
                dummy_ao_resources += declaration + "\n"
    enable_literal = "true" if enable_screen_ao else "false"
    return (
        declarations
        + dummy_ao_resources
        + f"\n\n#define INDIRECT_LIGHT_AO_SSS_COUNT {output_count}\n"
        + '#include "../indirect_light_ao_sss.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1"
        + output_parameter
        + ")\n"
        + "{\n"
        + "  IndirectLightAoSssResult result = "
          "EvaluateIndirectLightPerspectiveAoSssPolicy(\n"
        + f"      w1, {quality_radius_scale:.1f}, {enable_literal});\n"
        + "  o0 = result.ambientOcclusion;\n"
        + "  o1 = result.subsurface;\n"
        + output_assignment
        + "}\n"
    )


def _lift_perspective_cascade_only_reference(
    source: str,
    quality_radius_scale: float,
    enable_screen_ao: bool,
    output_count: int,
) -> str:
    """Bind cascade visibility and the requested trailing SSS layers."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_type = "float" if output_count == 1 else f"float{output_count}"
    swizzle = "xyzw"[:output_count]
    enable_literal = "true" if enable_screen_ao else "false"
    return (
        declarations
        + f"\n\n#define INDIRECT_LIGHT_CASCADE_OUTPUT_COUNT {output_count}\n"
        + '#include "../indirect_light_cascade.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1,\n"
        + f"  out {output_type} o2 : SV_Target2)\n"
        + "{\n"
        + "  IndirectLightCascadeResult result = "
          "EvaluateIndirectLightCascadeVisibilityPolicy(\n"
        + f"      w1, {quality_radius_scale:.1f}, {enable_literal});\n"
        + "  o0 = result.indirect;\n"
        + "  o1 = result.subsurface;\n"
        + f"  o2 = result.visibility.{swizzle};\n"
        + "}\n"
    )


def _lift_perspective_cascade_reflection_reference(
    source: str,
    quality_radius_scale: float,
    enable_screen_ao: bool,
    output_count: int,
) -> str:
    """Bind reflection lighting to cascade-first counted visibility."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_type = "float" if output_count == 1 else f"float{output_count}"
    swizzle = "xyzw"[:output_count]
    enable_literal = "true" if enable_screen_ao else "false"
    return (
        declarations
        + "\n\n#define INDIRECT_LIGHT_ENABLE_PROBE_GI 0\n"
        + '#include "../indirect_light_probe_cascade.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1,\n"
        + f"  out {output_type} o2 : SV_Target2)\n"
        + "{\n"
        + "  IndirectLightMediumResult result = "
          "EvaluateIndirectLightCascadeReflection(\n"
        + f"      w1, {quality_radius_scale:.1f}, {enable_literal}, "
          f"{output_count}u);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.subsurface;\n"
        + f"  o2 = result.occlusion.{swizzle};\n"
        + "}\n"
    )


def _lift_ortho_ssgi_quality_reference(
    source: str,
    quality_radius_scale: float,
    enable_screen_ao: bool,
    output_count: int,
) -> str:
    """Bind orthographic temporal SSGI to quality and counted SSS policy."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_parameter = ""
    output_assignment = ""
    if output_count > 0:
        output_type = "float" if output_count == 1 else f"float{output_count}"
        swizzle = "xyzw"[:output_count]
        output_parameter = f",\n  out {output_type} o2 : SV_Target2"
        output_assignment = (
            f"  o2 = result.subsurfaceOcclusion.{swizzle};\n"
        )
    enable_literal = "true" if enable_screen_ao else "false"
    dummy_probe_ao = ""
    if not enable_screen_ao and "taAo" not in declarations:
        dummy_probe_ao = (
            "\n\n// Parsed by the shared helper; removed by the no-AO policy.\n"
            "Texture2DArray<float> taAo : register(t7);"
        )
    return (
        declarations
        + dummy_probe_ao
        + '\n\n#include "../indirect_light_ortho_ssgi.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1"
        + output_parameter
        + ")\n"
        + "{\n"
        + "  IndirectLightOrthoSsgiResult result = "
          "EvaluateIndirectLightOrthoSsgiPolicy(\n"
        + f"      w1, {output_count}u, {quality_radius_scale:.1f}, "
          f"{enable_literal});\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.temporalConfidence;\n"
        + output_assignment
        + "}\n"
    )


def _lift_ortho_ao_sss_reference(
    source: str,
    quality_radius_scale: float,
    output_count: int,
) -> str:
    """Bind orthographic horizon AO to optional counted SSS output."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_parameter = ""
    output_assignment = ""
    dummy_point_sampler = ""
    if output_count > 0:
        output_type = "float" if output_count == 1 else f"float{output_count}"
        swizzle = "xyzw"[:output_count]
        output_parameter = f",\n  out {output_type} o2 : SV_Target2"
        output_assignment = f"  o2 = result.occlusion.{swizzle};\n"
    else:
        dummy_point_sampler = (
            "\n\n// Parsed by the shared SSS helpers; removed at zero layers.\n"
            '#include "../indirect_light_cluster_abi.hlsl"\n'
            "SamplerState PointClampClamp_s : register(s1);\n"
            "StructuredBuffer<uint> sbVoxelLightIds : register(t21);"
        )
    return (
        declarations
        + dummy_point_sampler
        + '\n\n#include "../indirect_light_ortho_ao_sss.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1"
        + output_parameter
        + ")\n"
        + "{\n"
        + "  IndirectLightOrthoAoSssResult result = "
          "EvaluateIndirectLightOrthoAoSss(\n"
        + f"      w1, {quality_radius_scale:.1f}, {output_count}u);\n"
        + "  o0 = result.ambientOcclusion;\n"
        + "  o1 = result.subsurface;\n"
        + output_assignment
        + "}\n"
    )


def _lift_ortho_cascade_reference(
    source: str,
    quality_radius_scale: float,
    output_count: int,
) -> str:
    """Bind orthographic horizon AO to cascade-first counted visibility."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_type = "float" if output_count == 1 else f"float{output_count}"
    swizzle = "xyzw"[:output_count]
    dummy_cluster_resources = ""
    if output_count == 1:
        dummy_cluster_resources = (
            '\n\n// Parsed by the shared SSS helper; optimized from count one.\n'
            '#include "../indirect_light_cluster_abi.hlsl"\n'
            "StructuredBuffer<uint> sbVoxelLightIds : register(t21);"
        )
    return (
        declarations
        + dummy_cluster_resources
        + f"\n\n#define INDIRECT_LIGHT_CASCADE_COMPILED_COUNT {output_count}\n"
        + '\n\n#include "../indirect_light_ortho_cascade.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1,\n"
        + f"  out {output_type} o2 : SV_Target2)\n"
        + "{\n"
        + "  IndirectLightOrthoCascadeResult result = "
          "EvaluateIndirectLightOrthoCascade(\n"
        + f"      w1, {quality_radius_scale:.1f}, {output_count}u);\n"
        + "  o0 = result.ambientOcclusion;\n"
        + "  o1 = result.subsurface;\n"
        + f"  o2 = result.visibility.{swizzle};\n"
        + "}\n"
    )


def _lift_ortho_reflection_reference(
    source: str,
    quality_radius_scale: float,
    enable_screen_ao: bool,
    output_count: int,
) -> str:
    """Bind orthographic reflection to optional AO and counted SSS."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_parameter = ""
    output_assignment = ""
    if output_count > 0:
        output_type = "float" if output_count == 1 else f"float{output_count}"
        swizzle = "xyzw"[:output_count]
        output_parameter = f",\n  out {output_type} o2 : SV_Target2"
        output_assignment = f"  o2 = result.occlusion.{swizzle};\n"
    dummy_screen_noise = ""
    if not enable_screen_ao and "tScreenNoise" not in declarations:
        dummy_screen_noise = (
            "\n// Parsed by the shared AO helper; removed by the no-AO policy.\n"
            "Texture2D<float> tScreenNoise : register(t4);\n"
        )
    if "tAoDepth" not in declarations:
        dummy_screen_noise += (
            "SamplerState LinearClampClamp_s : register(s6);\n"
            "Texture2D<float> tAoDepth : register(t1);\n"
        )
    enable_literal = "true" if enable_screen_ao else "false"
    return (
        declarations
        + "\n\n#define INDIRECT_LIGHT_ENABLE_PROBE_GI 0\n"
        + "#define INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI 0\n"
        + dummy_screen_noise
        + '#include "../indirect_light_ortho_ssgi.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1"
        + output_parameter
        + ")\n"
        + "{\n"
        + "  IndirectLightOrthoMediumResult result = "
          "EvaluateIndirectLightOrthoReflectionPolicy(\n"
        + f"      w1, {quality_radius_scale:.1f}, {enable_literal}, "
          f"{output_count}u);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.subsurface;\n"
        + output_assignment
        + "}\n"
    )


def _lift_ortho_cascade_reflection_reference(
    source: str,
    quality_radius_scale: float,
    enable_screen_ao: bool,
    output_count: int,
) -> str:
    """Bind orthographic reflection to cascade-first counted visibility."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_type = "float" if output_count == 1 else f"float{output_count}"
    swizzle = "xyzw"[:output_count]
    dummy_ao_resources = ""
    if not enable_screen_ao:
        if "LinearClampClamp_s" not in declarations:
            dummy_ao_resources += (
                "\n// Parsed by the shared AO helper; removed by policy.\n"
                "SamplerState LinearClampClamp_s : register(s6);\n"
            )
        if "tAoDepth" not in declarations:
            dummy_ao_resources += "Texture2D<float> tAoDepth : register(t1);\n"
        if "tScreenNoise" not in declarations:
            dummy_ao_resources += "Texture2D<float> tScreenNoise : register(t4);\n"
    enable_literal = "true" if enable_screen_ao else "false"
    return (
        declarations
        + dummy_ao_resources
        + '\n\n#include "../indirect_light_ortho_reflection_cascade.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1,\n"
        + f"  out {output_type} o2 : SV_Target2)\n"
        + "{\n"
        + "  IndirectLightOrthoMediumResult result = "
          "EvaluateIndirectLightOrthoReflectionCascadePolicy(\n"
        + f"      w1, {quality_radius_scale:.1f}, {enable_literal}, "
          f"{output_count}u);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.subsurface;\n"
        + f"  o2 = result.occlusion.{swizzle};\n"
        + "}\n"
    )


def _lift_ortho_cascade_ssgi_reference(
    source: str,
    quality_radius_scale: float,
    enable_screen_ao: bool,
    output_count: int,
) -> str:
    """Bind orthographic temporal SSGI to cascade-first visibility."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_parameter = ""
    output_assignment = ""
    if output_count > 0:
        output_type = "float" if output_count == 1 else f"float{output_count}"
        swizzle = "xyzw"[:output_count]
        output_parameter = f",\n  out {output_type} o2 : SV_Target2"
        output_assignment = f"  o2 = result.occlusion.{swizzle};\n"
    enable_literal = "true" if enable_screen_ao else "false"
    dummy_probe_ao = ""
    if not enable_screen_ao and "taAo" not in declarations:
        dummy_probe_ao = (
            "\n\n// Parsed by the shared helper; removed by the no-AO policy.\n"
            "Texture2DArray<float> taAo : register(t7);"
        )
    return (
        declarations
        + dummy_probe_ao
        + '\n\n#include "../indirect_light_ortho_ssgi_cascade.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1"
        + output_parameter
        + ")\n"
        + "{\n"
        + "  IndirectLightSsgiCascadeResult result = "
          "EvaluateIndirectLightOrthoSsgiCascade(\n"
        + f"      w1, {quality_radius_scale:.1f}, {enable_literal}, "
          f"{output_count}u);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.temporalConfidence;\n"
        + output_assignment
        + "}\n"
    )


def _lift_perspective_probe_cascade_reference(
    source: str,
    quality_radius_scale: float,
    enable_screen_ao: bool,
    output_count: int,
) -> str:
    """Bind probe/GI lighting to optional cascade and trailing SSS outputs."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_parameter = ""
    output_assignment = ""
    if output_count > 0:
        output_type = "float" if output_count == 1 else f"float{output_count}"
        swizzle = "xyzw"[:output_count]
        output_parameter = f",\n  out {output_type} o2 : SV_Target2"
        output_assignment = f"  o2 = result.visibility.{swizzle};\n"
    dummy_ao_resources = ""
    if output_count == 0:
        if "LinearClampClamp_s" not in declarations:
            dummy_ao_resources += (
                "\n// Parsed by unreachable trace helpers at count zero.\n"
                "SamplerState LinearClampClamp_s : register(s6);\n"
            )
        if "tAoDepth" not in declarations:
            dummy_ao_resources += "Texture2D<float> tAoDepth : register(t1);\n"
        if "tScreenNoise" not in declarations:
            dummy_ao_resources += "Texture2D<float> tScreenNoise : register(t4);\n"
    enable_literal = "true" if enable_screen_ao else "false"
    return (
        declarations
        + dummy_ao_resources
        + f"\n\n#define INDIRECT_LIGHT_PROBE_CASCADE_COUNT {output_count}\n"
        + "#define INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI 0\n"
        + f"#define INDIRECT_LIGHT_ENABLE_PROBE_AO {int(enable_screen_ao)}\n"
        + '#include "../indirect_light_probe_cascade_counted.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1"
        + output_parameter
        + ")\n"
        + "{\n"
        + "  IndirectLightProbeCascadeCountedResult result = "
          "EvaluateIndirectLightCountedProbeCascadePolicy(\n"
        + f"      w1, {quality_radius_scale:.1f}, {enable_literal});\n"
        + "  o0 = result.indirect;\n"
        + "  o1 = result.subsurface;\n"
        + output_assignment
        + "}\n"
    )


def _lift_perspective_ultra_quality_reference(
    source: str,
    quality_radius_scale: float,
    output_count: int,
) -> str:
    """Bind perspective ultra reconstruction to quality and SSS count."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_parameter = ""
    output_assignment = ""
    if output_count > 0:
        output_type = "float" if output_count == 1 else f"float{output_count}"
        swizzle = "xyzw"[:output_count]
        output_parameter = f",\n  out {output_type} o2 : SV_Target2"
        output_assignment = f"  o2 = result.occlusion.{swizzle};\n"
    return (
        declarations
        + '\n\n#include "../indirect_light_ultra.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1"
        + output_parameter
        + ")\n"
        + "{\n"
        + "  IndirectLightPerspectiveUltraResult result = "
          "EvaluateIndirectLightPerspectiveUltra(\n"
        + f"      w1, {quality_radius_scale:.1f}, {output_count}u);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.temporalConfidence;\n"
        + output_assignment
        + "}\n"
    )


def _lift_perspective_ssgi_probe_reference(
    source: str,
    quality_radius_scale: float,
    enable_screen_ao: bool,
    output_count: int,
) -> str:
    """Bind temporal SSGI/probe composition to AO and SSS policy."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_parameter = ""
    output_assignment = ""
    if output_count > 0:
        output_type = "float" if output_count == 1 else f"float{output_count}"
        swizzle = "xyzw"[:output_count]
        output_parameter = f",\n  out {output_type} o2 : SV_Target2"
        output_assignment = f"  o2 = result.occlusion.{swizzle};\n"
    dummy_probe_ao = ""
    if not enable_screen_ao and "taAo" not in declarations:
        dummy_probe_ao = (
            "\n\n// Parsed by the shared SSGI helper; removed by no-AO policy.\n"
            "Texture2DArray<float> taAo : register(t7);"
        )
    enable_literal = "true" if enable_screen_ao else "false"
    return (
        declarations
        + dummy_probe_ao
        + '\n\n#include "../indirect_light_ssgi_probe.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1"
        + output_parameter
        + ")\n"
        + "{\n"
        + "  IndirectLightSsgiProbeResult result = "
          "EvaluateIndirectLightSsgiProbePolicy(\n"
        + f"      w1, {quality_radius_scale:.1f}, {enable_literal}, "
          f"{output_count}u);\n"
        + "  o0 = result.indirect;\n"
        + "  o1 = result.temporalConfidence;\n"
        + output_assignment
        + "}\n"
    )


def _lift_perspective_ultra_no_ao_reference(
    source: str,
    output_count: int,
) -> str:
    """Bind ultra history/probe composition without an AO pass."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_parameter = ""
    output_assignment = ""
    if output_count > 0:
        output_type = "float" if output_count == 1 else f"float{output_count}"
        swizzle = "xyzw"[:output_count]
        output_parameter = f",\n  out {output_type} o2 : SV_Target2"
        output_assignment = f"  o2 = result.occlusion.{swizzle};\n"
    return (
        declarations
        + "\n\n// Parsed by the shared ultra helper; unreachable for no-AO policy.\n"
        + "Texture2DArray<float> taAo : register(t7);\n"
        + '#include "../indirect_light_ultra.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1"
        + output_parameter
        + ")\n"
        + "{\n"
        + "  IndirectLightPerspectiveUltraResult result = "
          "EvaluateIndirectLightPerspectiveUltraNoAo(\n"
        + f"      w1, {output_count}u);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.temporalConfidence;\n"
        + output_assignment
        + "}\n"
    )


def _lift_perspective_ultra_cascade_reference(
    source: str,
    quality_radius_scale: float,
    enable_screen_ao: bool,
    output_count: int,
) -> str:
    """Bind ultra history to cascade-first counted visibility."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_parameter = ""
    output_assignment = ""
    if output_count > 0:
        output_type = "float" if output_count == 1 else f"float{output_count}"
        swizzle = "xyzw"[:output_count]
        output_parameter = f",\n  out {output_type} o2 : SV_Target2"
        output_assignment = f"  o2 = result.occlusion.{swizzle};\n"
    dummy_probe_ao = ""
    if not enable_screen_ao and "taAo" not in declarations:
        dummy_probe_ao = (
            "\n\n// Parsed by the shared ultra helper; removed by no-AO policy.\n"
            "Texture2DArray<float> taAo : register(t7);"
        )
    enable_literal = "true" if enable_screen_ao else "false"
    return (
        declarations
        + dummy_probe_ao
        + '\n\n#include "../indirect_light_ultra.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1"
        + output_parameter
        + ")\n"
        + "{\n"
        + "  IndirectLightPerspectiveUltraResult result = "
          "EvaluateIndirectLightPerspectiveUltraCascadePolicy(\n"
        + f"      w1, {quality_radius_scale:.1f}, {enable_literal}, "
          f"{output_count}u);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.temporalConfidence;\n"
        + output_assignment
        + "}\n"
    )


def _lift_ortho_ultra_cascade_reference(
    source: str,
    quality_radius_scale: float,
    enable_screen_ao: bool,
    output_count: int,
) -> str:
    """Bind orthographic ultra history to cascade-first visibility."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_parameter = ""
    output_assignment = ""
    if output_count > 0:
        output_type = "float" if output_count == 1 else f"float{output_count}"
        swizzle = "xyzw"[:output_count]
        output_parameter = f",\n  out {output_type} o2 : SV_Target2"
        output_assignment = f"  o2 = result.occlusion.{swizzle};\n"
    dummy_probe_ao = ""
    if not enable_screen_ao and "taAo" not in declarations:
        dummy_probe_ao = (
            "\n\n// Parsed by the shared ultra helper; removed by no-AO policy.\n"
            "Texture2DArray<float> taAo : register(t7);"
        )
    enable_literal = "true" if enable_screen_ao else "false"
    return (
        declarations
        + dummy_probe_ao
        + '\n\n#include "../indirect_light_ultra.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1"
        + output_parameter
        + ")\n"
        + "{\n"
        + "  IndirectLightPerspectiveUltraResult result = "
          "EvaluateIndirectLightOrthoUltraCascadePolicy(\n"
        + f"      w1, {quality_radius_scale:.1f}, {enable_literal}, "
          f"{output_count}u);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.temporalConfidence;\n"
        + output_assignment
        + "}\n"
    )


def _lift_perspective_reflection_reference(
    source: str,
    quality_radius_scale: float,
    enable_screen_ao: bool,
    output_count: int,
) -> str:
    """Bind reflection-only lighting to optional AO and SSS outputs."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_parameter = ""
    output_assignment = ""
    if output_count > 0:
        output_type = "float" if output_count == 1 else f"float{output_count}"
        swizzle = "xyzw"[:output_count]
        output_parameter = f",\n  out {output_type} o2 : SV_Target2"
        output_assignment = f"  o2 = result.occlusion.{swizzle};\n"
    parse_only = ""
    if "tAoDepth" not in declarations:
        parse_only += "\nTexture2D<float> tAoDepth : register(t1);"
    if "tScreenNoise" not in declarations:
        parse_only += "\nTexture2D<float> tScreenNoise : register(t4);"
    if "LinearClampClamp_s" not in declarations:
        parse_only += "\nSamplerState LinearClampClamp_s : register(s6);"
    if parse_only:
        parse_only = (
            "\n\n// Parsed by inactive AO/SSS helpers and optimized away."
            + parse_only
        )
    enable_literal = "true" if enable_screen_ao else "false"
    return (
        declarations
        + parse_only
        + '\n\n#include "../indirect_light_reflection.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1"
        + output_parameter
        + ")\n"
        + "{\n"
        + "  IndirectLightReflectionResult result = "
          "EvaluateIndirectLightReflectionPolicy(\n"
        + f"      w1, {quality_radius_scale:.1f}, {enable_literal}, "
          f"{output_count}u);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.subsurface;\n"
        + output_assignment
        + "}\n"
    )


def _lift_ortho_probe_reference(
    source: str,
    quality_radius_scale: float,
    enable_screen_ao: bool,
    output_count: int,
) -> str:
    """Bind orthographic probe/GI lighting to optional AO and SSS."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_parameter = ""
    output_assignment = ""
    if output_count > 0:
        output_type = "float" if output_count == 1 else f"float{output_count}"
        swizzle = "xyzw"[:output_count]
        output_parameter = f",\n  out {output_type} o2 : SV_Target2"
        output_assignment = f"  o2 = result.occlusion.{swizzle};\n"
    parse_only = ""
    if "tAoDepth" not in declarations:
        parse_only += "\nTexture2D<float> tAoDepth : register(t1);"
    if "tScreenNoise" not in declarations:
        parse_only += "\nTexture2D<float> tScreenNoise : register(t4);"
    if "LinearClampClamp_s" not in declarations:
        parse_only += "\nSamplerState LinearClampClamp_s : register(s6);"
    if parse_only:
        parse_only = (
            "\n\n// Parsed by inactive AO/SSS helpers and optimized away."
            + parse_only
        )
    enable_literal = "true" if enable_screen_ao else "false"
    probe_ao_macro = "1" if enable_screen_ao else "0"
    return (
        declarations
        + parse_only
        + "\n\n#define INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI 0\n"
        + f"#define INDIRECT_LIGHT_ENABLE_PROBE_AO {probe_ao_macro}\n"
        + '#include "../indirect_light_medium_probe.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1"
        + output_parameter
        + ")\n"
        + "{\n"
        + "  IndirectLightMediumProbeResult result = "
          "EvaluateIndirectLightOrthoProbePolicy(\n"
        + f"      w1, {quality_radius_scale:.1f}, {enable_literal}, "
          f"{output_count}u);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.subsurface;\n"
        + output_assignment
        + "}\n"
    )


def _lift_ortho_probe_cascade_reference(
    source: str,
    quality_radius_scale: float,
    enable_screen_ao: bool,
    output_count: int,
) -> str:
    """Bind orthographic probe lighting to cascade-first visibility."""
    marker = source.index("// 3Dmigoto declarations")
    declarations = source[:marker].rstrip()
    output_parameter = ""
    output_assignment = ""
    if output_count > 0:
        output_type = "float" if output_count == 1 else f"float{output_count}"
        swizzle = "xyzw"[:output_count]
        output_parameter = f",\n  out {output_type} o2 : SV_Target2"
        output_assignment = f"  o2 = result.occlusion.{swizzle};\n"
    dummy_ao_resources = ""
    if not enable_screen_ao:
        if "LinearClampClamp_s" not in declarations:
            dummy_ao_resources += (
                "\n// Parsed by the shared AO helper; removed by policy.\n"
                "SamplerState LinearClampClamp_s : register(s6);\n"
            )
        if "tAoDepth" not in declarations:
            dummy_ao_resources += "Texture2D<float> tAoDepth : register(t1);\n"
        if "tScreenNoise" not in declarations:
            dummy_ao_resources += "Texture2D<float> tScreenNoise : register(t4);\n"
    enable_literal = "true" if enable_screen_ao else "false"
    return (
        declarations
        + dummy_ao_resources
        + "\n\n#define INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI 0\n"
        + f"#define INDIRECT_LIGHT_ENABLE_PROBE_AO {int(enable_screen_ao)}\n"
        + '\n#include "../indirect_light_medium_probe.hlsl"\n\n'
        + "void mainPS(\n"
        + "  float4 v0 : SV_Position0,\n"
        + "  float2 v1 : UV0,\n"
        + "  float2 w1 : UNSCALED_UV0,\n"
        + "  out float4 o0 : SV_Target0,\n"
        + "  out float o1 : SV_Target1"
        + output_parameter
        + ")\n"
        + "{\n"
        + "  IndirectLightMediumProbeResult result = "
          "EvaluateIndirectLightOrthoProbeCascadePolicy(\n"
        + f"      w1, {quality_radius_scale:.1f}, {enable_literal}, "
          f"{output_count}u);\n"
        + "  o0 = result.indirectAo;\n"
        + "  o1 = result.subsurface;\n"
        + output_assignment
        + "}\n"
    )


def _execution(blob: bytes) -> dict[str, Any]:
    abi = ShaderReflector().abi(blob)
    textures = [resource for resource in abi["resources"] if resource["type"] == 2]
    samplers = [resource for resource in abi["resources"] if resource["type"] == 3]
    buffers = [resource for resource in abi["resources"] if resource["type"] == 5]
    outputs = sorted(abi["outputs"], key=lambda output: output["index"])
    profiles = {
        0: "index",
        5: "projection",
        6: "cluster",
        9: "hdr",
        11: "reflection",
        12: "index",
    }
    return {
        "kind": "fullscreen_indirect_light",
        "vertex_harness": "fullscreen_uv",
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
                "profile": "zero",
            }
            for resource in buffers
        ],
        "samplers": [
            {
                "slot": resource["bind_point"],
                "filter": "point" if resource["bind_point"] == 1 else "linear",
            }
            for resource in samplers
        ],
        "constant_buffers": [
            {"slot": buffer["bind_point"], "profile": profiles[buffer["bind_point"]]}
            for buffer in abi["constant_buffers"]
            if buffer["bind_point"] >= 0
        ],
        "output": "color",
        "output_components": 4,
        "output_targets": len(outputs),
        "output_target_components": [
            max(1, output["mask"].bit_count()) for output in outputs
        ],
        "absolute_tolerance": 1.0e-7,
    }


def _emit_variant_snippets(
    staging: Path,
    variants: dict[str, str],
) -> dict[str, str]:
    """Emit every indirect-light permutation as an independent source file."""
    snippet_root = staging / "semantic" / "include" / "indirect_light"
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
        bodies[selector] = f'#include "include/indirect_light/{filename}"\n'
    return bodies


def apply_indirect_light_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [record for record in records if record["source_name"] == "indirect_light"]
    if len(shaders) != 375 or any(shader["stage"] != "pixel" for shader in shaders):
        return None
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    variants = module_variants(
        (staging / "hlsl" / "indirect_light.hlsl").read_text(encoding="utf-8"),
        definitions,
    )
    for cbuffer_name, filename in INDIRECT_LIGHT_ABI.items():
        ensure_recovered_cbuffer_include(
            staging, "indirect_light", cbuffer_name, filename
        )
    helper_path = (
        staging / "semantic" / "include" / "indirect_light_probe_cascade.hlsl"
    )
    helper_path.write_text(
        asset("indirect_light_probe_cascade.hlsl"),
        encoding="utf-8",
        newline="\n",
    )
    ortho_ssgi_path = (
        staging / "semantic" / "include" / "indirect_light_ortho_ssgi.hlsl"
    )
    ortho_ssgi_path.write_text(
        asset("indirect_light_ortho_ssgi.hlsl"),
        encoding="utf-8",
        newline="\n",
    )
    medium_probe_path = (
        staging / "semantic" / "include" / "indirect_light_medium_probe.hlsl"
    )
    medium_probe_path.write_text(
        asset("indirect_light_medium_probe.hlsl"),
        encoding="utf-8",
        newline="\n",
    )
    ultra_path = (
        staging / "semantic" / "include" / "indirect_light_ultra.hlsl"
    )
    ultra_path.write_text(
        asset("indirect_light_ultra.hlsl"),
        encoding="utf-8",
        newline="\n",
    )
    ssgi_cascade_path = (
        staging / "semantic" / "include" / "indirect_light_ssgi_cascade.hlsl"
    )
    ssgi_cascade_path.write_text(
        asset("indirect_light_ssgi_cascade.hlsl"),
        encoding="utf-8",
        newline="\n",
    )
    ortho_ssgi_cascade_path = (
        staging / "semantic" / "include"
        / "indirect_light_ortho_ssgi_cascade.hlsl"
    )
    ortho_ssgi_cascade_path.write_text(
        asset("indirect_light_ortho_ssgi_cascade.hlsl"),
        encoding="utf-8",
        newline="\n",
    )
    ortho_ao_sss_path = (
        staging / "semantic" / "include" / "indirect_light_ortho_ao_sss.hlsl"
    )
    ortho_ao_sss_path.write_text(
        asset("indirect_light_ortho_ao_sss.hlsl"),
        encoding="utf-8",
        newline="\n",
    )
    ao_sss_path = (
        staging / "semantic" / "include" / "indirect_light_ao_sss.hlsl"
    )
    ao_sss_path.write_text(
        asset("indirect_light_ao_sss.hlsl"),
        encoding="utf-8",
        newline="\n",
    )
    cascade_path = (
        staging / "semantic" / "include" / "indirect_light_cascade.hlsl"
    )
    cascade_path.write_text(
        asset("indirect_light_cascade.hlsl"),
        encoding="utf-8",
        newline="\n",
    )
    cascade_visibility_path = (
        staging / "semantic" / "include"
        / "indirect_light_cascade_visibility.hlsl"
    )
    cascade_visibility_path.write_text(
        asset("indirect_light_cascade_visibility.hlsl"),
        encoding="utf-8",
        newline="\n",
    )
    ortho_cascade_path = (
        staging / "semantic" / "include"
        / "indirect_light_ortho_cascade.hlsl"
    )
    ortho_cascade_path.write_text(
        asset("indirect_light_ortho_cascade.hlsl"),
        encoding="utf-8",
        newline="\n",
    )
    ortho_reflection_cascade_path = (
        staging / "semantic" / "include"
        / "indirect_light_ortho_reflection_cascade.hlsl"
    )
    ortho_reflection_cascade_path.write_text(
        asset("indirect_light_ortho_reflection_cascade.hlsl"),
        encoding="utf-8",
        newline="\n",
    )
    probe_cascade_counted_path = (
        staging / "semantic" / "include"
        / "indirect_light_probe_cascade_counted.hlsl"
    )
    probe_cascade_counted_path.write_text(
        asset("indirect_light_probe_cascade_counted.hlsl"),
        encoding="utf-8",
        newline="\n",
    )
    ssgi_probe_path = (
        staging / "semantic" / "include" / "indirect_light_ssgi_probe.hlsl"
    )
    ssgi_probe_path.write_text(
        asset("indirect_light_ssgi_probe.hlsl"),
        encoding="utf-8",
        newline="\n",
    )
    reflection_path = (
        staging / "semantic" / "include" / "indirect_light_reflection.hlsl"
    )
    reflection_path.write_text(
        asset("indirect_light_reflection.hlsl"),
        encoding="utf-8",
        newline="\n",
    )
    reflector = ShaderReflector()
    by_selector = {shader["selector"]: shader for shader in shaders}
    for selector, source in variants.items():
        source = source.replace("w1.xyzw", "w1.xyxy")
        source = source.replace("w1.yz", "w1.xy")
        shader = by_selector[selector]
        resources = reflector.abi(blobs[shader["bundle_index"]])["resources"]
        texture_declarations = {
            int(slot): (name, "Array" in kind)
            for kind, name, slot in re.findall(
                r"(Texture2D(?:Array)?)<[^>]+>\s+(\w+)\s*:\s*register\(t(\d+)\)",
                source,
            )
        }
        sampler_declarations = {
            int(slot): name
            for name, slot in re.findall(
                r"SamplerState\s+(\w+)\s*:\s*register\(s(\d+)\)", source
            )
        }
        sentinel = []
        for resource in resources:
            slot = resource["bind_point"]
            if resource["type"] == 2 and slot in texture_declarations:
                name, is_array = texture_declarations[slot]
                coordinate = "int4(0, 0, 0, 0)" if is_array else "int3(0, 0, 0)"
                sentinel.append(f"o0.x += {name}.Load({coordinate}).x;")
            elif resource["type"] == 5:
                sentinel.append("o0.x += (float)sbVoxelLightIds[0];")
        sample_texture = next(iter(texture_declarations.values()), None)
        if sample_texture:
            texture_name, is_array = sample_texture
            coordinate = "float3(w1.xy, 0)" if is_array else "w1.xy"
            for resource in resources:
                slot = resource["bind_point"]
                if resource["type"] == 3 and slot in sampler_declarations:
                    sentinel.append(
                        f"o0.x += {texture_name}.Sample("
                        f"{sampler_declarations[slot]}, {coordinate}).x;"
                    )
        if sentinel:
            insertion = source.rfind("  return;")
            sanitize = (
                "  if ((asuint(o0.w) & 0x7f800000u) == 0x7f800000u) "
                "o0.w = 1.0;\n"
            )
            source = (
                source[:insertion]
                + sanitize
                + "  if (cb_vNearFarViewCorner.x == -3.402823e+38) {\n    "
                + "\n    ".join(sentinel)
                + "\n  }\n"
                + source[insertion:]
            )
        source = rename_register_state(
            source, REGISTER_NAMES,
            note="Probe, ray, and subsurface accumulation retain DXBC order.",
        )
        source = _lift_indirect_light_abi(source)
        perspective_cascade_ssgi = _perspective_cascade_ssgi_policy(
            definitions[selector]
        )
        perspective_probe_quality = _perspective_probe_quality_policy(
            definitions[selector]
        )
        perspective_ao_sss = _perspective_ao_sss_policy(
            definitions[selector]
        )
        perspective_cascade_only = _perspective_cascade_only_policy(
            definitions[selector]
        )
        ortho_ssgi_quality = _ortho_ssgi_quality_policy(
            definitions[selector]
        )
        perspective_probe_cascade = _perspective_probe_cascade_policy(
            definitions[selector]
        )
        perspective_ultra_quality = _perspective_ultra_quality_policy(
            definitions[selector]
        )
        perspective_ssgi_probe = _perspective_ssgi_probe_policy(
            definitions[selector]
        )
        perspective_ultra_no_ao = _perspective_ultra_no_ao_policy(
            definitions[selector]
        )
        perspective_ultra_cascade = _perspective_ultra_cascade_policy(
            definitions[selector]
        )
        ortho_ultra_cascade = _ortho_ultra_cascade_policy(
            definitions[selector]
        )
        ortho_ultra = _ortho_ultra_policy(definitions[selector])
        perspective_reflection = _perspective_reflection_policy(
            definitions[selector]
        )
        ortho_probe = _ortho_probe_policy(definitions[selector])
        ortho_probe_cascade = _ortho_probe_cascade_policy(
            definitions[selector]
        )
        ortho_cascade_ssgi = _ortho_cascade_ssgi_policy(
            definitions[selector]
        )
        perspective_cascade_reflection = (
            _perspective_cascade_reflection_policy(definitions[selector])
        )
        ortho_ao_sss = _ortho_ao_sss_policy(definitions[selector])
        ortho_cascade = _ortho_cascade_policy(definitions[selector])
        ortho_reflection = _ortho_reflection_policy(definitions[selector])
        ortho_cascade_reflection = _ortho_cascade_reflection_policy(
            definitions[selector]
        )
        if ortho_probe_cascade is not None:
            source = _lift_ortho_probe_cascade_reference(
                source, *ortho_probe_cascade
            )
        elif ortho_probe is not None:
            source = _lift_ortho_probe_reference(source, *ortho_probe)
        elif perspective_reflection is not None:
            source = _lift_perspective_reflection_reference(
                source, *perspective_reflection
            )
        elif ortho_ultra_cascade is not None:
            source = _lift_ortho_ultra_cascade_reference(
                source, *ortho_ultra_cascade
            )
        elif ortho_ultra is not None:
            source = _lift_ortho_ultra_policy_reference(
                source, *ortho_ultra
            )
        elif ortho_cascade_reflection is not None:
            source = _lift_ortho_cascade_reflection_reference(
                source, *ortho_cascade_reflection
            )
        elif ortho_reflection is not None:
            source = _lift_ortho_reflection_reference(
                source, *ortho_reflection
            )
        elif ortho_cascade is not None:
            source = _lift_ortho_cascade_reference(
                source, *ortho_cascade
            )
        elif ortho_ao_sss is not None:
            source = _lift_ortho_ao_sss_reference(source, *ortho_ao_sss)
        elif perspective_cascade_reflection is not None:
            source = _lift_perspective_cascade_reflection_reference(
                source, *perspective_cascade_reflection
            )
        elif ortho_cascade_ssgi is not None:
            source = _lift_ortho_cascade_ssgi_reference(
                source, *ortho_cascade_ssgi
            )
        elif perspective_ultra_cascade is not None:
            source = _lift_perspective_ultra_cascade_reference(
                source, *perspective_ultra_cascade
            )
        elif perspective_ultra_no_ao is not None:
            source = _lift_perspective_ultra_no_ao_reference(
                source, perspective_ultra_no_ao
            )
        elif perspective_ssgi_probe is not None:
            source = _lift_perspective_ssgi_probe_reference(
                source, *perspective_ssgi_probe
            )
        elif perspective_ultra_quality is not None:
            source = _lift_perspective_ultra_quality_reference(
                source, *perspective_ultra_quality
            )
        elif perspective_probe_cascade is not None:
            source = _lift_perspective_probe_cascade_reference(
                source, *perspective_probe_cascade
            )
        elif ortho_ssgi_quality is not None:
            source = _lift_ortho_ssgi_quality_reference(
                source, *ortho_ssgi_quality
            )
        elif perspective_cascade_only is not None:
            source = _lift_perspective_cascade_only_reference(
                source, *perspective_cascade_only
            )
        elif perspective_ao_sss is not None:
            source = _lift_perspective_ao_sss_reference(
                source, *perspective_ao_sss
            )
        elif perspective_probe_quality is not None:
            source = _lift_perspective_probe_quality_reference(
                source, *perspective_probe_quality
            )
        elif _is_probe_cascade_reference(definitions[selector]):
            source = _lift_probe_cascade_reference(source)
        elif _is_cascade_medium_reference(definitions[selector]):
            source = _lift_cascade_medium_reference(source)
        elif _is_medium_sss_reference(definitions[selector]):
            source = _lift_medium_sss_reference(source)
        elif _is_ortho_medium_ssgi_three_reference(definitions[selector]):
            source = _lift_ortho_medium_ssgi_three_reference(source)
        elif _is_ortho_medium_reflection_two_reference(definitions[selector]):
            source = _lift_ortho_medium_reflection_two_reference(source)
        elif _is_medium_probe_four_reference(definitions[selector]):
            source = _lift_medium_probe_four_reference(source)
        elif _is_ortho_high_cascade_probe_reference(definitions[selector]):
            source = _lift_ortho_high_cascade_probe_reference(source)
        elif _is_ortho_high_ssgi_three_reference(definitions[selector]):
            source = _lift_ortho_high_ssgi_three_reference(source)
        elif _is_ortho_high_ultra_reference(definitions[selector]):
            source = _lift_ortho_high_ultra_reference(source)
        elif _is_ortho_medium_ultra_reference(definitions[selector]):
            source = _lift_ortho_medium_ultra_reference(source)
        elif _is_ortho_low_ultra_reference(definitions[selector]):
            source = _lift_ortho_low_ultra_reference(source)
        elif perspective_cascade_ssgi is not None:
            source = _lift_perspective_cascade_ssgi_reference(
                source, *perspective_cascade_ssgi
            )
        variants[selector] = source
    bodies = _emit_variant_snippets(staging, variants)
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="indirect_light",
        bodies=bodies,
        executions={
            shader["selector"]: _execution(blobs[shader["bundle_index"]])
            for shader in shaders
        },
    )
