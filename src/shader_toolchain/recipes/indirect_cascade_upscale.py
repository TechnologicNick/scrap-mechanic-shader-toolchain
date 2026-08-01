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

_BOUND_PERSPECTIVE_AO_SSS_TEMPORAL_TAIL = re.compile(
    r"^  cascadeAddressState\.[zw] = min\(viewDepthState\.z, "
    r"cascadeAddressState\.x\);.*?^\}\s*$",
    re.MULTILINE | re.DOTALL,
)


def _lift_bound_perspective_ao_sss_temporal_tail(
    source: str, *, cascade_history: bool
) -> str:
    """Keep the exact perspective cascade dataflow and lift its history tail."""
    if cascade_history:
        replacement = """  UpscaleSurface surface;
  surface.pixel = (int2)cascadeAddressState.xy;
  surface.viewDepth = viewDepthState.x;
  surface.viewPosition = sampleCoordinateState.xyz;
  surface.worldPosition = depthGatherState.xyz;
  surface.ao = viewDepthState.w;
  surface.sss = float4(normalDecodeState.x, cascadeSelectionState.xyz);
  surface.sssComplement = viewDepthState.y;
  surface.sssOcclusion = viewDepthState.z;
  UpscaleCascadeLighting cascade;
  cascade.shadowResponse = cascadeAddressState.x;
  cascade.visibility = cascadeAddressState.y;
  UpscaleTemporalResult resolved =
      ResolveBoundUpscaleTemporal(surface, cascade, v1);
  normalDecodeState = resolved.sss;
  o0.x = resolved.ao;
  o0.y = min(normalDecodeState.x, resolved.cascadeVisibility);
  o2 = normalDecodeState;
}
"""
    else:
        replacement = """  UpscaleTemporalResult resolved =
      ResolveUpscaleTemporalWithoutCascadeHistory(
      tTemporalAo, tTemporalSSS, tVolatile, LinearClampClamp_s,
      v1, viewDepthState.x, sampleCoordinateState.xyz,
      depthGatherState.xyz, viewDepthState.w,
      float4(normalDecodeState.x, cascadeSelectionState.xyz),
      viewDepthState.y, viewDepthState.z, cascadeAddressState.x,
      cb_xPrevWorldToViewProjection,
      cb_xPrevViewToWorld._m03_m13_m23, viewToWorld._m03_m13_m23,
      cb_vPrevRenderScale, cb_vPrevUvLimit, cb_fRenderScaleStability,
      cb_fFrameRateScale, cb_settings.vuSSSwaps);
  normalDecodeState = resolved.sss;
  o0.x = resolved.ao;
  o0.y = min(normalDecodeState.x, cascadeAddressState.y);
  o2 = normalDecodeState;
}
"""
    lifted = _BOUND_PERSPECTIVE_AO_SSS_TEMPORAL_TAIL.sub(
        replacement, source, count=1
    )
    if lifted == source:
        return source
    if cascade_history:
        lifted = lifted.replace(
            "#define cmp -\n\n\n",
            '#define cmp -\n#include "../indirect_cascade_upscale_bound.hlsl"\n\n',
            1,
        )
    lifted = re.sub(
        r"  const float4 icb\[\] = \{.*?\};\n",
        "",
        lifted,
        count=1,
        flags=re.DOTALL,
    )
    lifted = re.sub(
        r"  float4 cascadeAddressState.*?;\n"
        r"  // Cascade gathers and rejection weights retain DXBC order\.\n"
        r"  uint4 packedBitmask, integerDestination;\n"
        r"  float4 floatDestination;\n",
        "  float4 cascadeAddressState, viewDepthState, normalDecodeState;\n"
        "  float4 cascadeSelectionState, sampleCoordinateState;\n"
        "  float4 depthGatherState, normalGatherState;\n",
        lifted,
        count=1,
    )
    lifted = lifted.replace(
        "// Reconstructed Scrap Mechanic shader module: "
        "indirect_cascade_upscale.hlsl\n"
        "// Shared code is factored; define exactly one "
        "SM_SHADER_<key> selector.\n\n\n",
        "",
        1,
    )
    lifted = lifted.replace("// Lifted with 3Dmigoto v1.4.9\n\n", "", 1)
    lifted = lifted.replace("// 3Dmigoto declarations\n", "", 1)
    lifted = re.sub(r"\n{3,}", "\n\n", lifted)
    return "// COMPACT_BOUND_VARIANT\n" + lifted


def _bound_upscale_main(
    resolver: str,
    cascade_evaluator: str = "EvaluateBoundUpscaleCascadeLighting",
    surface_gather: str = "GatherBoundUpscaleSurface",
) -> str:
    surface_block = """  UpscaleSurface surface = __SURFACE_GATHER__(
      w1, pixel, viewDepth);"""
    cascade_block = """  UpscaleCascadeLighting cascade =
      __CASCADE_EVALUATOR__(surface);"""
    if surface_gather == "GatherBoundPerspectiveUpscaleSurface":
        surface_block = """  UpscaledAoSss spatial = FilterAoSssCross(
      tAoDepth, tIndirect_Ao, tSSS, tMaterial, LinearClampClamp_s,
      pixel, viewDepth, cb_vTargetSize.xy,
      cb_vRenderScale.xy, cb_vContainerPixelSize.xy,
      cb_settings.vInvScale.xy, cb_settings.vUvLimit.xy,
      cb_f720To4K, cb_uFrameCount, cb_fFrameRateScale);
  float2 clipPosition =
      w1 * float2(1.0, -1.0) + float2(0.0, 1.0);
  clipPosition =
      clipPosition * float2(2.0, 2.0) + float2(-1.0, -1.0);
  float3 viewPosition;
  viewPosition.xy = cb_vNearFarViewCorner.zw * clipPosition;
  viewPosition.xy = viewPosition.xy * viewDepth.xx;
  viewPosition.z = -viewDepth;
  UpscaleSurface surface;
  surface.pixel = pixel;
  surface.viewDepth = viewDepth;
  surface.viewPosition = viewPosition;
  surface.worldPosition =
      TransformUpscalePosition(viewToWorld, viewPosition);
  surface.ao = spatial.ao;
  surface.sss = spatial.sss;
  bool hasGeometry = viewDepth < UPSCALE_DEPTH_RANGE;
  surface.sssComplement =
      hasGeometry ? 1.0 + -spatial.sss.x : 0.0;
  surface.sssOcclusion =
      hasGeometry ? spatial.sss.x : 1.0;"""
        cascade_shadow = (
            "EvaluateUpscaleLowCascadeShadow"
            if cascade_evaluator == "EvaluateBoundLowUpscaleCascadeLighting"
            else "EvaluateUpscaleMediumCascadeShadow"
        )
        cascade_block = """  UpscaleCascadeLighting cascade;
  if (0.00999999978 < surface.sssOcclusion)
  {
    float3 normal = DecodeUpscaleNormal(
        tNormal.Load(int3(surface.pixel, 0)).xy);
    float cameraRangeFade =
        -surface.viewDepth * cb_vInverseCameraRange.x + 1.0;
    UpscaleCascadeSelection activeCascade = SelectUpscaleCascade(
        surface.worldPosition,
        cb_arrCascades[0], cb_arrCascades[1],
        cb_arrCascades[2], cb_arrCascades[3]);
    cascade.shadowResponse = __CASCADE_SHADOW__(
        taCascades, sShadowSamplerLinear_s, activeCascade,
        surface.worldPosition, cameraRangeFade,
        cb_vCascadeSplits, cb_vCascadeSize, cb_vCascadePixelSize,
        cb_arrCascades[1], cb_arrCascades[2], cb_arrCascades[3]);
    cascade.shadowResponse = ApplyUpscaleDirectionalFacing(
        cascade.shadowResponse, normal,
        cb_vDirectionalLightDirectionView.xyz);
    cascade.visibility = cascade.shadowResponse;
  }
  else
  {
    cascade.shadowResponse = 0.0;
    cascade.visibility = 1.0;
  }""".replace("__CASCADE_SHADOW__", cascade_shadow)
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

