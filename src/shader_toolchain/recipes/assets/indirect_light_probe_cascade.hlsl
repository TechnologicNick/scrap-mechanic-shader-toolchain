// Recovered deferred indirect-light path used by the cascade/probe family.

static const float INDIRECT_LIGHT_MIN_DEPTH = 0.1;
static const float INDIRECT_LIGHT_DEPTH_RANGE = 499.9;

#ifndef INDIRECT_LIGHT_ENABLE_PROBE_GI
#define INDIRECT_LIGHT_ENABLE_PROBE_GI 1
#endif

#ifndef INDIRECT_LIGHT_ENABLE_REFLECTION
#define INDIRECT_LIGHT_ENABLE_REFLECTION 1
#endif

#ifndef INDIRECT_LIGHT_ENABLE_DIFFUSE
#define INDIRECT_LIGHT_ENABLE_DIFFUSE 1
#endif

struct IndirectLightSurface
{
  float2 scaledUv;
  uint2 pixel;
  float depth;
  float2 viewCorner;
  float3 normalView;
  float3 diffuse;
  float3 material;
  uint4 neighborProfiles;
};

struct IndirectLightResult
{
  float4 indirect;
  float subsurface;
  float cascadeOcclusion;
};

struct IndirectLightMediumResult
{
  float4 indirectAo;
  float subsurface;
  float4 occlusion;
};

struct IndirectLightMediumSssResult
{
  float4 ambientOcclusion;
  float subsurface;
  float occlusion;
};

struct IndirectLightProbeAccumulation
{
  float3 reflection;
  float reflectionWeight;
  float3 gpuReflection;
  float gpuReflectionWeight;
  float3 diffuseGi;
  float diffuseGiWeight;
};

float DecodeIndirectLightDepth(float encodedDepth)
{
  return encodedDepth * encodedDepth * INDIRECT_LIGHT_DEPTH_RANGE
       + INDIRECT_LIGHT_MIN_DEPTH;
}

float3 DecodeIndirectLightNormal(float2 encoded)
{
  float2 octahedral = encoded * 2.0 - 1.0;
  float z = 1.0 - abs(octahedral.x) - abs(octahedral.y);
  float fold = saturate(-z);
  octahedral += octahedral >= 0.0 ? -fold : fold;
  float3 normal = float3(octahedral, z);
  return normal * rsqrt(dot(normal, normal));
}

float2 EncodeIndirectLightOctahedron(float3 direction)
{
  float inverseL1 = rcp(max(1.0e-4,
      abs(direction.x) + abs(direction.y) + abs(direction.z)));
  float2 octahedral = direction.xy * inverseL1;
  float2 fold = 1.0 - abs(octahedral.yx);
  fold = octahedral < 0.0 ? -fold : fold;
  octahedral = direction.z <= 0.0 ? fold : octahedral;
  octahedral += float2(-2.0, 2.0);
  octahedral = max(abs(octahedral.x), abs(octahedral.y)) >= 1.0
      ? -octahedral : octahedral;
  return octahedral * 0.5 + 0.5;
}

float3 TransformIndirectLightPosition(float4x4 transform, float3 position)
{
  return transform._m00_m10_m20 * position.xxx
       + transform._m01_m11_m21 * position.yyy
       + transform._m02_m12_m22 * position.zzz
       + transform._m03_m13_m23;
}

float3 TransformIndirectLightDirection(float4x4 transform, float3 direction)
{
  return transform._m00_m10_m20 * direction.xxx
       + transform._m01_m11_m21 * direction.yyy
       + transform._m02_m12_m22 * direction.zzz;
}

