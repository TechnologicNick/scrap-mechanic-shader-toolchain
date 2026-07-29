// Ultra temporal reconstruction shared by the indirect-light family.
//
// The ultra permutation differs from the ordinary SSGI path in two ways:
// it reprojects the current world position into the previous frame and it
// resolves a packed 2x2 history footprint before combining screen-space and
// clustered-probe lighting.  AO quality only changes the projected search
// radius, so it is an explicit policy argument rather than a separate shader.
#include "indirect_light_ortho_ssgi.hlsl"

struct IndirectLightUltraHistory
{
  float3 radiance;
  float depth;
  float confidence;
  float2 previousUv;
};

struct IndirectLightUltraResult
{
  float4 indirectAo;
  float temporalConfidence;
  float4 occlusion;
};

struct IndirectLightPerspectiveUltraResult
{
  float4 indirectAo;
  float temporalConfidence;
  float4 occlusion;
};

float IndirectLightHistoryDepth(float encodedDepth)
{
  return encodedDepth * encodedDepth
      * (cb_hdr.fMaxDepth - INDIRECT_LIGHT_MIN_DEPTH)
      + INDIRECT_LIGHT_MIN_DEPTH;
}

float IndirectLightHistoryTapWeight(
    float historyDepth,
    float currentDepth,
    float depthTolerance,
    float spatialWeight)
{
  float depthAgreement = saturate(
      1.0 - abs(historyDepth - currentDepth) / depthTolerance);
  return spatialWeight * depthAgreement * depthAgreement;
}

IndirectLightUltraHistory ResolveIndirectLightUltraHistory(
    IndirectLightSurface surface,
    float3 worldPosition)
{
  IndirectLightUltraHistory history;
  float4 previousClip = mul(
      float4(worldPosition, 1.0), cb_xPrevWorldToViewProjection);
  float2 previousUv = previousClip.xy / previousClip.z;
  previousUv = previousUv * float2(0.5, -0.5) + 0.5;
  previousUv = min(cb_settings.vRenderScale,
      cb_settings.vRenderScale * previousUv);
  history.previousUv = previousUv;

  // The red channel stores four 6/5/5 RGBE-like radiance values.  The green
  // channel stores the matching quadratic view depths.  Keeping the gather
  // footprint explicit documents the on-wire format used by tSSGITemporal.
  uint4 packed = (uint4)(
      tSSGITemporal.GatherRed(PointClampClamp_s, previousUv)
      * 65535.0 + 0.5).wzxy;
  float4 encodedDepth =
      tSSGITemporal.GatherGreen(PointClampClamp_s, previousUv);
  float4 tapDepth = encodedDepth * encodedDepth
      * (cb_hdr.fMaxDepth - INDIRECT_LIGHT_MIN_DEPTH)
      + INDIRECT_LIGHT_MIN_DEPTH;

  float depthTolerance = clamp(
      cb_settings.fThresholdBase * surface.depth * surface.depth,
      0.001, 0.05);
  float2 historySize = max(1.0, (float2)cb_settings.vuSize);
  float2 footprint = frac(previousUv * historySize - 0.5);
  float4 spatialWeight = float4(
      (1.0 - footprint.x) * (1.0 - footprint.y),
      footprint.x * (1.0 - footprint.y),
      (1.0 - footprint.x) * footprint.y,
      footprint.x * footprint.y);

  float4 weight;
  weight.x = IndirectLightHistoryTapWeight(
      tapDepth.x, surface.depth, depthTolerance, spatialWeight.x);
  weight.y = IndirectLightHistoryTapWeight(
      tapDepth.y, surface.depth, depthTolerance, spatialWeight.y);
  weight.z = IndirectLightHistoryTapWeight(
      tapDepth.z, surface.depth, depthTolerance, spatialWeight.z);
  weight.w = IndirectLightHistoryTapWeight(
      tapDepth.w, surface.depth, depthTolerance, spatialWeight.w);
  float totalWeight = dot(weight, 1.0);
  history.radiance = (
      DecodeIndirectLightTemporalRadiance(packed.x) * weight.x
      + DecodeIndirectLightTemporalRadiance(packed.y) * weight.y
      + DecodeIndirectLightTemporalRadiance(packed.z) * weight.z
      + DecodeIndirectLightTemporalRadiance(packed.w) * weight.w)
      / max(0.001, totalWeight);
  history.depth = dot(tapDepth, weight) / max(0.001, totalWeight);

  float volatility = tVolatile.SampleLevel(
      PointClampClamp_s, previousUv, 0.0);
  float2 hitUv = min(cb_vPrevRenderScale,
      previousUv * cb_vPrevRenderScale);
  float hitCache = tHitCache.SampleLevel(
      PointClampClamp_s, hitUv, 0.0);
  float stableSurface = 1.0 - saturate(abs(volatility));
  stableSurface *= stableSurface;
  float validHit = 1.0 - saturate(abs(hitCache));
  float inBounds = all(previousUv > 0.0)
      && all(previousUv < cb_settings.vRenderScale);
  history.confidence = inBounds
      ? saturate(totalWeight * cb_fRenderScaleStability
          * stableSurface * validHit)
      : 0.0;
  return history;
}