__SURFACE_BLOCK__
__CASCADE_BLOCK__
  UpscaleTemporalResult resolved = __RESOLVER__(
      surface, cascade, v1);

  o0.x = resolved.ao;
  o0.y = min(resolved.sss.x, resolved.cascadeVisibility);
  o2 = resolved.sss;
}
"""
    return template.replace("__RESOLVER__", resolver).replace(
        "__SURFACE_BLOCK__", surface_block
    ).replace("__SURFACE_GATHER__", surface_gather).replace(
        "__CASCADE_BLOCK__", cascade_block
    ).replace(
        "__CASCADE_EVALUATOR__", cascade_evaluator
    )


def _lift_bound_upscale_main(
    source: str, *, perspective: bool = False
) -> str:
    """Replace the full-history register shell with typed family operations."""
    required = (
        "UpscaledAoSss spatialAoSss = FilterAoSssCross(",
        "tTemporalAo.SampleLevel(",
        "tTemporalSSS.SampleLevel(",
        "o0.y = min(normalDecodeState.x, cascadeAddressState.y);",
    )
    if any(marker not in source for marker in required):
        return source
    if perspective:
        return _lift_bound_perspective_ao_sss_temporal_tail(
            source, cascade_history=True
        )
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
    if perspective:
        return _lift_bound_perspective_ao_sss_temporal_tail(
            source, cascade_history=False
        )
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
        "o0.y = min(normalDecodeState.x, cascadeAddressState.y);",
    )
    if any(marker not in source for marker in required):
        return source
    if cascade_history:
        if (
            "tTemporalAo.SampleLevel(" not in source
            or "tTemporalSSS.SampleLevel(" not in source
        ):
            return source
        resolver = "ResolveBoundUpscaleTemporal"
        if perspective:
            return _lift_bound_perspective_ao_sss_temporal_tail(
                source, cascade_history=True
            )
    else:
        if "tTemporalSSS.SampleLevel(" not in source:
            return source
        resolver = "ResolveBoundUpscaleTemporalWithoutCascadeHistory"
        if perspective:
            return _lift_bound_perspective_ao_sss_temporal_tail(
                source, cascade_history=False
            )
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
    source: str, *, quality: str, perspective: bool = True
) -> str:
    """Lift cascade-only temporal permutations."""
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
    bound_include = (
        "indirect_cascade_upscale_cascade_bound.hlsl"
        if perspective
        else "indirect_cascade_upscale_cascade_depth_bound.hlsl"
    )
    surface_gather = (
        "GatherBoundPerspectiveCascadeSurface"
        if perspective
        else "GatherBoundOrthoCascadeSurface"
    )
    replacement = """#include "../__BOUND_INCLUDE__"

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
      __SURFACE_GATHER__(w1, pixel, viewDepth);
  float cascadeVisibility =
      __CASCADE_EVALUATOR__(surface);
  cascadeVisibility = __TEMPORAL_RESOLVER__(
      v1, surface, cascadeVisibility);
  o0 = float2(1.0, cascadeVisibility);
}
"""
    replacement = replacement.replace(
        "__BOUND_INCLUDE__", bound_include
    ).replace("__SURFACE_GATHER__", surface_gather)
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


def _lift_bound_cascade_no_history_main(
    source: str, *, quality: str, perspective: bool
) -> str:
    """Lift cascade-only permutations that intentionally bypass history."""
    low_quality = quality == "low"
    shadow_markers = (
        ("0.142857149", "int2(-1,-1)", "int2(1,1)")
        if low_quality
        else ("0.0588235296", "int2(-2,-2)", "int2(2,2)")
    )
    required = (
        "0.330000013",
        "out float2 o0 : SV_Target0",
        "o0.xy = cascadeAddressState.yx;",
        *shadow_markers,
    )
    if any(marker not in source for marker in required):
        return source
    bound_include = (
        "indirect_cascade_upscale_cascade_bound.hlsl"
        if perspective
        else "indirect_cascade_upscale_cascade_depth_bound.hlsl"
    )
    gather = (
        "GatherBoundPerspectiveCascadeSurface"
        if perspective
        else "GatherBoundOrthoCascadeSurface"
    )
    evaluator = (
        "EvaluateBoundLowCascadeOnlyLighting"
        if low_quality
        else "EvaluateBoundMediumCascadeOnlyLighting"
    )
    replacement = """SamplerState LinearClampClamp_s : register(s6);
Texture2D<float2> tTemporalAo : register(t1);
Texture2D<float> tVolatile : register(t9);
#include "../__BOUND_INCLUDE__"

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

  UpscaleCascadeSurface surface = __GATHER__(
      w1, pixel, viewDepth);
  float visibility = __EVALUATOR__(surface);
  o0 = float2(1.0, visibility);
}
"""
    return _BOUND_UPSCALE_MAIN.sub(
        replacement.replace("__BOUND_INCLUDE__", bound_include)
        .replace("__GATHER__", gather)
        .replace("__EVALUATOR__", evaluator),
        source,
        count=1,
    )


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


def _lift_bound_sss_only_main(
    source: str, *, perspective: bool
) -> str:
    """Lift SSS-only filtering and temporal reprojection."""
    required = (
        "tSSS.SampleLevel(",
        "tTemporalSSS.SampleLevel(",
        "GatherUpscaleDepthError(",
        "ComputeUpscaleGaussianWeight(",
        "ComputeUpscaleCoverageWeight(",
        "SwizzleUpscaleSss(",
        "out float4 o2 : SV_Target2",
    )
    if any(marker not in source for marker in required):
        return source
    reconstructor = (
        "ReconstructBoundPerspectiveSssPosition"
        if perspective
        else "ReconstructBoundOrthoSssPosition"
    )
    replacement = """#define INDIRECT_CASCADE_UPSCALE_SSS_NO_CASCADE
#include "../indirect_cascade_upscale_sss_depth_bound.hlsl"

void mainPS(
  float4 v0 : SV_Position0,
  float2 v1 : UV0,
  float2 w1 : UNSCALED_UV0,
  out float4 o2 : SV_Target2)
{
  float2 pixelCoordinate = asuint(cb_vuViewportSize.xy);
  pixelCoordinate = w1.xy * pixelCoordinate;
  int2 pixel = (uint2)pixelCoordinate;
  float viewDepth = tHzb.Load(int3(pixel, 0)).x;
  float backgroundDepth = -1.0 + cb_vNearFarViewCorner.y;
  if (viewDepth >= backgroundDepth)
  {
    o2 = float4(1.0, 1.0, 1.0, 1.0);
    return;
  }

  UpscaledSss spatial = FilterBoundSssCross(pixel, viewDepth);
  BoundSssPosition surface =
      __POSITION_RECONSTRUCTOR__(w1, viewDepth);
  o2 = ResolveBoundSssOnlyTemporal(v1, viewDepth, surface, spatial.value);
}
"""
    replacement = replacement.replace(
        "__POSITION_RECONSTRUCTOR__", reconstructor
    )
    return _BOUND_UPSCALE_MAIN.sub(replacement, source, count=1)


def _lift_bound_indirect_sss_main(
    source: str, *, perspective: bool
) -> str:
    """Lift the shared indirect/SSS filter and their temporal outputs."""
    required = (
        "tSSS.SampleLevel(",
        "tTemporalSSS.SampleLevel(",
        "tTemporalIndirect.SampleLevel(",
        "GatherUpscaleDepthError(",
        "ComputeUpscaleGaussianWeight(",
        "ComputeUpscaleCoverageWeight(",
        "out float3 o1 : SV_Target1",
        "out float4 o2 : SV_Target2",
    )
    if any(marker not in source for marker in required):
        return source
    reconstructor = (
        "ReconstructBoundPerspectiveSssPosition"
        if perspective
        else "ReconstructBoundOrthoSssPosition"
    )
    replacement = """#include "../indirect_cascade_upscale_indirect_bound.hlsl"
#define INDIRECT_CASCADE_UPSCALE_SSS_NO_CASCADE
#include "../indirect_cascade_upscale_sss_depth_bound.hlsl"

