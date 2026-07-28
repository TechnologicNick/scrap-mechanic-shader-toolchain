"""Recognize indirect-light cascade reconstruction and upscale variants."""

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
1. Reconstruct view depth/normal and choose the active indirect-light cascade.
2. Gather depth-aware AO, indirect, subsurface and temporal neighborhoods.
3. Reject discontinuities and combine the selected quality/temporal path.
4. Emit AO, indirect RGB and/or SSS targets requested by the permutation.

The 163 feature permutations retain instruction ordering for gather lanes,
cascade transforms, packed material tests and temporal rejection thresholds.
*/
"""


REGISTER_NAMES = {
    0: "cascadeAddressState", 1: "viewDepthState",
    2: "normalDecodeState", 3: "cascadeSelectionState",
    4: "sampleCoordinateState", 5: "depthGatherState",
    6: "normalGatherState", 7: "indirectGatherState",
    8: "aoGatherState", 9: "subsurfaceGatherState",
    10: "edgeRejectionState", 11: "bilateralWeightState",
    12: "temporalRejectionState", 13: "weightedIndirectState",
    14: "weightedAoState", 15: "cascadeOutputState",
    16: "cascadeUpscaleScratch",
}


_DEPTH_GATHER = re.compile(
    r"^(?P<indent>\s*)(?P<delta>[A-Za-z_]\w*)\.xyzw = "
    r"tAoDepth\.Gather\(LinearClampClamp_s, "
    r"(?P<uv>[A-Za-z_]\w*\.[xyzw]{2})\)\.xyzw;\n"
    r"(?P=indent)(?P=delta)\.xyzw = (?P=delta)\.xyzw \* (?P=delta)\.xyzw;\n"
    r"(?P=indent)(?P=delta)\.xyzw = (?P=delta)\.xyzw \* "
    r"float4\(499\.899994,499\.899994,499\.899994,499\.899994\) \+ "
    r"float4\(0\.100000001,0\.100000001,0\.100000001,0\.100000001\);\n"
    r"(?P=indent)(?P=delta)\.xyzw = (?P=delta)\.xyzw \+ "
    r"-(?P<center>[A-Za-z_]\w*)\.(?P<center_lane>[xyzw])"
    r"(?P=center_lane)(?P=center_lane)(?P=center_lane);\n"
    r"(?P=indent)(?P=delta)\.xyzw = (?P=delta)\.xyzw \* (?P=delta)\.xyzw;$",
    re.MULTILINE,
)


def _lift_depth_gathers(source: str) -> str:
    """Name the squared view-depth error in each upscale Gather footprint."""
    return _DEPTH_GATHER.sub(
        lambda match: (
            f"{match.group('indent')}{match.group('delta')}.xyzw = "
            "GatherUpscaleDepthError(tAoDepth, LinearClampClamp_s, "
            f"{match.group('uv')}, "
            f"{match.group('center')}.{match.group('center_lane')});"
        ),
        source,
    )


_GAUSSIAN_WEIGHT = re.compile(
    r"^(?P<indent>\s*)(?P<weight>[A-Za-z_]\w*\.[xyzw]) = "
    r"dot\((?P<delta>[A-Za-z_]\w*\.xyzw), float4\(0\.25,0\.25,0\.25,0\.25\)\);\n"
    r"(?P=indent)(?P=weight) = -(?P=weight) \* "
    r"(?P<inverse>[A-Za-z_]\w*\.[xyzw]);\n"
    r"(?P=indent)(?P=weight) = 1\.44269502 \* (?P=weight);\n"
    r"(?P=indent)(?P=weight) = exp2\((?P=weight)\);$",
    re.MULTILINE,
)


def _lift_gaussian_weights(source: str) -> str:
    """Recover the Gaussian confidence used for coherent depth quads."""
    return _GAUSSIAN_WEIGHT.sub(
        lambda match: (
            f"{match.group('indent')}{match.group('weight')} = "
            f"ComputeUpscaleGaussianWeight({match.group('delta')}, "
            f"{match.group('inverse')});"
        ),
        source,
    )


_COVERAGE_WEIGHT = re.compile(
    r"^(?P<indent>\s*)(?P<delta>[A-Za-z_]\w*)\.xyzw = "
    r"(?P=delta)\.xyzw / (?P<threshold>[A-Za-z_]\w*)\."
    r"(?P<threshold_lane>[xyzw])(?P=threshold_lane)(?P=threshold_lane)"
    r"(?P=threshold_lane);\n"
    r"(?P=indent)(?P=delta)\.xyzw = float4\(1,1,1,1\) \+ -(?P=delta)\.xyzw;\n"
    r"(?P=indent)(?P=delta)\.xyzw = max\(float4\(0,0,0,0\), (?P=delta)\.xyzw\);\n"
    r"(?P=indent)(?P<weight>[A-Za-z_]\w*\.[xyzw]) = "
    r"dot\((?P=delta)\.xyzw, float4\(0\.25,0\.25,0\.25,0\.25\)\);\n"
    r"(?P=indent)(?P=weight) = log2\((?P=weight)\);\n"
    r"(?P=indent)(?P=weight) = (?:(?P=weight) \* (?P<exponent_a>[A-Za-z_]\w*\.[xyzw])|"
    r"(?P<exponent_b>[A-Za-z_]\w*\.[xyzw]) \* (?P=weight));\n"
    r"(?P=indent)(?P=weight) = exp2\((?P=weight)\);$",
    re.MULTILINE,
)


def _lift_coverage_weights(source: str) -> str:
    """Name the soft coverage term applied to rejected depth footprints."""
    return _COVERAGE_WEIGHT.sub(
        lambda match: (
            f"{match.group('indent')}{match.group('weight')} = "
            f"ComputeUpscaleCoverageWeight({match.group('delta')}.xyzw, "
            f"{match.group('threshold')}.{match.group('threshold_lane')}, "
            f"{match.group('exponent_a') or match.group('exponent_b')});"
        ),
        source,
    )


_LINEAR_DEPTH = re.compile(
    r"^(?P<indent>\s*)(?P<depth>[A-Za-z_]\w*\.[xyzw]) = "
    r"tDepth\.Load\((?P<coordinate>[^\n]+)\)\.x;\n"
    r"(?P=indent)(?P=depth) = cb_xViewToProjection\._m22 \+ (?P=depth);\n"
    r"(?P=indent)(?P=depth) = cb_xViewToProjection\._m23 / (?P=depth);$",
    re.MULTILINE,
)


def _lift_linear_depth(source: str) -> str:
    """Expose the projection inversion hidden in the recovered instructions."""
    return _LINEAR_DEPTH.sub(
        lambda match: (
            f"{match.group('indent')}{match.group('depth')} = "
            "LinearizeUpscaleDepth("
            f"tDepth.Load({match.group('coordinate')}).x, "
            "cb_xViewToProjection._m22, cb_xViewToProjection._m23);"
        ),
        source,
    )


_NORMAL_DECODE = re.compile(
    r"^(?P<indent>\s*)(?P<encoded>[A-Za-z_]\w*)\.xy = "
    r"tNormal\.Load\((?P<coordinate>[^\n]+)\)\.xy;\n"
    r"(?P=indent)(?P=encoded)\.xy = (?P=encoded)\.xy \* float2\(2,2\) \+ float2\(-1,-1\);\n"
    r"(?P=indent)(?P<fold>[A-Za-z_]\w*\.[xyzw]) = 1 \+ -abs\((?P=encoded)\.x\);\n"
    r"(?P=indent)(?P<zscratch>[A-Za-z_]\w*\.[xyzw]) = (?P=fold) \+ -abs\((?P=encoded)\.y\);\n"
    r"(?P=indent)(?P=fold) = saturate\(-(?P=zscratch)\);\n"
    r"(?P=indent)(?P<signs>[A-Za-z_]\w*\.[xyzw]{2}) = cmp\((?P=encoded)\.xy >= float2\(0,0\)\);\n"
    r"(?P=indent)(?P<correction>[A-Za-z_]\w*\.[xyzw]{2}) = (?P=signs) \? "
    r"-(?P<fold_base>[A-Za-z_]\w*)\.(?P<fold_lane>[xyzw])(?P=fold_lane) : "
    r"(?P=fold_base)\.(?P=fold_lane)(?P=fold_lane);\n"
    r"(?P=indent)(?P<normal>[A-Za-z_]\w*)\.xy = (?P=encoded)\.xy \+ (?P=correction);\n"
    r"(?P=indent)(?P<length>[A-Za-z_]\w*\.[xyzw]) = dot\((?P=normal)\.xyz, (?P=normal)\.xyz\);\n"
    r"(?P=indent)(?P=length) = rsqrt\((?P=length)\);\n"
    r"(?P=indent)(?P<destination>[A-Za-z_]\w*)\.xyz = (?P=normal)\.xyz \* "
    r"(?P<length_base>[A-Za-z_]\w*)\.(?P<length_lane>[xyzw])(?P=length_lane)(?P=length_lane);$",
    re.MULTILINE,
)


def _lift_normal_decodes(source: str) -> str:
    """Collapse octahedral G-buffer normal decoding into a domain helper."""
    return _NORMAL_DECODE.sub(
        lambda match: (
            f"{match.group('indent')}{match.group('destination')}.xyz = "
            f"DecodeUpscaleNormal(tNormal.Load({match.group('coordinate')}).xy);"
        ),
        source,
    )


_MATERIAL_RESPONSE = re.compile(
    r"^(?P<indent>\s*)(?P<state>[A-Za-z_]\w*)\.(?P<input_lane>[xyzw])"
    r"(?P<response_lane>[xyzw]) = tMaterial\.Load\("
    r"(?P<coordinate>[^\n]+)\)\.xy;\n"
    r"(?P=indent)(?P=state)\.(?P=response_lane) = 1 \+ -(?P=state)\."
    r"(?P=response_lane);\n"
    r"(?P=indent)(?P=state)\.(?P=response_lane) = log2\(abs\("
    r"(?P=state)\.(?P=response_lane)\)\);\n"
    r"(?P=indent)(?P=state)\.(?P=response_lane) = 0\.75 \* "
    r"(?P=state)\.(?P=response_lane);\n"
    r"(?P=indent)(?P=state)\.(?P=response_lane) = exp2\("
    r"(?P=state)\.(?P=response_lane)\);\n"
    r"(?P=indent)(?P=state)\.(?P=response_lane) = 1 \+ -(?P=state)\."
    r"(?P=response_lane);\n"
    r"(?P=indent)(?P=state)\.(?P=input_lane) = (?P=state)\."
    r"(?P=response_lane) \* (?P=state)\.(?P=input_lane);\n"
    r"(?P=indent)(?P=state)\.(?P=input_lane) = saturate\(3\.5999999 \* "
    r"(?P=state)\.(?P=input_lane)\);\n"
    r"(?P=indent)(?P=state)\.(?P=input_lane) = -0\.150000006 \+ "
    r"(?P=state)\.(?P=input_lane);\n"
    r"(?P=indent)(?P=state)\.(?P=input_lane) = max\(0, (?P=state)\."
    r"(?P=input_lane)\);\n"
    r"(?P=indent)(?P=state)\.(?P=input_lane) = 1\.42857146 \* "
    r"(?P=state)\.(?P=input_lane);\n"
    r"(?P=indent)(?P=state)\.(?P=input_lane) = min\(1, (?P=state)\."
    r"(?P=input_lane)\);\n"
    r"(?P=indent)(?P=state)\.(?P=response_lane) = 1 \+ -(?P=state)\."
    r"(?P=input_lane);\n"
    r"(?P=indent)(?P=state)\.(?P<radius_lane>[xyzw]) = (?P=state)\."
    r"(?P=response_lane) \* (?P=state)\.(?P=response_lane);\n"
    r"(?P=indent)(?P=state)\.(?P=radius_lane) = (?P=state)\."
    r"(?P=radius_lane) \* (?P=state)\.(?P=radius_lane);$",
    re.MULTILINE,
)


def _lift_material_responses(source: str) -> str:
    """Recover the material-driven edge response and adaptive tap radius."""
    def replace(match: re.Match[str]) -> str:
        indent = match.group("indent")
        state = match.group("state")
        return (
            f"{indent}UpscaleMaterialResponse materialResponse = "
            f"EvaluateUpscaleMaterial(tMaterial.Load("
            f"{match.group('coordinate')}).xy);\n"
            f"{indent}{state}.{match.group('input_lane')} = "
            "materialResponse.edgeResponse;\n"
            f"{indent}{state}.{match.group('response_lane')} = "
            "materialResponse.backgroundResponse;\n"
            f"{indent}{state}.{match.group('radius_lane')} = "
            "materialResponse.tapRadiusScale;"
        )

    return _MATERIAL_RESPONSE.sub(replace, source)


_POSITION_TRANSFORM = re.compile(
    r"^(?P<indent>\s*)(?P<destination>[A-Za-z_]\w*\.xyz) = "
    r"(?P<matrix>[A-Za-z_]\w*(?:\[[^\]]+\])?)\._m01_m11_m21 \* "
    r"(?P<y>[A-Za-z_]\w*\.[xyzw])(?P<y_lane>[xyzw])(?P=y_lane);\n"
    r"(?P=indent)(?P=destination) = (?P=matrix)\._m00_m10_m20 \* "
    r"(?P<x>[A-Za-z_]\w*\.[xyzw])(?P<x_lane>[xyzw])(?P=x_lane) \+ (?P=destination);\n"
    r"(?P=indent)(?P=destination) = (?P=matrix)\._m02_m12_m22 \* "
    r"(?P<z>[A-Za-z_]\w*\.[xyzw])(?P<z_lane>[xyzw])(?P=z_lane) \+ (?P=destination);\n"
    r"(?P=indent)(?P=destination) = (?P=matrix)\._m03_m13_m23 \+ (?P=destination);$",
    re.MULTILINE,
)


def _lift_position_transforms(source: str) -> str:
    """Recover affine position transforms used by view and cascade matrices."""
    return _POSITION_TRANSFORM.sub(
        lambda match: (
            f"{match.group('indent')}{match.group('destination')} = "
            f"TransformUpscalePosition({match.group('matrix')}, float3("
            f"{match.group('x')}, {match.group('y')}, {match.group('z')}));"
        ),
        source,
    )


_CLIP_TRANSFORM = re.compile(
    r"^(?P<indent>\s*)(?P<destination>[A-Za-z_]\w*\.xyz) = "
    r"(?P<matrix>[A-Za-z_]\w*)\._m01_m11_m31 \* "
    r"(?P<y>[A-Za-z_]\w*\.[xyzw])(?P<y_lane>[xyzw])(?P=y_lane);\n"
    r"(?P=indent)(?P<scratch>[A-Za-z_]\w*\.[xyzw]{3}) = "
    r"(?P=matrix)\._m00_m10_m30 \* (?P<x>[A-Za-z_]\w*\.[xyzw])"
    r"(?P<x_lane>[xyzw])(?P=x_lane) \+ (?P=destination);\n"
    r"(?P=indent)(?P<projected>[A-Za-z_]\w*\.xyz) = "
    r"(?P=matrix)\._m02_m12_m32 \* (?P<z>[A-Za-z_]\w*\.[xyzw])"
    r"(?P<z_lane>[xyzw])(?P=z_lane) \+ (?P=scratch);\n"
    r"(?P=indent)(?P=projected) = (?P=matrix)\._m03_m13_m33 \+ (?P=projected);$",
    re.MULTILINE,
)


def _lift_clip_transforms(source: str) -> str:
    """Name world-to-clip projection used by temporal reprojection."""
    return _CLIP_TRANSFORM.sub(
        lambda match: (
            f"{match.group('indent')}{match.group('projected')} = "
            f"ProjectUpscalePosition({match.group('matrix')}, float3("
            f"{match.group('x')}, {match.group('y')}, {match.group('z')}));"
        ),
        source,
    )


_SSS_SWIZZLE = re.compile(
    r"^(?P<indent>\s*)(?P<index>[A-Za-z_]\w*\.[xyzw]) = cb_settings\.vuSSSwaps\.x;\n"
    r"(?P=indent)(?P<output>[A-Za-z_]\w*)\.x = dot\((?P<input>[A-Za-z_]\w*)\.xyzw, icb\[(?P=index)\+0\]\.xyzw\);\n"
    r"(?P=indent)(?P=index) = cb_settings\.vuSSSwaps\.y;\n"
    r"(?P=indent)(?P=output)\.y = dot\((?P=input)\.xyzw, icb\[(?P=index)\+0\]\.xyzw\);\n"
    r"(?P=indent)(?P=index) = cb_settings\.vuSSSwaps\.z;\n"
    r"(?P=indent)(?P=output)\.z = dot\((?P=input)\.xyzw, icb\[(?P=index)\+0\]\.xyzw\);\n"
    r"(?P=indent)(?P=index) = cb_settings\.vuSSSwaps\.w;\n"
    r"(?P=indent)(?P=output)\.w = dot\((?P=input)\.xyzw, icb\[(?P=index)\+0\]\.xyzw\);$",
    re.MULTILINE,
)


def _lift_sss_swizzles(source: str) -> str:
    """Replace identity-row dot products with the recovered SSS channel map."""
    return _SSS_SWIZZLE.sub(
        lambda match: (
            f"{match.group('indent')}{match.group('output')}.xyzw = "
            f"SwizzleUpscaleSss({match.group('input')}.xyzw, "
            "cb_settings.vuSSSwaps);"
        ),
        source,
    )


_VOLATILITY = re.compile(
    r"^(?P<indent>\s*)(?P<gather>[A-Za-z_]\w*)\.xyzw = "
    r"tVolatile\.Gather\(LinearClampClamp_s, (?P<uv>[^\n]+)\)\.xyzw;\n"
    r"(?P=indent)(?P=gather)\.xyzw = cmp\((?P=gather)\.xyzw < float4\(0,0,0,0\)\);\n"
    r"(?P=indent)(?P=gather)\.xy = \(int2\)(?P=gather)\.zw \| \(int2\)(?P=gather)\.xy;\n"
    r"(?P=indent)(?P<value>[A-Za-z_]\w*\.[xyzw]) = \(int\)(?P=gather)\.y \| \(int\)(?P=gather)\.x;\n"
    r"(?P=indent)(?P<sample>[A-Za-z_]\w*\.[xyzw]) = "
    r"tVolatile\.SampleLevel\(LinearClampClamp_s, (?P=uv), 0\)\.x;\n"
    r"(?P=indent)(?P=value) = (?P=value) \? -1 : (?P=sample);$",
    re.MULTILINE,
)


def _lift_volatility(source: str) -> str:
    """Name the negative-neighborhood sentinel in temporal volatility."""
    return _VOLATILITY.sub(
        lambda match: (
            f"{match.group('indent')}{match.group('value')} = "
            "ReadUpscaleVolatility(tVolatile, LinearClampClamp_s, "
            f"{match.group('uv')});"
        ),
        source,
    )


_AO_SSS_CROSS = re.compile(
    r"^  viewDepthState\.y = cmp\(viewDepthState\.x < 499\.899994\);\n"
    r"  if \(viewDepthState\.y != 0\) \{.*?"
    r"^  \} else \{\n"
    r"    cascadeSelectionState\.xyz = float3\(0,0,0\);\n"
    r"    viewDepthState\.w = 1;\n"
    r"    normalDecodeState\.x = 0;\n"
    r"  \}$",
    re.MULTILINE | re.DOTALL,
)


def _lift_ao_sss_cross(source: str) -> str:
    """Recover the five-footprint AO/SSS cross filter as one typed operation."""
    def replace(match: re.Match[str]) -> str:
        block = match.group(0)
        required = (
            "tIndirect_Ao.SampleLevel",
            "tSSS.SampleLevel",
            "GatherUpscaleDepthError",
            "cascadeSelectionState.xyz = normalDecodeState.yzw;",
        )
        if any(marker not in block for marker in required):
            return block
        return """  viewDepthState.y = cmp(viewDepthState.x < 499.899994);
  UpscaledAoSss spatialAoSss = FilterAoSssCross(
      tAoDepth, tIndirect_Ao, tSSS, tMaterial, LinearClampClamp_s,
      (int2)cascadeAddressState.xy, viewDepthState.x, cb_vTargetSize.xy,
      cb_vRenderScale.xy, cb_vContainerPixelSize.xy,
      cb_settings.vInvScale.xy, cb_settings.vUvLimit.xy,
      cb_f720To4K, cb_uFrameCount, cb_fFrameRateScale);
  viewDepthState.w = spatialAoSss.ao;
  normalDecodeState.xyzw = spatialAoSss.sss;
  cascadeSelectionState.xyz = spatialAoSss.sss.yzw;"""

    return _AO_SSS_CROSS.sub(replace, source, count=1)


_CASCADE_SELECTION = re.compile(
    r"^    normalGatherState\.xyz = TransformUpscalePosition\(cb_arrCascades\[0\], "
    r"float3\(sampleCoordinateState\.x, sampleCoordinateState\.y, sampleCoordinateState\.z\)\);\n"
    r"    indirectGatherState\.xyz = float3\(-0\.5,-0\.5,-0\.5\) \+ normalGatherState\.xyz;.*?"
    r"^    \} else \{\n"
    r"      indirectGatherState\.xy = abs\(indirectGatherState\.xy\);\n"
    r"    \}$",
    re.MULTILINE | re.DOTALL,
)


def _lift_cascade_selection(source: str) -> str:
    """Replace the four nested containment tests with a typed selection."""
    return _CASCADE_SELECTION.sub(
        """    UpscaleCascadeSelection activeCascade = SelectUpscaleCascade(
        sampleCoordinateState.xyz,
        cb_arrCascades[0], cb_arrCascades[1],
        cb_arrCascades[2], cb_arrCascades[3]);
    normalGatherState.xyz = activeCascade.coordinate;
    indirectGatherState.xy = activeCascade.centeredCoordinate;
    indirectGatherState.z = activeCascade.index;""",
        source,
        count=1,
    )


_PERSPECTIVE_CASCADE_SELECTION = re.compile(
    r"^    normalGatherState\.xyz = TransformUpscalePosition\(cb_arrCascades\[0\], "
    r"float3\(depthGatherState\.x, depthGatherState\.y, depthGatherState\.z\)\);\n"
    r"    indirectGatherState\.xyz = float3\(-0\.5,-0\.5,-0\.5\) \+ normalGatherState\.xyz;.*?"
    r"^    \} else \{\n"
    r"      indirectGatherState\.xy = abs\(indirectGatherState\.xy\);\n"
    r"    \}$",
    re.MULTILINE | re.DOTALL,
)


def _lift_perspective_cascade_selection(source: str) -> str:
    """Recover cascade containment when world position uses depthGatherState."""
    def replace(match: re.Match[str]) -> str:
        block = match.group(0)
        if any(
            marker not in block
            for marker in (
                "cb_arrCascades[1]",
                "cb_arrCascades[2]",
                "cb_arrCascades[3]",
            )
        ):
            return block
        return """    UpscaleCascadeSelection activeCascade = SelectUpscaleCascade(
        depthGatherState.xyz,
        cb_arrCascades[0], cb_arrCascades[1],
        cb_arrCascades[2], cb_arrCascades[3]);
    normalGatherState.xyz = activeCascade.coordinate;
    indirectGatherState.xy = activeCascade.centeredCoordinate;
    indirectGatherState.z = activeCascade.index;"""

    return _PERSPECTIVE_CASCADE_SELECTION.sub(replace, source, count=1)


_MEDIUM_CASCADE_SHADOW = re.compile(
    r"^    normalGatherState\.xyz = activeCascade\.coordinate;\n"
    r"    indirectGatherState\.xy = activeCascade\.centeredCoordinate;\n"
    r"    indirectGatherState\.z = activeCascade\.index;\n"
    r"    sampleCoordinateState\.w = cmp\(3 >= \(uint\)indirectGatherState\.z\);\n"
    r"    if \(sampleCoordinateState\.w != 0\) \{.*?"
    r"^    \} else \{\n"
    r"      normalGatherState\.y = 1;\n"
    r"    \}$",
    re.MULTILINE | re.DOTALL,
)


def _lift_medium_cascade_shadow(
    source: str, world_position: str = "sampleCoordinateState.xyz"
) -> str:
    """Recover medium PCF sampling and adjacent-cascade boundary blending."""
    def replace(match: re.Match[str]) -> str:
        block = match.group(0)
        required = (
            "0.0588235296 * normalGatherState.x",
            "taCascades.GatherCmp",
            "cb_vCascadePixelSize.xy",
            "cb_arrCascades[depthGatherState.w]",
        )
        if any(marker not in block for marker in required):
            return block
        return f"""    normalGatherState.y = EvaluateUpscaleMediumCascadeShadow(
        taCascades, sShadowSamplerLinear_s, activeCascade,
        {world_position}, cascadeAddressState.w,
        cb_vCascadeSplits, cb_vCascadeSize, cb_vCascadePixelSize,
        cb_arrCascades[1], cb_arrCascades[2], cb_arrCascades[3]);"""

    return _MEDIUM_CASCADE_SHADOW.sub(replace, source, count=1)


def _lift_low_cascade_shadow(
    source: str, world_position: str = "sampleCoordinateState.xyz"
) -> str:
    """Recover the seven-weight low PCF path and boundary blending."""
    def replace(match: re.Match[str]) -> str:
        block = match.group(0)
        required = (
            "0.142857149 * normalGatherState.x",
            "taCascades.GatherCmp",
            "int2(-1,-1)",
            "cb_arrCascades[depthGatherState.w]",
        )
        if any(marker not in block for marker in required):
            return block
        return f"""    normalGatherState.y = EvaluateUpscaleLowCascadeShadow(
        taCascades, sShadowSamplerLinear_s, activeCascade,
        {world_position}, cascadeAddressState.w,
        cb_vCascadeSplits, cb_vCascadeSize, cb_vCascadePixelSize,
        cb_arrCascades[1], cb_arrCascades[2], cb_arrCascades[3]);"""

    return _MEDIUM_CASCADE_SHADOW.sub(replace, source, count=1)


_DIRECTIONAL_FACING = re.compile(
    r"^(?P<indent>\s*)(?P<state>[A-Za-z_]\w*)\.x = dot\("
    r"(?P=state)\.xyz, -cb_vDirectionalLightDirectionView\.xyz\);\n"
    r"(?P=indent)(?P=state)\.x = 0\.400000006 \+ (?P=state)\.x;\n"
    r"(?P=indent)(?P=state)\.x = saturate\(1\.66666663 \* (?P=state)\.x\);\n"
    r"(?P=indent)(?P=state)\.y = (?P=state)\.x \* -2 \+ 3;\n"
    r"(?P=indent)(?P=state)\.x = (?P=state)\.x \* (?P=state)\.x;\n"
    r"(?P=indent)(?P=state)\.x = (?P=state)\.y \* (?P=state)\.x;\n"
    r"(?P=indent)(?P=state)\.x = saturate\("
    r"(?P<shadow>[A-Za-z_]\w*\.[xyzw]) \* (?P=state)\.x\);\n"
    r"(?P=indent)(?P=state)\.y = (?P=state)\.x;$",
    re.MULTILINE,
)


def _lift_directional_facing(source: str) -> str:
    """Name the wrapped N-dot-L term applied to cascade visibility."""
    return _DIRECTIONAL_FACING.sub(
        lambda match: (
            f"{match.group('indent')}{match.group('state')}.x = "
            "ApplyUpscaleDirectionalFacing("
            f"{match.group('shadow')}, {match.group('state')}.xyz, "
            "cb_vDirectionalLightDirectionView.xyz);\n"
            f"{match.group('indent')}{match.group('state')}.y = "
            f"{match.group('state')}.x;"
        ),
        source,
    )


_TEMPORAL_RESOLVE = re.compile(
    r"^  cascadeAddressState\.w = min\(viewDepthState\.z, cascadeAddressState\.x\);\n"
    r"  viewDepthState\.z = -4 \+ viewDepthState\.x;.*?"
    r"^  \} else \{\n"
    r"    normalDecodeState\.yzw = cascadeSelectionState\.xyz;\n"
    r"    o0\.x = cascadeAddressState\.z;\n"
    r"  \}$",
    re.MULTILINE | re.DOTALL,
)


def _lift_temporal_resolve(
    source: str, *, perspective: bool = False
) -> str:
    """Recover reprojection, history rejection, and AO/SSS accumulation."""
    # The raw low/high PCF paths reuse depthGatherState.xyz before temporal
    # resolve. The medium lift removes those scratch-register clobbers and
    # establishes the typed viewPosition/worldPosition inputs used below.
    if not any(
        marker in source
        for marker in (
            "EvaluateUpscaleMediumCascadeShadow",
            "EvaluateUpscaleLowCascadeShadow",
        )
    ):
        return source

    def replace(match: re.Match[str]) -> str:
        block = match.group(0)
        required = (
            "ProjectUpscalePosition(cb_xPrevWorldToViewProjection",
            "ReadUpscaleVolatility(tVolatile",
            "tTemporalAo.SampleLevel",
            "tTemporalSSS.SampleLevel",
            "SwizzleUpscaleSss",
        )
        if any(marker not in block for marker in required):
            return block
        view_position = (
            "sampleCoordinateState.xyz"
            if perspective else "depthGatherState.xyz"
        )
        world_position = (
            "depthGatherState.xyz"
            if perspective else "sampleCoordinateState.xyz"
        )
        return f"""  UpscaleTemporalResult temporalResult = ResolveUpscaleTemporal(
      tTemporalAo, tTemporalSSS, tVolatile, LinearClampClamp_s,
      v1.xy, viewDepthState.x, {view_position},
      {world_position}, viewDepthState.w,
      float4(normalDecodeState.x, cascadeSelectionState.xyz),
      viewDepthState.y, viewDepthState.z, cascadeAddressState.x,
      cb_xPrevWorldToViewProjection,
      cb_xPrevViewToWorld._m03_m13_m23, viewToWorld._m03_m13_m23,
      cb_vPrevRenderScale, cb_vPrevUvLimit, cb_fRenderScaleStability,
      cb_fFrameRateScale, cb_settings.vuSSSwaps);
  normalDecodeState.xyzw = temporalResult.sss;
  cascadeAddressState.y = temporalResult.cascadeVisibility;
  o0.x = temporalResult.ao;"""

    return _TEMPORAL_RESOLVE.sub(replace, source, count=1)


_BOUND_UPSCALE_MAIN = re.compile(
    r"^// 3Dmigoto declarations\n#define cmp -\n\n\n"
    r"void mainPS\(.*?^\}\s*$",
    re.MULTILINE | re.DOTALL,
)


def _bound_upscale_main(
    resolver: str,
    cascade_evaluator: str = "EvaluateBoundUpscaleCascadeLighting",
    surface_gather: str = "GatherBoundUpscaleSurface",
) -> str:
    template = """#include \"../indirect_cascade_upscale_bound.hlsl\"

