#ifndef MAIN_PART_GLASS_HIGH_QUALITY_INCLUDED
#define MAIN_PART_GLASS_HIGH_QUALITY_INCLUDED

// High-quality transparent-surface policy.  This layer owns only the features
// absent from the medium graph: cascade/cloud visibility and mip-aware
// indirect/frame composition.  Material decoding, clustered lights, and
// reflection probes remain shared with the lower quality permutations.

struct MainPartHighShadowAddress
{
  float3 coordinate;
  uint cascade;
  float edgeBlend;
  bool valid;
};

float3 TransformMainPartCascade(uint cascade, float3 worldPosition)
{
  float3 result = cb_arrCascades[cascade]._m01_m11_m21 * worldPosition.y;
  result = cb_arrCascades[cascade]._m00_m10_m20 * worldPosition.x + result;
  result = cb_arrCascades[cascade]._m02_m12_m22 * worldPosition.z + result;
  return cb_arrCascades[cascade]._m03_m13_m23 + result;
}

MainPartHighShadowAddress ResolveMainPartCascade(float3 worldPosition)
{
  MainPartHighShadowAddress result;
  result.coordinate = 0.0;
  result.cascade = 4u;
  result.edgeBlend = 0.0;
  result.valid = false;

  [unroll]
  for (uint cascade = 0u; cascade < 4u; ++cascade)
  {
    float3 coordinate = TransformMainPartCascade(cascade, worldPosition);
    float extent = cascade == 3u ? 1.0 : 0.5;
    if (!result.valid && all(abs(coordinate - 0.5) <= extent))
    {
      result.coordinate = coordinate;
      result.cascade = cascade;
      result.valid = true;
    }
  }
  if (result.valid)
  {
    float edge = max(
        abs(result.coordinate.x - 0.5),
        abs(result.coordinate.y - 0.5)) * 2.0;
    float split = dot(cb_vCascadeSplits, float4(
        result.cascade == 0u, result.cascade == 1u,
        result.cascade == 2u, result.cascade == 3u));
    float depthFade = 1.0 - result.coordinate.z * split;
    result.edgeBlend = 1.0 - max(edge, depthFade);
  }
  return result;
}

float SampleMainPartCascadeTent(float3 coordinate, uint cascade)
{
  // The recovered program uses a 6x6 tent reconstructed from nine comparison
  // gathers. Keeping the gather topology here makes the costly filter reusable
  // without leaking its addressing mechanics into material shaders.
  float3 address = coordinate;
  address.z += ((float)cascade * 2.0 + 1.0)
      * (1.0 + coordinate.z * cb_vInverseCameraRange.x) * 5.99999985e-05;
  float2 texel = cb_vCascadeSize.yx * address.yx + 0.5;
  int2 baseTexel = (int2)floor(texel.yx);
  float2 uv = cb_vCascadePixelSize.xy * baseTexel;

  float total = 0.0;
  [unroll]
  for (int y = -2; y <= 2; y += 2)
  {
    [unroll]
    for (int x = -2; x <= 2; x += 2)
    {
      float4 comparison = taCascades.GatherCmp(
          sShadowSamplerLinear_s, float3(uv, address.z), address.z,
          int2(x, y));
      total += dot(comparison, 1.0);
    }
  }
  return total * (1.0 / 36.0);
}

float EvaluateMainPartCascadeVisibility(float3 worldPosition)
{
  if (cb_fTransparentUseCascade == 0.0)
    return 1.0;
  MainPartHighShadowAddress address = ResolveMainPartCascade(worldPosition);
  if (!address.valid)
    return 1.0;

  float visibility = SampleMainPartCascadeTent(
      address.coordinate, address.cascade);
  if (address.cascade < 3u && address.edgeBlend < 0.11)
  {
    float blend = saturate(address.edgeBlend / (0.11 * (address.cascade + 1u)));
    float3 next = TransformMainPartCascade(address.cascade + 1u, worldPosition);
    visibility = lerp(
        SampleMainPartCascadeTent(next, address.cascade + 1u),
        visibility, blend);
  }
  return visibility;
}

float EvaluateMainPartCloudOcclusion(float3 worldPosition)
{
  if (cb_clouds.fCloudShadowCoveragesInv >= 1.0)
    return 0.0;
  float3 relative = worldPosition - cb_clouds.vPlanetCenter.xyz;
  float alongLight = dot(relative, -cb_vDirectionalLightDirectionWorld.xyz);
  float discriminant = alongLight * alongLight
      - (dot(relative, relative) - cb_clouds.fAtmosphereRadiusSqr);
  float root = sqrt(max(0.0, discriminant));
  float rayDistance = max(root - alongLight, -root - alongLight);
  float2 cloudUv = (worldPosition.xz
      - cb_vDirectionalLightDirectionWorld.xy * rayDistance
      + cb_clouds.vRawScroll.xy) * 9.2307695e-05;
  float cloud = tCloudMap.SampleLevel(LinearWrapWrap_s, cloudUv, 0).x;
  cloud = 1.0 - min(1.0,
      (cloud - cb_clouds.fCloudShadowCoveragesInv) * 5.88235283);
  if (cloud >= 0.300000012)
    return 0.0;
  float coverage = 1.0
      - cb_clouds.fCloudCoveragesInv * cb_clouds.fCloudCoveragesInv;
  float fade = saturate((0.300000012 - cloud) / cloud);
  fade = 1.0 - fade * fade * fade * fade;
  return min(coverage, fade);
}