float EvaluateIndirectLightOrthoUltraAo(
    IndirectLightSurface surface,
    float2 unscaledUv,
    float qualityRadiusScale)
{
  uint2 aoSize = cb_settings.vuSize;
  float2 quantizedUv = ((uint2)(surface.scaledUv * (float2)aoSize) + 0.5)
      / (float2)aoSize;
  float3 center = LoadIndirectLightOrthoAoViewPosition(quantizedUv, aoSize);
  center += surface.normalView * 0.03;
  float3 viewDirection = normalize(-center);
  float depthScale = saturate(0.002 * surface.depth);
  float worldRadius = cb_settings.vStart.x + cb_settings.vAdd.x * depthScale;
  float projectedRadius = max(3.0,
      cb_settings.fProjectionScale * (2.0 * worldRadius)
      * qualityRadiusScale / max(0.01, surface.depth) / 3.0);
  float noise = frac(cb_fTime * 0.1 + tScreenNoise.Load(uint3(
      (uint2)(cb_vTargetSize * unscaledUv) & 63u, 0)));
  float initialRadius = projectedRadius
      * (0.8 * frac(abs(noise - 0.5) * projectedRadius)
         + saturate(0.25 * surface.depth - 1.0));
  float ao = 0.0;
  [unroll]
  for (uint slice = 0u; slice < 3u; ++slice)
  {
    float angle = 2.09439516 * (float)slice;
    float sine;
    float cosine;
    sincos(angle, sine, cosine);
    ao += EvaluateIndirectLightOrthoHorizonSlice(
        surface.scaledUv, aoSize, center, viewDirection,
        surface.normalView, float2(cosine, sine),
        initialRadius + projectedRadius, projectedRadius);
  }
  ao *= 1.0 / 3.0;
  ao = 1.0 - (1.0 - ao) * (1.0 - depthScale * depthScale);
  return pow(max(1.0e-4, ao), cb_settings.vAdd.y);
}

