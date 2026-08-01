#ifndef MAIN_PART_TINTED_DISSOLVE_GLASS_SURFACE_INCLUDED
#define MAIN_PART_TINTED_DISSOLVE_GLASS_SURFACE_INCLUDED

// One semantic program covers the complete default/medium/high x
// off/single/multi family. The policies control only the phases whose
// recovered implementations differ; material decode and composition stay
// selector-independent.
#define MAIN_PART_GLASS_SURFACE_HAS_DISSOLVE
#if defined(MAIN_PART_TINTED_DISSOLVE_QUALITY_MEDIUM) || \
    defined(MAIN_PART_TINTED_DISSOLVE_QUALITY_HIGH)
#define MAIN_PART_GLASS_SURFACE_ENABLE_MEDIUM_CLUSTERED
#endif
#if defined(MAIN_PART_TINTED_DISSOLVE_REFLECTION_MULTI) && \
    (defined(MAIN_PART_TINTED_DISSOLVE_QUALITY_MEDIUM) || \
     defined(MAIN_PART_TINTED_DISSOLVE_QUALITY_HIGH))
#define MAIN_PART_GLASS_SURFACE_ENABLE_MULTI_PROBES
#elif defined(MAIN_PART_TINTED_DISSOLVE_REFLECTION_SINGLE)
#define MAIN_PART_GLASS_SURFACE_ENABLE_SINGLE_PROBE
#endif

#include "main_part_legacy_glass_surface_basic.hlsl"
#if defined(MAIN_PART_TINTED_DISSOLVE_QUALITY_HIGH)
#include "main_part_glass_high_quality.hlsl"
#endif

MainPartGlassLighting EvaluateMainPartTintedDissolveLighting(
    float3 viewPosition, float3 screenUv,
    MainPartDissolveGlassMaterial material)
{
  MainPartGlassLighting lighting =
#if defined(MAIN_PART_TINTED_DISSOLVE_QUALITY_HIGH)
      EvaluateMainPartHighDirectionalGlassLighting(viewPosition, material);
#else
      EvaluateMainPartLegacyGlassDirectionalLighting(viewPosition, material);
#endif

#if defined(MAIN_PART_TINTED_DISSOLVE_QUALITY_MEDIUM) || \
    defined(MAIN_PART_TINTED_DISSOLVE_QUALITY_HIGH)
  if (-viewPosition.z < cb_cluster.fClusterMaxFarTotal)
  {
    MainPartGlassClusterAddress cluster =
        ResolveMainPartGlassCluster(viewPosition, screenUv.xy);
    MainPartGlassLocalLighting local = EvaluateMainPartGlassLocalLights(
        cluster, viewPosition, material, lighting);
    lighting.directColor = local.maximumColor + local.additiveColor;
    lighting.specular = local.specular;
    lighting.transmission = local.transmission;
#if defined(MAIN_PART_TINTED_DISSOLVE_REFLECTION_MULTI)
    lighting.reflectedColor =
        EvaluateMainPartGlassReflectionProbes(cluster, material)
        * material.reflectionScale;
#endif
  }
#endif

#if defined(MAIN_PART_TINTED_DISSOLVE_REFLECTION_SINGLE)
  lighting.reflectedColor = EvaluateMainPartSingleReflection(material);
#elif defined(MAIN_PART_TINTED_DISSOLVE_REFLECTION_OFF)
  lighting.reflectedColor = material.gloss * 0.119999997;
#elif !defined(MAIN_PART_TINTED_DISSOLVE_QUALITY_MEDIUM) && \
      !defined(MAIN_PART_TINTED_DISSOLVE_QUALITY_HIGH)
  lighting.reflectedColor = 0.0;
#endif
  return lighting;
}

