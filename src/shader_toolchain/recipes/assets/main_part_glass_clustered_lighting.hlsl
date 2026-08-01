#ifndef MAIN_PART_GLASS_CLUSTERED_LIGHTING_INCLUDED
#define MAIN_PART_GLASS_CLUSTERED_LIGHTING_INCLUDED

// Shared clustered-light traversal for medium transparent materials.  Material
// decoding and final composition stay outside this file; this layer owns only
// cluster addressing, local-light accumulation, and reflection-probe blending.

struct MainPartGlassClusterAddress
{
  float3 worldPosition;
  float3 cookieDerivativePosition;
  uint listBase;
  uint pointMaskWords;
  uint spotMaskWords;
  uint reflectionMaskWords;
};

struct MainPartGlassLocalLighting
{
  float3 maximumColor;
  float3 additiveColor;
  float transmission;
  float specular;
};

struct MainPartGlassProbeLighting
{
  float3 gpuColor;
  float3 fallbackColor;
  float gpuWeight;
  float fallbackWeight;
  float gpuBlend;
};

float3 MainPartGlassViewToWorldPosition(float3 viewPosition)
{
  float3 worldPosition = viewToWorld._m01_m11_m21 * viewPosition.y;
  worldPosition = viewToWorld._m00_m10_m20 * viewPosition.x + worldPosition;
  worldPosition = viewToWorld._m02_m12_m22 * viewPosition.z + worldPosition;
  return viewToWorld._m03_m13_m23 + worldPosition;
}

float3 MainPartGlassViewToWorldDirection(float3 viewDirection)
{
  float3 worldDirection = viewToWorld._m01_m11_m21 * viewDirection.y;
  worldDirection = viewToWorld._m00_m10_m20 * viewDirection.x
      + worldDirection;
  return viewToWorld._m02_m12_m22 * viewDirection.z + worldDirection;
}

MainPartGlassClusterAddress ResolveMainPartGlassCluster(
    float3 viewPosition, float2 screenUv)
{
  MainPartGlassClusterAddress result;
  result.worldPosition = MainPartGlassViewToWorldPosition(viewPosition);
  result.cookieDerivativePosition = result.worldPosition
      + ddx_coarse(result.worldPosition) + ddy_coarse(result.worldPosition);

  float3 voxelCoordinate;
  voxelCoordinate.xy = cb_vInvRenderScale.xy * screenUv;
  voxelCoordinate.z = -viewPosition.z * cb_cluster.fRcpClusterRange
      + cb_cluster.fClusterNearBias;
  voxelCoordinate.z = rsqrt(voxelCoordinate.z);
  voxelCoordinate.z = 1.0 / voxelCoordinate.z;
  voxelCoordinate *= cb_cluster.vVoxelDims.xyz;
  voxelCoordinate.z = floor(voxelCoordinate.z);
  uint3 voxel = (uint3)voxelCoordinate;
  uint clusterIndex = mad(
      (int)voxel.y, asint(cb_cluster.uClusterWidth), (int)voxel.x);
  clusterIndex = mad(
      (int)voxel.z, asint(cb_cluster.uClusterSliceSize),
      (int)clusterIndex);

  uint packedMasks = sbVoxelLightIds[clusterIndex * 33u];
  result.listBase = clusterIndex * 33u + 1u;
  result.pointMaskWords = packedMasks & 0x0000ff00u;
  result.spotMaskWords = packedMasks & 0x00ff0000u;
  result.reflectionMaskWords = packedMasks & 0xff000000u;
  return result;
}

float3 DecodeMainPartGlassLightColor(uint packedColor)
{
  return float3(
      (packedColor >> 24u) & 255u,
      (packedColor >> 16u) & 255u,
      (packedColor >> 8u) & 255u) * 0.00392156886;
}

float EvaluateMainPartGlassSpecular(
    float3 viewDirection, float3 lightDirection, float3 normalView,
    float glossExponent, float specularScale, float intensity)
{
  float3 halfDirection = viewDirection + lightDirection;
  halfDirection *= rsqrt(dot(halfDirection, halfDirection));
  float specular = dot(halfDirection, normalView) * 0.5 + 0.5;
  specular = exp2(log2(abs(specular)) * glossExponent);
  return saturate(specular * intensity * specularScale);
}

