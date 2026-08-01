// Orthographic temporal-SSGI policy shared by the indirect-light family.
#include "indirect_light_probe_cascade.hlsl"

#ifndef INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI
#define INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI 1
#endif

#ifndef INDIRECT_LIGHT_ENABLE_PROBE_AO
#define INDIRECT_LIGHT_ENABLE_PROBE_AO INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI
#endif

#if INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI
struct IndirectLightTemporalSample
{
  float3 radiance;
  float confidence;
  float depth;
};

struct IndirectLightOrthoSsgiResult
{
  float4 indirectAo;
  float temporalConfidence;
  float4 subsurfaceOcclusion;
};
#endif

struct IndirectLightOrthoMediumResult
{
  float4 indirectAo;
  float subsurface;
  float4 occlusion;
};

#if INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI
float SignedSquareIndirectLight(float value)
{
  return value * abs(value);
}

float3 DecodeIndirectLightTemporalRadiance(uint packed)
{
  float exponent = (float)((packed >> 10u) & 63u) * (1.0 / 63.0);
  float chromaA = (float)((packed >> 5u) & 31u) * (1.0 / 15.0) - 1.0;
  float chromaB = (float)(packed & 31u) * (1.0 / 15.0) - 1.0;
  chromaA = SignedSquareIndirectLight(chromaA);
  chromaB = SignedSquareIndirectLight(chromaB);
  float scale = 64.0 * exponent * exponent * exponent * exponent;
  return max(0.0, float3(
      1.0 + 2.0 * (chromaB - chromaA),
      1.0 + 2.0 * chromaA,
      1.0 - 2.0 * (chromaA + chromaB)) * scale);
}

IndirectLightTemporalSample LoadIndirectLightTemporalSample(
    uint2 pixel,
    uint2 temporalSize)
{
  pixel = min(pixel, temporalSize - 1u);
  float2 encoded = tSSGITemporal.Load(uint3(pixel, 0));
  IndirectLightTemporalSample sample;
  sample.radiance = DecodeIndirectLightTemporalRadiance(
      (uint)(encoded.x * 65535.0 + 0.5));
  sample.depth = encoded.y * encoded.y
      * (cb_hdr.fMaxDepth - INDIRECT_LIGHT_MIN_DEPTH)
      + INDIRECT_LIGHT_MIN_DEPTH;
  sample.confidence = encoded.x != 0.0 ? 1.0 : 0.0;
  return sample;
}
#endif

IndirectLightSurface LoadIndirectLightOrthoSurface(float2 unscaledUv)
{
  IndirectLightSurface surface;
  surface.scaledUv = cb_settings.vRenderScale * unscaledUv;
  uint2 aoPixel = (uint2)(surface.scaledUv * (float2)cb_settings.vuSize);
  surface.pixel = aoPixel << 1;
  surface.depth = tHzb.Load(uint3(aoPixel, 0));
  float2 clip = unscaledUv * float2(2.0, -2.0) + float2(-1.0, 1.0);
  surface.viewCorner = cb_vNearFarViewCorner.zw * clip + cb_vViewTranslate;
  surface.normalView = DecodeIndirectLightNormal(
      tNormal.Load(uint3(surface.pixel, 0)).xy);
#if INDIRECT_LIGHT_ENABLE_DIFFUSE
  surface.diffuse = tDiffuse.Load(uint3(surface.pixel, 0)).xyz;
#else
  surface.diffuse = 0.0;
#endif
  surface.material = tMaterial.Load(uint3(surface.pixel, 0)).xyw;
  surface.neighborProfiles = (uint4)(
      tMaterial.Gather(PointClampClamp_s, surface.scaledUv) * 255.0 + 0.5) & 7u;
  return surface;
}

float3 IndirectLightOrthoViewPosition(
    IndirectLightSurface surface,
    float depth)
{
  // The recovered orthographic path stores vertical, depth and horizontal
  // coordinates in this order before applying the view/world matrix.
  return float3(surface.viewCorner.y, -depth, surface.viewCorner.x);
}

float3 LoadIndirectLightOrthoAoViewPosition(
    float2 scaledUv,
    uint2 aoSize)
{
  float2 clampedUv = clamp(scaledUv, 0.0, cb_settings.vRenderScale);
  uint2 pixel = min((uint2)(cb_settings.vInvRenderScale
      * clampedUv * (float2)aoSize), aoSize - 1u);
  float2 unscaledUv = ((float2)pixel + 0.5) / (float2)aoSize;
  float depth = DecodeIndirectLightDepth(tAoDepth.SampleLevel(
      LinearClampClamp_s, clampedUv, 0.0));
  float2 clip = unscaledUv * float2(2.0, -2.0) + float2(-1.0, 1.0);
  float2 viewCorner = cb_vNearFarViewCorner.zw * clip + cb_vViewTranslate;
  return float3(viewCorner.y, -depth, viewCorner.x);
}