void mainPS(
  float4 v0 : SV_Position0,
  float2 v1 : UV0,
  float2 w1 : UNSCALED_UV0,
  out float2 o0 : SV_Target0,
  out float4 o2 : SV_Target2)
{
  // Keep the recovered float multiply followed by truncation for pixel lookup.
  float2 pixelCoordinate = asuint(cb_vuViewportSize.xy);
  pixelCoordinate = w1.xy * pixelCoordinate;
  int2 pixel = (uint2)pixelCoordinate;
  float viewDepth = tHzb.Load(int3(pixel, 0)).x;
  float backgroundDepth = -1.0 + cb_vNearFarViewCorner.y;
  if (viewDepth >= backgroundDepth)
  {
    o0 = float2(1.0, 1.0);
    o2 = float4(1.0, 1.0, 1.0, 1.0);
    return;
  }

  UpscaleSurface surface = __SURFACE_GATHER__(
      w1, pixel, viewDepth);
  UpscaleCascadeLighting cascade =
      __CASCADE_EVALUATOR__(surface);
  UpscaleTemporalResult resolved = __RESOLVER__(
      surface, cascade, v1);

  o0.x = resolved.ao;
  o0.y = min(resolved.sss.x, resolved.cascadeVisibility);
  o2 = resolved.sss;
}
"""
    return template.replace("__RESOLVER__", resolver).replace(
        "__CASCADE_EVALUATOR__", cascade_evaluator
    ).replace("__SURFACE_GATHER__", surface_gather)


def _lift_bound_upscale_main(
    source: str, *, perspective: bool = False
) -> str:
    """Replace the full-history register shell with typed family operations."""
    required = (
        "UpscaledAoSss spatialAoSss = FilterAoSssCross(",
        "EvaluateUpscaleMediumCascadeShadow(",
        "ApplyUpscaleDirectionalFacing(",
        "UpscaleTemporalResult temporalResult = ResolveUpscaleTemporal(",
    )
    if any(marker not in source for marker in required):
        return source
    return _BOUND_UPSCALE_MAIN.sub(
        _bound_upscale_main(
            "ResolveBoundUpscaleTemporal",
            surface_gather=(
                "GatherBoundPerspectiveUpscaleSurface"
                if perspective else "GatherBoundUpscaleSurface"
            ),
        ),
        source,
        count=1,
    )


def _lift_bound_no_cascade_history_main(
    source: str, *, perspective: bool = False
) -> str:
    """Lift AO/SSS history when cascade temporal accumulation is disabled."""
    required = (
        "UpscaledAoSss spatialAoSss = FilterAoSssCross(",
        "EvaluateUpscaleMediumCascadeShadow(",
        "ApplyUpscaleDirectionalFacing(",
        "tTemporalAo.SampleLevel(",
        "tTemporalSSS.SampleLevel(",
        "o0.y = min(normalDecodeState.x, cascadeAddressState.y);",
    )
    if any(marker not in source for marker in required):
        return source
    return _BOUND_UPSCALE_MAIN.sub(
        _bound_upscale_main(
            "ResolveBoundUpscaleTemporalWithoutCascadeHistory",
            surface_gather=(
                "GatherBoundPerspectiveUpscaleSurface"
                if perspective else "GatherBoundUpscaleSurface"
            ),
        ),
        source,
        count=1,
    )


def _lift_bound_low_upscale_main(
    source: str, *, cascade_history: bool, perspective: bool = False
) -> str:
    """Lift low-PCF AO/SSS entry points after their data flow is typed."""
    required = (
        "UpscaledAoSss spatialAoSss = FilterAoSssCross(",
        "EvaluateUpscaleLowCascadeShadow(",
        "ApplyUpscaleDirectionalFacing(",
    )
    if any(marker not in source for marker in required):
        return source
    if cascade_history:
        if "UpscaleTemporalResult temporalResult = ResolveUpscaleTemporal(" not in source:
            return source
        resolver = "ResolveBoundUpscaleTemporal"
    else:
        if "tTemporalSSS.SampleLevel(" not in source:
            return source
        resolver = "ResolveBoundUpscaleTemporalWithoutCascadeHistory"
    return _BOUND_UPSCALE_MAIN.sub(
        _bound_upscale_main(
            resolver,
            "EvaluateBoundLowUpscaleCascadeLighting",
            (
                "GatherBoundPerspectiveUpscaleSurface"
                if perspective else "GatherBoundUpscaleSurface"
            ),
        ),
        source,
        count=1,
    )


def _lift_bound_cascade_only_main(
    source: str, *, quality: str
) -> str:
    """Lift perspective cascade-only temporal permutations."""
    low_quality = quality == "low"
    shadow_markers = (
        ("0.142857149", "int2(-1,-1)", "int2(1,1)")
        if low_quality
        else ("0.0588235296", "int2(-2,-2)", "int2(2,2)")
    )
    required = (
        "0.330000013",
        *shadow_markers,
        "tTemporalAo.SampleLevel(",
        "tVolatile.Gather(",
        "o0.xy = cascadeAddressState.yx;",
    )
    if any(marker not in source for marker in required):
        return source
    replacement = """#include "../indirect_cascade_upscale_cascade_bound.hlsl"

