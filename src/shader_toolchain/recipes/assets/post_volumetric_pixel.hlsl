#include "include/post_volumetric_projection_abi.hlsl"
#include "include/post_volumetric_perframe_abi.hlsl"
#include "include/post_volumetric_hdr_abi.hlsl"
#include "include/post_volumetric_cluster_abi.hlsl"
#include "include/post_volumetric_lights_abi.hlsl"

SamplerState PointClampClamp_s : register(s1);
SamplerState LinearWrapWrap_s : register(s3);
SamplerState LinearClampClamp_s : register(s6);
SamplerComparisonState sShadowSamplerPoint_s : register(s13);
Texture2D<float> tHzb : register(t0);
StructuredBuffer<uint> sbVolumetricIds : register(t1);
Texture3D<float> tNoise : register(t2);
Texture2DArray<float> taCookies : register(t3);
Texture2DArray<float> tShadowAtlas : register(t4);
Texture2D<float> tTemporalHzb : register(t5);
Texture2D<float3> tTemporal : register(t6);
Texture2D<float> tScreenNoise : register(t7);
Texture2D<float> tVolatile : register(t8);

static const float INTERSECTION_EPSILON = 0.00100000005;
static const float SEGMENT_EPSILON = 9.99999975e-05;
static const float MIN_SAMPLE_DISTANCE = 0.5;
static const float MAX_MARCH_SPAN = 50.0;
static const float MARCH_PHASE_SCALE = 0.980000019;
static const float DISTANCE_FADE_SCALE = 0.333333343;

struct ClusteredVolumeRecord
{
  uint wordBase;
  uint sphereGroupMask;
  uint coneGroupMask;
};

struct TemporalHistory
{
  float3 radiance;
  float weight;
  float2 previousUv;
};

struct VolumetricRay
{
  float3 viewRay;
  float3 viewDirection;
  float3 worldDirection;
  float sceneDepth;
  float jitter;
  float stepSize;
};

struct RaySegment
{
  float entryDistance;
  float exitDistance;
  bool valid;
};

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

ClusteredVolumeRecord ResolveClusteredVolumes(float2 screenUv)
{
  uint2 tile = uint2(cb_cluster.vVoxelDims.xy * screenUv);
  uint clusterIndex = tile.y * cb_cluster.uClusterWidth + tile.x;
  uint headerIndex = clusterIndex * 17;
  uint header = sbVolumetricIds[headerIndex];

  ClusteredVolumeRecord result;
  result.wordBase = headerIndex + 1;
  result.sphereGroupMask = header & 255;
  result.coneGroupMask = (header >> 8) & 255;
  return result;
}

float3 ReconstructWorldPosition(float2 screenUv, float sceneDepth)
{
  float2 ndc = screenUv * float2(2.0, -2.0) + float2(-1.0, 1.0);
  float2 viewPosition = cb_vNearFarViewCorner.zw * ndc * sceneDepth;
  float3 worldPosition = viewToWorld._m01_m11_m21 * viewPosition.y;
  worldPosition = viewToWorld._m00_m10_m20 * viewPosition.x + worldPosition;
  worldPosition = viewToWorld._m02_m12_m22 * -sceneDepth + worldPosition;
  return viewToWorld._m03_m13_m23 + worldPosition;
}

