// Perspective temporal SSGI with cascade-first occlusion routing.
#include "indirect_light_ortho_ssgi.hlsl"

struct IndirectLightSsgiCascadeResult
{
  float4 indirectAo;
  float temporalConfidence;
  float4 occlusion;
};

float EvaluateIndirectLightPerspectiveAoQuality(
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
    ao += EvaluateIndirectLightHorizonSlice(
        surface.scaledUv, aoSize, center, viewDirection, surface.normalView,
        float2(cosine, sine), initialRadius + projectedRadius,
        projectedRadius);
  }
  ao *= 1.0 / 3.0;
  float depthFade = saturate(0.002 * surface.depth);
  ao = 1.0 - (1.0 - ao) * (1.0 - depthFade * depthFade);
  return pow(max(1.0e-4, ao), cb_settings.vAdd.y);
}

float4 EvaluateIndirectLightCascadeOcclusionSet(
    IndirectLightSurface surface,
    float2 unscaledUv,
    uint outputCount)
{
  float4 visibility = 1.0;
  float directionalFacing = dot(
      surface.normalView, cb_vDirectionalLightDirectionView);
  if (directionalFacing < 0.330000013)
    visibility.x = TraceIndirectLightCascade(surface, directionalFacing);

  uint slice = (uint)floor(cb_cluster.vVoxelDims.z * sqrt(
      surface.depth * cb_cluster.fRcpClusterRange
      + cb_cluster.fClusterNearBias));
  uint2 tile = (uint2)(cb_cluster.vVoxelDims.xy * unscaledUv);
  uint clusterIndex = slice * cb_cluster.uClusterSliceSize
      + tile.y * cb_cluster.uClusterWidth + tile.x;
  uint clusterMask = sbVoxelLightIds[clusterIndex * 33u];
  bool clusterHasSubsurface = (clusterMask & cb_settings.uSSMask) != 0u;
  bool thinSurface = any(surface.neighborProfiles == 2u);
  if (outputCount > 1u)
    visibility.y = EvaluateIndirectLightSubsurfaceLayer(
        surface, clusterIndex, clusterHasSubsurface, thinSurface,
        cb_settings.arrSsLight[1].uWordIndex,
        cb_settings.arrSsLight[1].uBitIndex,
        cb_settings.arrSsLight[1].vPointView);
  if (outputCount > 2u)
    visibility.z = EvaluateIndirectLightSubsurfaceLayer(
        surface, clusterIndex, clusterHasSubsurface, thinSurface,
        cb_settings.arrSsLight[2].uWordIndex,
        cb_settings.arrSsLight[2].uBitIndex,
        cb_settings.arrSsLight[2].vPointView);
  if (outputCount > 3u)
    visibility.w = EvaluateIndirectLightSubsurfaceLayer(
        surface, clusterIndex, clusterHasSubsurface, thinSurface,
        cb_settings.arrSsLight[3].uWordIndex,
        cb_settings.arrSsLight[3].uBitIndex,
        cb_settings.arrSsLight[3].vPointView);
  visibility *= visibility * visibility;
  return lerp(1.0, visibility, cb_settings.fInvSSGIKillSwitch);
}

IndirectLightSsgiCascadeResult EvaluateIndirectLightPerspectiveSsgiCascade(
    float2 unscaledUv,
    float qualityRadiusScale,
    bool enableScreenAo,
    uint occlusionOutputCount)
{
  IndirectLightSsgiCascadeResult result;
  result.indirectAo = float4(0.0, 0.0, 0.0, 1.0);
  result.temporalConfidence = 1.0;
  result.occlusion = 1.0;
  IndirectLightSurface surface = LoadIndirectLightSurface(unscaledUv);
  if (surface.depth >= cb_vNearFarViewCorner.y - 1.0)
    return result;

  bool receivesIndirect = surface.material.z < 0.941176474;
  if (receivesIndirect && surface.depth < 500.0)
  {
    if (enableScreenAo)
      result.indirectAo.w = EvaluateIndirectLightPerspectiveAoQuality(
          surface, unscaledUv, qualityRadiusScale);
    result.occlusion = EvaluateIndirectLightCascadeOcclusionSet(
        surface, unscaledUv, occlusionOutputCount);
  }

  IndirectLightTemporalSample temporal =
      GatherIndirectLightTemporalSsgi(surface, unscaledUv);
  float3 viewPosition = float3(
      surface.viewCorner * surface.depth, -surface.depth);
  float3 worldPosition = TransformIndirectLightPosition(viewToWorld, viewPosition);
  float4 previousClip = mul(
      float4(worldPosition, 1.0), cb_xPrevWorldToViewProjection);
  float2 previousUv = previousClip.xy / previousClip.z;
  previousUv = previousUv * float2(0.5, -0.5) + 0.5;
  previousUv = min(cb_settings.vRenderScale,
      cb_settings.vRenderScale * previousUv);
  float volatility = abs(tVolatile.SampleLevel(
      PointClampClamp_s, previousUv, 0.0));
  float hitConfidence = 1.0 - saturate(abs(tHitCache.SampleLevel(
      PointClampClamp_s,
      min(cb_vPrevRenderScale, previousUv * cb_vPrevRenderScale), 0.0)));
  temporal.confidence *= saturate(cb_fRenderScaleStability
      * (1.0 - volatility * volatility) * hitConfidence);

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
  float probeBlend = saturate(probes.reflectionWeight);
  float3 probeReflection = lerp(
      gpuReflection, localReflection, probeBlend * probeBlend);
  float3 probeGi = probes.diffuseGi / max(1.0, probes.diffuseGiWeight);
  float probeAo = GatherIndirectLightProbeAo(
      unscaledUv, surface.depth, worldPosition, normalWorld);

  float3 screenReflection = tSSR.SampleLevel(
      LinearClampClamp_s, surface.scaledUv, roughness * 5.0);
  float3 reflection = lerp(
      probeReflection, screenReflection, temporal.confidence);
  float3 diffuseIndirect = lerp(
      probeGi, temporal.radiance, temporal.confidence) * surface.diffuse;
  float reflectionEnergy = 1.0 - reflectivity * reflectivity;
  float3 indirect = diffuseIndirect + reflection * reflectionEnergy;
  indirect *= 0.884955764;
  indirect /= dot(indirect, float3(0.299, 0.587, 0.114)) * 0.2 + 1.4;
  result.indirectAo.xyz = ApplyIndirectLightMetalProfile(
      indirect, surface.diffuse, surface.neighborProfiles.x);
  if (enableScreenAo)
    result.indirectAo.w = min(result.indirectAo.w,
        lerp(1.0, probeAo, temporal.confidence));
  result.temporalConfidence = lerp(
      1.0, temporal.confidence, cb_settings.fInvSSGIKillSwitch);
  return result;
}