IndirectLightUltraResult EvaluateIndirectLightOrthoUltraPolicy(
    float2 unscaledUv,
    float qualityRadiusScale,
    bool enableScreenAo,
    uint subsurfaceLayerCount)
{
  IndirectLightUltraResult result;
  result.indirectAo = float4(0.0, 0.0, 0.0, 1.0);
  result.temporalConfidence = 1.0;
  result.occlusion = 1.0;
  IndirectLightSurface surface = LoadIndirectLightOrthoSurface(unscaledUv);
  if (surface.depth >= cb_vNearFarViewCorner.y - 1.0)
    return result;

  bool receivesIndirect = surface.material.z < 0.941176474;
  if (receivesIndirect && surface.depth < 500.0)
  {
    if (enableScreenAo)
      result.indirectAo.w = EvaluateIndirectLightOrthoUltraAo(
          surface, unscaledUv, qualityRadiusScale);
    result.occlusion = EvaluateIndirectLightSubsurfaceSet(
        surface, unscaledUv, subsurfaceLayerCount);
  }

  float3 viewPosition = IndirectLightOrthoViewPosition(surface, surface.depth);
  float3 worldPosition = TransformIndirectLightPosition(viewToWorld, viewPosition);
  IndirectLightUltraHistory history = ResolveIndirectLightUltraHistory(
      surface, worldPosition);

  float3 viewDirection = normalize(viewPosition);
  float3 reflectionView = normalize(reflect(
      viewDirection, surface.normalView));
  float3 reflectionWorld = normalize(TransformIndirectLightDirection(
      viewToWorld, reflectionView));
  float3 normalWorld = normalize(TransformIndirectLightDirection(
      viewToWorld, surface.normalView));
  float reflectivity = 1.0 - surface.material.x;
  float roughness = max(surface.material.y, 0.25 * reflectivity);
  IndirectLightProbeAccumulation probes = GatherIndirectLightProbes(
      unscaledUv, surface.depth, worldPosition, reflectionWorld,
      normalWorld, roughness * 5.0, 1.0 - saturate(0.5 * roughness));

  float3 localReflection = probes.reflection
      / max(0.125, probes.reflectionWeight);
  float3 gpuReflection = probes.gpuReflection
      / max(0.001, probes.gpuReflectionWeight);
  float reflectionBlend = saturate(probes.reflectionWeight);
  float3 probeReflection = lerp(
      gpuReflection, localReflection, reflectionBlend * reflectionBlend);
  float3 probeGi = probes.diffuseGi / max(1.0, probes.diffuseGiWeight);
  float probeAo = GatherIndirectLightProbeAo(
      unscaledUv, surface.depth, worldPosition, normalWorld);

  float historyBlend = history.confidence
      * saturate(1.0 - surface.depth / max(1.0, cb_hdr.fMaxDepth));
  float3 screenReflection = tSSR.SampleLevel(
      LinearClampClamp_s, surface.scaledUv, roughness * 5.0);
  float3 reflection = lerp(probeReflection, screenReflection, historyBlend);
  float3 diffuseIndirect = lerp(
      probeGi, history.radiance, history.confidence) * surface.diffuse;
  float reflectionEnergy = 1.0 - reflectivity * reflectivity;
  float3 indirect = diffuseIndirect + reflection * reflectionEnergy;
  indirect *= 0.884955764;
  indirect /= dot(indirect, float3(0.299, 0.587, 0.114)) * 0.2 + 1.4;
  result.indirectAo.xyz = ApplyIndirectLightMetalProfile(
      indirect, surface.diffuse, surface.neighborProfiles.x);
  if (enableScreenAo)
    result.indirectAo.w = min(result.indirectAo.w,
        lerp(1.0, probeAo, history.confidence));
  result.temporalConfidence = lerp(
      1.0, history.confidence, cb_settings.fInvSSGIKillSwitch);
  return result;
}

IndirectLightUltraResult EvaluateIndirectLightOrthoUltra(
    float2 unscaledUv,
    float qualityRadiusScale)
{
  return EvaluateIndirectLightOrthoUltraPolicy(
      unscaledUv, qualityRadiusScale, true, 0u);
}

float EvaluateIndirectLightPerspectiveUltraAo(
    IndirectLightSurface surface,
    float2 unscaledUv,
    float qualityRadiusScale)
{
  uint2 aoSize = max(1u, cb_settings.vuSize);
  float2 quantizedUv = floor(cb_settings.vInvRenderScale
      * surface.scaledUv * (float2)aoSize) / (float2)aoSize;
  float3 center = LoadIndirectLightAoViewPosition(quantizedUv, aoSize);
  center += surface.normalView * 0.03;
  float3 viewDirection = normalize(center);
  float projectedRadius = max(3.0,
      (2.0 * cb_settings.vStart.x * cb_settings.fProjectionScale)
      * qualityRadiusScale / max(0.01, surface.depth) / 3.0);
  float noise = abs(frac(cb_fTime * 0.1
      + tScreenNoise.Load(uint3(
          (uint2)(cb_vTargetSize * unscaledUv) & 63u, 0))) - 0.5);
  float initialRadius = saturate(0.25 * surface.depth - 1.0)
      * projectedRadius + frac(noise * projectedRadius) * 0.8;
  float ao = 0.0;
  [unroll]
  for (uint slice = 0u; slice < 3u; ++slice)
  {
    float angle = 2.09439516 * (float)slice;
    float sine;
    float cosine;
    sincos(angle, sine, cosine);
    ao += EvaluateIndirectLightHorizonSlice(
        surface.scaledUv, aoSize, center, viewDirection,
        surface.normalView, float2(cosine, sine),
        initialRadius + projectedRadius, projectedRadius);
  }
  ao *= 1.0 / 3.0;
  float depthFade = saturate(0.002 * surface.depth);
  ao = 1.0 - (1.0 - ao) * (1.0 - depthFade * depthFade);
  return pow(max(1.0e-4, ao), cb_settings.vAdd.y);
}

