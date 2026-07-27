"""Recognize the medium/high volumetric-light integration shaders."""

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
1. Resolve the screen tile's clustered-volumetric ID masks.
2. Reconstruct current world position and reproject it into the previous frame.
3. Validate temporal history with previous depth, camera motion and volatility.
4. Jitter a view ray with screen noise; quality controls the temporal/ray budget.
5. Walk clustered sphere/cone light IDs, integrating attenuation, cookies,
   shadow-atlas comparisons and 3D density noise along each light volume.
6. Blend new in-scattering with valid history and write radiance plus history.

Sphere traversal and marching are structural. The nested cone shadow/cookie
kernel retains recovered operation ordering because its accumulation chains are
contraction-sensitive.
*/
"""


STRUCTURAL_HELPERS = r"""
float SelectVolumetricMarchStep(float qualityFactor, float historyWeight)
{
#if defined(PS_SHADER_QUALITY_HIGH)
  float2 stepRange = qualityFactor * float2(0.300000012, 0.800000012)
                   + float2(0.200000003, 0.200000003);
  return historyWeight * (stepRange.y - stepRange.x) + stepRange.x;
#else
  float historyStep = qualityFactor * 0.600000024 + 0.200000003;
  return historyWeight * (1.0 - historyStep) + historyStep;
#endif
}

float3 DecodeVolumetricLightColor(uint packedColorAndFlags)
{
  uint3 encoded = uint3(
      packedColorAndFlags >> 24,
      (packedColorAndFlags >> 16) & 255,
      (packedColorAndFlags >> 8) & 255);
  return float3(encoded) * 0.00392156886;
}

float SampleVolumetricDensity(float3 worldPosition)
{
  float3 noiseUv = cb_vVolFogScale.xyz
                 * (cb_vVolFogScroll.xyz + worldPosition);
  float density = tNoise.SampleLevel(LinearWrapWrap_s, noiseUv, 0).x;
  density = frac(cb_fVolFogLoop + density) - 0.5;
  density = dot(abs(density.xx), cb_fVolFogMin);
  return cb_fVolFogMaxMul + density;
}

float3 EncodeVolumetricHdr(float3 radiance)
{
  float3 encoded = saturate(radiance);
  encoded = exp2(cb_hdr.fPow * log2(encoded));
  return saturate(cb_hdr.fRangeRcp * (encoded - cb_hdr.fBase));
}

float3 IntegrateSphereVolume(
    uint sphereIndex,
    float sceneDepth,
    float rayJitter,
    float marchStep,
    float3 viewRay,
    float3 worldRay)
{
  uint flags = cb_arrSphere[sphereIndex].uColorAndFlags;
  if ((flags & 4) != 0)
    return 0.0;

  float projectedCenter = dot(-cb_arrSphere[sphereIndex].vPosition, viewRay);
  float discriminant = projectedCenter * projectedCenter
                     - cb_arrSphere[sphereIndex].fC;
  if (discriminant < 0.00100000005)
    return 0.0;

  float root = sqrt(discriminant);
  float entryDistance = (-root - projectedCenter) * -viewRay.z;
  if (sceneDepth < entryDistance)
    return 0.0;

  float exitDistance = (root - projectedCenter) * -viewRay.z;
  float segmentLength = exitDistance - entryDistance;
  if (segmentLength <= 9.99999975e-05)
    return 0.0;

  float halfLength = 0.5 * segmentLength;
  float segmentCenter = entryDistance + halfLength;
  float stepSize = max(0.0133333337 * entryDistance, marchStep);
  float stepCount = halfLength < stepSize ? 0.0 : halfLength / stepSize;
  float lowerDistance = max(0.5, segmentCenter - stepSize * stepCount);
  float upperDistance = min(
      sceneDepth, min(50.0 + lowerDistance, segmentCenter + stepSize * stepCount));

  float3 snappedOffset = worldRay * upperDistance + viewToWorld._m03_m13_m23;
  snappedOffset = round(4.0 * snappedOffset);
  snappedOffset = -0.25 * snappedOffset + viewToWorld._m03_m13_m23;
  float alignment = dot(snappedOffset, worldRay) - 0.25;
  float sampleDistance = -stepSize * rayJitter * 0.980000019 - alignment;
  float integratedIntensity = 0.0;

  while (lowerDistance < sampleDistance)
  {
    float clippedDistance = min(sampleDistance, sceneDepth);
    float distanceFade = saturate((clippedDistance - 0.5) * 0.333333343);
    float sampleIntensity = cb_arrSphere[sphereIndex].fIntensity
                          * distanceFade * distanceFade;
    if (sampleIntensity >= 0.00100000005)
    {
      float3 lightOffset = cb_arrSphere[sphereIndex].vPosition
                         - viewRay * clippedDistance;
      float lightDistance = length(lightOffset);
      float innerFade = saturate(
          cb_arrSphere[sphereIndex].fRcpMinRadius * lightDistance);
      if (innerFade < 1.0)
      {
        float outerFade = max(0.00999999978, saturate(
            cb_arrSphere[sphereIndex].fRcpMaxRadius * lightDistance));
        outerFade = 1.0 - exp2(
            cb_arrSphere[sphereIndex].fFalloffFactor * log2(outerFade));
        float innerShape = max(0.00999999978, 1.0 - innerFade);
        innerShape = exp2(
            cb_arrSphere[sphereIndex].fFalloffFactor * log2(innerShape));
        float3 worldPosition = worldRay * clippedDistance
                             + viewToWorld._m03_m13_m23;
        float contribution = innerShape * outerFade * sampleIntensity
                           * SampleVolumetricDensity(worldPosition);
        contribution = min(
            cb_arrSphere[sphereIndex].fMaxIntensity, contribution);
        integratedIntensity = max(integratedIntensity, contribution);
      }
    }
    sampleDistance -= stepSize;
  }
  return DecodeVolumetricLightColor(flags) * integratedIntensity;
}

