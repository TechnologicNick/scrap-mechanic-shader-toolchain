#ifndef MAIN_PART_GLASS_DISSOLVE_BEHIND_SINGLE_HLSL
#define MAIN_PART_GLASS_DISSOLVE_BEHIND_SINGLE_HLSL

#define MAIN_PART_GLASS_SURFACE_HAS_DISSOLVE
#define MAIN_PART_GLASS_SURFACE_ENABLE_SINGLE_PROBE
#define MAIN_PART_GLASS_SURFACE_SKIP_FRAME_COMPOSITION
#include "main_part_glass_surface_shared.hlsl"
#undef MAIN_PART_GLASS_SURFACE_SKIP_FRAME_COMPOSITION
#undef MAIN_PART_GLASS_SURFACE_ENABLE_SINGLE_PROBE
#undef MAIN_PART_GLASS_SURFACE_HAS_DISSOLVE

struct MainPartDissolveBehindComposite
{
  float3 weightedColor;
  float2 accumulation;
};

void RejectMainPartDissolveBehindOpaqueDepth(float3 screenUv)
{
  float opaqueDepth = tDepth.SampleLevel(
      PointClampClamp_s, screenUv.xy, 0).x;
  if (screenUv.z < opaqueDepth)
    discard;
}

float3 EvaluateMainPartDissolveBehindFallbackReflection(
    MainPartDissolveGlassMaterial material)
{
  if (cb_fDirectionalLightIntensity != 0.0)
    return 0.0;
  float3 worldNormal = viewToWorld._m01_m11_m21 * material.normalView.y;
  worldNormal = viewToWorld._m00_m10_m20 * material.normalView.x
      + worldNormal;
  worldNormal = viewToWorld._m02_m12_m22 * material.normalView.z
      + worldNormal;
  return taReflection.SampleLevel(
      LinearMirrorMirror_s,
      float3(EncodeMainPartOctahedralDirection(worldNormal), 0.0),
      5.0).xyz;
}

MainPartDissolveBehindComposite ComposeMainPartDissolveBehindSingle(
    float depth, bool frontFace, MainPartDissolveGlassMaterial material,
    MainPartGlassLighting lighting, float3 fallbackReflection,
    float3 singleReflection)
{
  MainPartDissolveBehindComposite result;
  float3 environment = lighting.directColor + fallbackReflection;
  environment = material.coverage * (1.0 - environment) + environment;

  float normalFacing = dot(material.viewDirection, material.normalView);
  float minimumFresnel = material.gloss * 0.5 + 0.00999999978;
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

  float3 composedColor = material.gloss * singleReflection;
  composedColor = material.diffuseColor * environment + composedColor;
  composedColor += environment * reflectionEnergy;
  float3 channelDifferences = material.diffuseColor.xxy
      - material.diffuseColor.zyz;
  float oitWeight = depth + abs(channelDifferences.x)
      + abs(channelDifferences.y) + abs(channelDifferences.z);
  float weightedAlpha = oitWeight * transparency;
  result.weightedColor = composedColor * weightedAlpha;
  result.accumulation = float2(
      weightedAlpha * transparency, weightedAlpha);
  return result;
}

void EvaluateMainPartDissolveBehindSingle(
    float4 position, float3 viewPosition, float2 uv,
    float3 normalView, float3 tangentView, float3 bitangentView,
    float4 vertexColor, float3 screenUv, float4 fogColor,
    float cutoffOffset, uint frontFace,
    out float3 colorTarget, out float2 accumulationTarget)
{
  RejectMainPartDissolveBehindOpaqueDepth(screenUv);
  MainPartDissolveGlassMaterial material =
      EvaluateMainPartDissolveGlassMaterial(
          viewPosition, uv, normalView, tangentView, bitangentView,
          vertexColor, cutoffOffset, frontFace != 0);
  MainPartGlassLighting lighting =
      EvaluateMainPartGlassDirectionalLighting(viewPosition, material);
  float3 fallbackReflection =
      EvaluateMainPartDissolveBehindFallbackReflection(material);
  float3 singleReflection = EvaluateMainPartSingleReflection(material);
  MainPartDissolveBehindComposite composite =
      ComposeMainPartDissolveBehindSingle(
          screenUv.z, frontFace != 0, material, lighting,
          fallbackReflection, singleReflection);
  colorTarget = composite.weightedColor;
  accumulationTarget = composite.accumulation;
}

#endif // MAIN_PART_GLASS_DISSOLVE_BEHIND_SINGLE_HLSL