TemporalHistory ReprojectTemporalHistory(
    float2 screenUv,
    float3 worldPosition,
    float sceneDepth)
{
  TemporalHistory history;
  history.radiance = 0.0;
  history.weight = 0.0;
  history.previousUv = 0.0;

  float3 previousClip = cb_xPrevWorldToViewProjection._m01_m11_m31
                      * worldPosition.y;
  previousClip = cb_xPrevWorldToViewProjection._m00_m10_m30
               * worldPosition.x + previousClip;
  previousClip = cb_xPrevWorldToViewProjection._m02_m12_m32
               * worldPosition.z + previousClip;
  previousClip += cb_xPrevWorldToViewProjection._m03_m13_m33;
  if (!all(abs(previousClip.xy) < previousClip.zz))
    return history;

  float2 previousNdc = previousClip.xy / previousClip.z;
  history.previousUv = cb_vPrevRenderScale.xy
                     * (previousNdc * float2(0.5, -0.5) + 0.5);
  float previousDepth = tTemporalHzb.SampleLevel(
      LinearClampClamp_s, history.previousUv, 2).x;
  float2 previousViewPosition = cb_vPrevViewCorner.xy
                              * previousNdc * previousDepth;
  float3 previousWorldPosition = cb_xPrevViewToWorld._m01_m11_m21
                               * previousViewPosition.y;
  previousWorldPosition = cb_xPrevViewToWorld._m00_m10_m20
                        * previousViewPosition.x + previousWorldPosition;
  previousWorldPosition = cb_xPrevViewToWorld._m02_m12_m22
                        * -previousDepth + previousWorldPosition;
  previousWorldPosition += cb_xPrevViewToWorld._m03_m13_m23;

  float3 cameraDelta = viewToWorld._m03_m13_m23
                     - cb_xPrevViewToWorld._m03_m13_m23;
  float cameraWeight = 1.0 - min(1.0, length(cameraDelta));
  float depthWeight = saturate((sceneDepth - 1.0) * 0.200000003);
  float positionTolerance = min(
      2.0, max(9.99999975e-06, sceneDepth * sceneDepth * 0.00249999994));
  float positionError = min(
      1.0, length(previousWorldPosition - worldPosition) / positionTolerance);
  float volatility = 1.0 - abs(tVolatile.SampleLevel(
      LinearClampClamp_s, screenUv, 0).x);
  history.weight = min(
      1.0, 1.0 + cameraWeight * depthWeight - positionError) * volatility;
  if (history.weight != 0.0)
    history.radiance = tTemporal.SampleLevel(
        LinearClampClamp_s, history.previousUv, 0).xyz;
  return history;
}

float SelectVolumetricMarchStep(float qualityFactor, float historyWeight)
{
#if defined(PS_SHADER_QUALITY_HIGH)
  float2 stepRange = qualityFactor * float2(0.300000012, 0.800000012) + 0.2;
  return historyWeight * (stepRange.y - stepRange.x) + stepRange.x;
#else
  float historyStep = qualityFactor * 0.600000024 + 0.200000003;
  return historyWeight * (1.0 - historyStep) + historyStep;
#endif
}

VolumetricRay BuildVolumetricRay(
    float2 screenUv,
    uint2 pixel,
    float sceneDepth,
    float historyWeight)
{
  VolumetricRay ray;
  uint2 noisePixel = pixel & 63;
  ray.jitter = frac(cb_fTime * 20.0 + tScreenNoise.Load(int3(noisePixel, 0)).x);
  float qualityFactor = max(
      cb_fFrameRateScale, saturate(cb_vRenderScale.y * 2.0 - 1.0));
  ray.stepSize = SelectVolumetricMarchStep(qualityFactor, historyWeight);
  float3 viewRay = float3(cb_cluster.vViewCorner.xy
                       * (screenUv * float2(2.0, -2.0) + float2(-1.0, 1.0)), -1.0);
  ray.viewRay = viewRay;
  ray.viewDirection = normalize(viewRay);
  ray.worldDirection = viewToWorld._m01_m11_m21 * viewRay.y;
  ray.worldDirection = viewToWorld._m00_m10_m20 * viewRay.x
                     + ray.worldDirection;
  ray.worldDirection -= viewToWorld._m02_m12_m22;
  ray.sceneDepth = sceneDepth;
  return ray;
}

float ComputeDistanceFalloff(float normalizedDistance, float exponent)
{
  float distance = max(0.00999999978, saturate(normalizedDistance));
  return exp2(exponent * log2(distance));
}