float EvaluateMainPartGlassDiffuseResponse(float normalDotLight)
{
#ifdef MAIN_PART_GLASS_SURFACE_STANDARD_LIGHTING
  return abs(normalDotLight);
#else
  float transmission = max(0.0, normalDotLight);
  return transmission * cb_glass.fTransmissionRange
      + cb_glass.fTransmissionBase;
#endif
}

void AccumulateMainPartGlassLightColor(
    uint packedColor, float3 color, inout MainPartGlassLocalLighting lighting)
{
  if ((packedColor & 1u) != 0u)
    lighting.additiveColor += max(0.0, color);
  else
    lighting.maximumColor = max(lighting.maximumColor, color);
}

void AccumulateMainPartGlassPointLight(
    int lightIndex, float3 viewPosition,
    MainPartDissolveGlassMaterial material,
    inout MainPartGlassLocalLighting lighting)
{
  float3 toLight = cb_arrPoint[lightIndex].vPosition.xyz - viewPosition;
  float distanceToLight = sqrt(dot(toLight, toLight));
  float3 lightDirection = toLight / max(0.00100000005, distanceToLight);
  float diffuseResponse = EvaluateMainPartGlassDiffuseResponse(
      dot(lightDirection, material.normalView));

  float normalizedDistance = saturate(
      cb_arrPoint[lightIndex].fRcpRadius * distanceToLight);
  normalizedDistance = max(0.00999999978, normalizedDistance);
  float intensity = exp2(
      cb_arrPoint[lightIndex].fFalloffFactor * log2(normalizedDistance));
  intensity = cb_arrPoint[lightIndex].fIntensity * (1.0 - intensity);
  intensity = min(cb_arrPoint[lightIndex].fMaxIntensity, intensity);

  uint packedColor = cb_arrPoint[lightIndex].uColor;
  float3 color = DecodeMainPartGlassLightColor(packedColor)
      * (diffuseResponse * intensity);
  lighting.specular = max(
      lighting.specular,
      EvaluateMainPartGlassSpecular(
          material.viewDirection, lightDirection, material.normalView,
          material.glossExponent, material.specularScale, intensity));
#ifndef MAIN_PART_GLASS_SURFACE_STANDARD_LIGHTING
  lighting.transmission = max(
      lighting.transmission, diffuseResponse * intensity);
#endif
  AccumulateMainPartGlassLightColor(packedColor, color, lighting);
}

float3 ProjectMainPartGlassSpot(int lightIndex, float3 worldPosition)
{
  float3 projected =
      cb_arrSpot[lightIndex].xClip._m01_m11_m31 * worldPosition.y;
  projected = cb_arrSpot[lightIndex].xClip._m00_m10_m30
      * worldPosition.x + projected;
  projected = cb_arrSpot[lightIndex].xClip._m02_m12_m32
      * worldPosition.z + projected;
  return cb_arrSpot[lightIndex].xClip._m03_m13_m33 + projected;
}