IndirectLightPerspectiveUltraResult EvaluateIndirectLightPerspectiveUltra(
    float2 unscaledUv,
    float qualityRadiusScale,
    uint subsurfaceLayerCount)
{
  IndirectLightPerspectiveUltraResult result;
  result.indirectAo = float4(0.0, 0.0, 0.0, 1.0);
  result.temporalConfidence = 1.0;
  result.occlusion = 1.0;
  IndirectLightSurface surface = LoadIndirectLightSurface(unscaledUv);
  if (surface.depth >= cb_vNearFarViewCorner.y - 1.0)
    return result;

  bool receivesIndirect = surface.material.z < 0.941176474;
  if (receivesIndirect && surface.depth < 500.0)
  {
    result.indirectAo.w = EvaluateIndirectLightPerspectiveUltraAo(
        surface, unscaledUv, qualityRadiusScale);
    result.occlusion = EvaluateIndirectLightSubsurfaceSet(
        surface, unscaledUv, subsurfaceLayerCount);
  }

  float3 viewPosition = float3(
      surface.viewCorner * surface.depth, -surface.depth);
  float3 worldPosition = TransformIndirectLightPosition(
      viewToWorld, viewPosition);
  IndirectLightUltraHistory history = ResolveIndirectLightUltraHistory(
      surface, worldPosition);
  float3 viewDirection = normalize(viewPosition);
  float3 reflectionView = normalize(reflect(
      viewDirection, surface.normalView));
  float3 reflectionWorld = normalize(TransformIndirectLightDirection(
      viewToWorld, reflectionView));
  float3 normalWorld = normalize(TransformIndirectLightDirection(
      viewToWorld, surface.normalView));
  float reflectivity = 1.0 - surface.material.x;
  float roughness = max(surface.material.y, 0.25 * reflectivity);
  IndirectLightProbeAccumulation probes = GatherIndirectLightProbes(
      unscaledUv, surface.depth, worldPosition, reflectionWorld,
      normalWorld, roughness * 5.0, 1.0 - saturate(0.5 * roughness));

  float3 localReflection = probes.reflection
      / max(0.125, probes.reflectionWeight);
  float3 gpuReflection = probes.gpuReflection
      / max(0.001, probes.gpuReflectionWeight);
  float reflectionBlend = saturate(probes.reflectionWeight);
  float3 probeReflection = lerp(
      gpuReflection, localReflection, reflectionBlend * reflectionBlend);
  float3 probeGi = probes.diffuseGi / max(1.0, probes.diffuseGiWeight);
  float probeAo = GatherIndirectLightProbeAo(
      unscaledUv, surface.depth, worldPosition, normalWorld);
  float historyBlend = history.confidence
      * saturate(1.0 - surface.depth / max(1.0, cb_hdr.fMaxDepth));
  float3 screenReflection = tSSR.SampleLevel(
      LinearClampClamp_s, surface.scaledUv, roughness * 5.0);
  float3 reflection = lerp(
      probeReflection, screenReflection, historyBlend);
  float3 diffuseIndirect = lerp(
      probeGi, history.radiance, history.confidence) * surface.diffuse;
  float reflectionEnergy = 1.0 - reflectivity * reflectivity;
  float3 indirect = diffuseIndirect + reflection * reflectionEnergy;
  indirect *= 0.884955764;
  indirect /= dot(indirect, float3(0.299, 0.587, 0.114)) * 0.2 + 1.4;
  result.indirectAo.xyz = ApplyIndirectLightMetalProfile(
      indirect, surface.diffuse, surface.neighborProfiles.x);
  result.indirectAo.w = min(result.indirectAo.w,
      lerp(1.0, probeAo, history.confidence));
  result.temporalConfidence = lerp(
      1.0, history.confidence, cb_settings.fInvSSGIKillSwitch);
  return result;
}

