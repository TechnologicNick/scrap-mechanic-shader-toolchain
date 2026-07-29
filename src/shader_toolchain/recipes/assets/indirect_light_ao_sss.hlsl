// Perspective horizon AO with an ABI-optional set of clustered SSS rays.
#ifndef INDIRECT_LIGHT_AO_SSS_COUNT
#define INDIRECT_LIGHT_AO_SSS_COUNT 0
#endif

static const float INDIRECT_LIGHT_AO_MIN_DEPTH = 0.100000001;
static const float INDIRECT_LIGHT_AO_DEPTH_RANGE = 499.899994;

struct IndirectLightAoSurface
{
  float2 scaledUv;
  uint2 pixel;
  float depth;
  float2 viewCorner;
  float3 normalView;
  float3 material;
  uint profile;
};

struct IndirectLightAoSssResult
{
  float4 ambientOcclusion;
  float subsurface;
  float4 occlusion;
};

float DecodeIndirectLightAoDepth(float encodedDepth)
{
  return encodedDepth * encodedDepth * INDIRECT_LIGHT_AO_DEPTH_RANGE
      + INDIRECT_LIGHT_AO_MIN_DEPTH;
}

float3 DecodeIndirectLightAoNormal(float2 encoded)
{
  float2 octahedron = encoded * 2.0 - 1.0;
  float3 normal = float3(
      octahedron, 1.0 - abs(octahedron.x) - abs(octahedron.y));
  float fold = saturate(-normal.z);
  normal.xy += (normal.xy >= 0.0) ? -fold : fold;
  return normalize(normal);
}

IndirectLightAoSurface LoadIndirectLightAoSurface(float2 unscaledUv)
{
  IndirectLightAoSurface surface;
  surface.scaledUv = cb_settings.vRenderScale * unscaledUv;
  uint2 aoPixel = (uint2)(surface.scaledUv * (float2)cb_settings.vuSize);
  surface.pixel = aoPixel << 1;
  surface.depth = tHzb.Load(uint3(aoPixel, 0));
  float2 clip = unscaledUv * float2(2.0, -2.0) + float2(-1.0, 1.0);
  surface.viewCorner = cb_vNearFarViewCorner.zw * clip;
  surface.normalView = DecodeIndirectLightAoNormal(
      tNormal.Load(uint3(surface.pixel, 0)).xy);
  surface.material = tMaterial.Load(uint3(surface.pixel, 0)).xyw;
  surface.profile = (uint)(surface.material.z * 255.0 + 0.5) & 7u;
  return surface;
}

float3 LoadIndirectLightAoOnlyViewPosition(float2 scaledUv, uint2 aoSize)
{
  float2 clampedUv = saturate(scaledUv);
  uint2 pixel = min((uint2)(clampedUv * (float2)aoSize), aoSize - 1u);
  float2 pixelUv = (float2)pixel / (float2)aoSize;
  float depth = DecodeIndirectLightAoDepth(tAoDepth.Load(uint3(pixel, 0)));
  float2 clip = pixelUv * float2(2.0, -2.0) + float2(-1.0, 1.0);
  return float3(cb_vNearFarViewCorner.zw * clip * depth, -depth);
}

float EvaluateIndirectLightAoOnlyHorizonSlice(
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
    float3 positive = LoadIndirectLightAoOnlyViewPosition(
        scaledUv + offset, aoSize) - centerViewPosition;
    float3 negative = LoadIndirectLightAoOnlyViewPosition(
        scaledUv - offset, aoSize) - centerViewPosition;
    float positiveLength = max(1.0e-4, length(positive));
    float negativeLength = max(1.0e-4, length(negative));
    float distanceFade = rcp(max(1.0,
        radius * cb_settings.fRcpFadeDistance));
    horizon.x = max(horizon.x,
        lerp(-1.0, dot(positive / positiveLength, -viewDirection), distanceFade));
    horizon.y = max(horizon.y,
        lerp(-1.0, dot(negative / negativeLength, -viewDirection), distanceFade));
  }
  float3 tangent = normalize(float3(axis.y, -axis.x, 0.0));
  float projectedNormal = saturate(dot(normalView, tangent) * 0.5 + 0.5);
  float visibility = 1.0 - 0.25 * saturate(horizon.x + horizon.y + 2.0);
  return lerp(visibility, 1.0, projectedNormal * projectedNormal);
}