IndirectLightSurface LoadIndirectLightSurface(float2 unscaledUv)
{
  IndirectLightSurface surface;
  surface.scaledUv = cb_settings.vRenderScale * unscaledUv;
  uint2 aoPixel = (uint2)(surface.scaledUv * (float2)cb_settings.vuSize);
  surface.pixel = aoPixel << 1;
  surface.depth = tHzb.Load(uint3(aoPixel, 0));

  float2 clip = unscaledUv * float2(2.0, -2.0) + float2(-1.0, 1.0);
  surface.viewCorner = cb_vNearFarViewCorner.zw * clip;
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

uint SelectIndirectLightDepthMip(float2 uv, float depth)
{
  float4 gathered = tAoDepth.Gather(LinearClampClamp_s, uv, int2(4, 4));
  gathered = gathered.zwyx * gathered.zwyx * INDIRECT_LIGHT_DEPTH_RANGE
           + INDIRECT_LIGHT_MIN_DEPTH;
  float4 differences = gathered.wzwy - gathered;
  float2 maxima = max(abs(differences.xz), abs(differences.yw));
  float discontinuity = max(maxima.x, maxima.y);
  float depthScale = max(2.5e-4, 1.0e-3 * depth);
  float stable = 2.0 - min(1.0, discontinuity / depthScale);
  return min(2u, (uint)ceil((cb_f720To4K + cb_f720To4K) * stable));
}

float3 ProjectIndirectLightViewPosition(float3 viewPosition)
{
  float3 clip = cb_xViewToProjection._m00_m10_m30 * viewPosition.xxx
              + cb_xViewToProjection._m01_m11_m31 * viewPosition.yyy
              + cb_xViewToProjection._m02_m12_m32 * viewPosition.zzz
              + cb_xViewToProjection._m03_m13_m33;
  float2 uv = clip.xy / clip.z;
  return float3(uv * float2(0.5, -0.5) + 0.5, clip.z);
}

float TraceIndirectLightCascade(
    IndirectLightSurface surface,
    float directionalFacing)
{
  uint mip = SelectIndirectLightDepthMip(surface.scaledUv, surface.depth);
  float rayDepth = DecodeIndirectLightDepth(
      tAoDepth.SampleLevel(LinearClampClamp_s, surface.scaledUv, mip));
  float2 rayViewPosition = surface.viewCorner * rayDepth;

  float depthScale = saturate(0.002 * surface.depth);
  float maxDistance = 29.9 * depthScale + 0.1;
  float phaseScale = -1.5 * depthScale + 1.75;
  float distanceFade = saturate(0.25 * (surface.depth - 2.0));
  float normalizedDistance = rcp(maxDistance * (0.75 - 0.5 * distanceFade));
  float stepDistance = 0.125 * maxDistance;
  float invTravelRange = rcp(4.0 * maxDistance);

  uint4 thinMask = surface.neighborProfiles == 2u;
  bool thinSurface = any(thinMask != 0u);
  float noise = frac(cb_fTime * 0.1
      + tScreenNoise.Load(uint3((uint2)(cb_vTargetSize * surface.scaledUv) & 63u, 0)));
  noise = abs(noise - 0.5) * 2.0;

  float normalFade = 1.0 - depthScale * depthScale;
  normalFade *= thinSurface ? 0.6 : 1.0;
  float lightOffset = dot(depthScale.xx, phaseScale.xx);
  float3 rayDirection = normalize(-cb_vDirectionalLightDirectionView + lightOffset);
  float facingDistance = -0.5 * maxDistance
      * saturate(1.33333337 * (1.0 + directionalFacing));
  float inverseFacingDistance = rcp(facingDistance);

  float2 projectedDelta = rayViewPosition * rayDirection.z
      + rayDepth * rayDirection.xy;
  projectedDelta *= cb_vViewToScreenScale * cb_settings.vRenderScale;
  float projectedLength = max(1.0e-4, length(projectedDelta));
  float projectedStepLength = projectedLength / (rayDepth * rayDepth)
      * stepDistance;
  float2 projectedStep = projectedDelta / projectedLength * projectedStepLength;
  float depthStep = -rayDirection.z * stepDistance;

  float2 rayUv = ProjectIndirectLightViewPosition(
      float3(rayViewPosition, -rayDepth)).xy;
  float travel = stepDistance * (noise + 1.0);
  rayUv = rayUv * cb_settings.vRenderScale + projectedStep * noise;
  rayUv += projectedStep;
  float expectedDepth = rayDepth + depthStep * (noise + 1.0);
  float occlusion = 0.0;
  float2 screenStep = projectedStep;
  float currentDepthStep = depthStep;
  float currentDistanceStep = stepDistance;

  [unroll]
  for (uint stepIndex = 0u; stepIndex < 8u; ++stepIndex)
  {
    if (all(rayUv > 0.0) && all(rayUv < cb_settings.vRenderScale))
    {
      float sceneDepth = DecodeIndirectLightDepth(
          tAoDepth.SampleLevel(LinearClampClamp_s, rayUv, mip));
      float separation = expectedDepth - sceneDepth;
      bool insideThickness = facingDistance < separation && separation < maxDistance;

      float travelRatio = min(1.0, travel * invTravelRange);
      float travelCurve = travelRatio * travelRatio;
      travelCurve = 1.0 - travelCurve * travelCurve + occlusion;

      float freeSpace = 1.0 - saturate(separation * inverseFacingDistance);
      freeSpace = max(1.0e-4, freeSpace);
      freeSpace = rsqrt(rsqrt(rsqrt(freeSpace)));
      float freeSpaceCurve = freeSpace * min(1.0, travel * normalizedDistance)
          + occlusion;

      bool positiveSeparation = separation > 0.0;
      float candidate = positiveSeparation ? travelCurve : freeSpaceCurve;
      if (insideThickness)
        occlusion = candidate;

      float scale = positiveSeparation ? 0.85 : 1.2;
      currentDistanceStep = (positiveSeparation ? 0.10625 : 0.15) * maxDistance;
      currentDepthStep = scale * depthStep;
      screenStep = scale * projectedStep;
    }

    travel += currentDistanceStep;
    rayUv += screenStep;
    expectedDepth += currentDepthStep;
  }

  return 1.0 - 0.125 * occlusion * normalFade;
}

float DistanceToIndirectLightProbeBox(float3 localPosition, float3 extents)
{
  float3 outside = abs(localPosition) - extents;
  float outsideDistance = length(max(0.0, outside));
  float insideDistance = min(0.0, max(outside.x, max(outside.y, outside.z)));
  return outsideDistance + insideDistance;
}

float3 IntersectIndirectLightProbeBox(
    float3 worldPosition,
    float3 direction,
    float3 probePosition,
    float3 boxMin,
    float3 boxMax)
{
  float3 inverseDirection = rcp(direction);
  float3 farMinimum = (boxMin - worldPosition) * inverseDirection;
  float3 farMaximum = (boxMax - worldPosition) * inverseDirection;
  float distance = min(min(max(farMinimum.x, farMaximum.x),
                           max(farMinimum.y, farMaximum.y)),
                       max(farMinimum.z, farMaximum.z));
  return worldPosition + direction * distance - probePosition;
}

#if INDIRECT_LIGHT_ENABLE_REFLECTION
void AccumulateIndirectLightProbe(
    uint probeIndex,
    float3 worldPosition,
    float3 reflectionWorld,
    float3 normalWorld,
    float roughnessMip,
    float fallbackWeight,
    inout IndirectLightProbeAccumulation accumulation)
{
  float3 localPosition = worldPosition
      - cb_reflections.vecProbes[probeIndex].vPosition;
  float signedDistance = DistanceToIndirectLightProbeBox(
      localPosition, cb_reflections.vecProbes[probeIndex].vExtents);
  signedDistance -= cb_reflections.vecProbes[probeIndex].fMargin;
  signedDistance *= cb_reflections.vecProbes[probeIndex].fGpuEnable;
  if (signedDistance >= 0.0)
    return;

  float marginWeight = saturate(
      -signedDistance * cb_reflections.vecProbes[probeIndex].fMarginRcp);
  bool fallback = cb_reflections.vecProbes[probeIndex].fIsFallback != 0.0;
  float probeWeight = fallback ? 1.0 : marginWeight;
  float blendWeight = cb_reflections.vecProbes[probeIndex].fBlend * probeWeight;

  float3 lookupDirection = IntersectIndirectLightProbeBox(
      worldPosition, reflectionWorld,
      cb_reflections.vecProbes[probeIndex].vPosition,
      cb_reflections.vecProbes[probeIndex].vMin,
      cb_reflections.vecProbes[probeIndex].vMax);
  if (!fallback)
  {
    float parallax = cb_reflections.vecProbes[probeIndex].fParallax * fallbackWeight;
    lookupDirection = normalize(
        normalize(lookupDirection) * parallax
        + reflectionWorld * (1.0 - parallax));
  }

  float3 reflectionSample = taReflection.SampleLevel(
      LinearMirrorMirror_s,
      float3(EncodeIndirectLightOctahedron(lookupDirection),
             cb_reflections.vecProbes[probeIndex].fSlotIndex),
      roughnessMip).xyz;
  accumulation.reflection += reflectionSample * blendWeight;
  accumulation.reflectionWeight +=
      probeWeight * cb_reflections.vecProbes[probeIndex].fBlend;

  if (!fallback)
  {
    float4 gpuSample = taReflection.SampleLevel(
        LinearMirrorMirror_s,
        float3(EncodeIndirectLightOctahedron(lookupDirection),
               cb_reflections.vecProbes[probeIndex].fSlotIndex),
        roughnessMip);
    float gpuDistance = gpuSample.w * gpuSample.w * 127.5 + 0.5;
    float3 hitPosition = lookupDirection * gpuDistance
        + cb_reflections.vecProbes[probeIndex].vPosition;
    float gpuMargin = saturate(-DistanceToIndirectLightProbeBox(
        hitPosition - cb_reflections.vecProbes[probeIndex].vGpuPosition,
        cb_reflections.vecProbes[probeIndex].vGpuExtents)
        * cb_reflections.vecProbes[probeIndex].fGpuMarginRcp);
    float normalWeight = dot(normalWorld, lookupDirection) * 0.5 + 0.5;
    normalWeight *= normalWeight;
    float distanceWeight = saturate(1.0 - gpuDistance * (1.0 / 4096.0));
    distanceWeight *= distanceWeight * gpuMargin * normalWeight;
    float hitWeight = (distanceWeight * marginWeight * 10.0 + 1.0)
        * max(gpuMargin, fallbackWeight) * marginWeight * normalWeight;
    accumulation.gpuReflection += gpuSample.xyz * hitWeight * blendWeight;
    accumulation.gpuReflectionWeight += hitWeight * blendWeight;
  }

#if INDIRECT_LIGHT_ENABLE_PROBE_GI
  if (cb_reflections.vecProbes[probeIndex].fGiEnable != 0.0)
  {
    float4 giSample = taGi.SampleLevel(
        LinearMirrorMirror_s,
        float3(EncodeIndirectLightOctahedron(normalWorld),
               cb_reflections.vecProbes[probeIndex].fSlotIndex), 0.0);
    float giDistance = giSample.w * giSample.w * 127.5 + 0.5;
    float3 giPosition = normalWorld * giDistance
        + cb_reflections.vecProbes[probeIndex].vPosition;
    float distanceSquared = dot(worldPosition - giPosition,
                                worldPosition - giPosition);
    float giRangeSquared = cb_reflections.vecProbes[probeIndex].fGiInfinit != 0.0
        ? 16384.0 : 9216.0;
    float giWeight = 1.0 - min(1.0, distanceSquared / giRangeSquared);
    accumulation.diffuseGi += giSample.xyz * (2.0 * giWeight * blendWeight);
    accumulation.diffuseGiWeight +=
        probeWeight * cb_reflections.vecProbes[probeIndex].fBlend;
  }
#endif
}

IndirectLightProbeAccumulation GatherIndirectLightProbes(
    float2 unscaledUv,
    float depth,
    float3 worldPosition,
    float3 reflectionWorld,
    float3 normalWorld,
    float roughnessMip,
    float fallbackWeight)
{
  IndirectLightProbeAccumulation result =
      (IndirectLightProbeAccumulation)0;
  float clusterDepth = depth * cb_cluster.fRcpClusterRange
      + cb_cluster.fClusterNearBias;
  uint slice = (uint)floor(cb_cluster.vVoxelDims.z * sqrt(clusterDepth));
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
      AccumulateIndirectLightProbe(
          probeBase + bitIndex, worldPosition, reflectionWorld, normalWorld,
          roughnessMip, fallbackWeight, result);
    }
  }
  return result;
}
#endif