void AccumulateMainPartGlassSpotLight(
    int lightIndex, MainPartGlassClusterAddress cluster,
    float3 viewPosition, MainPartDissolveGlassMaterial material,
    inout MainPartGlassLocalLighting lighting)
{
  float3 toLight = cb_arrSpot[lightIndex].vPosition.xyz - viewPosition;
  float distanceToLight = sqrt(dot(toLight, toLight));
  float normalizedDistance =
      cb_arrSpot[lightIndex].fRcpRange * distanceToLight;
  if (normalizedDistance > 1.0)
    return;

  float3 lightDirection = toLight / max(0.00100000005, distanceToLight);
  float cone = dot(-lightDirection, cb_arrSpot[lightIndex].vForward.xyz);
  if (cone <= 0.0)
    return;
  cone = saturate(cone * cb_arrSpot[lightIndex].fCutoffScale
      + cb_arrSpot[lightIndex].fCutoffOffset);

  uint packedColor = cb_arrSpot[lightIndex].uColor;
  if ((packedColor & 240u) != 0u)
  {
    float3 projected = ProjectMainPartGlassSpot(
        lightIndex, cluster.worldPosition);
    float3 projectedDerivative = ProjectMainPartGlassSpot(
        lightIndex, cluster.cookieDerivativePosition);
    float2 cookieUv = projected.xy / projected.z * 0.5 + 0.5;
    float2 cookieDerivative =
        projectedDerivative.xy / projectedDerivative.z * 0.5 + 0.5
        - cookieUv;
    uint cookieIndex = ((packedColor >> 4u) & 15u) - 1u;
    cone *= taCookies.SampleGrad(
        LinearClampClamp_s, float3(cookieUv, cookieIndex),
        cookieDerivative.x, cookieDerivative.y).x;
  }
  if (cone <= 0.0)
    return;

  normalizedDistance = max(0.00999999978, normalizedDistance);
  float intensity = exp2(
      cb_arrSpot[lightIndex].fFalloffFactor * log2(normalizedDistance));
  intensity = cb_arrSpot[lightIndex].fIntensity * (1.0 - intensity) * cone;
  intensity = min(cb_arrSpot[lightIndex].fMaxIntensity, intensity);
  float diffuseResponse = EvaluateMainPartGlassDiffuseResponse(
      dot(lightDirection, material.normalView));

  float3 color = DecodeMainPartGlassLightColor(packedColor)
      * (diffuseResponse * intensity);
  lighting.specular = max(
      lighting.specular,
      EvaluateMainPartGlassSpecular(
          material.viewDirection, lightDirection, material.normalView,
          material.glossExponent, material.specularScale, intensity));
#ifndef MAIN_PART_GLASS_SURFACE_STANDARD_LIGHTING
  lighting.transmission = max(
      lighting.transmission, diffuseResponse * intensity);
#endif
  AccumulateMainPartGlassLightColor(packedColor, color, lighting);
}

MainPartGlassLocalLighting EvaluateMainPartGlassLocalLights(
    MainPartGlassClusterAddress cluster, float3 viewPosition,
    MainPartDissolveGlassMaterial material, MainPartGlassLighting directional)
{
  MainPartGlassLocalLighting result;
  result.maximumColor = directional.directColor;
  result.additiveColor = 0.0;
  result.transmission = directional.transmission;
  result.specular = directional.specular;

  uint wordMask = cluster.pointMaskWords;
  while (wordMask != 0u)
  {
    uint wordBit = firstbitlow(wordMask);
    wordMask ^= 1u << wordBit;
    uint lights = sbVoxelLightIds[cluster.listBase + wordBit];
    uint lightBase = wordBit << 5u;
    while (lights != 0u)
    {
      uint lightBit = firstbitlow(lights);
      lights ^= 1u << lightBit;
      int lightIndex = (int)((lightBase + lightBit) << 1u) - 512;
      AccumulateMainPartGlassPointLight(
          lightIndex, viewPosition, material, result);
    }
  }

  wordMask = cluster.spotMaskWords;
  while (wordMask != 0u)
  {
    uint wordBit = firstbitlow(wordMask);
    wordMask ^= 1u << wordBit;
    uint lights = sbVoxelLightIds[cluster.listBase + wordBit];
    uint lightBase = wordBit << 5u;
    while (lights != 0u)
    {
      uint lightBit = firstbitlow(lights);
      lights ^= 1u << lightBit;
      int lightIndex = (int)(lightBase + lightBit) * 9 - 4608;
      AccumulateMainPartGlassSpotLight(
          lightIndex, cluster, viewPosition, material, result);
    }
  }
  return result;
}

#ifdef MAIN_PART_GLASS_SURFACE_ENABLE_MULTI_PROBES
float MainPartGlassBoxDistance(float3 offset, float3 extents)
{
  float3 boxOffset = abs(offset) - extents;
  float outside = sqrt(dot(max(0.0, boxOffset), max(0.0, boxOffset)));
  float inside = min(0.0, max(boxOffset.x, max(boxOffset.y, boxOffset.z)));
  return outside + inside;
}