float EvaluateIndirectLightAoOnlyQuality(
    IndirectLightAoSurface surface,
    float2 unscaledUv,
    float qualityRadiusScale)
{
  uint2 aoSize = max(1u, cb_settings.vuSize);
  float2 quantizedUv = floor(cb_settings.vInvRenderScale
      * surface.scaledUv * (float2)aoSize) / (float2)aoSize;
  float3 center = LoadIndirectLightAoOnlyViewPosition(quantizedUv, aoSize);
  center += surface.normalView * 0.03;
  float3 viewDirection = normalize(center);
  float projectedRadius = max(3.0,
      (2.0 * cb_settings.vStart.x * cb_settings.fProjectionScale)
      * qualityRadiusScale / max(0.01, surface.depth) / 3.0);
  float noise = abs(frac(cb_fTime * 0.1
      + tScreenNoise.Load(uint3((uint2)(cb_vTargetSize * unscaledUv) & 63u, 0)))
      - 0.5);
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
    ao += EvaluateIndirectLightAoOnlyHorizonSlice(
        surface.scaledUv, aoSize, center, viewDirection, surface.normalView,
        float2(cosine, sine), initialRadius + projectedRadius,
        projectedRadius);
  }
  ao *= 1.0 / 3.0;
  float depthFade = saturate(0.002 * surface.depth);
  ao = 1.0 - (1.0 - ao) * (1.0 - depthFade * depthFade);
  return pow(max(1.0e-4, ao), cb_settings.vAdd.y);
}

#if INDIRECT_LIGHT_AO_SSS_COUNT > 0
float TraceIndirectLightAoSubsurface(
    IndirectLightAoSurface surface,
    float3 lightPointView,
    bool thinSurface)
{
  float3 centerView = float3(surface.viewCorner * surface.depth, -surface.depth);
  float3 toLight = centerView - lightPointView;
  float distanceToLight = max(1.0e-4, length(toLight));
  float3 direction = toLight / distanceToLight;
  float facing = dot(surface.normalView, direction);
  if (facing >= 0.330000013)
    return 1.0;
  float depthScale = saturate(0.002 * surface.depth);
  float maxDistance = (7.9 + 22.0 * saturate(facing)) * depthScale + 0.1;
  float stepDistance = 0.125 * maxDistance;
  float2 projectedDelta = surface.viewCorner * surface.depth * direction.z
      + surface.depth * direction.xy;
  projectedDelta *= cb_vViewToScreenScale * cb_settings.vRenderScale;
  float2 stepUv = normalize(projectedDelta) * stepDistance
      * length(projectedDelta) / max(1.0e-4, surface.depth * surface.depth);
  float depthStep = -direction.z * stepDistance;
  float2 rayUv = surface.scaledUv + stepUv;
  float expectedDepth = surface.depth + depthStep;
  float occlusion = 0.0;
  [unroll]
  for (uint stepIndex = 0u; stepIndex < 8u; ++stepIndex)
  {
    if (all(rayUv > 0.0) && all(rayUv < cb_settings.vRenderScale))
    {
      float sceneDepth = DecodeIndirectLightAoDepth(
          tAoDepth.SampleLevel(LinearClampClamp_s, rayUv, 0.0));
      float separation = expectedDepth - sceneDepth;
      if (separation > -0.5 * maxDistance && separation < maxDistance)
      {
        float travel = min(1.0, stepDistance * (stepIndex + 1u)
            / max(1.0e-4, 4.0 * maxDistance));
        occlusion = max(occlusion, 1.0 - travel * travel * travel * travel);
      }
    }
    rayUv += stepUv;
    expectedDepth += depthStep;
  }
  float normalFade = (1.0 - depthScale * depthScale)
      * (thinSurface ? 0.8 : 1.0);
  return 1.0 - 0.125 * occlusion * normalFade;
}