float EvaluateIndirectLightOrthoHorizonSlice(
    float2 scaledUv,
    uint2 aoSize,
    float3 centerViewPosition,
    float3 viewDirection,
    float3 normalView,
    float2 axis,
    float initialRadius,
    float radiusStep)
{
  float2 horizon = -1.0;
  [unroll]
  for (uint sampleIndex = 0u; sampleIndex < 4u; ++sampleIndex)
  {
    float radius = initialRadius + radiusStep * sampleIndex;
    float2 offset = axis * radius * cb_settings.vFlippedPixelSize;
    float3 positive = LoadIndirectLightOrthoAoViewPosition(
        scaledUv + offset, aoSize) - centerViewPosition;
    float3 negative = LoadIndirectLightOrthoAoViewPosition(
        scaledUv - offset, aoSize) - centerViewPosition;
    float positiveLength = max(1.0e-4, length(positive));
    float negativeLength = max(1.0e-4, length(negative));
    float distanceFade = rcp(max(1.0,
        radius * cb_settings.fRcpFadeDistance));
    horizon.x = max(horizon.x, lerp(-1.0,
        dot(positive / positiveLength, -viewDirection), distanceFade));
    horizon.y = max(horizon.y, lerp(-1.0,
        dot(negative / negativeLength, -viewDirection), distanceFade));
  }
  float3 tangent = normalize(float3(axis.y, 0.0, axis.x));
  float projectedNormal = saturate(dot(normalView, tangent) * 0.5 + 0.5);
  float visibility = 1.0 - 0.25 * saturate(horizon.x + horizon.y + 2.0);
  return lerp(visibility, 1.0, projectedNormal * projectedNormal);
}