float3 IntegrateClusteredSphereVolumes(
    uint clusterWordBase,
    uint groupMask,
    float sceneDepth,
    float rayJitter,
    float marchStep,
    float3 viewRay,
    float3 worldRay)
{
  float3 radiance = 0.0;
  while (groupMask != 0)
  {
    uint group = firstbitlow(groupMask);
    groupMask ^= 1u << group;
    uint lightMask = sbVolumetricIds[clusterWordBase + group];
    while (lightMask != 0)
    {
      uint bit = firstbitlow(lightMask);
      lightMask ^= 1u << bit;
      uint sphereIndex = group * 32 + bit;
      radiance = max(radiance, IntegrateSphereVolume(
          sphereIndex, sceneDepth, rayJitter, marchStep, viewRay, worldRay));
    }
  }
  return radiance;
}
"""


REGISTER_NAMES = {
    "r0": "pixelAndClusterState",
    "r1": "viewRayAndDepthState",
    "r2": "reprojectionState",
    "r3": "temporalAndNoiseState",
    "r4": "lightMaskIterator",
    "r5": "marchPositionState",
    "r6": "lightGeometryState",
    "r7": "attenuationState",
    "r8": "coneAndCookieState",
    "r9": "shadowProjectionState",
    "r10": "shadowFilterState",
    "r11": "densityNoiseState",
    "r12": "scatteringState",
    "r13": "historyState",
    "r14": "radianceAccumulator",
    "r15": "integrationScratch",
}


def _name_volumetric_registers(source: str) -> str:
    """Give the recovered register state stable roles without reordering it."""
    for register, name in sorted(
        REGISTER_NAMES.items(), key=lambda item: -len(item[0])
    ):
        source = re.sub(rf"\b{register}\b", name, source)
    source = source.replace(
        "  uint4 bitmask, uiDest;\n  float4 fDest;\n",
        "  // The remaining state follows the original nested mask-walk order.\n",
    )
    return source


def _replace_quality_step(source: str) -> str:
    high = """    temporalAndNoiseState.xy = viewRayAndDepthState.yy * float2(0.300000012,0.800000012) + float2(0.200000003,0.200000003);
    viewRayAndDepthState.y = temporalAndNoiseState.y + -temporalAndNoiseState.x;
    viewRayAndDepthState.y = pixelAndClusterState.w * viewRayAndDepthState.y + temporalAndNoiseState.x;"""
    medium = """    viewRayAndDepthState.y = viewRayAndDepthState.y * 0.600000024 + 0.200000003;
    reprojectionState.w = 1 + -viewRayAndDepthState.y;
    viewRayAndDepthState.y = pixelAndClusterState.w * reprojectionState.w + viewRayAndDepthState.y;"""
    replacement = """    viewRayAndDepthState.y = SelectVolumetricMarchStep(
        viewRayAndDepthState.y, pixelAndClusterState.w);"""
    if high in source:
        return source.replace(high, replacement)
    if medium in source:
        return source.replace(medium, replacement)
    raise RuntimeError("post_volumetric quality-step block was not found")


def _extract_clustered_light_helper(source: str) -> str:
    """Move the long mask walk behind a typed, domain-level interface."""
    start_marker = "    lightGeometryState.xyz = float3(0,0,0);\n"
    end_marker = "\n  } else {\n    coneAndCookieState.xyz = float3(0,0,0);\n  }"
    start = source.find(start_marker)
    end = source.find(end_marker, start)
    if start < 0 or end < 0:
        raise RuntimeError("post_volumetric integration block was not found")
    integration = source[start:end]
    sphere_end_marker = (
        "    attenuationState.z = 0;\n"
        "    coneAndCookieState.xyz = lightGeometryState.xyz;\n"
    )
    sphere_end = integration.find(sphere_end_marker)
    if sphere_end < 0:
        raise RuntimeError("post_volumetric sphere-integration block was not found")
    integration = (
        "    coneAndCookieState.xyz = IntegrateClusteredSphereVolumes(\n"
        "        clusterWordBase, sphereGroupMask, sceneDepth, rayJitter,\n"
        "        marchStep, viewRay, worldRay);\n"
        "    attenuationState.z = 0;\n"
        + integration[sphere_end + len(sphere_end_marker):]
    )
    helper = f"""