void mainPS(
  float4 v0 : SV_Position0,
  float2 v1 : UV0,
  float2 w1 : UNSCALED_UV0,
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
    o1 = float3(0.0, 0.0, 0.0);
    o2 = float4(1.0, 1.0, 1.0, 1.0);
    return;
  }

  UpscaledIndirect indirect = FilterBoundIndirectCross(pixel, viewDepth);
  UpscaledSss sss = FilterBoundSssCross(pixel, viewDepth);
  BoundSssPosition surface =
      __POSITION_RECONSTRUCTOR__(w1, viewDepth);
  o1 = ResolveBoundIndirectTemporal(
      v1, viewDepth, surface.worldPosition, indirect);
  o2 = ResolveBoundSssOnlyTemporal(
      v1, viewDepth, surface, sss.value);
}
"""
    replacement = replacement.replace(
        "__POSITION_RECONSTRUCTOR__", reconstructor
    )
    return _BOUND_UPSCALE_MAIN.sub(replacement, source, count=1)


def _lift_bound_ao_only_main(
    source: str, *, perspective: bool, quality: str
) -> str:
    """Lift AO filtering and its packed two-channel temporal history."""
    required = (
        "tIndirect_Ao.SampleLevel(",
        "tTemporalAo.SampleLevel(",
        "GatherUpscaleDepthError(",
        "ComputeUpscaleGaussianWeight(",
        "ComputeUpscaleCoverageWeight(",
        "out float2 o0 : SV_Target0",
        "o0.y = 1;",
    )
    if any(marker not in source for marker in required):
        return source
    reconstructor = (
        "ReconstructBoundPerspectiveAoPosition"
        if perspective
        else "ReconstructBoundOrthoAoPosition"
    )
    rejected_response = (
        "0.649999976" if quality == "high" else "0.819999993"
    )
    replacement = """#define INDIRECT_CASCADE_UPSCALE_AO_NO_CASCADE
#include "../indirect_cascade_upscale_ao_depth_bound.hlsl"

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

  UpscaledAo spatial = FilterBoundAoCross(pixel, viewDepth);
  BoundAoPosition surface =
      __POSITION_RECONSTRUCTOR__(w1, viewDepth);
  o0 = ResolveBoundAoCascadeTemporal(
      v1, viewDepth, surface, float2(spatial.value, 1.0),
      0.0, __REJECTED_RESPONSE__);
}
"""
    replacement = replacement.replace(
        "__POSITION_RECONSTRUCTOR__", reconstructor
    ).replace("__REJECTED_RESPONSE__", rejected_response)
    return _BOUND_UPSCALE_MAIN.sub(replacement, source, count=1)


def _lift_bound_ao_sss_main(
    source: str, *, perspective: bool, quality: str
) -> str:
    """Lift parallel AO and SSS filtering with shared reprojection policy."""
    required = (
        "tIndirect_Ao.SampleLevel(",
        "tTemporalAo.SampleLevel(",
        "tSSS.SampleLevel(",
        "tTemporalSSS.SampleLevel(",
        "GatherUpscaleDepthError(",
        "ComputeUpscaleCoverageWeight(",
        "out float2 o0 : SV_Target0",
        "out float4 o2 : SV_Target2",
    )
    if any(marker not in source for marker in required):
        return source
    ao_reconstructor = (
        "ReconstructBoundPerspectiveAoPosition"
        if perspective
        else "ReconstructBoundOrthoAoPosition"
    )
    sss_reconstructor = (
        "ReconstructBoundPerspectiveSssPosition"
        if perspective
        else "ReconstructBoundOrthoSssPosition"
    )
    rejected_response = (
        "0.649999976" if quality == "high" else "0.819999993"
    )
    replacement = """#define INDIRECT_CASCADE_UPSCALE_AO_NO_CASCADE
#include "../indirect_cascade_upscale_ao_depth_bound.hlsl"
#define INDIRECT_CASCADE_UPSCALE_SSS_NO_CASCADE
#include "../indirect_cascade_upscale_sss_depth_bound.hlsl"

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
  float viewDepth = tHzb.Load(int3(pixel, 0)).x;
  float backgroundDepth = -1.0 + cb_vNearFarViewCorner.y;
  if (viewDepth >= backgroundDepth)
  {
    o0 = float2(1.0, 1.0);
    o2 = float4(1.0, 1.0, 1.0, 1.0);
    return;
  }

  UpscaledAo ao = FilterBoundAoCross(pixel, viewDepth);
  UpscaledSss sss = FilterBoundSssCross(pixel, viewDepth);
  BoundAoPosition aoSurface =
      __AO_RECONSTRUCTOR__(w1, viewDepth);
  BoundSssPosition sssSurface =
      __SSS_RECONSTRUCTOR__(w1, viewDepth);
  o0 = ResolveBoundAoCascadeTemporal(
      v1, viewDepth, aoSurface, float2(ao.value, 1.0),
      0.0, __REJECTED_RESPONSE__);
  o2 = ResolveBoundSssOnlyTemporal(
      v1, viewDepth, sssSurface, sss.value);
}
"""
    replacement = replacement.replace(
        "__AO_RECONSTRUCTOR__", ao_reconstructor
    ).replace(
        "__SSS_RECONSTRUCTOR__", sss_reconstructor
    ).replace("__REJECTED_RESPONSE__", rejected_response)
    return _BOUND_UPSCALE_MAIN.sub(replacement, source, count=1)


def _lift_bound_cascade_indirect_main(
    source: str, *, perspective: bool, quality: str
) -> str:
    """Lift independent cascade and indirect temporal outputs."""
    shadow_markers = (
        ("0.142857149", "int2(-1,-1)", "int2(1,1)")
        if quality == "low"
        else ("0.0588235296", "int2(-2,-2)", "int2(2,2)")
    )
    required = (
        "tTemporalAo.SampleLevel(",
        "tTemporalIndirect.SampleLevel(",
        "tIndirect_Ao.SampleLevel(",
        "GatherUpscaleDepthError(",
        "out float2 o0 : SV_Target0",
        "out float3 o1 : SV_Target1",
        *shadow_markers,
    )
    if any(marker not in source for marker in required):
        return source
    bound_include = (
        "indirect_cascade_upscale_cascade_bound.hlsl"
        if perspective
        else "indirect_cascade_upscale_cascade_depth_bound.hlsl"
    )
    surface_gather = (
        "GatherBoundPerspectiveCascadeSurface"
        if perspective
        else "GatherBoundOrthoCascadeSurface"
    )
    cascade_evaluator = (
        "EvaluateBoundLowCascadeOnlyLighting"
        if quality == "low"
        else "EvaluateBoundMediumCascadeOnlyLighting"
    )
    cascade_resolver = (
        "ResolveBoundHighCascadeOnlyTemporal"
        if quality == "high"
        else "ResolveBoundLowMediumCascadeOnlyTemporal"
    )
    replacement = """#include "../__BOUND_INCLUDE__"
#include "../indirect_cascade_upscale_indirect_bound.hlsl"

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

  UpscaleCascadeSurface cascadeSurface =
      __SURFACE_GATHER__(w1, pixel, viewDepth);
  float cascadeVisibility =
      __CASCADE_EVALUATOR__(cascadeSurface);
  cascadeVisibility = __CASCADE_RESOLVER__(
      v1, cascadeSurface, cascadeVisibility);
  UpscaledIndirect indirect = FilterBoundIndirectCross(pixel, viewDepth);
  o0 = float2(1.0, cascadeVisibility);
  o1 = ResolveBoundIndirectTemporal(
      v1, viewDepth, cascadeSurface.worldPosition, indirect);
}
"""
    replacement = replacement.replace(
        "__BOUND_INCLUDE__", bound_include
    ).replace(
        "__SURFACE_GATHER__", surface_gather
    ).replace(
        "__CASCADE_EVALUATOR__", cascade_evaluator
    ).replace("__CASCADE_RESOLVER__", cascade_resolver)
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


def _lift_bound_cascade_depth_no_history_main(
    source: str, *, perspective: bool, quality: str
) -> str:
    """Lift depth-derived cascade-only permutations without history."""
    low_quality = quality == "low"
    shadow_markers = (
        ("0.142857149", "int2(-1,-1)", "int2(1,1)")
        if low_quality
        else ("0.0588235296", "int2(-2,-2)", "int2(2,2)")
    )
    required = (
        "LinearizeUpscaleDepth(tDepth.Load(",
        "0.330000013",
        "out float2 o0 : SV_Target0",
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
    replacement = """SamplerState LinearClampClamp_s : register(s6);