float EvaluateIndirectLightAoSubsurfaceLayer(
    IndirectLightAoSurface surface,
    uint clusterIndex,
    bool clusterHasSubsurface,
    uint layerIndex)
{
  if (!clusterHasSubsurface)
    return 1.0;
  uint lightWord = sbVoxelLightIds[clusterIndex * 33u + 1u
      + cb_settings.arrSsLight[layerIndex].uWordIndex];
  if ((lightWord & cb_settings.arrSsLight[layerIndex].uBitIndex) == 0u)
    return 1.0;
  return TraceIndirectLightAoSubsurface(surface,
      cb_settings.arrSsLight[layerIndex].vPointView, surface.profile == 2u);
}

float4 EvaluateIndirectLightAoSubsurfaceSet(
    IndirectLightAoSurface surface,
    float2 unscaledUv)
{
  float4 visibility = 1.0;
  uint slice = (uint)floor(cb_cluster.vVoxelDims.z * sqrt(
      surface.depth * cb_cluster.fRcpClusterRange
      + cb_cluster.fClusterNearBias));
  uint2 tile = (uint2)(cb_cluster.vVoxelDims.xy * unscaledUv);
  uint clusterIndex = slice * cb_cluster.uClusterSliceSize
      + tile.y * cb_cluster.uClusterWidth + tile.x;
  uint clusterMask = sbVoxelLightIds[clusterIndex * 33u];
  bool active = (clusterMask & cb_settings.uSSMask) != 0u;
#if INDIRECT_LIGHT_AO_SSS_COUNT > 0
  visibility.x = EvaluateIndirectLightAoSubsurfaceLayer(
      surface, clusterIndex, active, 0u);
#endif
#if INDIRECT_LIGHT_AO_SSS_COUNT > 1
  visibility.y = EvaluateIndirectLightAoSubsurfaceLayer(
      surface, clusterIndex, active, 1u);
#endif
#if INDIRECT_LIGHT_AO_SSS_COUNT > 2
  visibility.z = EvaluateIndirectLightAoSubsurfaceLayer(
      surface, clusterIndex, active, 2u);
#endif
#if INDIRECT_LIGHT_AO_SSS_COUNT > 3
  visibility.w = EvaluateIndirectLightAoSubsurfaceLayer(
      surface, clusterIndex, active, 3u);
#endif
  visibility *= visibility * visibility;
  return lerp(1.0, visibility, cb_settings.fInvSSGIKillSwitch);
}
#endif

IndirectLightAoSssResult EvaluateIndirectLightPerspectiveAoSssPolicy(
    float2 unscaledUv,
    float qualityRadiusScale,
    bool enableScreenAo)
{
  IndirectLightAoSssResult result;
  result.ambientOcclusion = float4(0.0, 0.0, 0.0, 1.0);
  result.subsurface = 1.0;
  result.occlusion = 1.0;
  IndirectLightAoSurface surface = LoadIndirectLightAoSurface(unscaledUv);
  if (surface.depth >= cb_vNearFarViewCorner.y - 1.0)
    return result;
  bool receivesIndirect = surface.material.z < 0.941176474
      && surface.depth < 500.0;
  if (receivesIndirect)
  {
    if (enableScreenAo)
      result.ambientOcclusion.w = EvaluateIndirectLightAoOnlyQuality(
          surface, unscaledUv, qualityRadiusScale);
#if INDIRECT_LIGHT_AO_SSS_COUNT > 0
    result.occlusion = EvaluateIndirectLightAoSubsurfaceSet(
        surface, unscaledUv);
#endif
  }
  return result;
}

IndirectLightAoSssResult EvaluateIndirectLightPerspectiveAoSss(
    float2 unscaledUv,
    float qualityRadiusScale)
{
  return EvaluateIndirectLightPerspectiveAoSssPolicy(
      unscaledUv, qualityRadiusScale, true);
}
