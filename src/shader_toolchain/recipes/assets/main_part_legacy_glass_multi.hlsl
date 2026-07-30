#ifndef MAIN_PART_LEGACY_GLASS_MULTI_HLSL
#define MAIN_PART_LEGACY_GLASS_MULTI_HLSL

#include "main_part_legacy_glass_multi_lighting.hlsl"

struct MainPartLegacyGlassMaterial
{
  float3 viewDirection;
  float3 normalView;
  float3 diffuseColor;
  float gloss;
  float coverage;
  float reflectionStrength;
  float glossExponent;
  float specularScale;
  float viewDistance;
};

struct MainPartLegacyGlassDirectional
{
  float3 color;
  float specular;
};

struct MainPartLegacyGlassForwardOutput
{
  float4 color;
  float4 gForward;
};

MainPartLegacyGlassMaterial EvaluateMainPartLegacyGlassMaterial(
    float3 viewPosition, float2 uv, float3 normalView,
    float3 tangentView, float3 bitangentView, float4 vertexColor,
    uint frontFace)
{
  MainPartLegacyGlassMaterial result;
  result.viewDirection = -viewPosition * rsqrt(dot(-viewPosition, -viewPosition));
  float3 asg = tAsg.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias).yzw;
  result.gloss = asg.x;
  result.coverage = vertexColor.w * asg.y;
  result.reflectionStrength = asg.z;
  float2 mapped = tNor.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias).xy;
  mapped = mapped * 1.99215686 - 1.0;
  float mappedZ = sqrt(max(0.0, 1.0 - dot(mapped, mapped)));
  float3 normal = bitangentView * mapped.y;
  normal = tangentView * mapped.x + normal;
  normal = normalView * mappedZ + normal;
  normal *= rsqrt(dot(normal, normal));
  normal = frontFace.xxx ? normal : -normal;
  result.normalView = normal * rsqrt(dot(normal, normal));
  float4 diffuse = tDif.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias);
  result.diffuseColor = (diffuse.xyz - vertexColor.xyz) * diffuse.w
      + vertexColor.xyz;
  result.viewDistance = sqrt(dot(viewPosition, viewPosition));
  result.glossExponent = result.gloss * result.gloss * 750.0 + 35.0;
  result.specularScale = result.reflectionStrength * result.gloss;
  return result;
}

MainPartLegacyGlassDirectional EvaluateMainPartLegacyGlassDirectional(
    MainPartLegacyGlassMaterial material)
{
  MainPartLegacyGlassDirectional result;
  if (cb_fDirectionalLightIntensity != 0.0)
  {
    float ndl = dot(material.normalView, -cb_vDirectionalLightDirectionView.xyz);
    float halfLambert = ndl * 0.5 + 0.5;
    float absoluteNdl = min(1.0, abs(ndl));
    float distanceShape = min(1.0, 0.00400000019 * material.viewDistance);
    distanceShape = 1.0 - distanceShape;
    distanceShape *= distanceShape;
    distanceShape = distanceShape * 0.200000018 + 0.400000006;
    float2 shapeRange = float2(1.0, 1.20000005) - distanceShape;
    float shaped = saturate(halfLambert - distanceShape) / shapeRange.x;
    shaped *= shaped;
    distanceShape = shaped * shapeRange.y + distanceShape;
    float3 mappedLight = tLightColorMap.SampleLevel(
        LinearWrapClamp_s, float2(cb_fTimeOfDay, saturate(halfLambert)), 0).xyz;
    mappedLight = (mappedLight - cb_vDirectionalShadowColor.xyz)
        * halfLambert + cb_vDirectionalShadowColor.xyz;
    distanceShape *= cb_fDirectionalLightMapMul;
    result.color = mappedLight * distanceShape * cb_fDirectionalLightIntensity;
    float3 halfDirection = material.viewDirection
        - cb_vDirectionalLightDirectionView.xyz;
    halfDirection *= rsqrt(dot(halfDirection, halfDirection));
    float specular = dot(halfDirection, material.normalView) * 0.5 + 0.5;
    specular = exp2(material.glossExponent * log2(abs(specular)));
    result.specular = saturate(specular * absoluteNdl * material.specularScale);
  }
  else
  {
    result.color = 0.0;
    result.specular = 0.0;
  }
  return result;
}

MainPartLegacyGlassForwardOutput ComposeMainPartLegacyGlassMulti(
    MainPartLegacyGlassMaterial material,
    MainPartLegacyGlassLighting lighting,
    float2 screenUv, float4 fogColor, bool frontFace)
{
  float3 direct = material.coverage * (1.0 - lighting.directColor)
      + lighting.directColor;
  float responsive = min(0.5, 0.5 * material.coverage);
  float facing = dot(material.viewDirection, material.normalView);
  float minimumFresnel = material.gloss * 0.119999997 + 0.00999999978;
  float grazing = 1.0 - facing;
  float fresnel = grazing * grazing;
  fresnel *= fresnel;
  fresnel *= grazing;
  fresnel = (1.0 - minimumFresnel) * fresnel + minimumFresnel;
  float faceTransparency = frontFace
      ? cb_glass.fTransparencyFront : cb_glass.fTransparencyBack;
  float opacity = saturate(faceTransparency + lighting.maximumSpecular + fresnel);
  float reflectionEnergy = lighting.maximumSpecular + fresnel;
  float2 frameUv = min(cb_vRenderScale.xy, screenUv);
  frameUv -= max(0.0, screenUv - cb_vUvLimit.xy);
  float4 frame = tFrame.SampleLevel(LinearMirrorMirror_s, frameUv, 0);
  float3 color = frame.xyz + opacity * (material.diffuseColor * frame.xyz - frame.xyz);
  color += direct * reflectionEnergy;
  color += lighting.reflection * material.gloss;
  float fogWeight = 0.349999994 * responsive;
  fogWeight *= 1.0 - min(1.0, 0.00999999978 * material.viewDistance);
  float maximumChannel = max(abs(color.x), abs(color.y));
  maximumChannel = max(maximumChannel, abs(color.z));
  fogWeight = (1.0 - fogWeight * maximumChannel) * fogColor.w;
  MainPartLegacyGlassForwardOutput result;
  result.color.xyz = color + fogWeight * (fogColor.xyz - color);
  result.color.w = max(frame.w, opacity);
  result.gForward = float4(0.5 * responsive, 0.0, 0.0, result.color.w);
  return result;
}

#endif