float3 IntegrateSphereVolume(uint sphereIndex, VolumetricRay ray)
{
  uint flags = cb_arrSphere[sphereIndex].uColorAndFlags;
  if ((flags & 4) != 0)
    return 0.0;

  float projectedCenter = dot(-cb_arrSphere[sphereIndex].vPosition,
                              ray.viewDirection);
  float discriminant = projectedCenter * projectedCenter
                     - cb_arrSphere[sphereIndex].fC;
  if (discriminant < INTERSECTION_EPSILON)
    return 0.0;

  float root = sqrt(discriminant);
  float entry = (-root - projectedCenter) * -ray.viewDirection.z;
  float exit = (root - projectedCenter) * -ray.viewDirection.z;
  if (ray.sceneDepth < entry || exit - entry <= SEGMENT_EPSILON)
    return 0.0;

  float halfLength = 0.5 * (exit - entry);
  float center = entry + halfLength;
  float stepSize = max(0.0133333337 * entry, ray.stepSize);
  float stepCount = halfLength < stepSize ? 0.0 : halfLength / stepSize;
  float lower = max(MIN_SAMPLE_DISTANCE, center - stepSize * stepCount);
  float upper = min(ray.sceneDepth,
                    min(MAX_MARCH_SPAN + lower, center + stepSize * stepCount));
  float3 snapped = ray.worldDirection * upper + viewToWorld._m03_m13_m23;
  snapped = -0.25 * round(4.0 * snapped) + viewToWorld._m03_m13_m23;
  float sampleDistance = -stepSize * ray.jitter * MARCH_PHASE_SCALE
                       - (dot(snapped, ray.worldDirection) - 0.25);
  float maximumIntensity = 0.0;
  while (lower < sampleDistance)
  {
    float clippedDistance = min(sampleDistance, ray.sceneDepth);
    float distanceFade = saturate(
        (clippedDistance - 0.5) * DISTANCE_FADE_SCALE);
    float intensity = cb_arrSphere[sphereIndex].fIntensity
                    * distanceFade * distanceFade;
    float3 lightOffset = cb_arrSphere[sphereIndex].vPosition
                       - ray.viewRay * clippedDistance;
    float lightDistance = length(lightOffset);
    float innerFade = saturate(
        cb_arrSphere[sphereIndex].fRcpMinRadius * lightDistance);
    if (intensity >= INTERSECTION_EPSILON && innerFade < 1.0)
    {
      float outerShape = 1.0 - ComputeDistanceFalloff(
          cb_arrSphere[sphereIndex].fRcpMaxRadius * lightDistance,
          cb_arrSphere[sphereIndex].fFalloffFactor);
      float innerShape = ComputeDistanceFalloff(
          1.0 - innerFade, cb_arrSphere[sphereIndex].fFalloffFactor);
      float3 worldPosition = ray.worldDirection * clippedDistance
                           + viewToWorld._m03_m13_m23;
      float contribution = innerShape * outerShape * intensity
                         * SampleVolumetricDensity(worldPosition);
      maximumIntensity = max(maximumIntensity, min(
          cb_arrSphere[sphereIndex].fMaxIntensity, contribution));
    }
    sampleDistance -= stepSize;
  }
  return DecodeVolumetricLightColor(flags) * maximumIntensity;
}

RaySegment IntersectConeVolume(uint coneIndex, float3 viewDirection)
{
  RaySegment segment;
  segment.entryDistance = 0.0;
  segment.exitDistance = 0.0;
  segment.valid = false;
  uint flags = cb_arrCone[coneIndex].uColorAndFlags;
  if ((flags & 4) != 0)
    return segment;

  float rayForward = dot(viewDirection, cb_arrCone[coneIndex].vForward);
  float quadraticA = rayForward * rayForward
                   - cb_arrCone[coneIndex].fCutoffCosSqr;
  float projectedPosition = dot(
      viewDirection, -cb_arrCone[coneIndex].vPosition);
  float quadraticB = rayForward * cb_arrCone[coneIndex].fProjectedForward
                   - cb_arrCone[coneIndex].fCutoffCosSqr * projectedPosition;
  float positionLengthSquared = dot(
      -cb_arrCone[coneIndex].vPosition, -cb_arrCone[coneIndex].vPosition);
  float quadraticC = cb_arrCone[coneIndex].fProjectedForward
                   * cb_arrCone[coneIndex].fProjectedForward
                   - cb_arrCone[coneIndex].fCutoffCosSqr * positionLengthSquared;
  float discriminant = 4.0 * (
      quadraticB * quadraticB - quadraticA * quadraticC);
  if (discriminant < SEGMENT_EPSILON)
    return segment;

  float root = sqrt(discriminant);
  float denominator = 2.0 * quadraticA;
  float firstRoot = (-2.0 * quadraticB - root) / denominator;
  float secondRoot = (-2.0 * quadraticB + root) / denominator;
  float projectedEnd = max(
      0.0, cb_arrCone[coneIndex].fNegProjectedEnd / rayForward);

  float3 firstPosition = firstRoot * viewDirection
                       - cb_arrCone[coneIndex].vPosition;
  float firstForward = dot(firstPosition, cb_arrCone[coneIndex].vForward);
  if (firstForward < INTERSECTION_EPSILON
      || cb_arrCone[coneIndex].fMinRange < firstForward)
    firstRoot = projectedEnd;

  float3 secondPosition = secondRoot * viewDirection
                        - cb_arrCone[coneIndex].vPosition;
  float secondForward = dot(secondPosition, cb_arrCone[coneIndex].vForward);
  if (secondForward < INTERSECTION_EPSILON
      || cb_arrCone[coneIndex].fMinRange < secondForward)
    secondRoot = projectedEnd;

  float firstDepth = firstRoot * -viewDirection.z;
  float secondDepth = secondRoot * -viewDirection.z;
  segment.entryDistance = min(firstDepth, secondDepth);
  segment.exitDistance = max(firstDepth, secondDepth);
  segment.valid = segment.exitDistance - segment.entryDistance >= 0.00999999978;
  return segment;
}

