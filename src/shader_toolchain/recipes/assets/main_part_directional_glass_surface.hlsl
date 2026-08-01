#ifndef MAIN_PART_DIRECTIONAL_GLASS_SURFACE_INCLUDED
#define MAIN_PART_DIRECTIONAL_GLASS_SURFACE_INCLUDED

// Directional-map (FBDRF) glass frontend.  This is deliberately a material
// policy layered over the common glass lighting/reflection/composition phases.
#define MAIN_PART_GLASS_SURFACE_STANDARD_LIGHTING
#define MAIN_PART_GLASS_SURFACE_UNRESPONSIVE
#define MAIN_PART_GLASS_SURFACE_GEOMETRIC_NORMAL_ONLY
#if defined(MAIN_PART_DIRECTIONAL_GLASS_QUALITY_MEDIUM)
#define MAIN_PART_GLASS_SURFACE_ENABLE_MEDIUM_CLUSTERED
#elif defined(MAIN_PART_DIRECTIONAL_GLASS_QUALITY_HIGH)
#define MAIN_PART_GLASS_SURFACE_ENABLE_MEDIUM_CLUSTERED
#endif
#if defined(MAIN_PART_DIRECTIONAL_GLASS_REFLECTION_MULTI)
#define MAIN_PART_GLASS_SURFACE_ENABLE_MULTI_PROBES
#elif defined(MAIN_PART_DIRECTIONAL_GLASS_REFLECTION_SINGLE)
#define MAIN_PART_GLASS_SURFACE_ENABLE_SINGLE_PROBE
#else
#define MAIN_PART_GLASS_SURFACE_OFF_AMBIENT
#endif

#include "main_part_glass_surface_shared.hlsl"
#include "main_part_directional_map.hlsl"
#if defined(MAIN_PART_DIRECTIONAL_GLASS_QUALITY_HIGH)
#include "main_part_glass_high_quality.hlsl"
#endif

MainPartDissolveGlassMaterial EvaluateMainPartDirectionalGlassMaterial(
    float3 viewPosition, float2 uv, float3 normalView, float4 vertexColor)
{
  MainPartDissolveGlassMaterial result;
  float inverseViewLength = rsqrt(dot(-viewPosition, -viewPosition));
  result.viewDirection = -viewPosition * inverseViewLength;
  result.normalView = normalView * rsqrt(dot(normalView, normalView));

  // ASG is addressed by UV0 while diffuse uses the directional map.
  float3 asg = tAsg.SampleBias(
      LinearWrapWrap_s, uv, cb_fMipBias).yzw;
  result.diffuseColor = SampleMainPartDirectionalMapDiffuse(
      viewPosition, result.normalView, vertexColor);
  result.coverage = vertexColor.w * asg.y;
  result.inverseViewLength = inverseViewLength;
  result.viewDistance = sqrt(dot(viewPosition, viewPosition));
  result.gloss = asg.x;
  result.reflectionScale = asg.z;
  result.glossExponent = asg.x * asg.x * 750.0 + 35.0;
  result.specularScale = asg.z * asg.x;
  return result;
}