void mainPS(
  float4 v0 : SV_Position0,
  float2 v1 : UV0,
  float2 w1 : UNSCALED_UV0,
  out float2 o0 : SV_Target0)
{
  float2 pixelCoordinate = asuint(cb_vuViewportSize.xy);
  pixelCoordinate = w1.xy * pixelCoordinate;
  int2 pixel = (uint2)pixelCoordinate;
  float viewDepth = tHzb.Load(int3(pixel, 0)).x;
  float backgroundDepth = -1.0 + cb_vNearFarViewCorner.y;
  if (viewDepth >= backgroundDepth)
  {
    o0 = float2(1.0, 1.0);
    return;
  }

  UpscaleCascadeSurface surface =
      GatherBoundPerspectiveCascadeSurface(w1, pixel, viewDepth);
  float cascadeVisibility =
      __CASCADE_EVALUATOR__(surface);
  cascadeVisibility = __TEMPORAL_RESOLVER__(
      v1, surface, cascadeVisibility);
  o0 = float2(1.0, cascadeVisibility);
}
"""
    cascade_evaluator = (
        "EvaluateBoundLowCascadeOnlyLighting"
        if low_quality
        else "EvaluateBoundMediumCascadeOnlyLighting"
    )
    temporal_resolver = (
        "ResolveBoundHighCascadeOnlyTemporal"
        if quality == "high"
        else "ResolveBoundLowMediumCascadeOnlyTemporal"
    )
    replacement = replacement.replace(
        "__CASCADE_EVALUATOR__", cascade_evaluator
    ).replace("__TEMPORAL_RESOLVER__", temporal_resolver)
    return _BOUND_UPSCALE_MAIN.sub(replacement, source, count=1)


def _lift_bound_indirect_only_main(
    source: str, *, perspective: bool
) -> str:
    """Lift the adaptive cross filter and history of indirect-only variants."""
    required = (
        "tMaterial.Load(",
        "3.5999999",
        "1.42857146",
        "GatherUpscaleDepthError(",
        "ComputeUpscaleGaussianWeight(",
        "ComputeUpscaleCoverageWeight(",
        "tTemporalIndirect.SampleLevel(",
        "tVolatile.Gather(",
        "o1.xyz = cascadeAddressState.zzz * viewDepthState.xyz",
    )
    if any(marker not in source for marker in required):
        return source
    position_reconstructor = (
        "ReconstructBoundPerspectiveIndirectPosition"
        if perspective
        else "ReconstructBoundOrthoIndirectPosition"
    )
    replacement = """#include "../indirect_cascade_upscale_indirect_bound.hlsl"