Texture2D<float2> tTemporalAo : register(t1);
Texture2D<float> tVolatile : register(t9);
#include "../indirect_cascade_upscale_cascade_depth_bound.hlsl"

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
  float visibility = __EVALUATOR__(
      hzbSurface, sceneWorldPosition, sceneDepth);
  o0 = float2(1.0, visibility);
}
"""
    return _BOUND_UPSCALE_MAIN.sub(
        replacement.replace("__GATHER__", gather)
        .replace("__RECONSTRUCT__", reconstruct)
        .replace("__EVALUATOR__", evaluator),
        source,
        count=1,
    )


def _lift_bound_cascade_payload_no_history_main(
    source: str,
    *,
    perspective: bool,
    quality: str,
    from_depth: bool,
    indirect: bool,
    sss: bool,
) -> str:
    """Compose a current-frame cascade with optional indirect and SSS history."""
    low_quality = quality == "low"
    shadow_markers = (
        ("0.142857149", "int2(-1,-1)", "int2(1,1)")
        if low_quality
        else ("0.0588235296", "int2(-2,-2)", "int2(2,2)")
    )
    required = [
        "out float2 o0 : SV_Target0",
        *shadow_markers,
    ]
    if from_depth:
        required.append("LinearizeUpscaleDepth(tDepth.Load(")
    if indirect:
        required.extend(
            (
                "tIndirect_Ao.SampleLevel(",
                "tTemporalAo.SampleLevel(",
                "tTemporalIndirect.SampleLevel(",
                "out float3 o1 : SV_Target1",
            )
        )
    if sss:
        required.extend(
            (
                "tSSS.SampleLevel(",
                "tTemporalSSS.SampleLevel(",
                "out float4 o2 : SV_Target2",
                "0.959999979",
            )
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
    sss_reconstruct = (
        "ReconstructBoundPerspectiveSssPosition"
        if perspective
        else "ReconstructBoundOrthoSssPosition"
    )
    if from_depth:
        evaluator = (
            "EvaluateBoundLowDepthCascadeOnlyLighting"
            if low_quality
            else "EvaluateBoundMediumDepthCascadeOnlyLighting"
        )
        cascade_block = """  float sceneDepth = LinearizeUpscaleDepth(
      tDepth.Load(int3(pixel, 0)).x,
      cb_xViewToProjection._m22, cb_xViewToProjection._m23);
  float3 sceneWorldPosition = __RECONSTRUCT__(w1, sceneDepth);
  float visibility = __EVALUATOR__(
      surface, sceneWorldPosition, sceneDepth);
"""
    else:
        evaluator = (
            "EvaluateBoundLowCascadeOnlyLighting"
            if low_quality
            else "EvaluateBoundMediumCascadeOnlyLighting"
        )
        cascade_block = """  float visibility = __EVALUATOR__(surface);
"""

    includes = []
    if "Texture2D<float2> tTemporalAo : register(t1);" not in source:
        includes.append("Texture2D<float2> tTemporalAo : register(t1);")
    includes.append(
        '#include "../indirect_cascade_upscale_cascade_depth_bound.hlsl"'
    )
    signature = ["  out float2 o0 : SV_Target0"]
    background = ["    o0 = float2(1.0, 1.0);"]
    payload = []
    outputs = []
    if indirect:
        includes.append(
            '#include "../indirect_cascade_upscale_ao_indirect_bound.hlsl"'
        )
        signature.append("  out float3 o1 : SV_Target1")
        background.append("    o1 = float3(0.0, 0.0, 0.0);")
        ao_indirect_gather = (
            "GatherBoundPerspectiveAoIndirectSurface"
            if perspective
            else "GatherBoundOrthoAoIndirectSurface"
        )
        auxiliary_response = (
            "0.649999976" if quality == "high" else "0.819999993"
        )
        payload.append(
            """  UpscaleAoIndirectSurface aoIndirectSurface =
      __AO_INDIRECT_GATHER__(w1, pixel, viewDepth);
  float2 resolvedAo = ResolveBoundAoIndirectTemporal(
      v1, aoIndirectSurface, __AUXILIARY_RESPONSE__);
  float3 resolvedIndirect = ResolveBoundIndirectTemporal(
      v1, viewDepth, aoIndirectSurface.worldPosition,
      aoIndirectSurface.indirect);
"""
            .replace("__AO_INDIRECT_GATHER__", ao_indirect_gather)
            .replace("__AUXILIARY_RESPONSE__", auxiliary_response)
        )
        outputs.append("  o1 = resolvedIndirect;")
    if sss:
        includes.extend(
            (
                "#define INDIRECT_CASCADE_UPSCALE_SSS_NO_CASCADE",
                '#include "../indirect_cascade_upscale_sss_depth_bound.hlsl"',
            )
        )
        signature.append("  out float4 o2 : SV_Target2")
        background.append("    o2 = float4(1.0, 1.0, 1.0, 1.0);")
        payload.append(
            """  UpscaledSss sss = FilterBoundSssCross(pixel, viewDepth);
  BoundSssPosition sssSurface =
      __SSS_RECONSTRUCT__(w1, viewDepth);
  float4 resolvedSss = ResolveBoundSssTemporal(
      v1, viewDepth, sssSurface, sss.value);
"""
        )
        outputs.append("  o2 = resolvedSss;")
        outputs.insert(
            0,
            "  o0 = float2("
            + ("resolvedAo.x" if indirect else "1.0")
            + ", min(resolvedSss.x, visibility));",
        )
    else:
        outputs.insert(
            0,
            "  o0 = float2("
            + ("resolvedAo.x" if indirect else "1.0")
            + ", visibility);",
        )

    replacement = """__INCLUDES__

void mainPS(
  float4 v0 : SV_Position0,
  float2 v1 : UV0,
  float2 w1 : UNSCALED_UV0,
__SIGNATURE__)
{
  float2 pixelCoordinate = asuint(cb_vuViewportSize.xy);
  pixelCoordinate = w1.xy * pixelCoordinate;
  int2 pixel = (uint2)pixelCoordinate;
  float viewDepth = tHzb.Load(int3(pixel, 0)).x;
  float backgroundDepth = -1.0 + cb_vNearFarViewCorner.y;
  if (viewDepth >= backgroundDepth)
  {
__BACKGROUND__
    return;
  }

  UpscaleCascadeSurface surface = __GATHER__(
      w1, pixel, viewDepth);
__CASCADE_BLOCK__
__PAYLOAD__
__OUTPUTS__
}
"""
    replacement = (
        replacement.replace("__INCLUDES__", "\n".join(includes))
        .replace("__SIGNATURE__", ",\n".join(signature))
        .replace("__BACKGROUND__", "\n".join(background))
        .replace("__GATHER__", gather)
        .replace("__CASCADE_BLOCK__", cascade_block)
        .replace("__PAYLOAD__", "\n".join(payload))
        .replace("__OUTPUTS__", "\n".join(outputs))
        .replace("__RECONSTRUCT__", reconstruct)
        .replace("__SSS_RECONSTRUCT__", sss_reconstruct)
        .replace("__EVALUATOR__", evaluator)
    )
    return _BOUND_UPSCALE_MAIN.sub(replacement, source, count=1)


def _lift_bound_ao_cascade_no_history_main(
    source: str,
    *,
    perspective: bool,
    quality: str,
    from_depth: bool,
    sss: bool,
) -> str:
    """Compose AO history with a current-frame cascade and optional SSS."""
    low_quality = quality == "low"
    shadow_markers = (
        ("0.142857149", "int2(-1,-1)", "int2(1,1)")
        if low_quality
        else ("0.0588235296", "int2(-2,-2)", "int2(2,2)")
    )
    required = [
        "tIndirect_Ao.SampleLevel(",
        "tTemporalAo.SampleLevel(",
        "out float2 o0 : SV_Target0",
        *shadow_markers,
    ]
    if from_depth:
        required.append("LinearizeUpscaleDepth(tDepth.Load(")
    if sss:
        required.extend(
            (
                "tSSS.SampleLevel(",
                "tTemporalSSS.SampleLevel(",
                "SwizzleUpscaleSss(",
                "out float4 o2 : SV_Target2",
                "0.959999979",
            )
        )
    if any(marker not in source for marker in required):
        return source

    if from_depth and sss:
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
        temporal_indirect_declaration = (
            ""
            if "Texture2D<float3> tTemporalIndirect : register(t6);" in source
            else "Texture2D<float3> tTemporalIndirect : register(t6);\n"
        )
        replacement = """__TEMPORAL_INDIRECT_DECLARATION__#include "../indirect_cascade_upscale_full_depth_bound.hlsl"

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

  UpscaleFullSurface surface = __GATHER__(w1, pixel, hzbDepth);
  float sceneDepth = LinearizeUpscaleDepth(
      tDepth.Load(int3(pixel, 0)).x,
      cb_xViewToProjection._m22, cb_xViewToProjection._m23);
  float3 sceneWorldPosition = __RECONSTRUCT__(w1, sceneDepth);
  UpscaleCascadeLighting cascade = __EVALUATOR__(
      surface, sceneWorldPosition, sceneDepth);
  UpscaleTemporalResult resolved = ResolveBoundFullDepthAoSssTemporal(
      surface, cascade, v1, sceneDepth);

  o0 = float2(
      resolved.ao, min(resolved.sss.x, cascade.visibility));
  o2 = resolved.sss;
}
"""
        return _BOUND_UPSCALE_MAIN.sub(
            replacement.replace(
                "__TEMPORAL_INDIRECT_DECLARATION__",
                temporal_indirect_declaration,
            )
            .replace("__GATHER__", gather)
            .replace("__RECONSTRUCT__", reconstruct)
            .replace("__EVALUATOR__", evaluator),
            source,
            count=1,
        )

    cascade_gather = (
        "GatherBoundPerspectiveCascadeSurface"
        if perspective
        else "GatherBoundOrthoCascadeSurface"
    )
    cascade_reconstruct = (
        "ReconstructBoundPerspectiveCascadePosition"
        if perspective
        else "ReconstructBoundOrthoCascadePosition"
    )
    ao_reconstruct = (
        "ReconstructBoundPerspectiveAoPosition"
        if perspective
        else "ReconstructBoundOrthoAoPosition"
    )
    sss_reconstruct = (
        "ReconstructBoundPerspectiveSssPosition"
        if perspective
        else "ReconstructBoundOrthoSssPosition"
    )
    if from_depth:
        evaluator = (
            "EvaluateBoundLowDepthCascadeOnlyLighting"
            if low_quality
            else "EvaluateBoundMediumDepthCascadeOnlyLighting"
        )
        cascade_block = """  float sceneDepth = LinearizeUpscaleDepth(
      tDepth.Load(int3(pixel, 0)).x,
      cb_xViewToProjection._m22, cb_xViewToProjection._m23);
  float3 sceneWorldPosition =
      __CASCADE_RECONSTRUCT__(w1, sceneDepth);
  float visibility = __EVALUATOR__(
      cascadeSurface, sceneWorldPosition, sceneDepth);