IndirectLightPerspectiveUltraResult
EvaluateIndirectLightPerspectiveUltraNoAo(
    float2 unscaledUv,
    uint subsurfaceLayerCount)
{
  IndirectLightPerspectiveUltraResult result =
      EvaluateIndirectLightPerspectiveUltra(
          unscaledUv, 1.0, subsurfaceLayerCount);
  result.indirectAo.w = 1.0;
  return result;
}

float EvaluateIndirectLightUltraCascadeSssLayer(
    IndirectLightSurface surface,
    uint clusterIndex,
    bool clusterHasSubsurface,
    bool thinSurface,
    uint wordIndex,
    uint bitIndex,
    float3 lightPointView)
{
  if (!clusterHasSubsurface)
    return 1.0;
  uint lightWord = sbVoxelLightIds[
      clusterIndex * 33u + 1u + wordIndex];
  if ((lightWord & bitIndex) == 0u)
    return 1.0;
  return TraceIndirectLightSubsurface(
      surface, lightPointView, thinSurface);
}

IndirectLightPerspectiveUltraResult
EvaluateIndirectLightPerspectiveUltraCascadePolicy(
    float2 unscaledUv,
    float qualityRadiusScale,
    bool enableScreenAo,
    uint outputCount)
{
  IndirectLightPerspectiveUltraResult result =
      EvaluateIndirectLightPerspectiveUltra(
          unscaledUv, qualityRadiusScale, 0u);
  if (!enableScreenAo)
    result.indirectAo.w = 1.0;
  result.occlusion = 1.0;
  if (outputCount == 0u)
    return result;

  IndirectLightSurface surface = LoadIndirectLightSurface(unscaledUv);
  bool receivesIndirect = surface.depth < cb_vNearFarViewCorner.y - 1.0
      && surface.material.z < 0.941176474
      && surface.depth < 500.0;
  if (!receivesIndirect)
    return result;

  float directionalFacing = dot(
      surface.normalView, cb_vDirectionalLightDirectionView);
  if (directionalFacing < 0.330000013)
  {
    result.occlusion.x = TraceIndirectLightCascade(
        surface, directionalFacing);
  }
  if (outputCount == 1u)
  {
    result.occlusion.x = lerp(
        1.0, result.occlusion.x, cb_settings.fInvSSGIKillSwitch);
    return result;
  }

  uint slice = (uint)floor(cb_cluster.vVoxelDims.z * sqrt(
      surface.depth * cb_cluster.fRcpClusterRange
      + cb_cluster.fClusterNearBias));
  uint2 tile = (uint2)(cb_cluster.vVoxelDims.xy * unscaledUv);
  uint clusterIndex = slice * cb_cluster.uClusterSliceSize
      + tile.y * cb_cluster.uClusterWidth + tile.x;
  uint clusterMask = sbVoxelLightIds[clusterIndex * 33u];
  bool clusterHasSubsurface =
      (clusterMask & cb_settings.uSSMask) != 0u;
  bool thinSurface = any(surface.neighborProfiles == 2u);
  result.occlusion.y = EvaluateIndirectLightUltraCascadeSssLayer(
      surface, clusterIndex, clusterHasSubsurface, thinSurface,
      cb_settings.arrSsLight[1].uWordIndex,
      cb_settings.arrSsLight[1].uBitIndex,
      cb_settings.arrSsLight[1].vPointView);
  if (outputCount > 2u)
  {
    result.occlusion.z = EvaluateIndirectLightUltraCascadeSssLayer(
        surface, clusterIndex, clusterHasSubsurface, thinSurface,
        cb_settings.arrSsLight[2].uWordIndex,
        cb_settings.arrSsLight[2].uBitIndex,
        cb_settings.arrSsLight[2].vPointView);
  }
  if (outputCount > 3u)
  {
    result.occlusion.w = EvaluateIndirectLightUltraCascadeSssLayer(
        surface, clusterIndex, clusterHasSubsurface, thinSurface,
        cb_settings.arrSsLight[3].uWordIndex,
        cb_settings.arrSsLight[3].uBitIndex,
        cb_settings.arrSsLight[3].vPointView);
  }
  result.occlusion = lerp(
      1.0, result.occlusion, cb_settings.fInvSSGIKillSwitch);
  return result;
}