float3 MainPartGlassBoxProjectedDirection(
    int probeIndex, float3 worldPosition, float3 direction,
    float3 inverseDirection)
{
  float3 toMaximum = (cb_reflections.vecProbes[probeIndex].vMax.xyz
      - worldPosition) * inverseDirection;
  float3 toMinimum = (cb_reflections.vecProbes[probeIndex].vMin.xyz
      - worldPosition) * inverseDirection;
  float distanceAlongRay = min(
      max(toMinimum.x, toMaximum.x),
      min(max(toMinimum.y, toMaximum.y), max(toMinimum.z, toMaximum.z)));
  return direction * distanceAlongRay + worldPosition
      - cb_reflections.vecProbes[probeIndex].vPosition.xyz;
}

float2 EncodeMainPartGlassProbeDirection(float3 direction)
{
  float inverseL1 = rcp(max(
      9.99999975e-05,
      abs(direction.x) + abs(direction.y) + abs(direction.z)));
  float2 encoded = direction.xy * inverseL1;
  float2 folded = 1.0 - abs(encoded.yx);
  folded = encoded < 0.0 ? -folded : folded;
  encoded = direction.z <= 0.0 ? folded : encoded;
  encoded += float2(-2.0, 2.0);
  encoded = max(abs(encoded.x), abs(encoded.y)) >= 1.0
      ? -encoded : encoded;
  return encoded * 0.5 + 0.5;
}

void AccumulateMainPartGlassProbe(
    int probeIndex, MainPartGlassClusterAddress cluster,
    float3 reflectionDirection, float3 inverseReflectionDirection,
    float roughnessLod, float parallaxBlend, float reliability,
    inout MainPartGlassProbeLighting lighting)
{
  float signedDistance = MainPartGlassBoxDistance(
      cb_reflections.vecProbes[probeIndex].vPosition.xyz
          - cluster.worldPosition,
      cb_reflections.vecProbes[probeIndex].vExtents.xyz);
  signedDistance = cb_reflections.vecProbes[probeIndex].fGpuEnable
      * (signedDistance - cb_reflections.vecProbes[probeIndex].fMargin);
  if (signedDistance >= 0.0)
    return;

  float marginWeight = saturate(
      cb_reflections.vecProbes[probeIndex].fMarginRcp * -signedDistance);
  bool fallback = cb_reflections.vecProbes[probeIndex].fIsFallback != 0.0;
  float containment = fallback ? 1.0 : marginWeight;
  float probeWeight = cb_reflections.vecProbes[probeIndex].fBlend
      * containment;

  if (cb_reflections.vecProbes[probeIndex].fIsFallback == 1.0)
  {
    float3 direction = reflectionDirection;
    if (cb_reflections.vecProbes[probeIndex].fParallax == 1.0)
      direction = MainPartGlassBoxProjectedDirection(
          probeIndex, cluster.worldPosition, reflectionDirection,
          inverseReflectionDirection);
    float3 address = float3(
        EncodeMainPartGlassProbeDirection(direction),
        cb_reflections.vecProbes[probeIndex].fSlotIndex);
    float3 sampleColor = taReflection.SampleLevel(
        LinearMirrorMirror_s, address, roughnessLod).xyz;
    lighting.fallbackWeight += containment
        * cb_reflections.vecProbes[probeIndex].fBlend;
    lighting.fallbackColor += sampleColor * probeWeight;
    return;
  }

  float3 projectedDirection = MainPartGlassBoxProjectedDirection(
      probeIndex, cluster.worldPosition, reflectionDirection,
      inverseReflectionDirection);
  projectedDirection *= rsqrt(dot(projectedDirection, projectedDirection));
  projectedDirection = lerp(
      reflectionDirection, projectedDirection,
      cb_reflections.vecProbes[probeIndex].fParallax * parallaxBlend);
  projectedDirection *= rsqrt(dot(projectedDirection, projectedDirection));
  float3 address = float3(
      EncodeMainPartGlassProbeDirection(projectedDirection),
      cb_reflections.vecProbes[probeIndex].fSlotIndex);
  float4 probeSample = taReflection.SampleLevel(
      LinearMirrorMirror_s, address, roughnessLod);

  float hitDistance = probeSample.w * probeSample.w * 127.5 + 0.5;
  float3 hitPosition = projectedDirection * hitDistance
      + cb_reflections.vecProbes[probeIndex].vPosition.xyz;
  float3 toSurface = cluster.worldPosition - hitPosition;
  float distanceSquared = dot(toSurface, toSurface);
  float gpuSignedDistance = MainPartGlassBoxDistance(
      cb_reflections.vecProbes[probeIndex].vGpuPosition.xyz - hitPosition,
      cb_reflections.vecProbes[probeIndex].vGpuExtents.xyz)
      - cb_reflections.vecProbes[probeIndex].fGpuMargin;
  float gpuMargin = saturate(
      cb_reflections.vecProbes[probeIndex].fGpuMarginRcp
      * -gpuSignedDistance);
  float facing = dot(reflectionDirection, projectedDirection) * 0.5 + 0.5;
  facing *= facing;
  float distanceFade = 1.0 - min(1.0, distanceSquared * 0.000244140625);
  distanceFade *= distanceFade;
  float correction = distanceFade * gpuMargin * facing * marginWeight;
  correction = correction * 10.0 + 1.0;
  float contribution = max(gpuMargin, reliability)
      * marginWeight * facing * correction;
  float weightedContribution = contribution * probeWeight;
  float active = contribution > 0.0 ? 1.0 : 0.0;
  lighting.gpuWeight += weightedContribution;
  lighting.gpuBlend += probeWeight * active;
  lighting.gpuColor += probeSample.xyz * weightedContribution * active;
}