float3 ApplyIndirectLightMetalProfile(
    float3 indirect,
    float3 diffuse,
    uint packedProfile)
{
  if ((packedProfile & 7u) != 6u)
    return indirect;
  uint profileIndex = (packedProfile >> 3u) & 31u;
  float3 specular = lerp(diffuse,
      cb_profiles.arrMetal[profileIndex].vSpecularColor,
      cb_profiles.arrMetal[profileIndex].vSpecularColor.w);
  float compensation = 1.0 + abs(1.0 - dot(specular, (1.0 / 3.0).xxx))
      * cb_profiles.arrMetal[profileIndex].fDiffuseCompensation;
  return indirect * specular * compensation;
}

#if INDIRECT_LIGHT_ENABLE_REFLECTION
IndirectLightResult EvaluateIndirectLightProbeCascade(float2 unscaledUv)
{
  IndirectLightResult result;
  result.indirect = float4(0.0, 0.0, 0.0, 1.0);
  result.subsurface = 1.0;
  result.cascadeOcclusion = 1.0;

  IndirectLightSurface surface = LoadIndirectLightSurface(unscaledUv);
  if (surface.depth >= cb_vNearFarViewCorner.y - 1.0)
    return result;

  float directionalFacing = dot(
      surface.normalView, cb_vDirectionalLightDirectionView);
  bool receivesIndirect = surface.material.z < 0.941176474
      && surface.depth < 500.0;
  if (receivesIndirect && directionalFacing < 0.330000013)
  {
    float cascade = TraceIndirectLightCascade(surface, directionalFacing);
    result.cascadeOcclusion = lerp(
        1.0, cascade, cb_settings.fInvSSGIKillSwitch);
  }

  if (surface.material.z < 0.941176474)
  {
    float materialCoverage = 1.0 - pow(abs(1.0 - surface.material.y), 0.75);
    materialCoverage = saturate((3.6 * materialCoverage * surface.material.x
                                - 0.15) / 0.7);
    float roughness = surface.material.z * 0.15 + 0.125;
    float luminance = max(0.3, dot(surface.diffuse,
        float3(0.299, 0.587, 0.114)));
    float reflectionStrength = saturate(
        (1.0 - luminance) * (1.0 - luminance) * roughness
        + materialCoverage);
    float diffuseStrength = (1.0 - materialCoverage)
        * lerp(1.0 - (1.0 - cb_fDirectionalLightIntensity)
                       * (1.0 - cb_fDirectionalLightIntensity),
               1.0, 0.4);

    if (surface.depth < cb_cluster.fClusterMaxFarReflections)
    {
      float3 viewPosition = float3(surface.viewCorner * surface.depth,
                                   -surface.depth);
      float3 worldPosition = TransformIndirectLightPosition(
          viewToWorld, viewPosition);
      float3 viewDirection = normalize(viewPosition);
      float3 reflectionView = viewDirection
          - 2.0 * dot(viewDirection, surface.normalView) * surface.normalView;
      float3 reflectionWorld = normalize(TransformIndirectLightDirection(
          viewToWorld, reflectionView));
      float3 normalWorld = TransformIndirectLightDirection(
          viewToWorld, surface.normalView);
      float roughnessMip = max(surface.material.z,
                               0.25 * (1.0 - surface.material.y));
      float fallbackWeight = 1.0 - saturate(0.5 * roughnessMip);

      IndirectLightProbeAccumulation probes = GatherIndirectLightProbes(
          unscaledUv, surface.depth, worldPosition, reflectionWorld,
          normalWorld, roughnessMip, fallbackWeight);
      float3 reflection = probes.reflection / max(0.125,
          probes.gpuReflectionWeight);
      float3 gpuReflection = probes.gpuReflection / max(0.001,
          probes.reflectionWeight);
      float gpuBlend = saturate(probes.reflectionWeight);
      reflection = lerp(gpuReflection, reflection, gpuBlend * gpuBlend);
      float3 diffuseGi = probes.diffuseGi / max(1.0, probes.diffuseGiWeight);
      diffuseGi = lerp(diffuseGi * surface.diffuse, diffuseGi,
                       result.cascadeOcclusion);
      result.indirect.xyz = reflectionStrength * reflection
          + diffuseStrength * diffuseGi;
    }
  }

  result.indirect.xyz *= 0.884955764;
  float compression = dot(result.indirect.xyz,
      float3(0.299, 0.587, 0.114)) * 0.2 + 1.4;
  result.indirect.xyz /= compression;
  result.indirect.xyz = ApplyIndirectLightMetalProfile(
      result.indirect.xyz, surface.diffuse, surface.neighborProfiles.x);
  return result;
}
#endif