float ProjectConeAttenuation(uint coneIndex, float3 lightOffset, float3 worldPosition)
{
  float lightDistance = max(INTERSECTION_EPSILON, length(lightOffset));
  float3 lightDirection = lightOffset / lightDistance;
  float attenuation = saturate(
      dot(cb_arrCone[coneIndex].vForward, -lightDirection)
      * cb_arrCone[coneIndex].fCutoffScale
      + cb_arrCone[coneIndex].fCutoffOffset);

  float4 clipPosition = cb_arrCone[coneIndex].xClip._m01_m11_m21_m31
                      * worldPosition.y;
  clipPosition += cb_arrCone[coneIndex].xClip._m00_m10_m20_m30
                * worldPosition.x;
  clipPosition += cb_arrCone[coneIndex].xClip._m02_m12_m22_m32
                * worldPosition.z;
  clipPosition += cb_arrCone[coneIndex].xClip._m03_m13_m23_m33;
  float3 projected = clipPosition.xyz / clipPosition.w;
  float2 projectedUv = projected.xy * 0.5 + 0.5;

  uint flags = cb_arrCone[coneIndex].uColorAndFlags;
  if ((flags & 240) != 0)
  {
    // SM_COVERAGE_CANARY: cone_cookie
    uint cookieSlice = ((flags >> 4) & 15) - 1;
    attenuation *= taCookies.SampleLevel(
        PointClampClamp_s, float3(projectedUv, cookieSlice), 5).x;
  }
  if (cb_arrCone[coneIndex].shadowProps.fScale != 0.0)
  {
    // SM_COVERAGE_CANARY: cone_shadow
    float2 atlasScale = cb_arrCone[coneIndex].shadowProps.fScale
                      * float2(cb_cluster.fShadowAtlasAspect, 1.0);
    float3 shadowUv = float3(
        projectedUv * atlasScale
        + cb_arrCone[coneIndex].shadowProps.vPosition,
        0.0);
    float visibility = tShadowAtlas.SampleCmpLevelZero(
        sShadowSamplerPoint_s, shadowUv, projected.z).x;
    visibility = min(1.0,
        cb_arrCone[coneIndex].shadowProps.fFade + visibility);
    attenuation *= visibility;
  }
  return attenuation;
}

float3 IntegrateConeVolume(uint coneIndex, VolumetricRay ray, float3 radiance)
{
  RaySegment segment = IntersectConeVolume(coneIndex, ray.viewDirection);
  if (!segment.valid || ray.sceneDepth < segment.entryDistance)
    return radiance;
  // SM_COVERAGE_CANARY: cone_intersection

  float segmentLength = segment.exitDistance - segment.entryDistance;
  float halfLength = 0.5 * segmentLength;
  float center = segment.entryDistance + halfLength;
  float stepSize = max(0.0133333337 * segment.entryDistance, ray.stepSize);
  float stepCount = halfLength < stepSize ? 0.0 : halfLength / stepSize;
  float lower = max(ray.stepSize, center - stepSize * stepCount);
  float upper = min(ray.sceneDepth,
                    min(MAX_MARCH_SPAN + lower, center + stepSize * stepCount));
  float3 snapped = ray.worldDirection * upper + viewToWorld._m03_m13_m23;
  snapped = -0.25 * round(4.0 * snapped) + viewToWorld._m03_m13_m23;
  float sampleDistance = -stepSize * ray.jitter * MARCH_PHASE_SCALE
                       - (dot(snapped, ray.worldDirection) - 0.25);
  float maximumIntensity = 0.0;
  while (lower < sampleDistance)
  {
    // SM_COVERAGE_CANARY: cone_march
    float clippedDistance = min(sampleDistance, ray.sceneDepth);
    float3 lightOffset = cb_arrCone[coneIndex].vPosition
                       - ray.viewRay * clippedDistance;
    float distanceFade = saturate(
        (clippedDistance - 0.5) * DISTANCE_FADE_SCALE);
    float axialDistance = dot(
        -lightOffset, cb_arrCone[coneIndex].vForward);
    float fadeIn = saturate(
        (axialDistance - cb_arrCone[coneIndex].fFadeInStart)
        * cb_arrCone[coneIndex].fFadeInRangeRcp);
    float intensity = cb_arrCone[coneIndex].fIntensity
                    * fadeIn * distanceFade * distanceFade;
    float lightDistance = length(lightOffset);
    float innerFade = saturate(
        cb_arrCone[coneIndex].fRcpMinRange * lightDistance);
    if (intensity >= INTERSECTION_EPSILON && innerFade < 1.0)
    {
      float3 worldPosition = ray.worldDirection * clippedDistance
                           + viewToWorld._m03_m13_m23;
      intensity *= ProjectConeAttenuation(
          coneIndex, lightOffset, worldPosition);
      if (intensity > INTERSECTION_EPSILON)
      {
        float outerShape = 1.0 - ComputeDistanceFalloff(
            cb_arrCone[coneIndex].fRcpMaxRange * lightDistance,
            cb_arrCone[coneIndex].fFalloffFactor);
        float innerShape = ComputeDistanceFalloff(
            1.0 - innerFade, cb_arrCone[coneIndex].fFalloffFactor);
        float contribution = innerShape * outerShape * intensity
                           * SampleVolumetricDensity(worldPosition);
        maximumIntensity = max(maximumIntensity, min(
            cb_arrCone[coneIndex].fMaxIntensity, contribution));
      }
    }
    sampleDistance -= stepSize;
  }
  float3 coneRadiance = DecodeVolumetricLightColor(
      cb_arrCone[coneIndex].uColorAndFlags) * maximumIntensity;
  return max(radiance, coneRadiance);
}