void mainPS(
  float4 v0 : SV_Position0,
  float2 v1 : UV0,
  float2 w1 : UNSCALED_UV0,
  out float3 o1 : SV_Target1)
{
  float2 pixelCoordinate = asuint(cb_vuViewportSize.xy);
  pixelCoordinate = w1.xy * pixelCoordinate;
  int2 pixel = (uint2)pixelCoordinate;
  float viewDepth = tHzb.Load(int3(pixel, 0)).x;
  float backgroundDepth = -1.0 + cb_vNearFarViewCorner.y;
  if (viewDepth >= backgroundDepth)
  {
    o1 = float3(0.0, 0.0, 0.0);
    return;
  }

  UpscaledIndirect spatial = FilterBoundIndirectCross(pixel, viewDepth);
  float3 worldPosition = __POSITION_RECONSTRUCTOR__(w1, viewDepth);
  o1 = ResolveBoundIndirectTemporal(
      v1, viewDepth, worldPosition, spatial);
}
"""
    replacement = replacement.replace(
        "__POSITION_RECONSTRUCTOR__", position_reconstructor
    )
    return _BOUND_UPSCALE_MAIN.sub(replacement, source, count=1)


def _lift_bound_sss_depth_cascade_main(
    source: str, *, perspective: bool, quality: str
) -> str:
    """Lift SSS filtering with a non-temporal cascade sampled at tDepth."""
    shadow_markers = (
        ("0.142857149", "int2(-1,-1)", "int2(1,1)")
        if quality == "low"
        else ("0.0588235296", "int2(-2,-2)", "int2(2,2)")
    )
    required = (
        "tSSS.SampleLevel(",
        "tTemporalSSS.SampleLevel(",
        "LinearizeUpscaleDepth(tDepth.Load(",
        "GatherUpscaleDepthError(",
        "ComputeUpscaleCoverageWeight(",
        "SwizzleUpscaleSss(",
        "o0.y = min(normalDecodeState.x, cascadeAddressState.x);",
        *shadow_markers,
    )
    if any(marker not in source for marker in required):
        return source
    reconstructor = (
        "ReconstructBoundPerspectiveSssPosition"
        if perspective
        else "ReconstructBoundOrthoSssPosition"
    )
    medium_quality = "true" if quality != "low" else "false"
    replacement = """#include "../indirect_cascade_upscale_sss_depth_bound.hlsl"

