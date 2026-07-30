// Typed low-quality legacy-glass surface policy. Reflection-off and the
// low "multi" permutation share this backend because neither samples probes.
#include "main_part_glass_surface_common.hlsl"

MainPartGlassLighting EvaluateMainPartLegacyGlassDirectionalLighting(
    float3 viewPosition,
    MainPartDissolveGlassMaterial material)
{
  MainPartGlassLighting result;
  result.reflectedColor = float3(0.0, 0.0, 0.0);
  result.transmission = 0.0;
  if (cb_fDirectionalLightIntensity != 0.0)
  {
    float normalDotLight = dot(
        material.normalView, -cb_vDirectionalLightDirectionView.xyz);
    float mapCoordinate = normalDotLight * 0.5 + 0.5;
    float diffuseFacing = min(1.0, abs(normalDotLight));

    float distanceResponse = min(1.0, 0.00400000019 * material.viewDistance);
    distanceResponse = 1.0 - distanceResponse;
    distanceResponse *= distanceResponse;
    distanceResponse = distanceResponse * 0.200000018 + 0.400000006;
    float edge = saturate(mapCoordinate - distanceResponse)
        / (1.0 - distanceResponse);
    distanceResponse = edge * edge * (1.20000005 - distanceResponse)
        + distanceResponse;

    float3 lightColor = tLightColorMap.SampleLevel(
        LinearWrapClamp_s,
        float2(cb_fTimeOfDay, saturate(mapCoordinate)), 0).xyz;
    lightColor = (lightColor - cb_vDirectionalShadowColor.xyz)
        * mapCoordinate + cb_vDirectionalShadowColor.xyz;
    result.directColor = lightColor
        * (cb_fDirectionalLightMapMul * distanceResponse)
        * cb_fDirectionalLightIntensity;

    float3 halfDirection = material.viewDirection
        - cb_vDirectionalLightDirectionView.xyz;
    halfDirection *= rsqrt(dot(halfDirection, halfDirection));
    float specular = dot(halfDirection, material.normalView) * 0.5 + 0.5;
    specular = exp2(log2(abs(specular)) * material.glossExponent);
    result.specular = saturate(
        specular * diffuseFacing * material.specularScale);
  }
  else
  {
    result.directColor = float3(0.0, 0.0, 0.0);
    result.specular = 0.0;
  }
  return result;
}

MainPartGlassSurfaceComposite ComposeMainPartLegacyGlassSurface(
    float3 screenUv,
    float4 fogColor,
    bool frontFace,
    MainPartDissolveGlassMaterial material,
    MainPartGlassLighting lighting)
{
  MainPartGlassSurfaceComposite result;
  lighting.directColor = material.coverage * (1.0 - lighting.directColor)
      + lighting.directColor;
  float auxiliaryCoverage = min(0.5, 0.5 * material.coverage);

  float normalFacing = dot(material.viewDirection, material.normalView);
  float minimumFresnel = material.gloss * 0.119999997 + 0.00999999978;
  float grazing = 1.0 - normalFacing;
  float fresnel = grazing * grazing;
  fresnel *= fresnel;
  fresnel *= grazing;
  fresnel = (1.0 - minimumFresnel) * fresnel + minimumFresnel;

  float faceTransparency = frontFace
      ? cb_glass.fTransparencyFront : cb_glass.fTransparencyBack;
  float transparency = saturate(
      faceTransparency + lighting.specular + fresnel);
  float reflectionEnergy = lighting.specular + fresnel;
  float4 frame = tFrame.SampleLevel(
      LinearMirrorMirror_s, ClampMainPartFrameUv(screenUv.xy), 0);
  float3 glassColor = (material.diffuseColor * frame.xyz - frame.xyz)
      * transparency + frame.xyz;
  glassColor += lighting.directColor * reflectionEnergy;
  glassColor += lighting.reflectedColor;

  float fogStrength = 0.349999994 * auxiliaryCoverage;
  fogStrength *= 1.0 - min(1.0, 0.00999999978 * material.viewDistance);
  float largestChannel = max(abs(glassColor.x), abs(glassColor.y));
  largestChannel = max(largestChannel, abs(glassColor.z));
  fogStrength = (1.0 - fogStrength * largestChannel) * fogColor.w;
  result.color.xyz = (fogColor.xyz - glassColor) * fogStrength + glassColor;
  result.color.w = max(frame.w, transparency);
  result.auxiliary = float4(
      auxiliaryCoverage, 0.0, 0.0, result.color.w);
  return result;
}

#ifndef MAIN_PART_GLASS_SURFACE_GEOMETRIC_NORMAL_ONLY
void EvaluateMainPartLegacyGlassSurfaceBasic(
    float4 position,
    float3 viewPosition,
    float2 uv,
    float3 normalView,
    float3 tangentView,
    float3 bitangentView,
    float4 vertexColor,
    float3 screenUv,
    float4 fogColor,
    uint frontFace,
    out float4 colorTarget,
    out float4 auxiliaryTarget)
{
  MainPartDissolveGlassMaterial material;
#ifdef MAIN_PART_LEGACY_GLASS_SURFACE_NO_CUTOUT
  material = EvaluateMainPartGlassMaterialNoCutout(
      viewPosition, uv, normalView, tangentView, bitangentView,
      vertexColor, frontFace != 0);
#else
  material = EvaluateMainPartGlassMaterial(
      viewPosition, uv, normalView, tangentView, bitangentView,
      vertexColor, frontFace != 0);
#endif
  MainPartGlassLighting lighting =
      EvaluateMainPartLegacyGlassDirectionalLighting(viewPosition, material);
#ifdef MAIN_PART_LEGACY_GLASS_SURFACE_OFF_AMBIENT
  lighting.reflectedColor = material.gloss * 0.119999997;
#endif
#ifdef MAIN_PART_LEGACY_GLASS_SURFACE_SINGLE_PROBE
  lighting.reflectedColor = EvaluateMainPartSingleReflection(material);
#endif
  MainPartGlassSurfaceComposite composite =
      ComposeMainPartLegacyGlassSurface(
          screenUv, fogColor, frontFace != 0, material, lighting);
  colorTarget = composite.color;
  auxiliaryTarget = composite.auxiliary;
}
#endif
