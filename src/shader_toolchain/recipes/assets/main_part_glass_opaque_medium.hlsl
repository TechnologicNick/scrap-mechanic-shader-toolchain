#ifndef MAIN_PART_GLASS_OPAQUE_MEDIUM_HLSL
#define MAIN_PART_GLASS_OPAQUE_MEDIUM_HLSL

#include "main_part_glass_opaque_medium_clustered.hlsl"

struct MainPartOpaqueGlassMaterial
{
  float3 viewDirection;
  float3 normalView;
  float3 diffuseAo;
  float gloss;
  float coverage;
  float specularScale;
  float viewDistance;
  float glossExponent;
};

struct MainPartOpaqueGlassDirectionalLighting
{
  float3 color;
  float transmission;
  float specular;
};

struct MainPartOpaqueGlassForwardOutput
{
  float4 color;
  float4 gForward;
};

MainPartOpaqueGlassMaterial EvaluateMainPartOpaqueGlassMaterial(
    float3 viewPosition,
    float2 uv,
    float3 normalView,
    float3 tangentView,
    float3 bitangentView,
    float4 vertexColor,
    float2 screenUv,
    bool frontFace)
{
  MainPartOpaqueGlassMaterial result;
  float inverseViewLength = rsqrt(dot(-viewPosition, -viewPosition));
  result.viewDirection = -viewPosition * inverseViewLength;

  float3 asg = tAsg.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias).yzw;
  result.gloss = asg.x;
  result.coverage = vertexColor.w * asg.y;
  result.specularScale = asg.z;

  float2 tangentNormal = tNor.SampleBias(
      LinearWrapWrap_s, uv, cb_fMipBias).xy;
  tangentNormal = tangentNormal * 1.99215686 - 1.0;
  float tangentNormalZ = sqrt(max(
      0.0, 1.0 - dot(tangentNormal, tangentNormal)));
  float3 mappedNormal = bitangentView * tangentNormal.y;
  mappedNormal = tangentView * tangentNormal.x + mappedNormal;
  mappedNormal = normalView * tangentNormalZ + mappedNormal;
  mappedNormal *= rsqrt(dot(mappedNormal, mappedNormal));
  mappedNormal = frontFace ? mappedNormal : -mappedNormal;
  result.normalView = mappedNormal * rsqrt(dot(mappedNormal, mappedNormal));

  float4 diffuse = tDif.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias);
  diffuse.xyz = (diffuse.xyz - vertexColor.xyz) * diffuse.w
      + vertexColor.xyz;
  result.viewDistance = sqrt(dot(viewPosition, viewPosition));
  result.glossExponent = result.gloss * result.gloss * 750.0 + 35.0;

  float ambientOcclusion = tAo.Sample(PointClampClamp_s, screenUv).x;
  float aoFactor = cb_glass.fAoMultiplier * ambientOcclusion;
  result.diffuseAo = aoFactor * diffuse.xyz;
  return result;
}

MainPartOpaqueGlassDirectionalLighting
EvaluateMainPartOpaqueGlassDirectionalLighting(
    float3 viewPosition,
    float2 screenUv,
    MainPartOpaqueGlassMaterial material)
{
  MainPartOpaqueGlassDirectionalLighting result;
  if (cb_fDirectionalLightIntensity != 0.0)
  {
    float normalDotLight = dot(
        material.normalView, -cb_vDirectionalLightDirectionView.xyz);
    float halfLambert = normalDotLight * 0.5 + 0.5;
    float transmission = max(0.0, normalDotLight);
    transmission = transmission * cb_glass.fTransmissionRange
        + cb_glass.fTransmissionBase;
    transmission = min(1.0, transmission);

    float distanceFactor = min(1.0, 0.00400000019 * material.viewDistance);
    float distanceInverse = 1.0 - distanceFactor;
    distanceInverse *= distanceInverse;
    float ambientOcclusion = tAo.Sample(PointClampClamp_s, screenUv).x;
    float aoFactor = cb_glass.fAoMultiplier * ambientOcclusion;
    float aoDistance = -ambientOcclusion * cb_glass.fAoMultiplier + 1.0;
    aoDistance = distanceFactor * aoDistance + aoFactor;
    aoDistance *= aoDistance;
    float aoDistanceSquared = aoDistance * aoDistance;
    float distanceCurve = 0.400000006 * aoDistanceSquared;
    aoDistance = aoDistance * 0.200000018 + 0.400000006;
    aoDistance = -aoDistanceSquared * 0.400000006 + aoDistance;
    aoDistance = distanceInverse * aoDistance + distanceCurve;

    float2 shapeRange = float2(1.0, 1.20000005) - aoDistance;
    float shapedLight = saturate(halfLambert - aoDistance);
    shapedLight /= shapeRange.x;
    shapedLight *= shapedLight;
    aoDistance = shapedLight * shapeRange.y + aoDistance;

    float3 lightMap = tLightColorMap.SampleLevel(
        LinearWrapClamp_s,
        float2(cb_fTimeOfDay, saturate(halfLambert)), 0).xyz;
    lightMap = (lightMap - cb_vDirectionalShadowColor.xyz) * halfLambert
        + cb_vDirectionalShadowColor.xyz;
    aoDistance *= cb_fDirectionalLightMapMul;
    result.color = lightMap * aoDistance * cb_fDirectionalLightIntensity;
    result.transmission = cb_fDirectionalLightIntensity * transmission;

    float3 halfDirection = material.viewDirection
        - cb_vDirectionalLightDirectionView.xyz;
    halfDirection *= rsqrt(dot(halfDirection, halfDirection));
    float specular = dot(halfDirection, material.normalView) * 0.5 + 0.5;
    specular = log2(abs(specular));
    specular = material.glossExponent * specular;
    specular = exp2(specular);
    specular *= transmission;
    result.specular = saturate(specular * material.specularScale);
  }
  else
  {
    result.color = 0.0;
    result.transmission = 0.0;
    result.specular = 0.0;
  }
  return result;
}