void mainPS(
  float4 v0 : SV_Position0,
  float2 v1 : UV0,
  float2 w1 : UNSCALED_UV0,
  out float2 o0 : SV_Target0,
  out float4 o2 : SV_Target2)
{
  float2 pixelCoordinate = asuint(cb_vuViewportSize.xy);
  pixelCoordinate = w1.xy * pixelCoordinate;
  int2 pixel = (uint2)pixelCoordinate;
  float hzbDepth = tHzb.Load(int3(pixel, 0)).x;
  float backgroundDepth = -1.0 + cb_vNearFarViewCorner.y;
  if (hzbDepth >= backgroundDepth)
  {
    o0 = float2(1.0, 1.0);
    o2 = float4(1.0, 1.0, 1.0, 1.0);
    return;
  }

  UpscaledSss spatial = FilterBoundSssCross(pixel, hzbDepth);
  BoundSssPosition hzbSurface = __RECONSTRUCTOR__(w1, hzbDepth);
  float sceneDepth = LinearizeUpscaleDepth(
      tDepth.Load(int3(pixel, 0)).x,
      cb_xViewToProjection._m22, cb_xViewToProjection._m23);
  BoundSssPosition sceneSurface = __RECONSTRUCTOR__(w1, sceneDepth);
  float cascadeVisibility = EvaluateBoundDepthCascadeImpl(
      pixel, hzbDepth, sceneDepth, spatial.value.x,
      sceneSurface, __MEDIUM_QUALITY__);
  float4 resolvedSss = ResolveBoundSssTemporal(
      v1, hzbDepth, hzbSurface, spatial.value);

  o0 = float2(1.0, min(resolvedSss.x, cascadeVisibility));
  o2 = resolvedSss;
}
"""
    replacement = replacement.replace(
        "__RECONSTRUCTOR__", reconstructor
    ).replace("__MEDIUM_QUALITY__", medium_quality)
    return _BOUND_UPSCALE_MAIN.sub(replacement, source, count=1)


def _lift_bound_full_output_main(
    source: str, *, perspective: bool, quality: str
) -> str:
    """Compose typed AO, indirect, SSS, cascade, and temporal operations."""
    shadow_markers = (
        ("0.142857149", "int2(-1,-1)", "int2(1,1)")
        if quality == "low"
        else ("0.0588235296", "int2(-2,-2)", "int2(2,2)")
    )
    required = (
        "tIndirect_Ao.SampleLevel(",
        "tSSS.SampleLevel(",
        "tTemporalIndirect.SampleLevel(",
        "tTemporalAo.SampleLevel(",
        "tTemporalSSS.SampleLevel(",
        "GatherUpscaleDepthError(",
        "SwizzleUpscaleSss(",
        "o1.xyz = cascadeAddressState.zzz * viewDepthState.xyz",
        "o0.y = min(normalDecodeState.x, cascadeAddressState.y);",
        *shadow_markers,
    )
    if any(marker not in source for marker in required):
        return source
    gather = (
        "GatherBoundPerspectiveFullSurface"
        if perspective
        else "GatherBoundOrthoFullSurface"
    )
    cascade_evaluator = (
        "EvaluateBoundUpscaleCascadeLighting"
        if quality != "low"
        else "EvaluateBoundLowUpscaleCascadeLighting"
    )
    replacement = """#include "../indirect_cascade_upscale_full_bound.hlsl"