IndirectLightPerspectiveUltraResult
EvaluateIndirectLightPerspectiveUltraCascade(
    float2 unscaledUv,
    float qualityRadiusScale,
    uint outputCount)
{
  return EvaluateIndirectLightPerspectiveUltraCascadePolicy(
      unscaledUv, qualityRadiusScale, true, outputCount);
}

IndirectLightPerspectiveUltraResult
EvaluateIndirectLightOrthoUltraCascadePolicy(
    float2 unscaledUv,
    float qualityRadiusScale,
    bool enableScreenAo,
    uint outputCount)
{
  IndirectLightUltraResult base = EvaluateIndirectLightOrthoUltraPolicy(
      unscaledUv, qualityRadiusScale, enableScreenAo, 0u);
  IndirectLightPerspectiveUltraResult result;
  result.indirectAo = base.indirectAo;
  result.temporalConfidence = base.temporalConfidence;
  result.occlusion = 1.0;
  if (outputCount == 0u)
    return result;

  IndirectLightSurface surface = LoadIndirectLightOrthoSurface(unscaledUv);
  bool receivesIndirect = surface.depth < cb_vNearFarViewCorner.y - 1.0
      && surface.material.z < 0.941176474
      && surface.depth < 500.0;
  if (!receivesIndirect)
    return result;

  float directionalFacing = dot(
      surface.normalView, cb_vDirectionalLightDirectionView);
  if (directionalFacing < 0.330000013)
    result.occlusion.x = TraceIndirectLightCascade(
        surface, directionalFacing);
  if (outputCount == 1u)
  {
    result.occlusion.x = lerp(
        1.0, result.occlusion.x, cb_settings.fInvSSGIKillSwitch);
    return result;
  }

  uint slice = (uint)floor(cb_cluster.vVoxelDims.z * sqrt(
      surface.depth * cb_cluster.fRcpClusterRange
      + cb_cluster.fClusterNearBias));
  uint2 tile = (uint2)(cb_cluster.vVoxelDims.xy * unscaledUv);
  uint clusterIndex = slice * cb_cluster.uClusterSliceSize
      + tile.y * cb_cluster.uClusterWidth + tile.x;
  uint clusterMask = sbVoxelLightIds[clusterIndex * 33u];
  bool clusterHasSubsurface =
      (clusterMask & cb_settings.uSSMask) != 0u;
  bool thinSurface = any(surface.neighborProfiles == 2u);
  result.occlusion.y = EvaluateIndirectLightUltraCascadeSssLayer(
      surface, clusterIndex, clusterHasSubsurface, thinSurface,
      cb_settings.arrSsLight[1].uWordIndex,
      cb_settings.arrSsLight[1].uBitIndex,
      cb_settings.arrSsLight[1].vPointView);
  if (outputCount > 2u)
    result.occlusion.z = EvaluateIndirectLightUltraCascadeSssLayer(
        surface, clusterIndex, clusterHasSubsurface, thinSurface,
        cb_settings.arrSsLight[2].uWordIndex,
        cb_settings.arrSsLight[2].uBitIndex,
        cb_settings.arrSsLight[2].vPointView);
  if (outputCount > 3u)
    result.occlusion.w = EvaluateIndirectLightUltraCascadeSssLayer(
        surface, clusterIndex, clusterHasSubsurface, thinSurface,
        cb_settings.arrSsLight[3].uWordIndex,
        cb_settings.arrSsLight[3].uBitIndex,
        cb_settings.arrSsLight[3].vPointView);
  result.occlusion = lerp(
      1.0, result.occlusion, cb_settings.fInvSSGIKillSwitch);
  return result;
}