MainPartOpaqueGlassForwardOutput ComposeMainPartOpaqueGlassForward(
    MainPartOpaqueGlassMaterial material,
    MainPartOpaqueGlassClusterLighting lighting,
    float4 fogColor)
{
  MainPartOpaqueGlassForwardOutput result;
  float3 lightColor = lighting.maxLightColor + lighting.additiveLightColor;
  float responsive = saturate(lighting.maximumTransmission);
  float glow = responsive * cb_glass.fResponsiveGlowRange
      + cb_glass.fResponsiveGlowBase;
  glow = material.coverage * glow;
  lightColor = glow * (1.0 - lightColor) + lightColor;
  float responsiveTarget = min(0.5, 0.5 * glow);

  float normalFacing = dot(material.viewDirection, material.normalView);
  float minimumFresnel = material.gloss * 0.5 + 0.00999999978;
  float grazing = 1.0 - normalFacing;
  float fresnel = grazing * grazing;
  fresnel *= fresnel;
  fresnel *= grazing;
  fresnel = (1.0 - minimumFresnel) * fresnel + minimumFresnel;
  fresnel += lighting.maximumSpecular;

  float3 surface = lightColor * fresnel;
  surface = material.diffuseAo * lightColor + surface;
  surface += material.gloss * 0.119999997;

  float fogWeight = 0.349999994 * responsiveTarget;
  float distanceFade = min(1.0, 0.00999999978 * material.viewDistance);
  fogWeight *= 1.0 - distanceFade;
  float maximumChannel = max(abs(surface.x), abs(surface.y));
  maximumChannel = max(maximumChannel, abs(surface.z));
  fogWeight = 1.0 - fogWeight * maximumChannel;
  fogWeight *= fogColor.w;
  result.color.xyz = (fogColor.xyz - surface) * fogWeight + surface;
  result.color.w = 1.0;
  result.gForward = float4(responsiveTarget, 0.0, 0.0, 1.0);
  return result;
}

MainPartOpaqueGlassForwardOutput EvaluateMainPartOpaqueGlassForwardMedium(
    float3 viewPosition,
    float2 uv,
    float3 normalView,
    float3 tangentView,
    float3 bitangentView,
    float4 vertexColor,
    float2 screenUv,
    float4 fogColor,
    bool frontFace)
{
  MainPartOpaqueGlassMaterial material = EvaluateMainPartOpaqueGlassMaterial(
      viewPosition, uv, normalView, tangentView, bitangentView,
      vertexColor, screenUv, frontFace);
  MainPartOpaqueGlassDirectionalLighting directional =
      EvaluateMainPartOpaqueGlassDirectionalLighting(
          viewPosition, screenUv, material);

  MainPartOpaqueGlassClusterInput clusterInput;
  clusterInput.viewPosition = viewPosition;
  clusterInput.screenUv = screenUv;
  clusterInput.normalView = material.normalView;
  clusterInput.viewDirection = material.viewDirection;
  clusterInput.glossExponent = material.glossExponent;
  clusterInput.specularScale = material.specularScale;
  clusterInput.directionalColor = directional.color;
  clusterInput.directionalTransmission = directional.transmission;
  clusterInput.directionalSpecular = directional.specular;
  MainPartOpaqueGlassClusterLighting lighting =
      EvaluateMainPartOpaqueGlassCluster(clusterInput);
  return ComposeMainPartOpaqueGlassForward(material, lighting, fogColor);
}

#endif // MAIN_PART_GLASS_OPAQUE_MEDIUM_HLSL