void mainPS(
  float4 v0 : SV_Position0,
  float2 v1 : UV0,
  float2 w1 : UNSCALED_UV0,
  out float2 o0 : SV_Target0,
  out float3 o1 : SV_Target1,
  out float4 o2 : SV_Target2)
{
  float2 pixelCoordinate = asuint(cb_vuViewportSize.xy);
  pixelCoordinate = w1.xy * pixelCoordinate;
  int2 pixel = (uint2)pixelCoordinate;
  float viewDepth = tHzb.Load(int3(pixel, 0)).x;
  float backgroundDepth = -1.0 + cb_vNearFarViewCorner.y;
  if (viewDepth >= backgroundDepth)
  {
    o0 = float2(1.0, 1.0);
    o1 = float3(0.0, 0.0, 0.0);
    o2 = float4(1.0, 1.0, 1.0, 1.0);
    return;
  }

  UpscaleFullSurface surface = __GATHER__(
      w1, pixel, viewDepth);
  UpscaleCascadeLighting cascade = __CASCADE_EVALUATOR__(
      surface.common);
  UpscaleFullTemporalResult resolved =
      ResolveBoundFullTemporalWithoutCascadeHistory(
          surface, cascade, v1);

  o0 = float2(
      resolved.ao, min(resolved.sss.x, resolved.cascadeVisibility));
  o1 = resolved.indirect;
  o2 = resolved.sss;
}
"""
    replacement = replacement.replace("__GATHER__", gather).replace(
        "__CASCADE_EVALUATOR__", cascade_evaluator
    )
    return _BOUND_UPSCALE_MAIN.sub(replacement, source, count=1)


def _lift_bound_ao_depth_cascade_main(
    source: str, *, perspective: bool, quality: str
) -> str:
    """Lift AO with a depth-derived cascade and two-channel history."""
    low_quality = quality == "low"
    shadow_markers = (
        ("0.142857149", "int2(-1,-1)", "int2(1,1)")
        if low_quality
        else ("0.0588235296", "int2(-2,-2)", "int2(2,2)")
    )
    required = (
        "tIndirect_Ao.SampleLevel(",
        "tTemporalAo.SampleLevel(",
        "LinearizeUpscaleDepth(tDepth.Load(",
        "GatherUpscaleDepthError(",
        "0.330000013",
        "o0.xy = cascadeSelectionState.xy * cascadeAddressState.xy",
        *shadow_markers,
    )
    if any(marker not in source for marker in required):
        return source
    reconstructor = (
        "ReconstructBoundPerspectiveAoPosition"
        if perspective
        else "ReconstructBoundOrthoAoPosition"
    )
    medium_quality = "false" if low_quality else "true"
    if quality == "high":
        accepted_response = "-0.350000024"
        rejected_response = "0.649999976"
    else:
        accepted_response = "-0.180000007"
        rejected_response = "0.819999993"
    replacement = """#include "../indirect_cascade_upscale_ao_depth_bound.hlsl"

void mainPS(
  float4 v0 : SV_Position0,
  float2 v1 : UV0,
  float2 w1 : UNSCALED_UV0,
  out float2 o0 : SV_Target0)
{
  float2 pixelCoordinate = asuint(cb_vuViewportSize.xy);
  pixelCoordinate = w1.xy * pixelCoordinate;
  int2 pixel = (uint2)pixelCoordinate;
  float hzbDepth = tHzb.Load(int3(pixel, 0)).x;
  float backgroundDepth = -1.0 + cb_vNearFarViewCorner.y;
  if (hzbDepth >= backgroundDepth)
  {
    o0 = float2(1.0, 1.0);
    return;
  }

  UpscaledAo spatialAo = FilterBoundAoCross(pixel, hzbDepth);
  BoundAoPosition hzbSurface = __RECONSTRUCTOR__(w1, hzbDepth);
  float sceneDepth = LinearizeUpscaleDepth(
      tDepth.Load(int3(pixel, 0)).x,
      cb_xViewToProjection._m22, cb_xViewToProjection._m23);
  BoundAoPosition sceneSurface = __RECONSTRUCTOR__(w1, sceneDepth);
  float cascadeResponse = EvaluateBoundAoDepthCascade(
      pixel, sceneSurface, sceneDepth, __MEDIUM_QUALITY__);
  o0 = ResolveBoundAoCascadeTemporal(
      v1, hzbDepth, hzbSurface,
      float2(spatialAo.value, cascadeResponse),
      __ACCEPTED_RESPONSE__, __REJECTED_RESPONSE__);
}
"""
    return _BOUND_UPSCALE_MAIN.sub(
        replacement.replace("__RECONSTRUCTOR__", reconstructor)
        .replace("__MEDIUM_QUALITY__", medium_quality)
        .replace("__ACCEPTED_RESPONSE__", accepted_response)
        .replace("__REJECTED_RESPONSE__", rejected_response),
        source,
        count=1,
    )


def _lift_bound_cascade_depth_only_main(
    source: str, *, perspective: bool, quality: str
) -> str:
    """Lift cascade-only history using a full-resolution depth position."""
    low_quality = quality == "low"
    shadow_markers = (
        ("0.142857149", "int2(-1,-1)", "int2(1,1)")
        if low_quality
        else ("0.0588235296", "int2(-2,-2)", "int2(2,2)")
    )
    required = (
        "LinearizeUpscaleDepth(tDepth.Load(",
        "tTemporalAo.SampleLevel(",
        "tVolatile.Gather(",
        "0.330000013",
        "o0.xy = cascadeAddressState.yx;",
        *shadow_markers,
    )
    if any(marker not in source for marker in required):
        return source

    gather = (
        "GatherBoundPerspectiveCascadeSurface"
        if perspective
        else "GatherBoundOrthoCascadeSurface"
    )
    reconstruct = (
        "ReconstructBoundPerspectiveCascadePosition"
        if perspective
        else "ReconstructBoundOrthoCascadePosition"
    )
    evaluator = (
        "EvaluateBoundLowDepthCascadeOnlyLighting"
        if low_quality
        else "EvaluateBoundMediumDepthCascadeOnlyLighting"
    )
    temporal = (
        "ResolveBoundHighCascadeOnlyTemporal"
        if quality == "high"
        else "ResolveBoundLowMediumCascadeOnlyTemporal"
    )
    replacement = """#include "../indirect_cascade_upscale_cascade_depth_bound.hlsl"

void mainPS(
  float4 v0 : SV_Position0,
  float2 v1 : UV0,
  float2 w1 : UNSCALED_UV0,
  out float2 o0 : SV_Target0)
{
  float2 pixelCoordinate = asuint(cb_vuViewportSize.xy);
  pixelCoordinate = w1.xy * pixelCoordinate;
  int2 pixel = (uint2)pixelCoordinate;
  float hzbDepth = tHzb.Load(int3(pixel, 0)).x;
  float backgroundDepth = -1.0 + cb_vNearFarViewCorner.y;
  if (hzbDepth >= backgroundDepth)
  {
    o0 = float2(1.0, 1.0);
    return;
  }

  UpscaleCascadeSurface hzbSurface = __GATHER__(
      w1, pixel, hzbDepth);
  float sceneDepth = LinearizeUpscaleDepth(
      tDepth.Load(int3(pixel, 0)).x,
      cb_xViewToProjection._m22, cb_xViewToProjection._m23);
  float3 sceneWorldPosition = __RECONSTRUCT__(w1, sceneDepth);
  float currentVisibility = __EVALUATOR__(
      hzbSurface, sceneWorldPosition, sceneDepth);
  float resolvedVisibility = __TEMPORAL__(
      v1, hzbSurface, currentVisibility);
  o0 = float2(1.0, resolvedVisibility);
}
"""
    return _BOUND_UPSCALE_MAIN.sub(
        replacement.replace("__GATHER__", gather)
        .replace("__RECONSTRUCT__", reconstruct)
        .replace("__EVALUATOR__", evaluator)
        .replace("__TEMPORAL__", temporal),
        source,
        count=1,
    )


def _lift_bound_full_depth_no_history_main(
    source: str, *, perspective: bool, quality: str
) -> str:
    """Lift full output with a depth-derived, current-frame cascade."""
    low_quality = quality == "low"
    shadow_markers = (
        ("0.142857149", "int2(-1,-1)", "int2(1,1)")
        if low_quality
        else ("0.0588235296", "int2(-2,-2)", "int2(2,2)")
    )
    required = (
        "tIndirect_Ao.SampleLevel(",
        "tSSS.SampleLevel(",
        "tTemporalIndirect.SampleLevel(",
        "tTemporalAo.SampleLevel(",
        "tTemporalSSS.SampleLevel(",
        "LinearizeUpscaleDepth(tDepth.Load(",
        "GatherUpscaleDepthError(",
        "SwizzleUpscaleSss(",
        "o1.xyz = cascadeAddressState.zzz * viewDepthState.xyz",
        "o0.y = min(normalDecodeState.x, cascadeAddressState.y);",
        *shadow_markers,
    )
    if any(marker not in source for marker in required):
        return source

    gather = (
        "GatherBoundPerspectiveFullSurface"
        if perspective
        else "GatherBoundOrthoFullSurface"
    )
    reconstruct = (
        "ReconstructBoundPerspectiveCascadePosition"
        if perspective
        else "ReconstructBoundOrthoCascadePosition"
    )
    evaluator = (
        "EvaluateBoundLowFullDepthCascade"
        if low_quality
        else "EvaluateBoundMediumFullDepthCascade"
    )
    replacement = """#include "../indirect_cascade_upscale_full_depth_bound.hlsl"