float3 IntegrateClusteredVolumetricLights(
    uint clusterWordBase,
    float sceneDepth,
    uint sphereGroupMask,
    uint coneGroupMask,
    float rayJitter,
    float marchStep,
    float3 viewRay,
    float3 worldRay)
{{
  // Scratch remains operation-ordered inside this numerical kernel. Its
  // public interface exposes the recovered algorithm instead of DXBC state.
  float4 pixelAndClusterState, viewRayAndDepthState, reprojectionState;
  float4 temporalAndNoiseState, lightMaskIterator, marchPositionState;
  float4 lightGeometryState, attenuationState, coneAndCookieState;
  float4 shadowProjectionState, shadowFilterState, densityNoiseState;
  float4 scatteringState, historyState, radianceAccumulator;
  float4 integrationScratch;

  pixelAndClusterState = float4(clusterWordBase, 0, sceneDepth, 0);
  viewRayAndDepthState = float4(
      rayJitter, marchStep, sphereGroupMask, coneGroupMask);
  temporalAndNoiseState = float4(viewRay, 0);
  lightMaskIterator = float4(viewRay, 0);
  marchPositionState = float4(worldRay, 0);
{integration}
  return coneAndCookieState.xyz;
}}
"""
    call = """    coneAndCookieState.xyz = IntegrateClusteredVolumetricLights(
        (uint)pixelAndClusterState.x,
        pixelAndClusterState.z,
        (uint)viewRayAndDepthState.z,
        (uint)viewRayAndDepthState.w,
        viewRayAndDepthState.x,
        viewRayAndDepthState.y,
        temporalAndNoiseState.xyz,
        marchPositionState.xyz);"""
    source = source[:start] + call + source[end:]
    insertion = "#define cmp -\n\n\nvoid mainPS"
    if insertion not in source:
        raise RuntimeError("post_volumetric main marker was not found")
    return source.replace(
        insertion,
        "#define cmp -\n" + STRUCTURAL_HELPERS + helper + "\nvoid mainPS",
    )


def _lift_volumetric_body(source: str) -> str:
    source = _replace_quality_step(source)
    source = _extract_clustered_light_helper(source)
    source, sphere_colors = re.subn(
        r"\s+coneAndCookieState\.y = asuint\(cb_arrSphere\[marchPositionState\.w\]\.uColorAndFlags\) >> 24;.*?"
        r"shadowProjectionState\.yz = float2\(0\.00392156886,0\.00392156886\) \* coneAndCookieState\.yz;",
        "\n                shadowProjectionState.xyz = DecodeVolumetricLightColor(\n"
        "                    cb_arrSphere[marchPositionState.w].uColorAndFlags);",
        source,
        count=1,
        flags=re.DOTALL,
    )
    source, cone_colors = re.subn(
        r"\s+lightGeometryState\.w = asuint\(cb_arrCone\[lightMaskIterator\.w\]\.uColorAndFlags\) >> 24;.*?"
        r"shadowFilterState\.yz = float2\(0\.00392156886,0\.00392156886\) \* densityNoiseState\.xy;",
        "\n                shadowFilterState.xyz = DecodeVolumetricLightColor(\n"
        "                    cb_arrCone[lightMaskIterator.w].uColorAndFlags);\n"
        "                densityNoiseState.z =\n"
        "                    (cb_arrCone[lightMaskIterator.w].uColorAndFlags >> 4) & 15;",
        source,
        count=1,
        flags=re.DOTALL,
    )
    sphere_fog = """                  shadowFilterState.yzw = cb_vVolFogScroll.xyz + densityNoiseState.xyz;
                  shadowFilterState.yzw = cb_vVolFogScale.xyz * shadowFilterState.yzw;
                  shadowFilterState.y = tNoise.SampleLevel(LinearWrapWrap_s, shadowFilterState.yzw, 0).x;
                  shadowFilterState.y = cb_fVolFogLoop + shadowFilterState.y;
                  shadowFilterState.y = frac(shadowFilterState.y);
                  shadowFilterState.y = -0.5 + shadowFilterState.y;
                  shadowFilterState.y = dot(abs(shadowFilterState.yy), cb_fVolFogMin);
                  shadowFilterState.y = cb_fVolFogMaxMul + shadowFilterState.y;"""
    cone_fog = """                  historyState.xyz = cb_vVolFogScroll.xyz + radianceAccumulator.yzw;
                  historyState.xyz = cb_vVolFogScale.xyz * historyState.xyz;
                  attenuationState.y = tNoise.SampleLevel(LinearWrapWrap_s, historyState.xyz, 0).x;
                  attenuationState.y = cb_fVolFogLoop + attenuationState.y;
                  attenuationState.y = frac(attenuationState.y);
                  attenuationState.y = -0.5 + attenuationState.y;
                  attenuationState.y = dot(abs(attenuationState.yy), cb_fVolFogMin);
                  attenuationState.y = cb_fVolFogMaxMul + attenuationState.y;"""
    if cone_fog not in source:
        raise RuntimeError("post_volumetric density blocks were not found")
    if sphere_fog in source:
        source = source.replace(
            sphere_fog,
            "                  shadowFilterState.y =\n"
            "                      SampleVolumetricDensity(densityNoiseState.xyz);",
        )
    source = source.replace(
        cone_fog,
        "                  attenuationState.y =\n"
        "                      SampleVolumetricDensity(radianceAccumulator.yzw);",
    )
    hdr = """  viewRayAndDepthState.xyz = saturate(pixelAndClusterState.xyz);
  viewRayAndDepthState.xyz = log2(viewRayAndDepthState.xyz);
  viewRayAndDepthState.xyz = cb_hdr.fPow * viewRayAndDepthState.xyz;
  viewRayAndDepthState.xyz = exp2(viewRayAndDepthState.xyz);
  viewRayAndDepthState.xyz = -cb_hdr.fBase + viewRayAndDepthState.xyz;
  viewRayAndDepthState.xyz = saturate(cb_hdr.fRangeRcp * viewRayAndDepthState.xyz);"""
    if hdr not in source:
        raise RuntimeError("post_volumetric HDR block was not found")
    source = source.replace(
        hdr,
        "  viewRayAndDepthState.xyz = EncodeVolumetricHdr(\n"
        "      pixelAndClusterState.xyz);",
    )
    source = source.replace(
        "  float4 pixelAndClusterState,viewRayAndDepthState,reprojectionState,temporalAndNoiseState,lightMaskIterator,marchPositionState,lightGeometryState,attenuationState,coneAndCookieState,shadowProjectionState,shadowFilterState,densityNoiseState,scatteringState,historyState,radianceAccumulator,integrationScratch;",
        "  float4 pixelAndClusterState, viewRayAndDepthState, reprojectionState;\n"
        "  float4 temporalAndNoiseState, lightMaskIterator, marchPositionState;\n"
        "  float4 coneAndCookieState;",
    )
    source = source.replace(
        "  pixelAndClusterState.xy = cb_cluster.vVoxelDims.xy",
        "  // Resolve the 17-word clustered-volumetric record for this tile.\n"
        "  pixelAndClusterState.xy = cb_cluster.vVoxelDims.xy",
    ).replace(
        "  reprojectionState.xy = cb_vNearFarViewCorner.zw",
        "  // Reconstruct the current world position and previous-frame UV.\n"
        "  reprojectionState.xy = cb_vNearFarViewCorner.zw",
    ).replace(
        "  if (pixelAndClusterState.y != 0) {",
        "  // Jitter and integrate only when the tile references light volumes.\n"
        "  if (pixelAndClusterState.y != 0) {",
        1,
    ).replace(
        "  pixelAndClusterState.x = cb_fFrameRateScale",
        "  // Resolve temporal history, then encode the display-facing target.\n"
        "  pixelAndClusterState.x = cb_fFrameRateScale",
    )
    if sphere_colors not in (0, 1) or cone_colors != 1:
        raise RuntimeError("post_volumetric packed-color blocks were not found")
    return source


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
    # The recovered packed signature places UNSCALED_UV in register components
    # zw. FXC maps the decompiler's logical float2 axes back to physical wz, so
    # spell out the physical scalar order instead of letting vector packing
    # silently reverse both axes.
    expanded = {
        selector: source.replace(
            "  r0.xy = cb_cluster.vVoxelDims.xy * w1.xy;",
            "  r0.x = cb_cluster.vVoxelDims.x * w1.y;\n"
            "  r0.y = cb_cluster.vVoxelDims.y * w1.x;",
        ).replace(
            "  r0.zw = w1.xy * r0.zw;",
            "  r0.z = w1.y * r0.z;\n  r0.w = w1.x * r0.w;",
        ).replace(
            "  r1.zw = w1.xy * float2(1,-1) + float2(0,1);",
            "  r1.z = w1.y;\n  r1.w = w1.x;\n"
            "  r1.zw = r1.zw * float2(1,-1) + float2(0,1);",
        ).replace(
            "LinearClampClamp_s, w1.xy, 0",
            "LinearClampClamp_s, float2(w1.y, w1.x), 0",
        )
        for selector, source in expanded.items()
    }
    # 3Dmigoto prints dynamic constant-register offsets as HLSL array indices.
    # Restore logical light indices; FXC applies the 3- and 10-register record
    # strides when compiling the struct arrays.
    expanded = {
        selector: source.replace(
            "r5.w = (int)r6.w * 3;",
            "r5.w = (uint)r6.w;",
        ).replace(
            "r4.w = mad((int)r5.w, 10, -2560);",
            "r4.w = (uint)r5.w - 256;",
        )
        for selector, source in expanded.items()
    }
    expanded = {
        selector: _name_volumetric_registers(source)
        for selector, source in expanded.items()
    }
    lifted = {
        selector: _lift_volumetric_body(source)
        for selector, source in expanded.items()
    }
    shared_bodies = set(lifted.values())
    if len(shared_bodies) != 1:
        raise RuntimeError("post_volumetric variants did not converge to shared HLSL")
    shared_source = SEMANTIC_PHASE_MAP + shared_bodies.pop()
    bodies = {shader["selector"]: shared_source for shader in shaders}
    execution = {
        "kind": "fullscreen_uv",
        "vertex_harness": "fullscreen_packed_uv",
        "texture_slots": [0, 2, 3, 4, 5, 6, 7, 8],
        "texture_kinds": ["2d", "3d", "2darray", "2darray", "2d", "2d", "2d", "2d"],
        "structured_inputs": [
            {"slot": 1, "elements": 17, "stride": 4, "profile": "volumetric"},
        ],
        "samplers": [
            {"slot": 1, "filter": "point"},
            {"slot": 3, "filter": "linear"},
            {"slot": 6, "filter": "linear"},
            {"slot": 13, "filter": "point", "comparison": True},
        ],
        "constant_buffers": [
            {"slot": 0, "profile": "volumetric-cluster"},
            {"slot": 1, "profile": "volumetric-lights"},
            {"slot": 5, "profile": "projection"},
            {"slot": 9, "profile": "hdr"},
            {"slot": 12, "profile": "volumetric-frame"},
        ],
        "output": "color",
        "output_components": 4,
        "output_targets": 2,
        "absolute_tolerance": 1.0e-5,
        "relative_tolerance": 1.0e-5,
        "ulp_tolerance": 32,
    }
    return emit_validated_module(
        staging, shaders, blobs, compiler,
        recipe_name="post_volumetric", bodies=bodies,
        executions={shader["selector"]: execution for shader in shaders},
        shared_source=shared_source,
    )