MainPartGlassSurfaceComposite ComposeMainPartTintedDissolveGraph(
    float3 viewPosition, float3 screenUv, float4 fogColor, bool frontFace,
    MainPartDissolveGlassMaterial material, MainPartGlassLighting lighting)
{
#if defined(MAIN_PART_TINTED_DISSOLVE_QUALITY_HIGH)
  // High quality adds thickness-aware screen refraction and mip selection.
  // This is intentionally a composition phase: lower quality policies never
  // bind or sample opaque depth.
  float3 incident = -material.viewDirection;
  float3 refracted = refract(incident, material.normalView, cb_glass.fROI);
  float2 offset = refracted.xy * (
      cb_glass.fRefraction * cb_fProjectionScale / -viewPosition.z);
  offset *= cb_vContainerPixelSize.xy * cb_vRenderScale.xy;
  float2 depthUv = screenUv.xy + offset;
  float deviceDepth = tDepth.SampleLevel(
      PointClampClamp_s, depthUv, 0).x;
  bool perspective = cb_xViewToProjection._m33 != 1.0;
  float sampledViewDepth = perspective
      ? cb_xViewToProjection._m23
          / (cb_xViewToProjection._m22 + deviceDepth)
      : (1.0 - deviceDepth) * cb_vInverseCameraRange.y
          + cb_vNearFarViewCorner.x;
  float thickness = saturate(
      (viewPosition.z + sampledViewDepth) * sampledViewDepth);
  float2 refractedUv = screenUv.xy + offset * thickness;

  float mip = min(1.0, lighting.specular * lighting.specular)
      * cb_vRenderScale.x;
  float2 edge = abs(refractedUv - cb_vRenderScale.xy * 0.5)
      / cb_vRenderScale.xy * 2.0;
  float edgeMip = 5.0 * saturate(5.0 * (max(edge.x, edge.y) - 0.8));
  mip = mip * 2.5 + edgeMip;
  float pixelRadius = exp2(mip);
  float4 frame = tFrame.SampleLevel(
      LinearMirrorMirror_s,
      ClampMainPartHighFrameUv(refractedUv, pixelRadius), mip);

  lighting.directColor = material.coverage * (1.0 - lighting.directColor)
      + lighting.directColor;
  float auxiliaryCoverage = min(0.5, 0.5 * material.coverage);
  float normalFacing = dot(material.viewDirection, material.normalView);
  float minimumFresnel = material.gloss * 0.119999997 + 0.00999999978;
  float grazing = 1.0 - normalFacing;
  float fresnel = grazing * grazing;
  fresnel *= fresnel * grazing;
  fresnel = (1.0 - minimumFresnel) * fresnel + minimumFresnel;
  float faceTransparency = frontFace
      ? cb_glass.fTransparencyFront : cb_glass.fTransparencyBack;
  float transparency = saturate(
      faceTransparency + lighting.specular + fresnel);

  float3 indirect = tIndirect.SampleLevel(
      PointClampClamp_s, screenUv.xy, 0).xyz;
  float luminance = dot(indirect, float3(0.298999995, 0.587000012, 0.114));
  indirect *= 1.13 * (luminance * 0.200000003 + 1.39999998);
  indirect = indirect * saturate(material.viewDistance - 1.0) + 0.119999997;
  float reflectionEnergy = lighting.specular + fresnel;
  float3 glassColor = lerp(
      frame.xyz, material.diffuseColor * frame.xyz, transparency);
  glassColor += lighting.directColor * reflectionEnergy;
  glassColor += indirect * material.gloss + lighting.reflectedColor;
  float fogStrength = 0.349999994 * auxiliaryCoverage;
  fogStrength *= 1.0 - min(1.0, 0.00999999978 * material.viewDistance);
  float largestChannel = max(abs(glassColor.x), abs(glassColor.y));
  largestChannel = max(largestChannel, abs(glassColor.z));
  fogStrength = (1.0 - fogStrength * largestChannel) * fogColor.w;
  MainPartGlassSurfaceComposite result;
  result.color.xyz = lerp(glassColor, fogColor.xyz, fogStrength);
  result.color.w = max(frame.w, transparency);
  result.auxiliary = float4(
      auxiliaryCoverage, 0.0, 0.0, result.color.w);
  return result;
#else
  return ComposeMainPartLegacyGlassSurface(
      screenUv, fogColor, frontFace, material, lighting);
#endif
}

void EvaluateMainPartTintedDissolveGlassSurfaceGraph(
    float4 position, float3 viewPosition, float2 materialUv,
    float2 dissolveUv, float3 normalView, float3 tangentView,
    float3 bitangentView, float4 vertexColor, float3 screenUv,
    float4 fogColor, float cutoffOffset, uint frontFace,
    out float4 colorTarget, out float4 auxiliaryTarget)
{
  MainPartDissolveGlassMaterial material =
      EvaluateMainPartDissolveGlassMaterialAtUv(
          viewPosition, materialUv, dissolveUv, normalView, tangentView,
          bitangentView, vertexColor, cutoffOffset, frontFace != 0);
  MainPartGlassLighting lighting = EvaluateMainPartTintedDissolveLighting(
      viewPosition, screenUv, material);
  MainPartGlassSurfaceComposite composite =
      ComposeMainPartTintedDissolveGraph(
          viewPosition, screenUv, fogColor, frontFace != 0,
          material, lighting);
  colorTarget = composite.color;
  auxiliaryTarget = composite.auxiliary;
}

#undef MAIN_PART_GLASS_SURFACE_HAS_DISSOLVE
#ifdef MAIN_PART_GLASS_SURFACE_ENABLE_MEDIUM_CLUSTERED
#undef MAIN_PART_GLASS_SURFACE_ENABLE_MEDIUM_CLUSTERED
#endif
#ifdef MAIN_PART_GLASS_SURFACE_ENABLE_MULTI_PROBES
#undef MAIN_PART_GLASS_SURFACE_ENABLE_MULTI_PROBES
#endif
#ifdef MAIN_PART_GLASS_SURFACE_ENABLE_SINGLE_PROBE
#undef MAIN_PART_GLASS_SURFACE_ENABLE_SINGLE_PROBE
#endif

#endif