MainPartGlassLighting EvaluateMainPartDirectionalMapGlassLighting(
    float3 viewPosition, MainPartDissolveGlassMaterial material)
{
  MainPartGlassLighting result;
  result.reflectedColor = 0.0;
  result.transmission = 0.0;
  if (cb_fDirectionalLightIntensity != 0.0)
  {
    float normalDotLight = dot(
        material.normalView, -cb_vDirectionalLightDirectionView.xyz);
    float halfLambert = normalDotLight * 0.5 + 0.5;
    float distanceShape = min(1.0, 0.00400000019 * material.viewDistance);
    distanceShape = 1.0 - distanceShape;
    distanceShape *= distanceShape;
    distanceShape = distanceShape * 0.200000018 + 0.400000006;
    float2 shapeRange = float2(1.0, 1.20000005) - distanceShape;
    float shapedLight = saturate(halfLambert - distanceShape) / shapeRange.x;
    shapedLight *= shapedLight;
    distanceShape = shapedLight * shapeRange.y + distanceShape;
    float3 mappedLight = tLightColorMap.SampleLevel(
        LinearWrapClamp_s,
        float2(cb_fTimeOfDay, saturate(halfLambert)), 0).xyz;
    mappedLight = (mappedLight - cb_vDirectionalShadowColor.xyz)
        * halfLambert + cb_vDirectionalShadowColor.xyz;
    result.directColor = mappedLight
        * (cb_fDirectionalLightMapMul * distanceShape)
        * cb_fDirectionalLightIntensity;
    float3 halfDirection = material.viewDirection
        - cb_vDirectionalLightDirectionView.xyz;
    halfDirection *= rsqrt(dot(halfDirection, halfDirection));
    float specular = dot(halfDirection, material.normalView) * 0.5 + 0.5;
    specular = exp2(log2(abs(specular)) * material.glossExponent);
    specular *= min(1.0, abs(normalDotLight));
    result.specular = saturate(specular * material.specularScale);
  }
  else
  {
    result.directColor = 0.0;
    result.specular = 0.0;
  }
  return result;
}

void EvaluateMainPartDirectionalGlassSurface(
    float4 position, float3 viewPosition, float2 uv, float3 normalView,
    float4 vertexColor, float3 screenUv, float4 fogColor, uint frontFace,
    out float4 colorTarget, out float4 auxiliaryTarget)
{
  MainPartDissolveGlassMaterial material =
      EvaluateMainPartDirectionalGlassMaterial(
          viewPosition, uv, normalView, vertexColor);
  MainPartGlassLighting lighting =
#if defined(MAIN_PART_DIRECTIONAL_GLASS_QUALITY_HIGH)
      EvaluateMainPartHighDirectionalGlassLighting(viewPosition, material);
#else
      EvaluateMainPartDirectionalMapGlassLighting(viewPosition, material);
#endif

#if defined(MAIN_PART_DIRECTIONAL_GLASS_QUALITY_MEDIUM) || \
    defined(MAIN_PART_DIRECTIONAL_GLASS_QUALITY_HIGH)
  if (-viewPosition.z < cb_cluster.fClusterMaxFarTotal)
  {
    MainPartGlassClusterAddress cluster =
        ResolveMainPartGlassCluster(viewPosition, screenUv.xy);
    MainPartGlassLocalLighting local = EvaluateMainPartGlassLocalLights(
        cluster, viewPosition, material, lighting);
    lighting.directColor = local.maximumColor + local.additiveColor;
    lighting.specular = local.specular;
#if defined(MAIN_PART_DIRECTIONAL_GLASS_REFLECTION_MULTI)
    lighting.reflectedColor =
        EvaluateMainPartGlassReflectionProbes(cluster, material)
        * material.reflectionScale;
#endif
  }
#endif

#if defined(MAIN_PART_DIRECTIONAL_GLASS_REFLECTION_SINGLE)
  lighting.reflectedColor = EvaluateMainPartSingleReflection(material);
#elif defined(MAIN_PART_DIRECTIONAL_GLASS_REFLECTION_OFF)
  lighting.reflectedColor = material.gloss * 0.119999997;
#elif !defined(MAIN_PART_DIRECTIONAL_GLASS_QUALITY_MEDIUM) && \
    !defined(MAIN_PART_DIRECTIONAL_GLASS_QUALITY_HIGH)
  lighting.reflectedColor = 0.0;
#endif

  MainPartGlassSurfaceComposite composite =
#if defined(MAIN_PART_DIRECTIONAL_GLASS_QUALITY_HIGH)
      ComposeMainPartHighUnresponsiveGlassSurface(
          screenUv, fogColor, frontFace != 0, material, lighting);
#else
      ComposeMainPartUnresponsiveGlassSurface(
          screenUv, fogColor, frontFace != 0, material, lighting);
#endif
  colorTarget = composite.color;
  auxiliaryTarget = composite.auxiliary;
}

#endif