float3 LoadIndirectLightAoViewPosition(float2 scaledUv, uint2 aoSize)
{
  float2 clampedUv = saturate(scaledUv);
  uint2 pixel = min((uint2)(clampedUv * (float2)aoSize), aoSize - 1u);
  float2 pixelUv = (float2)pixel / (float2)aoSize;
  float depth = DecodeIndirectLightDepth(tAoDepth.Load(uint3(pixel, 0)));
  float2 clip = pixelUv * float2(2.0, -2.0) + float2(-1.0, 1.0);
  return float3(cb_vNearFarViewCorner.zw * clip * depth, -depth);
}

float EvaluateIndirectLightHorizonSlice(
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
    float3 positive = LoadIndirectLightAoViewPosition(
        scaledUv + offset, aoSize) - centerViewPosition;
    float3 negative = LoadIndirectLightAoViewPosition(
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

float EvaluateIndirectLightAoQuality(
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
      * qualityRadiusScale
      / max(0.01, surface.depth) / 3.0);
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

float EvaluateIndirectLightMediumAo(
    IndirectLightSurface surface,
    float2 unscaledUv)
{
  return EvaluateIndirectLightAoQuality(surface, unscaledUv, 1.0);
}

float TraceIndirectLightSubsurface(
    IndirectLightSurface surface,
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
      float sceneDepth = DecodeIndirectLightDepth(
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

#if INDIRECT_LIGHT_ENABLE_REFLECTION
float3 EvaluateIndirectLightReflectionOnly(
    IndirectLightSurface surface,
    float2 unscaledUv)
{
  float reflectivity = 1.0 - surface.material.x;
  float reflectionEnergy = 1.0 - reflectivity * reflectivity;
  if (reflectionEnergy <= 0.1
      || surface.depth >= cb_cluster.fClusterMaxFarReflections)
    return 0.0;

  float3 viewPosition = float3(surface.viewCorner * surface.depth,
                               -surface.depth);
  float3 worldPosition = TransformIndirectLightPosition(viewToWorld, viewPosition);
  float3 viewDirection = normalize(viewPosition);
  float3 reflectionView = viewDirection
      - 2.0 * dot(viewDirection, surface.normalView) * surface.normalView;
  float3 reflectionWorld = normalize(TransformIndirectLightDirection(
      viewToWorld, reflectionView));
  float3 normalWorld = normalize(TransformIndirectLightDirection(
      viewToWorld, surface.normalView));
  float roughnessMip = max(1.0 - surface.material.y, 0.25 * reflectivity);
  float fallbackWeight = 1.0 - saturate(0.5 * roughnessMip);
  IndirectLightProbeAccumulation probes = GatherIndirectLightProbes(
      unscaledUv, surface.depth, worldPosition, reflectionWorld,
      normalWorld, 5.0 * roughnessMip, fallbackWeight);
  float3 reflection = probes.reflection / max(0.125,
      probes.gpuReflectionWeight);
  float3 gpuReflection = probes.gpuReflection / max(0.001,
      probes.reflectionWeight);
  float blend = saturate(probes.reflectionWeight);
  return reflectionEnergy * lerp(gpuReflection, reflection, blend * blend);
}

float EvaluateIndirectLightCascadeReflectionSssLayer(
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

IndirectLightMediumResult EvaluateIndirectLightCascadeReflection(
    float2 unscaledUv,
    float qualityRadiusScale,
    bool enableScreenAo,
    uint occlusionOutputCount)
{
  IndirectLightMediumResult result;
  result.indirectAo = float4(0.0, 0.0, 0.0, 1.0);
  result.subsurface = 1.0;
  result.occlusion = 1.0;
  IndirectLightSurface surface = LoadIndirectLightSurface(unscaledUv);
  if (surface.depth >= cb_vNearFarViewCorner.y - 1.0)
    return result;

  bool receivesIndirect = surface.material.z < 0.941176474
      && surface.depth < 500.0;
  if (receivesIndirect && enableScreenAo)
    result.indirectAo.w = EvaluateIndirectLightAoQuality(
        surface, unscaledUv, qualityRadiusScale);

  float directionalFacing = dot(surface.normalView,
      cb_vDirectionalLightDirectionView);
  if (occlusionOutputCount > 0u
      && receivesIndirect && directionalFacing < 0.330000013)
  {
    result.occlusion.x = TraceIndirectLightCascade(surface, directionalFacing);
  }

  if (occlusionOutputCount > 1u && receivesIndirect)
  {
    uint clusterDepth = (uint)floor(cb_cluster.vVoxelDims.z * sqrt(
        surface.depth * cb_cluster.fRcpClusterRange
        + cb_cluster.fClusterNearBias));
    uint2 clusterTile = (uint2)(cb_cluster.vVoxelDims.xy * unscaledUv);
    uint clusterIndex = clusterDepth * cb_cluster.uClusterSliceSize
        + clusterTile.y * cb_cluster.uClusterWidth + clusterTile.x;
    uint clusterMask = sbVoxelLightIds[clusterIndex * 33u];
    bool clusterHasSubsurface =
        (clusterMask & cb_settings.uSSMask) != 0u;
    bool thinSurface = any(surface.neighborProfiles == 2u);
    result.occlusion.y = EvaluateIndirectLightCascadeReflectionSssLayer(
        surface, clusterIndex, clusterHasSubsurface, thinSurface,
        cb_settings.arrSsLight[1].uWordIndex,
        cb_settings.arrSsLight[1].uBitIndex,
        cb_settings.arrSsLight[1].vPointView);
    if (occlusionOutputCount > 2u)
      result.occlusion.z = EvaluateIndirectLightCascadeReflectionSssLayer(
          surface, clusterIndex, clusterHasSubsurface, thinSurface,
          cb_settings.arrSsLight[2].uWordIndex,
          cb_settings.arrSsLight[2].uBitIndex,
          cb_settings.arrSsLight[2].vPointView);
    if (occlusionOutputCount > 3u)
      result.occlusion.w = EvaluateIndirectLightCascadeReflectionSssLayer(
          surface, clusterIndex, clusterHasSubsurface, thinSurface,
          cb_settings.arrSsLight[3].uWordIndex,
          cb_settings.arrSsLight[3].uBitIndex,
          cb_settings.arrSsLight[3].vPointView);
  }
  result.occlusion = lerp(1.0, result.occlusion,
                          cb_settings.fInvSSGIKillSwitch);

  result.indirectAo.xyz = EvaluateIndirectLightReflectionOnly(
      surface, unscaledUv);
  result.indirectAo.xyz *= 0.884955764;
  float compression = dot(result.indirectAo.xyz,
      float3(0.299, 0.587, 0.114)) * 0.2 + 1.4;
  result.indirectAo.xyz /= compression;
  result.indirectAo.xyz = ApplyIndirectLightMetalProfile(
      result.indirectAo.xyz, surface.diffuse, surface.neighborProfiles.x);
  return result;
}

IndirectLightMediumResult EvaluateIndirectLightCascadeMedium(
    float2 unscaledUv)
{
  return EvaluateIndirectLightCascadeReflection(
      unscaledUv, 1.0, true, 2u);
}
#endif

IndirectLightMediumSssResult EvaluateIndirectLightMediumSss(
    float2 unscaledUv)
{
  IndirectLightMediumSssResult result;
  result.ambientOcclusion = float4(0.0, 0.0, 0.0, 1.0);
  result.subsurface = 1.0;
  result.occlusion = 1.0;

  IndirectLightSurface surface = LoadIndirectLightSurface(unscaledUv);
  if (surface.depth >= cb_vNearFarViewCorner.y - 1.0)
    return result;

  bool receivesIndirect = surface.material.z < 0.941176474
      && surface.depth < 500.0;
  if (!receivesIndirect)
    return result;

  result.ambientOcclusion.w =
      EvaluateIndirectLightMediumAo(surface, unscaledUv);

  uint clusterDepth = (uint)floor(cb_cluster.vVoxelDims.z * sqrt(
      surface.depth * cb_cluster.fRcpClusterRange
      + cb_cluster.fClusterNearBias));
  uint2 clusterTile = (uint2)(cb_cluster.vVoxelDims.xy * unscaledUv);
  uint clusterIndex = clusterDepth * cb_cluster.uClusterSliceSize
      + clusterTile.y * cb_cluster.uClusterWidth + clusterTile.x;
  uint clusterMask = sbVoxelLightIds[clusterIndex * 33u];
  bool subsurfaceActive = (clusterMask & cb_settings.uSSMask) != 0u;
  if (subsurfaceActive)
  {
    uint lightWord = sbVoxelLightIds[clusterIndex * 33u + 1u
        + cb_settings.arrSsLight[0].uWordIndex];
    subsurfaceActive =
        (lightWord & cb_settings.arrSsLight[0].uBitIndex) != 0u;
  }
  if (subsurfaceActive)
  {
    bool thinSurface = any(surface.neighborProfiles == 2u);
    float visibility = TraceIndirectLightSubsurface(
        surface, cb_settings.arrSsLight[0].vPointView, thinSurface);
    visibility *= visibility * visibility;
    result.occlusion = lerp(
        1.0, visibility, cb_settings.fInvSSGIKillSwitch);
  }
  return result;
}