float3 EvaluateMainPartGlassReflectionProbes(
    MainPartGlassClusterAddress cluster,
    MainPartDissolveGlassMaterial material)
{
  float normalDotView = dot(-material.viewDirection, material.normalView);
  float3 reflectedView = material.normalView * (-2.0 * normalDotView)
      - material.viewDirection;
  float3 reflectedWorld = MainPartGlassViewToWorldDirection(reflectedView);
  float roughness = exp2(0.75 * log2(abs(1.0 - material.gloss)));
  float roughnessLod = 5.0 * roughness;
  float reliability = 1.0 - min(1.0, 0.5 * roughness);
  float parallaxBlend = 1.0
      - saturate((roughnessLod - 3.0) * 2.0);
  float3 inverseDirection = rcp(reflectedWorld);

  MainPartGlassProbeLighting lighting;
  lighting.gpuColor = 0.0;
  lighting.fallbackColor = 0.0;
  lighting.gpuWeight = 0.0;
  lighting.fallbackWeight = 0.0;
  lighting.gpuBlend = 0.0;
  uint wordMask = cluster.reflectionMaskWords;
  while (wordMask != 0u)
  {
    uint wordBit = firstbitlow(wordMask);
    wordMask ^= 1u << wordBit;
    uint probes = sbVoxelLightIds[cluster.listBase + wordBit];
    uint probeBase = wordBit << 5u;
    while (probes != 0u)
    {
      uint probeBit = firstbitlow(probes);
      probes ^= 1u << probeBit;
      int probeIndex = (int)(probeBase + probeBit) * 10 - 7680;
      AccumulateMainPartGlassProbe(
          probeIndex, cluster, reflectedWorld, inverseDirection,
          roughnessLod, parallaxBlend, reliability, lighting);
    }
  }

  float3 gpuColor = lighting.gpuColor / max(0.125, lighting.gpuWeight);
  float3 fallbackColor = lighting.fallbackColor
      / max(0.00100000005, lighting.fallbackWeight);
  float blend = saturate(lighting.gpuBlend);
  blend *= blend;
  return lerp(fallbackColor, gpuColor, blend);
}
#endif

#endif // MAIN_PART_GLASS_CLUSTERED_LIGHTING_INCLUDED