"""
    else:
        evaluator = (
            "EvaluateBoundLowCascadeOnlyLighting"
            if low_quality
            else "EvaluateBoundMediumCascadeOnlyLighting"
        )
        cascade_block = (
            "  float visibility = __EVALUATOR__(cascadeSurface);\n"
        )

    sss_include = ""
    sss_signature = ""
    sss_background = ""
    sss_block = ""
    sss_output = ""
    cascade_output = "visibility"
    if sss:
        sss_include = """#define INDIRECT_CASCADE_UPSCALE_SSS_NO_CASCADE
#include "../indirect_cascade_upscale_sss_depth_bound.hlsl"
"""
        sss_signature = ",\n  out float4 o2 : SV_Target2"
        sss_background = "\n    o2 = float4(1.0, 1.0, 1.0, 1.0);"
        sss_block = """  UpscaledSss sss = FilterBoundSssCross(pixel, viewDepth);
  BoundSssPosition sssSurface =
      __SSS_RECONSTRUCT__(w1, viewDepth);
  float4 resolvedSss = ResolveBoundSssTemporal(
      v1, viewDepth, sssSurface, sss.value);
"""
        sss_output = "\n  o2 = resolvedSss;"
        cascade_output = "min(resolvedSss.x, visibility)"

    replacement = """#include "../indirect_cascade_upscale_cascade_depth_bound.hlsl"
#define INDIRECT_CASCADE_UPSCALE_AO_NO_CASCADE
#include "../indirect_cascade_upscale_ao_depth_bound.hlsl"
__SSS_INCLUDE__
void mainPS(
  float4 v0 : SV_Position0,
  float2 v1 : UV0,
  float2 w1 : UNSCALED_UV0,
  out float2 o0 : SV_Target0__SSS_SIGNATURE__)
{
  float2 pixelCoordinate = asuint(cb_vuViewportSize.xy);
  pixelCoordinate = w1.xy * pixelCoordinate;
  int2 pixel = (uint2)pixelCoordinate;
  float viewDepth = tHzb.Load(int3(pixel, 0)).x;
  float backgroundDepth = -1.0 + cb_vNearFarViewCorner.y;
  if (viewDepth >= backgroundDepth)
  {
    o0 = float2(1.0, 1.0);__SSS_BACKGROUND__
    return;
  }

  UpscaledAo ao = FilterBoundAoCross(pixel, viewDepth);
  BoundAoPosition aoSurface = __AO_RECONSTRUCT__(w1, viewDepth);
  UpscaleCascadeSurface cascadeSurface = __CASCADE_GATHER__(
      w1, pixel, viewDepth);
__CASCADE_BLOCK__
  float2 resolvedAo = ResolveBoundAoCascadeTemporal(
      v1, viewDepth, aoSurface, float2(ao.value, visibility),
      -0.180000007, 0.819999993);
__SSS_BLOCK__
  o0 = float2(resolvedAo.x, __CASCADE_OUTPUT__);__SSS_OUTPUT__
}
"""
    replacement = (
        replacement.replace("__SSS_INCLUDE__", sss_include)
        .replace("__SSS_SIGNATURE__", sss_signature)
        .replace("__SSS_BACKGROUND__", sss_background)
        .replace("__SSS_BLOCK__", sss_block)
        .replace("__SSS_OUTPUT__", sss_output)
        .replace("__CASCADE_OUTPUT__", cascade_output)
        .replace("__AO_RECONSTRUCT__", ao_reconstruct)
        .replace("__CASCADE_GATHER__", cascade_gather)
        .replace("__CASCADE_BLOCK__", cascade_block)
        .replace("__CASCADE_RECONSTRUCT__", cascade_reconstruct)
        .replace("__SSS_RECONSTRUCT__", sss_reconstruct)
        .replace("__EVALUATOR__", evaluator)
    )
    return _BOUND_UPSCALE_MAIN.sub(replacement, source, count=1)


def _lift_bound_cascade_payload_main(
    source: str,
    *,
    perspective: bool,
    quality: str,
    from_depth: bool,
    indirect: bool,
    sss: bool,
) -> str:
    """Compose cascade history with optional indirect and SSS outputs."""
    low_quality = quality == "low"
    shadow_markers = (
        ("0.142857149", "int2(-1,-1)", "int2(1,1)")
        if low_quality
        else ("0.0588235296", "int2(-2,-2)", "int2(2,2)")
    )
    required = [
        "tTemporalAo.SampleLevel(",
        "out float2 o0 : SV_Target0",
        *shadow_markers,
    ]
    if from_depth:
        required.append("LinearizeUpscaleDepth(tDepth.Load(")
    if indirect:
        required.extend(
            (
                "tIndirect_Ao.SampleLevel(",
                "tTemporalIndirect.SampleLevel(",
                "out float3 o1 : SV_Target1",
            )
        )
    if sss:
        required.extend(
            (
                "tSSS.SampleLevel(",
                "tTemporalSSS.SampleLevel(",
                "out float4 o2 : SV_Target2",
                "0.959999979",
            )
        )
    if any(marker not in source for marker in required):
        return source

    gather = (
        "GatherBoundPerspectiveCascadeSurface"
        if perspective
        else "GatherBoundOrthoCascadeSurface"
    )
    cascade_reconstruct = (
        "ReconstructBoundPerspectiveCascadePosition"
        if perspective
        else "ReconstructBoundOrthoCascadePosition"
    )
    sss_reconstruct = (
        "ReconstructBoundPerspectiveSssPosition"
        if perspective
        else "ReconstructBoundOrthoSssPosition"
    )
    temporal = (
        "ResolveBoundHighCascadeOnlyTemporal"
        if quality == "high"
        else "ResolveBoundLowMediumCascadeOnlyTemporal"
    )
    includes = [
        '#include "../indirect_cascade_upscale_cascade_depth_bound.hlsl"'
    ]
    signature = ["  out float2 o0 : SV_Target0"]
    background = ["    o0 = float2(1.0, 1.0);"]
    pre_cascade = []
    post_cascade = []
    outputs = []
    if indirect:
        includes.append(
            '#include "../indirect_cascade_upscale_indirect_bound.hlsl"'
        )
        signature.append("  out float3 o1 : SV_Target1")
        background.append("    o1 = float3(0.0, 0.0, 0.0);")
        post_cascade.append(
            """  UpscaledIndirect indirectLighting =
      FilterBoundIndirectCross(pixel, viewDepth);
  float3 resolvedIndirect = ResolveBoundIndirectTemporal(
      v1, viewDepth, surface.worldPosition, indirectLighting);