float EvaluateIndirectLightOrthoAoQuality(
    IndirectLightSurface surface,
    float2 unscaledUv,
    float qualityRadiusScale)
{
  uint2 aoSize = cb_settings.vuSize;
  float2 quantizedUv = ((uint2)(surface.scaledUv * (float2)aoSize) + 0.5)
      / (float2)aoSize;
  float3 center = LoadIndirectLightOrthoAoViewPosition(
      quantizedUv, aoSize);
  center += surface.normalView * 0.03;
  float3 viewDirection = normalize(-center);
  float depthScale = saturate(0.002 * surface.depth);
  float worldRadius = cb_settings.vStart.x + cb_settings.vAdd.x * depthScale;
  float projectedRadius = max(3.0,
      cb_settings.fProjectionScale * (2.0 * worldRadius)
      * qualityRadiusScale
      / max(0.01, surface.depth) / 3.0);
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

float EvaluateIndirectLightOrthoMediumAo(
    IndirectLightSurface surface,
    float2 unscaledUv)
{
  return EvaluateIndirectLightOrthoAoQuality(
      surface, unscaledUv, 1.0);
}

float EvaluateIndirectLightSubsurfaceLayer(
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

float4 EvaluateIndirectLightSubsurfaceSet(
    IndirectLightSurface surface,
    float2 unscaledUv,
    uint layerCount)
{
  float4 visibility = 1.0;
  uint slice = (uint)floor(cb_cluster.vVoxelDims.z * sqrt(
      surface.depth * cb_cluster.fRcpClusterRange
      + cb_cluster.fClusterNearBias));
  uint2 tile = (uint2)(cb_cluster.vVoxelDims.xy * unscaledUv);
  uint clusterIndex = slice * cb_cluster.uClusterSliceSize
      + tile.y * cb_cluster.uClusterWidth + tile.x;
  uint clusterMask = sbVoxelLightIds[clusterIndex * 33u];
  bool clusterHasSubsurface = (clusterMask & cb_settings.uSSMask) != 0u;
  bool thinSurface = any(surface.neighborProfiles == 2u);
  if (layerCount > 0u)
    visibility.x = EvaluateIndirectLightSubsurfaceLayer(
        surface, clusterIndex, clusterHasSubsurface, thinSurface,
        cb_settings.arrSsLight[0].uWordIndex,
        cb_settings.arrSsLight[0].uBitIndex,
        cb_settings.arrSsLight[0].vPointView);
  if (layerCount > 1u)
    visibility.y = EvaluateIndirectLightSubsurfaceLayer(
        surface, clusterIndex, clusterHasSubsurface, thinSurface,
        cb_settings.arrSsLight[1].uWordIndex,
        cb_settings.arrSsLight[1].uBitIndex,
        cb_settings.arrSsLight[1].vPointView);
  if (layerCount > 2u)
    visibility.z = EvaluateIndirectLightSubsurfaceLayer(
        surface, clusterIndex, clusterHasSubsurface, thinSurface,
        cb_settings.arrSsLight[2].uWordIndex,
        cb_settings.arrSsLight[2].uBitIndex,
        cb_settings.arrSsLight[2].vPointView);
  if (layerCount > 3u)
    visibility.w = EvaluateIndirectLightSubsurfaceLayer(
        surface, clusterIndex, clusterHasSubsurface, thinSurface,
        cb_settings.arrSsLight[3].uWordIndex,
        cb_settings.arrSsLight[3].uBitIndex,
        cb_settings.arrSsLight[3].vPointView);
  visibility *= visibility * visibility;
  return lerp(1.0, visibility, cb_settings.fInvSSGIKillSwitch);
}

#if INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI
IndirectLightTemporalSample GatherIndirectLightTemporalSsgi(
    IndirectLightSurface surface,
    float2 unscaledUv)
{
  uint2 temporalSize = max(1u, cb_settings.vuSize >> 1u);
  float2 temporalPosition = surface.scaledUv * (float2)temporalSize - 1.5;
  int2 basePixel = (int2)floor(temporalPosition);
  float3 radiance = 0.0;
  float totalWeight = 0.0;
  float weightedDepth = 0.0;
  [unroll]
  for (uint y = 0u; y < 4u; ++y)
  {
    [unroll]
    for (uint x = 0u; x < 4u; ++x)
    {
      uint2 pixel = (uint2)max(0, basePixel + int2(x, y));
      IndirectLightTemporalSample tap =
          LoadIndirectLightTemporalSample(pixel, temporalSize);
      float depthTolerance = clamp(
          cb_settings.fThresholdBase * surface.depth * surface.depth,
          0.001, 0.05);
      float depthWeight = saturate(
          1.0 - abs(tap.depth - surface.depth) / depthTolerance);
      float2 delta = (float2)(basePixel + int2(x, y))
          + 0.5 - temporalPosition;
      float spatialWeight = saturate(1.0 - 0.25 * dot(delta, delta));
      float weight = tap.confidence * depthWeight * spatialWeight;
      radiance += tap.radiance * weight;
      weightedDepth += tap.depth * weight;
      totalWeight += weight;
    }
  }
  IndirectLightTemporalSample result;
  result.radiance = radiance / max(0.001, totalWeight);
  result.depth = weightedDepth / max(0.001, totalWeight);
  result.confidence = saturate(totalWeight * (1.0 / 12.0));
  return result;
}
#endif

#if INDIRECT_LIGHT_ENABLE_PROBE_AO
float GatherIndirectLightProbeAo(
    float2 unscaledUv,
    float depth,
    float3 worldPosition,
    float3 normalWorld)
{
  float weightedAo = 0.0;
  float totalWeight = 0.0;
  uint slice = (uint)floor(cb_cluster.vVoxelDims.z * sqrt(
      depth * cb_cluster.fRcpClusterRange + cb_cluster.fClusterNearBias));
  uint2 tile = (uint2)(cb_cluster.vVoxelDims.xy * unscaledUv);
  uint clusterIndex = slice * cb_cluster.uClusterSliceSize
      + tile.y * cb_cluster.uClusterWidth + tile.x;
  uint wordMask = sbVoxelLightIds[clusterIndex * 33u] & 0xff000000u;
  uint wordBase = clusterIndex * 33u + 1u;
  while (wordMask != 0u)
  {
    uint wordIndex = firstbitlow(wordMask);
    wordMask ^= 1u << wordIndex;
    uint probeMask = sbVoxelLightIds[wordBase + wordIndex];
    uint probeBase = (wordIndex << 5u) - 768u;
    while (probeMask != 0u)
    {
      uint bitIndex = firstbitlow(probeMask);
      probeMask ^= 1u << bitIndex;
      uint probeIndex = probeBase + bitIndex;
      if (cb_reflections.vecProbes[probeIndex].fGiEnable == 0.0)
        continue;
      float3 local = worldPosition
          - cb_reflections.vecProbes[probeIndex].vPosition;
      float signedDistance = DistanceToIndirectLightProbeBox(
          local, cb_reflections.vecProbes[probeIndex].vExtents)
          - cb_reflections.vecProbes[probeIndex].fMargin;
      if (signedDistance >= 0.0)
        continue;
      float weight = cb_reflections.vecProbes[probeIndex].fBlend
          * (cb_reflections.vecProbes[probeIndex].fIsFallback != 0.0
             ? 1.0 : saturate(-signedDistance
                 * cb_reflections.vecProbes[probeIndex].fMarginRcp));
      float ao = taAo.SampleLevel(LinearMirrorMirror_s,
          float3(EncodeIndirectLightOctahedron(normalWorld),
                 cb_reflections.vecProbes[probeIndex].fSlotIndex), 0.0);
      weightedAo += ao * weight;
      totalWeight += weight;
    }
  }
  return totalWeight > 0.0 ? weightedAo / max(1.0, totalWeight) : 1.0;
}
#endif

#if INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI
IndirectLightOrthoSsgiResult EvaluateIndirectLightOrthoSsgiPolicy(
    float2 unscaledUv,
    uint subsurfaceLayerCount,
    float qualityRadiusScale,
    bool enableScreenAo)
{
  IndirectLightOrthoSsgiResult result;
  result.indirectAo = float4(0.0, 0.0, 0.0, 1.0);
  result.temporalConfidence = 1.0;
  result.subsurfaceOcclusion = 1.0;
  IndirectLightSurface surface = LoadIndirectLightOrthoSurface(unscaledUv);
  if (surface.depth >= cb_vNearFarViewCorner.y - 1.0)
    return result;

  bool receivesIndirect = surface.material.z < 0.941176474;
  if (receivesIndirect && surface.depth < 500.0)
  {
    if (enableScreenAo)
      result.indirectAo.w = EvaluateIndirectLightOrthoAoQuality(
          surface, unscaledUv, qualityRadiusScale);
    result.subsurfaceOcclusion = EvaluateIndirectLightSubsurfaceSet(
        surface, unscaledUv, subsurfaceLayerCount);
  }

  IndirectLightTemporalSample temporal =
      GatherIndirectLightTemporalSsgi(surface, unscaledUv);
  float2 previousUv = min(cb_settings.vRenderScale,
      cb_settings.vRenderScale * unscaledUv);
  float volatility = abs(tVolatile.SampleLevel(
      PointClampClamp_s, previousUv, 0.0));
  float hitConfidence = 1.0 - saturate(abs(tHitCache.SampleLevel(
      PointClampClamp_s, previousUv * cb_vPrevRenderScale, 0.0)));
  float stability = saturate(cb_fRenderScaleStability
      * (1.0 - volatility * volatility) * hitConfidence);
  temporal.confidence *= stability;

  float3 viewPosition = IndirectLightOrthoViewPosition(surface, surface.depth);
  float3 worldPosition = TransformIndirectLightPosition(viewToWorld, viewPosition);
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
  float3 probeReflection = probes.reflection
      / max(0.125, probes.reflectionWeight);
  float3 gpuReflection = probes.gpuReflection
      / max(0.001, probes.gpuReflectionWeight);
  float reflectionBlend = saturate(probes.reflectionWeight);
  probeReflection = lerp(gpuReflection, probeReflection,
      reflectionBlend * reflectionBlend);
  float3 probeGi = probes.diffuseGi / max(1.0, probes.diffuseGiWeight);
  float probeAo = 1.0;
  if (enableScreenAo)
    probeAo = GatherIndirectLightProbeAo(
        unscaledUv, surface.depth, worldPosition, normalWorld);

  uint2 fullSize = max(1u, cb_settings.vuSize);
  uint2 fullPixel = min(fullSize - 1u,
      (uint2)(surface.scaledUv * (float2)fullSize));
  float3 screenReflection = tSSR.Load(uint3(fullPixel, 0));
  float screenReflectionWeight = temporal.confidence
      * saturate(1.0 - 0.02 * surface.depth);
  float3 reflection = lerp(probeReflection, screenReflection,
      screenReflectionWeight);
  float3 diffuseIndirect = lerp(probeGi, temporal.radiance,
      temporal.confidence) * surface.diffuse;
  float reflectionEnergy = 1.0 - reflectivity * reflectivity;
  float3 indirect = diffuseIndirect + reflection * reflectionEnergy;
  indirect *= 0.884955764;
  indirect /= dot(indirect, float3(0.299, 0.587, 0.114)) * 0.2 + 1.4;
  result.indirectAo.xyz = ApplyIndirectLightMetalProfile(
      indirect, surface.diffuse, surface.neighborProfiles.x);
  result.indirectAo.w = min(result.indirectAo.w,
      lerp(1.0, probeAo, temporal.confidence));
  result.temporalConfidence = lerp(1.0, temporal.confidence,
      cb_settings.fInvSSGIKillSwitch);
  return result;
}

IndirectLightOrthoSsgiResult EvaluateIndirectLightOrthoSsgi(
    float2 unscaledUv,
    uint subsurfaceLayerCount,
    float qualityRadiusScale)
{
  return EvaluateIndirectLightOrthoSsgiPolicy(
      unscaledUv, subsurfaceLayerCount, qualityRadiusScale, true);
}
#endif

#if INDIRECT_LIGHT_ENABLE_REFLECTION
float3 EvaluateIndirectLightOrthoReflection(
    IndirectLightSurface surface,
    float2 unscaledUv)
{
  float reflectivity = 1.0 - surface.material.x;
  float reflectionEnergy = 1.0 - reflectivity * reflectivity;
  if (reflectionEnergy <= 0.1
      || surface.depth >= cb_cluster.fClusterMaxFarReflections)
    return 0.0;
  float3 viewPosition = IndirectLightOrthoViewPosition(surface, surface.depth);
  float3 worldPosition = TransformIndirectLightPosition(viewToWorld, viewPosition);
  float3 viewDirection = normalize(viewPosition);
  float3 reflectionView = normalize(reflect(viewDirection, surface.normalView));
  float3 reflectionWorld = normalize(TransformIndirectLightDirection(
      viewToWorld, reflectionView));
  float3 normalWorld = normalize(TransformIndirectLightDirection(
      viewToWorld, surface.normalView));
  float roughness = max(surface.material.y, 0.25 * reflectivity);
  IndirectLightProbeAccumulation probes = GatherIndirectLightProbes(
      unscaledUv, surface.depth, worldPosition, reflectionWorld,
      normalWorld, roughness * 5.0, 1.0 - saturate(0.5 * roughness));
  float3 reflection = probes.reflection / max(0.125,
      probes.reflectionWeight);
  float3 gpuReflection = probes.gpuReflection / max(0.001,
      probes.gpuReflectionWeight);
  float blend = saturate(probes.reflectionWeight);
  return reflectionEnergy * lerp(gpuReflection, reflection, blend * blend);
}

IndirectLightOrthoMediumResult EvaluateIndirectLightOrthoReflectionPolicy(
    float2 unscaledUv,
    float qualityRadiusScale,
    bool enableScreenAo,
    uint subsurfaceLayerCount)
{
  IndirectLightOrthoMediumResult result;
  result.indirectAo = float4(0.0, 0.0, 0.0, 1.0);
  result.subsurface = 1.0;
  result.occlusion = 1.0;
  IndirectLightSurface surface = LoadIndirectLightOrthoSurface(unscaledUv);
  if (surface.depth >= cb_vNearFarViewCorner.y - 1.0)
    return result;
  bool receivesIndirect = surface.material.z < 0.941176474
      && surface.depth < 500.0;
  if (receivesIndirect)
  {
    if (enableScreenAo)
      result.indirectAo.w = EvaluateIndirectLightOrthoAoQuality(
          surface, unscaledUv, qualityRadiusScale);
    if (subsurfaceLayerCount > 0u)
      result.occlusion = EvaluateIndirectLightSubsurfaceSet(
          surface, unscaledUv, subsurfaceLayerCount);
  }
  result.indirectAo.xyz = EvaluateIndirectLightOrthoReflection(
      surface, unscaledUv);
  result.indirectAo.xyz *= 0.884955764;
  float compression = dot(result.indirectAo.xyz,
      float3(0.299, 0.587, 0.114)) * 0.2 + 1.4;
  result.indirectAo.xyz /= compression;
  result.indirectAo.xyz = ApplyIndirectLightMetalProfile(
      result.indirectAo.xyz, surface.diffuse, surface.neighborProfiles.x);
  return result;
}

IndirectLightOrthoMediumResult EvaluateIndirectLightOrthoMediumReflection(
    float2 unscaledUv,
    uint subsurfaceLayerCount)
{
  return EvaluateIndirectLightOrthoReflectionPolicy(
      unscaledUv, 1.0, true, subsurfaceLayerCount);
}
#endif