float3 IntegrateClusteredVolumes(
    ClusteredVolumeRecord cluster,
    VolumetricRay ray)
{
  float3 radiance = 0.0;
  uint groupMask = cluster.sphereGroupMask;
  while (groupMask != 0)
  {
    uint group = firstbitlow(groupMask);
    groupMask ^= 1u << group;
    uint lightMask = sbVolumetricIds[cluster.wordBase + group];
    while (lightMask != 0)
    {
      uint bit = firstbitlow(lightMask);
      lightMask ^= 1u << bit;
      radiance = max(radiance,
          IntegrateSphereVolume(group * 32 + bit, ray));
    }
  }

  groupMask = cluster.coneGroupMask;
  while (groupMask != 0)
  {
    uint group = firstbitlow(groupMask);
    groupMask ^= 1u << group;
    uint lightMask = sbVolumetricIds[cluster.wordBase + 8 + group];
    while (lightMask != 0)
    {
      uint bit = firstbitlow(lightMask);
      lightMask ^= 1u << bit;
      // SM_COVERAGE_CANARY: cone_mask
      radiance = IntegrateConeVolume(group * 32 + bit, ray, radiance);
    }
  }
  return radiance;
}

float3 ResolveVolumetricHistory(float3 current, TemporalHistory history)
{
  float blend = (cb_fFrameRateScale * 0.139999986 + 0.800000012)
              * history.weight;
  return lerp(current, history.radiance, blend);
}

void mainPS(
    float4 position : SV_Position0,
    float2 uv : UV0,
    float2 packedUv : UNSCALED_UV0,
    out float4 displayTarget : SV_Target0,
    out float4 historyTarget : SV_Target1)
{
  float2 screenUv = float2(packedUv.y, packedUv.x);
  uint2 pixel = uint2(asuint(cb_vuViewportSize.xy) * screenUv);
  float sceneDepth = tHzb.Load(int3(pixel, 2)).x;
  ClusteredVolumeRecord cluster = ResolveClusteredVolumes(screenUv);
  float3 worldPosition = ReconstructWorldPosition(screenUv, sceneDepth);
  TemporalHistory history = ReprojectTemporalHistory(
      screenUv, worldPosition, sceneDepth);

  float3 radiance = 0.0;
  if (cluster.sphereGroupMask != 0 || cluster.coneGroupMask != 0)
  {
    VolumetricRay ray = BuildVolumetricRay(
        screenUv, pixel, sceneDepth, history.weight);
    radiance = IntegrateClusteredVolumes(cluster, ray);
  }

  float3 resolved = ResolveVolumetricHistory(radiance, history);
  displayTarget = cb_fVolFogIntensity
                * float4(EncodeVolumetricHdr(resolved), 1.0);
  historyTarget = float4(resolved, 1.0);
}