"""
        )
        outputs.append("  o1 = resolvedIndirect;")
    if sss:
        if not from_depth:
            includes.append(
                "#define INDIRECT_CASCADE_UPSCALE_SSS_NO_CASCADE"
            )
        includes.append(
            '#include "../indirect_cascade_upscale_sss_depth_bound.hlsl"'
        )
        signature.append("  out float4 o2 : SV_Target2")
        background.append("    o2 = float4(1.0, 1.0, 1.0, 1.0);")
        pre_cascade.append(
            """  UpscaledSss sss = FilterBoundSssCross(pixel, viewDepth);
  BoundSssPosition hzbSssSurface =
      __SSS_RECONSTRUCT__(w1, viewDepth);
"""
        )
        post_cascade.append(
            """  float4 resolvedSss = ResolveBoundSssTemporal(
      v1, viewDepth, hzbSssSurface, sss.value);
"""
        )
        outputs.append("  o2 = resolvedSss;")
        outputs.insert(
            0,
            "  o0 = float2(1.0, min(resolvedSss.x, resolvedVisibility));",
        )
    else:
        outputs.insert(0, "  o0 = float2(1.0, resolvedVisibility);")

    if from_depth:
        if sss:
            medium_quality = "false" if low_quality else "true"
            cascade_block = """  float sceneDepth = LinearizeUpscaleDepth(
      tDepth.Load(int3(pixel, 0)).x,
      cb_xViewToProjection._m22, cb_xViewToProjection._m23);
  BoundSssPosition sceneSssSurface =
      __SSS_RECONSTRUCT__(w1, sceneDepth);
  float visibility = EvaluateBoundDepthCascadeImpl(
      pixel, viewDepth, sceneDepth, sss.value.x,
      sceneSssSurface, __MEDIUM_QUALITY__);
"""
            cascade_block = cascade_block.replace(
                "__MEDIUM_QUALITY__", medium_quality
            )
        else:
            evaluator = (
                "EvaluateBoundLowDepthCascadeOnlyLighting"
                if low_quality
                else "EvaluateBoundMediumDepthCascadeOnlyLighting"
            )
            cascade_block = """  float sceneDepth = LinearizeUpscaleDepth(
      tDepth.Load(int3(pixel, 0)).x,
      cb_xViewToProjection._m22, cb_xViewToProjection._m23);
  float3 sceneWorldPosition =
      __CASCADE_RECONSTRUCT__(w1, sceneDepth);
  float visibility = __EVALUATOR__(
      surface, sceneWorldPosition, sceneDepth);
"""
            cascade_block = cascade_block.replace("__EVALUATOR__", evaluator)
    else:
        evaluator = (
            "EvaluateBoundLowCascadeOnlyLighting"
            if low_quality
            else "EvaluateBoundMediumCascadeOnlyLighting"
        )
        cascade_block = "  float visibility = __EVALUATOR__(surface);\n"
        cascade_block = cascade_block.replace("__EVALUATOR__", evaluator)
    cascade_block += (
        "  float resolvedVisibility = __TEMPORAL__(\n"
        "      v1, surface, visibility);\n"
    )

    replacement = """__INCLUDES__

void mainPS(
  float4 v0 : SV_Position0,
  float2 v1 : UV0,
  float2 w1 : UNSCALED_UV0,
__SIGNATURE__)
{
  float2 pixelCoordinate = asuint(cb_vuViewportSize.xy);
  pixelCoordinate = w1.xy * pixelCoordinate;
  int2 pixel = (uint2)pixelCoordinate;
  float viewDepth = tHzb.Load(int3(pixel, 0)).x;
  float backgroundDepth = -1.0 + cb_vNearFarViewCorner.y;
  if (viewDepth >= backgroundDepth)
  {
__BACKGROUND__
    return;
  }

  UpscaleCascadeSurface surface = __GATHER__(
      w1, pixel, viewDepth);
__PRE_CASCADE__
__CASCADE_BLOCK__
__POST_CASCADE__
__OUTPUTS__
}
"""
    replacement = (
        replacement.replace("__INCLUDES__", "\n".join(includes))
        .replace("__SIGNATURE__", ",\n".join(signature))
        .replace("__BACKGROUND__", "\n".join(background))
        .replace("__GATHER__", gather)
        .replace("__PRE_CASCADE__", "\n".join(pre_cascade))
        .replace("__CASCADE_BLOCK__", cascade_block)
        .replace("__POST_CASCADE__", "\n".join(post_cascade))
        .replace("__OUTPUTS__", "\n".join(outputs))
        .replace("__CASCADE_RECONSTRUCT__", cascade_reconstruct)
        .replace("__SSS_RECONSTRUCT__", sss_reconstruct)
        .replace("__TEMPORAL__", temporal)
    )
    return _BOUND_UPSCALE_MAIN.sub(replacement, source, count=1)


def _lift_bound_ao_cascade_main(
    source: str, *, perspective: bool, quality: str
) -> str:
    """Lift paired AO and cascade history without SSS or indirect outputs."""
    low_quality = quality == "low"
    shadow_markers = (
        ("0.142857149", "int2(-1,-1)", "int2(1,1)")
        if low_quality
        else ("0.0588235296", "int2(-2,-2)", "int2(2,2)")
    )
    required = (
        "tIndirect_Ao.SampleLevel(",
        "tTemporalAo.SampleLevel(",
        "out float2 o0 : SV_Target0",
        *shadow_markers,
    )
    if any(marker not in source for marker in required):
        return source
    ao_reconstruct = (
        "ReconstructBoundPerspectiveAoPosition"
        if perspective
        else "ReconstructBoundOrthoAoPosition"
    )
    cascade_gather = (
        "GatherBoundPerspectiveCascadeSurface"
        if perspective
        else "GatherBoundOrthoCascadeSurface"
    )
    evaluator = (
        "EvaluateBoundLowCascadeOnlyLighting"
        if low_quality
        else "EvaluateBoundMediumCascadeOnlyLighting"
    )
    accepted_response = (
        "-0.350000024" if quality == "high" else "-0.180000007"
    )
    rejected_response = (
        "0.649999976" if quality == "high" else "0.819999993"
    )
    replacement = """#include "../indirect_cascade_upscale_cascade_depth_bound.hlsl"
#define INDIRECT_CASCADE_UPSCALE_AO_NO_CASCADE
#include "../indirect_cascade_upscale_ao_depth_bound.hlsl"

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

  UpscaledAo ao = FilterBoundAoCross(pixel, viewDepth);
  BoundAoPosition aoSurface = __AO_RECONSTRUCT__(w1, viewDepth);
  UpscaleCascadeSurface cascadeSurface = __CASCADE_GATHER__(
      w1, pixel, viewDepth);
  float visibility = __EVALUATOR__(cascadeSurface);
  o0 = ResolveBoundAoCascadeTemporal(
      v1, viewDepth, aoSurface, float2(ao.value, visibility),
      __ACCEPTED_RESPONSE__, __REJECTED_RESPONSE__);
}
"""
    return _BOUND_UPSCALE_MAIN.sub(
        replacement.replace("__AO_RECONSTRUCT__", ao_reconstruct)
        .replace("__CASCADE_GATHER__", cascade_gather)
        .replace("__EVALUATOR__", evaluator)
        .replace("__ACCEPTED_RESPONSE__", accepted_response)
        .replace("__REJECTED_RESPONSE__", rejected_response),
        source,
        count=1,
    )


def _lift_bound_full_temporal_main(
    source: str,
    *,
    perspective: bool,
    quality: str,
    from_depth: bool,
    indirect: bool,
) -> str:
    """Lift full AO/SSS history with cascade history and optional indirect."""
    low_quality = quality == "low"
    shadow_markers = (
        ("0.142857149", "int2(-1,-1)", "int2(1,1)")
        if low_quality
        else ("0.0588235296", "int2(-2,-2)", "int2(2,2)")
    )
    required = [
        "tIndirect_Ao.SampleLevel(",
        "tTemporalAo.SampleLevel(",
        "tSSS.SampleLevel(",
        "tTemporalSSS.SampleLevel(",
        "out float2 o0 : SV_Target0",
        "out float4 o2 : SV_Target2",
        *shadow_markers,
    ]
    if from_depth:
        required.append("LinearizeUpscaleDepth(tDepth.Load(")
    if indirect:
        required.extend(
            (
                "tTemporalIndirect.SampleLevel(",
                "out float3 o1 : SV_Target1",
            )
        )
    if any(marker not in source for marker in required):
        return source

    gather = (
        "GatherBoundPerspectiveFullSurface"
        if perspective
        else "GatherBoundOrthoFullSurface"
    )
    signature = ""
    background = ""
    indirect_block = ""
    indirect_output = ""
    if indirect:
        signature = ",\n  out float3 o1 : SV_Target1"
        background = "\n    o1 = float3(0.0, 0.0, 0.0);"
        indirect_block = """  float3 resolvedIndirect = ResolveBoundIndirectTemporal(
      v1, surface.common.viewDepth,
      surface.common.worldPosition, surface.indirect);