MainPartGlassLighting EvaluateMainPartHighDirectionalGlassLighting(
    float3 viewPosition, MainPartDissolveGlassMaterial material)
{
  MainPartGlassLighting result;
  result.directColor = 0.0;
  result.reflectedColor = 0.0;
  result.transmission = 0.0;
  result.specular = 0.0;
  if (cb_fDirectionalLightIntensity == 0.0)
    return result;

  float3 worldPosition = MainPartGlassViewToWorldPosition(viewPosition);
  float normalDotLight = dot(
      material.normalView, -cb_vDirectionalLightDirectionView.xyz);
  float visibility = EvaluateMainPartCascadeVisibility(worldPosition);
  float normalFade = saturate((0.400000006 + abs(normalDotLight))
      * 1.66666663);
  normalFade = normalFade * normalFade * (3.0 - 2.0 * normalFade);
  visibility *= normalFade;
  visibility = saturate(
      visibility - EvaluateMainPartCloudOcclusion(worldPosition));

  float halfLambert = normalDotLight * 0.5 + 0.5;
  float distanceShape = 1.0 - min(1.0, 0.00400000019 * material.viewDistance);
  distanceShape = distanceShape * distanceShape * 0.200000018 + 0.400000006;
  float2 shapeRange = float2(1.0, 1.20000005) - distanceShape;
  float shapedLight = saturate(halfLambert - distanceShape) / shapeRange.x;
  shapedLight *= shapedLight;
  distanceShape = shapedLight * shapeRange.y + distanceShape;
  float3 mappedLight = tLightColorMap.SampleLevel(
      LinearWrapClamp_s,
      float2(cb_fTimeOfDay, saturate(halfLambert)), 0).xyz;
  mappedLight = (mappedLight - cb_vDirectionalShadowColor.xyz)
      * (visibility * halfLambert) + cb_vDirectionalShadowColor.xyz;
  result.directColor = mappedLight
      * (cb_fDirectionalLightMapMul * distanceShape)
      * cb_fDirectionalLightIntensity;

  float3 halfDirection = material.viewDirection
      - cb_vDirectionalLightDirectionView.xyz;
  halfDirection *= rsqrt(dot(halfDirection, halfDirection));
  float specular = dot(halfDirection, material.normalView) * 0.5 + 0.5;
  specular = exp2(log2(abs(specular)) * material.glossExponent);
  specular *= min(visibility, abs(normalDotLight));
  result.specular = saturate(specular * material.specularScale);
  return result;
}

float2 ClampMainPartHighFrameUv(float2 screenUv, float pixelRadius)
{
  float2 upper = cb_vRenderScale.xy
      - cb_vContainerPixelSize.xy * pixelRadius;
  return min(cb_vRenderScale.xy, screenUv)
      - max(0.0, screenUv - upper);
}

MainPartGlassSurfaceComposite ComposeMainPartHighUnresponsiveGlassSurface(
    float3 screenUv, float4 fogColor, bool frontFace,
    MainPartDissolveGlassMaterial material, MainPartGlassLighting lighting)
{
  MainPartGlassSurfaceComposite result;
  lighting.directColor = material.coverage * (1.0 - lighting.directColor)
      + lighting.directColor;
  float auxiliaryCoverage = min(0.5, 0.5 * material.coverage);
  float normalFacing = dot(material.viewDirection, material.normalView);
  float minimumFresnel = material.gloss * 0.5 + 0.00999999978;
  float grazing = 1.0 - normalFacing;
  float fresnel = grazing * grazing;
  fresnel *= fresnel * grazing;
  fresnel = (1.0 - minimumFresnel) * fresnel + minimumFresnel;
  float faceTransparency = frontFace
      ? cb_glass.fTransparencyFront : cb_glass.fTransparencyBack;
  float transparency = saturate(
      faceTransparency + lighting.specular + fresnel);
  float reflectionEnergy = lighting.specular + fresnel;

  float3 indirect = tIndirect.SampleLevel(
      PointClampClamp_s, screenUv.xy, 0).xyz;
  float luminance = dot(indirect, float3(0.298999995, 0.587000012, 0.114));
  indirect *= 1.13 * (luminance * 0.200000003 + 1.39999998);
  indirect = indirect * saturate(material.viewDistance - 1.0) + 0.119999997;

  float mip = saturate(
      (1.0 - material.gloss) * (1.0 - material.gloss)
      + cb_glass.fBlurriness) * cb_vRenderScale.x;
  float2 edge = abs(screenUv.xy - cb_vRenderScale.xy * 0.5)
      / cb_vRenderScale.xy * 2.0;
  float edgeMip = 5.0 * saturate(5.0 * (max(edge.x, edge.y) - 0.8));
  mip = mip * 5.0 + edgeMip;
  float pixelRadius = exp2(mip);
  float4 frame = tFrame.SampleLevel(
      LinearMirrorMirror_s,
      ClampMainPartHighFrameUv(screenUv.xy, pixelRadius), mip);

  float3 glassColor = material.diffuseColor * lighting.directColor;
  glassColor += lighting.directColor * reflectionEnergy;
  glassColor += indirect * material.gloss + lighting.reflectedColor;
  glassColor = lerp(frame.xyz, glassColor, transparency);
  float fogStrength = 0.349999994 * auxiliaryCoverage;
  fogStrength *= 1.0 - min(1.0, 0.00999999978 * material.viewDistance);
  float largestChannel = max(abs(glassColor.x), abs(glassColor.y));
  largestChannel = max(largestChannel, abs(glassColor.z));
  fogStrength = (1.0 - fogStrength * largestChannel) * fogColor.w;
  result.color.xyz = lerp(glassColor, fogColor.xyz, fogStrength);
  result.color.w = max(frame.w, transparency);
  result.auxiliary = float4(auxiliaryCoverage, 0.0, 0.0, result.color.w);
  return result;
}

#endif