void mainPS(
  float4 v0 : SV_Position0,
  float2 v1 : UV0,
  float2 w1 : UNSCALED_UV0,
  out float2 o0 : SV_Target0,
  out float3 o1 : SV_Target1,
  out float4 o2 : SV_Target2)
{
  float2 pixelCoordinate = asuint(cb_vuViewportSize.xy);
  pixelCoordinate = w1.xy * pixelCoordinate;
  int2 pixel = (uint2)pixelCoordinate;
  float hzbDepth = tHzb.Load(int3(pixel, 0)).x;
  float backgroundDepth = -1.0 + cb_vNearFarViewCorner.y;
  if (hzbDepth >= backgroundDepth)
  {
    o0 = float2(1.0, 1.0);
    o1 = float3(0.0, 0.0, 0.0);
    o2 = float4(1.0, 1.0, 1.0, 1.0);
    return;
  }

  UpscaleFullSurface surface = __GATHER__(w1, pixel, hzbDepth);
  float sceneDepth = LinearizeUpscaleDepth(
      tDepth.Load(int3(pixel, 0)).x,
      cb_xViewToProjection._m22, cb_xViewToProjection._m23);
  float3 sceneWorldPosition = __RECONSTRUCT__(w1, sceneDepth);
  UpscaleCascadeLighting cascade = __EVALUATOR__(
      surface, sceneWorldPosition, sceneDepth);
  UpscaleFullTemporalResult resolved =
      ResolveBoundFullDepthTemporalWithoutCascadeHistory(
          surface, cascade, v1, sceneDepth);

  o0 = float2(
      resolved.ao, min(resolved.sss.x, resolved.cascadeVisibility));
  o1 = resolved.indirect;
  o2 = resolved.sss;
}
"""
    return _BOUND_UPSCALE_MAIN.sub(
        replacement.replace("__GATHER__", gather)
        .replace("__RECONSTRUCT__", reconstruct)
        .replace("__EVALUATOR__", evaluator),
        source,
        count=1,
    )


def _lift_bound_ao_indirect_main(
    source: str, *, perspective: bool, quality: str
) -> str:
    """Lift paired AO/indirect spatial filtering and temporal rejection."""
    required = (
        "tIndirect_Ao.SampleLevel(",
        "tTemporalIndirect.SampleLevel(",
        "tTemporalAo.SampleLevel(",
        "GatherUpscaleDepthError(",
        "ComputeUpscaleGaussianWeight(",
        "ComputeUpscaleCoverageWeight(",
        "out float2 o0 : SV_Target0",
        "out float3 o1 : SV_Target1",
        "o0.y = 1;",
    )
    if any(marker not in source for marker in required):
        return source
    gather = (
        "GatherBoundPerspectiveAoIndirectSurface"
        if perspective
        else "GatherBoundOrthoAoIndirectSurface"
    )
    auxiliary_response = (
        "0.649999976" if quality == "high" else "0.819999993"
    )
    replacement = """#include "../indirect_cascade_upscale_ao_indirect_bound.hlsl"