"""
        indirect_output = "\n  o1 = resolvedIndirect;"
    else:
        indirect_declaration = (
            ""
            if "Texture2D<float3> tTemporalIndirect : register(t6);" in source
            else "Texture2D<float3> tTemporalIndirect : register(t6);\n"
        )

    if from_depth:
        reconstruct = (
            "ReconstructBoundPerspectiveCascadePosition"
            if perspective
            else "ReconstructBoundOrthoCascadePosition"
        )
        cascade_gather = (
            "GatherBoundPerspectiveCascadeSurface"
            if perspective
            else "GatherBoundOrthoCascadeSurface"
        )
        evaluator = (
            "EvaluateBoundLowFullDepthCascade"
            if low_quality
            else "EvaluateBoundMediumFullDepthCascade"
        )
        temporal = (
            "ResolveBoundHighCascadeOnlyTemporal"
            if quality == "high"
            else "ResolveBoundLowMediumCascadeOnlyTemporal"
        )
        body = """  float sceneDepth = LinearizeUpscaleDepth(
      tDepth.Load(int3(pixel, 0)).x,
      cb_xViewToProjection._m22, cb_xViewToProjection._m23);
  float3 sceneWorldPosition = __RECONSTRUCT__(w1, sceneDepth);
  UpscaleCascadeLighting cascade = __EVALUATOR__(
      surface, sceneWorldPosition, sceneDepth);
  UpscaleTemporalResult aoSss = ResolveBoundFullDepthAoSssTemporal(
      surface, cascade, v1, sceneDepth);
  UpscaleCascadeSurface cascadeSurface = __CASCADE_GATHER__(
      w1, pixel, viewDepth);
  float resolvedCascade = __TEMPORAL__(
      v1, cascadeSurface, cascade.visibility);
"""
        body = (
            body.replace("__RECONSTRUCT__", reconstruct)
            .replace("__EVALUATOR__", evaluator)
            .replace("__CASCADE_GATHER__", cascade_gather)
            .replace("__TEMPORAL__", temporal)
        )
        include = (
            '__INDIRECT_DECLARATION__#include '
            '"../indirect_cascade_upscale_full_depth_bound.hlsl"'
        )
        cascade_result = "resolvedCascade"
    else:
        evaluator = (
            "EvaluateBoundLowUpscaleCascadeLighting"
            if low_quality
            else "EvaluateBoundUpscaleCascadeLighting"
        )
        body = """  UpscaleCascadeLighting cascade = __EVALUATOR__(
      surface.common);
  UpscaleTemporalResult aoSss = ResolveBoundUpscaleTemporal(
      surface.common, cascade, v1);
"""
        body = body.replace("__EVALUATOR__", evaluator)
        include = (
            '__INDIRECT_DECLARATION__#include '
            '"../indirect_cascade_upscale_full_bound.hlsl"'
        )
        cascade_result = "aoSss.cascadeVisibility"

    replacement = """__INCLUDE__

void mainPS(
  float4 v0 : SV_Position0,
  float2 v1 : UV0,
  float2 w1 : UNSCALED_UV0,
  out float2 o0 : SV_Target0__INDIRECT_SIGNATURE__,
  out float4 o2 : SV_Target2)
{
  float2 pixelCoordinate = asuint(cb_vuViewportSize.xy);
  pixelCoordinate = w1.xy * pixelCoordinate;
  int2 pixel = (uint2)pixelCoordinate;
  float viewDepth = tHzb.Load(int3(pixel, 0)).x;
  float backgroundDepth = -1.0 + cb_vNearFarViewCorner.y;
  if (viewDepth >= backgroundDepth)
  {
    o0 = float2(1.0, 1.0);__INDIRECT_BACKGROUND__
    o2 = float4(1.0, 1.0, 1.0, 1.0);
    return;
  }

  UpscaleFullSurface surface = __GATHER__(w1, pixel, viewDepth);
__BODY__
__INDIRECT_BLOCK__
  o0 = float2(aoSss.ao, min(aoSss.sss.x, __CASCADE_RESULT__));
  o2 = aoSss.sss;__INDIRECT_OUTPUT__
}
"""
    indirect_declaration = (
        ""
        if indirect
        or "Texture2D<float3> tTemporalIndirect : register(t6);" in source
        else "Texture2D<float3> tTemporalIndirect : register(t6);\n"
    )
    replacement = (
        replacement.replace(
            "__INCLUDE__",
            include.replace(
                "__INDIRECT_DECLARATION__", indirect_declaration
            ),
        )
        .replace("__INDIRECT_SIGNATURE__", signature)
        .replace("__INDIRECT_BACKGROUND__", background)
        .replace("__GATHER__", gather)
        .replace("__BODY__", body)
        .replace("__INDIRECT_BLOCK__", indirect_block)
        .replace("__CASCADE_RESULT__", cascade_result)
        .replace("__INDIRECT_OUTPUT__", indirect_output)
    )
    return _BOUND_UPSCALE_MAIN.sub(replacement, source, count=1)


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


def _lift_bound_ao_indirect_sss_main(
    source: str, *, perspective: bool, quality: str
) -> str:
    """Compose packed AO/indirect filtering with independent SSS history."""
    required = (
        "tIndirect_Ao.SampleLevel(",
        "tTemporalIndirect.SampleLevel(",
        "tTemporalAo.SampleLevel(",
        "tSSS.SampleLevel(",
        "tTemporalSSS.SampleLevel(",
        "GatherUpscaleDepthError(",
        "ComputeUpscaleGaussianWeight(",
        "ComputeUpscaleCoverageWeight(",
        "SwizzleUpscaleSss(",
        "out float2 o0 : SV_Target0",
        "out float3 o1 : SV_Target1",
        "out float4 o2 : SV_Target2",
        "o0.y = 1;",
    )
    if any(marker not in source for marker in required):
        return source
    ao_indirect_gather = (
        "GatherBoundPerspectiveAoIndirectSurface"
        if perspective
        else "GatherBoundOrthoAoIndirectSurface"
    )
    sss_reconstructor = (
        "ReconstructBoundPerspectiveSssPosition"
        if perspective
        else "ReconstructBoundOrthoSssPosition"
    )
    auxiliary_response = (
        "0.649999976" if quality == "high" else "0.819999993"
    )
    replacement = """#include "../indirect_cascade_upscale_ao_indirect_bound.hlsl"