void mainPS(
  float4 v0 : SV_Position0,
  float2 v1 : UV0,
  float2 w1 : UNSCALED_UV0,
  out float2 o0 : SV_Target0,
  out float3 o1 : SV_Target1)
{
  float2 pixelCoordinate = asuint(cb_vuViewportSize.xy);
  pixelCoordinate = w1.xy * pixelCoordinate;
  int2 pixel = (uint2)pixelCoordinate;
  float viewDepth = tHzb.Load(int3(pixel, 0)).x;
  float backgroundDepth = -1.0 + cb_vNearFarViewCorner.y;
  if (viewDepth >= backgroundDepth)
  {
    o0 = float2(1.0, 1.0);
    o1 = float3(0.0, 0.0, 0.0);
    return;
  }

  UpscaleAoIndirectSurface surface = __GATHER__(
      w1, pixel, viewDepth);
  o0 = ResolveBoundAoIndirectTemporal(
      v1, surface, __AUXILIARY_RESPONSE__);
  o1 = ResolveBoundIndirectTemporal(
      v1, surface.viewDepth, surface.worldPosition, surface.indirect);
}
"""
    return _BOUND_UPSCALE_MAIN.sub(
        replacement.replace("__GATHER__", gather).replace(
            "__AUXILIARY_RESPONSE__", auxiliary_response
        ),
        source,
        count=1,
    )


def _execution(blob: bytes) -> dict[str, Any]:
    abi = ShaderReflector().abi(blob)
    textures = [resource for resource in abi["resources"] if resource["type"] == 2]
    samplers = [resource for resource in abi["resources"] if resource["type"] == 3]
    outputs = abi["outputs"]
    target_count = max((output["index"] for output in outputs), default=0) + 1
    components = [4] * target_count
    for output in outputs:
        components[output["index"]] = max(1, output["mask"].bit_count())
    profiles = {0: "index", 5: "projection", 12: "index"}
    return {
        "kind": "fullscreen_indirect_cascade",
        "vertex_harness": "fullscreen_uv",
        "width": 1,
        "height": 1,
        "texture_slots": [resource["bind_point"] for resource in textures],
        "texture_kinds": [
            "2darray" if resource["dimension"] == 5 else "2d"
            for resource in textures
        ],
        "smooth_texture_slots": [resource["bind_point"] for resource in textures],
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
        ],
        "output": "color",
        "output_components": 4,
        "output_targets": target_count,
        "output_target_components": components,
    }


def _emit_variant_snippets(
    staging: Path, variants: dict[str, str]
) -> dict[str, str]:
    """Keep the 163 independently reflected ABI shapes out of one giant tree."""
    include_root = staging / "semantic" / "include"
    include_root.mkdir(parents=True, exist_ok=True)
    for helper_name in (
        "indirect_cascade_upscale_primitives.hlsl",
        "indirect_cascade_upscale_bound.hlsl",
        "indirect_cascade_upscale_cascade_bound.hlsl",
        "indirect_cascade_upscale_indirect_bound.hlsl",
        "indirect_cascade_upscale_sss_depth_bound.hlsl",
        "indirect_cascade_upscale_full_bound.hlsl",
        "indirect_cascade_upscale_ao_depth_bound.hlsl",
        "indirect_cascade_upscale_cascade_depth_bound.hlsl",
        "indirect_cascade_upscale_full_depth_bound.hlsl",
        "indirect_cascade_upscale_ao_indirect_bound.hlsl",
    ):
        (include_root / helper_name).write_text(
            asset(helper_name), encoding="utf-8", newline="\n"
        )
    snippet_root = (
        staging / "semantic" / "include" / "indirect_cascade_upscale"
    )
    snippet_root.mkdir(parents=True, exist_ok=True)
    bodies: dict[str, str] = {}
    for selector, source in variants.items():
        filename = f"{selector}.hlsl"
        source = source.replace('#include "include/', '#include "../')
        (snippet_root / filename).write_text(
            SEMANTIC_PHASE_MAP
            + '#include "../indirect_cascade_upscale_primitives.hlsl"\n\n'
            + source,
            encoding="utf-8",
            newline="\n",
        )
        bodies[selector] = (
            f'#include "include/indirect_cascade_upscale/{filename}"\n'
        )
    return bodies


def apply_indirect_cascade_upscale_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    shaders = [
        record
        for record in records
        if record["source_name"] == "indirect_cascade_upscale"
    ]
    if len(shaders) != 163 or any(shader["stage"] != "pixel" for shader in shaders):
        return None
    definitions = {shader["selector"]: shader["defines"] for shader in shaders}
    abi_includes = (
        ("CB_PERFRAME", "indirect_cascade_upscale_perframe_abi.hlsl"),
        ("CB_PROJECTION", "indirect_cascade_upscale_projection_abi.hlsl"),
        ("CB_SETTINGS", "indirect_cascade_upscale_settings_abi.hlsl"),
    )
    for cbuffer_name, filename in abi_includes:
        ensure_recovered_cbuffer_include(
            staging, "indirect_cascade_upscale", cbuffer_name, filename
        )
    variants = module_variants(
        (staging / "hlsl" / "indirect_cascade_upscale.hlsl").read_text(
            encoding="utf-8"
        ),
        definitions,
    )
    for selector, source in variants.items():
        source = re.sub(
            r"cb_arrCascades\[([^\]]+)/4\]\.(_m[0-9_]+)",
            r"cb_arrCascades[\1].\2",
            source,
        )
        source = rename_register_state(
            source, REGISTER_NAMES,
            note="Cascade gathers and rejection weights retain DXBC order.",
        )
        for cbuffer_name, filename in abi_includes:
            if f"cbuffer {cbuffer_name}" in source:
                source = replace_cbuffer_with_include(
                    source, cbuffer_name, filename
                )
        lifts = (
            _lift_depth_gathers,
            _lift_gaussian_weights,
            _lift_coverage_weights,
            _lift_linear_depth,
            _lift_normal_decodes,
            _lift_position_transforms,
            _lift_clip_transforms,
            _lift_volatility,
            _lift_sss_swizzles,
            _lift_cascade_selection,
        )
        for lift in lifts:
            source = lift(source)
        perspective = "ORTHO" not in definitions[selector]
        if perspective:
            source = _lift_perspective_cascade_selection(source)
        world_position = (
            "depthGatherState.xyz"
            if perspective else "sampleCoordinateState.xyz"
        )
        supports_seventeen_weight_pcf = (
            "PS_SHADER_QUALITY_MEDIUM" in definitions[selector]
            or (
                "PS_SHADER_QUALITY_HIGH" in definitions[selector]
                and not perspective
            )
        )
        if supports_seventeen_weight_pcf:
            source = _lift_medium_cascade_shadow(
                source, world_position
            )
            source = _lift_directional_facing(source)
            if not perspective:
                source = _lift_temporal_resolve(source)
        supports_low_pcf = "PS_SHADER_QUALITY_LOW" in definitions[selector]
        if supports_low_pcf:
            source = _lift_low_cascade_shadow(source, world_position)
            source = _lift_directional_facing(source)
            if not perspective:
                source = _lift_temporal_resolve(source)
        source = _lift_ao_sss_cross(source)
        source = _lift_material_responses(source)
        if supports_seventeen_weight_pcf and not perspective:
            source = _lift_bound_upscale_main(
                source, perspective=perspective
            )
            if "PS_DISABLE_CASCADE_TEMPORAL" in definitions[selector]:
                source = _lift_bound_no_cascade_history_main(
                    source, perspective=perspective
                )
        if supports_low_pcf and not perspective:
            source = _lift_bound_low_upscale_main(
                source,
                cascade_history=(
                    "PS_DISABLE_CASCADE_TEMPORAL"
                    not in definitions[selector]
                ),
                perspective=perspective,
            )
        feature_set = set(definitions[selector])
        cascade_only_temporal = (
            "PS_CASCADE" in feature_set
            and "ORTHO" not in feature_set
            and "PS_AO" not in feature_set
            and "PS_INDIRECT" not in feature_set
            and "PS_SSS" not in feature_set
            and "PS_CASCADE_FROM_DEPTH" not in feature_set
            and "PS_DISABLE_CASCADE_TEMPORAL" not in feature_set
        )
        if cascade_only_temporal:
            quality = next(
                name.removeprefix("PS_SHADER_QUALITY_").lower()
                for name in feature_set
                if name.startswith("PS_SHADER_QUALITY_")
            )
            source = _lift_bound_cascade_only_main(source, quality=quality)
        indirect_only_temporal = (
            "PS_INDIRECT" in feature_set
            and "PS_AO" not in feature_set
            and "PS_CASCADE" not in feature_set
            and "PS_SSS" not in feature_set
        )
        if indirect_only_temporal:
            source = _lift_bound_indirect_only_main(
                source, perspective=perspective
            )
        sss_depth_cascade = (
            "PS_SSS" in feature_set
            and "PS_CASCADE" in feature_set
            and "PS_CASCADE_FROM_DEPTH" in feature_set
            and "PS_DISABLE_CASCADE_TEMPORAL" in feature_set
            and "PS_AO" not in feature_set
            and "PS_INDIRECT" not in feature_set
        )
        if sss_depth_cascade:
            quality = next(
                name.removeprefix("PS_SHADER_QUALITY_").lower()
                for name in feature_set
                if name.startswith("PS_SHADER_QUALITY_")
            )
            source = _lift_bound_sss_depth_cascade_main(
                source, perspective=perspective, quality=quality
            )
        full_output_no_cascade_history = (
            "PS_AO" in feature_set
            and "PS_INDIRECT" in feature_set
            and "PS_SSS" in feature_set
            and "PS_CASCADE" in feature_set
            and "PS_DISABLE_CASCADE_TEMPORAL" in feature_set
            and "PS_CASCADE_FROM_DEPTH" not in feature_set
        )
        if full_output_no_cascade_history:
            quality = next(
                name.removeprefix("PS_SHADER_QUALITY_").lower()
                for name in feature_set
                if name.startswith("PS_SHADER_QUALITY_")
            )
            source = _lift_bound_full_output_main(
                source, perspective=perspective, quality=quality
            )
        ao_depth_cascade_temporal = (
            "PS_AO" in feature_set
            and "PS_CASCADE" in feature_set
            and "PS_CASCADE_FROM_DEPTH" in feature_set
            and "PS_DISABLE_CASCADE_TEMPORAL" not in feature_set
            and "PS_INDIRECT" not in feature_set
            and "PS_SSS" not in feature_set
        )
        if ao_depth_cascade_temporal:
            quality = next(
                name.removeprefix("PS_SHADER_QUALITY_").lower()
                for name in feature_set
                if name.startswith("PS_SHADER_QUALITY_")
            )
            source = _lift_bound_ao_depth_cascade_main(
                source, perspective=perspective, quality=quality
            )
        cascade_depth_only_temporal = (
            "PS_CASCADE" in feature_set
            and "PS_CASCADE_FROM_DEPTH" in feature_set
            and "PS_DISABLE_CASCADE_TEMPORAL" not in feature_set
            and "PS_AO" not in feature_set
            and "PS_INDIRECT" not in feature_set
            and "PS_SSS" not in feature_set
        )
        if cascade_depth_only_temporal:
            quality = next(
                name.removeprefix("PS_SHADER_QUALITY_").lower()
                for name in feature_set
                if name.startswith("PS_SHADER_QUALITY_")
            )
            source = _lift_bound_cascade_depth_only_main(
                source, perspective=perspective, quality=quality
            )
        full_depth_no_cascade_history = (
            "PS_AO" in feature_set
            and "PS_INDIRECT" in feature_set
            and "PS_SSS" in feature_set
            and "PS_CASCADE" in feature_set
            and "PS_CASCADE_FROM_DEPTH" in feature_set
            and "PS_DISABLE_CASCADE_TEMPORAL" in feature_set
        )
        if full_depth_no_cascade_history:
            quality = next(
                name.removeprefix("PS_SHADER_QUALITY_").lower()
                for name in feature_set
                if name.startswith("PS_SHADER_QUALITY_")
            )
            source = _lift_bound_full_depth_no_history_main(
                source, perspective=perspective, quality=quality
            )
        ao_indirect_temporal = (
            "PS_AO" in feature_set
            and "PS_INDIRECT" in feature_set
            and "PS_SSS" not in feature_set
            and "PS_CASCADE" not in feature_set
        )
        if ao_indirect_temporal:
            quality = next(
                name.removeprefix("PS_SHADER_QUALITY_").lower()
                for name in feature_set
                if name.startswith("PS_SHADER_QUALITY_")
            )
            source = _lift_bound_ao_indirect_main(
                source, perspective=perspective, quality=quality
            )
        variants[selector] = source
    bodies = _emit_variant_snippets(staging, variants)
    return emit_validated_module(
        staging,
        shaders,
        blobs,
        compiler,
        recipe_name="indirect_cascade_upscale",
        bodies=bodies,
        executions={
            shader["selector"]: _execution(blobs[shader["bundle_index"]])
            for shader in shaders
        },
    )