#define INDIRECT_CASCADE_UPSCALE_SSS_NO_CASCADE
#include "../indirect_cascade_upscale_sss_depth_bound.hlsl"

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

  UpscaleAoIndirectSurface surface = __AO_INDIRECT_GATHER__(
      w1, pixel, viewDepth);
  UpscaledSss sss = FilterBoundSssCross(pixel, viewDepth);
  BoundSssPosition sssSurface =
      __SSS_RECONSTRUCTOR__(w1, viewDepth);

  o0 = ResolveBoundAoIndirectTemporal(
      v1, surface, __AUXILIARY_RESPONSE__);
  o1 = ResolveBoundIndirectTemporal(
      v1, surface.viewDepth, surface.worldPosition, surface.indirect);
  o2 = ResolveBoundSssOnlyTemporal(
      v1, viewDepth, sssSurface, sss.value);
}
"""
    return _BOUND_UPSCALE_MAIN.sub(
        replacement.replace(
            "__AO_INDIRECT_GATHER__", ao_indirect_gather
        ).replace(
            "__SSS_RECONSTRUCTOR__", sss_reconstructor
        ).replace(
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
        phase_map = SEMANTIC_PHASE_MAP
        if source.startswith("// COMPACT_BOUND_VARIANT\n"):
            source = source.removeprefix("// COMPACT_BOUND_VARIANT\n")
            phase_map = ""
        source = source.replace('#include "include/', '#include "../')
        (snippet_root / filename).write_text(
            phase_map
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
            or "PS_SHADER_QUALITY_HIGH" in definitions[selector]
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
        if supports_seventeen_weight_pcf:
            if "PS_DISABLE_CASCADE_TEMPORAL" in definitions[selector]:
                source = _lift_bound_no_cascade_history_main(
                    source, perspective=perspective
                )
            else:
                source = _lift_bound_upscale_main(
                    source, perspective=perspective
                )
        if supports_low_pcf:
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
            source = _lift_bound_cascade_only_main(
                source, quality=quality, perspective=perspective
            )
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
        sss_only_temporal = (
            "PS_SSS" in feature_set
            and "PS_AO" not in feature_set
            and "PS_INDIRECT" not in feature_set
            and "PS_CASCADE" not in feature_set
        )
        if sss_only_temporal:
            source = _lift_bound_sss_only_main(
                source, perspective=perspective
            )
        indirect_sss_temporal = (
            "PS_INDIRECT" in feature_set
            and "PS_SSS" in feature_set
            and "PS_AO" not in feature_set
            and "PS_CASCADE" not in feature_set
        )
        if indirect_sss_temporal:
            source = _lift_bound_indirect_sss_main(
                source, perspective=perspective
            )
        ao_only_temporal = (
            "PS_AO" in feature_set
            and "PS_INDIRECT" not in feature_set
            and "PS_SSS" not in feature_set
            and "PS_CASCADE" not in feature_set
        )
        if ao_only_temporal:
            quality = next(
                name.removeprefix("PS_SHADER_QUALITY_").lower()
                for name in feature_set
                if name.startswith("PS_SHADER_QUALITY_")
            )
            source = _lift_bound_ao_only_main(
                source, perspective=perspective, quality=quality
            )
        ao_sss_temporal = (
            "PS_AO" in feature_set
            and "PS_SSS" in feature_set
            and "PS_INDIRECT" not in feature_set
            and "PS_CASCADE" not in feature_set
        )
        if ao_sss_temporal:
            quality = next(
                name.removeprefix("PS_SHADER_QUALITY_").lower()
                for name in feature_set
                if name.startswith("PS_SHADER_QUALITY_")
            )
            source = _lift_bound_ao_sss_main(
                source, perspective=perspective, quality=quality
            )
        cascade_indirect_temporal = (
            "PS_CASCADE" in feature_set
            and "PS_INDIRECT" in feature_set
            and "PS_AO" not in feature_set
            and "PS_SSS" not in feature_set
            and "PS_CASCADE_FROM_DEPTH" not in feature_set
            and "PS_DISABLE_CASCADE_TEMPORAL" not in feature_set
        )
        if cascade_indirect_temporal:
            quality = next(
                name.removeprefix("PS_SHADER_QUALITY_").lower()
                for name in feature_set
                if name.startswith("PS_SHADER_QUALITY_")
            )
            source = _lift_bound_cascade_indirect_main(
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
        cascade_only_no_history = (
            "PS_CASCADE" in feature_set
            and "PS_DISABLE_CASCADE_TEMPORAL" in feature_set
            and "PS_CASCADE_FROM_DEPTH" not in feature_set
            and "PS_AO" not in feature_set
            and "PS_INDIRECT" not in feature_set
            and "PS_SSS" not in feature_set
        )
        if cascade_only_no_history:
            quality = next(
                name.removeprefix("PS_SHADER_QUALITY_").lower()
                for name in feature_set
                if name.startswith("PS_SHADER_QUALITY_")
            )
            source = _lift_bound_cascade_no_history_main(
                source, perspective=perspective, quality=quality
            )
        cascade_depth_only_no_history = (
            "PS_CASCADE" in feature_set
            and "PS_CASCADE_FROM_DEPTH" in feature_set
            and "PS_DISABLE_CASCADE_TEMPORAL" in feature_set
            and "PS_AO" not in feature_set
            and "PS_INDIRECT" not in feature_set
            and "PS_SSS" not in feature_set
        )
        if cascade_depth_only_no_history:
            quality = next(
                name.removeprefix("PS_SHADER_QUALITY_").lower()
                for name in feature_set
                if name.startswith("PS_SHADER_QUALITY_")
            )
            source = _lift_bound_cascade_depth_no_history_main(
                source, perspective=perspective, quality=quality
            )
        cascade_payload_no_history = (
            "PS_CASCADE" in feature_set
            and "PS_DISABLE_CASCADE_TEMPORAL" in feature_set
            and "PS_AO" not in feature_set
            and (
                "PS_INDIRECT" in feature_set
                or "PS_SSS" in feature_set
            )
        )
        if cascade_payload_no_history:
            quality = next(
                name.removeprefix("PS_SHADER_QUALITY_").lower()
                for name in feature_set
                if name.startswith("PS_SHADER_QUALITY_")
            )
            source = _lift_bound_cascade_payload_no_history_main(
                source,
                perspective=perspective,
                quality=quality,
                from_depth="PS_CASCADE_FROM_DEPTH" in feature_set,
                indirect="PS_INDIRECT" in feature_set,
                sss="PS_SSS" in feature_set,
            )
        ao_cascade_no_history = (
            "PS_AO" in feature_set
            and "PS_CASCADE" in feature_set
            and "PS_DISABLE_CASCADE_TEMPORAL" in feature_set
            and "PS_INDIRECT" not in feature_set
        )
        if ao_cascade_no_history:
            quality = next(
                name.removeprefix("PS_SHADER_QUALITY_").lower()
                for name in feature_set
                if name.startswith("PS_SHADER_QUALITY_")
            )
            source = _lift_bound_ao_cascade_no_history_main(
                source,
                perspective=perspective,
                quality=quality,
                from_depth="PS_CASCADE_FROM_DEPTH" in feature_set,
                sss="PS_SSS" in feature_set,
            )
        cascade_payload_temporal = (
            "PS_CASCADE" in feature_set
            and "PS_DISABLE_CASCADE_TEMPORAL" not in feature_set
            and "PS_AO" not in feature_set
            and (
                "PS_INDIRECT" in feature_set
                or "PS_SSS" in feature_set
            )
        )
        if cascade_payload_temporal:
            quality = next(
                name.removeprefix("PS_SHADER_QUALITY_").lower()
                for name in feature_set
                if name.startswith("PS_SHADER_QUALITY_")
            )
            source = _lift_bound_cascade_payload_main(
                source,
                perspective=perspective,
                quality=quality,
                from_depth="PS_CASCADE_FROM_DEPTH" in feature_set,
                indirect="PS_INDIRECT" in feature_set,
                sss="PS_SSS" in feature_set,
            )
        ao_cascade_temporal = (
            "PS_AO" in feature_set
            and "PS_CASCADE" in feature_set
            and "PS_DISABLE_CASCADE_TEMPORAL" not in feature_set
            and "PS_CASCADE_FROM_DEPTH" not in feature_set
            and "PS_INDIRECT" not in feature_set
            and "PS_SSS" not in feature_set
        )
        if ao_cascade_temporal:
            quality = next(
                name.removeprefix("PS_SHADER_QUALITY_").lower()
                for name in feature_set
                if name.startswith("PS_SHADER_QUALITY_")
            )
            source = _lift_bound_ao_cascade_main(
                source, perspective=perspective, quality=quality
            )
        full_temporal = (
            "PS_AO" in feature_set
            and "PS_CASCADE" in feature_set
            and "PS_SSS" in feature_set
            and "PS_DISABLE_CASCADE_TEMPORAL" not in feature_set
        )
        if full_temporal:
            quality = next(
                name.removeprefix("PS_SHADER_QUALITY_").lower()
                for name in feature_set
                if name.startswith("PS_SHADER_QUALITY_")
            )
            source = _lift_bound_full_temporal_main(
                source,
                perspective=perspective,
                quality=quality,
                from_depth="PS_CASCADE_FROM_DEPTH" in feature_set,
                indirect="PS_INDIRECT" in feature_set,
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
        ao_indirect_sss_temporal = (
            "PS_AO" in feature_set
            and "PS_INDIRECT" in feature_set
            and "PS_SSS" in feature_set
            and "PS_CASCADE" not in feature_set
        )
        if ao_indirect_sss_temporal:
            quality = next(
                name.removeprefix("PS_SHADER_QUALITY_").lower()
                for name in feature_set
                if name.startswith("PS_SHADER_QUALITY_")
            )
            source = _lift_bound_ao_indirect_sss_main(
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
