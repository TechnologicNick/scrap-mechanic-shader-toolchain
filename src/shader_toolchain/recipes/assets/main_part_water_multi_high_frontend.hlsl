#ifndef MAIN_PART_WATER_MULTI_HIGH_FRONTEND_HLSL
#define MAIN_PART_WATER_MULTI_HIGH_FRONTEND_HLSL

struct MainPartMultiWaterMaterial
{
  float3 normalView;
  float3 viewDirection;
  float3 diffuseColor;
  float fresnel;
  float surfaceBlend;
  float reflectionStrength;
  float fresnelBase;
  float normalDotView;
  float roughnessComplement;
};

float3 SampleMainPartMultiWaterAsg(float2 uv)
{
  return tAsg.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias).xyw;
}

MainPartMultiWaterMaterial EvaluateMainPartMultiWaterMaterial(
    float3 viewPosition,
    float2 uv,
    float3 normalView,
    float4 vertexColor,
    uint frontFace,
    float3 asg)
{
  MainPartMultiWaterMaterial result;
  float3 orientedNormal = frontFace.xxx ? normalView : -normalView;
  orientedNormal *= rsqrt(dot(orientedNormal, orientedNormal));
  result.normalView = orientedNormal;

  float4 diffuse = tDif.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias);
  result.diffuseColor = (diffuse.xyz - vertexColor.xyz) * diffuse.w
      + vertexColor.xyz;
  result.viewDirection = -viewPosition * rsqrt(dot(-viewPosition, -viewPosition));

  float inverseLightLength = rsqrt(dot(
      -cb_vDirectionalLightDirectionView.xyz,
      -cb_vDirectionalLightDirectionView.xyz));
  float2 complements = 1.0 - asg.yz;
  result.roughnessComplement = complements.x;
  result.reflectionStrength = asg.z;
  result.fresnelBase = 1.0 - complements.x * complements.x;

  float3 halfDirection = -cb_vDirectionalLightDirectionView.xyz
      * inverseLightLength + result.viewDirection;
  halfDirection *= rsqrt(dot(halfDirection, halfDirection));
  float halfDotNormal = dot(halfDirection, orientedNormal) * 0.5 + 0.5;
  result.normalDotView = dot(orientedNormal, result.viewDirection);

  float clampedNormalDotView = max(0.00999999978, result.normalDotView);
  float exponent = max(0.100000001, 4.0 * asg.y);
  float surfaceBlend = exp2(log2(clampedNormalDotView) * exponent);
  surfaceBlend = min(1.0, surfaceBlend);
  surfaceBlend = 1.0 - surfaceBlend;
  surfaceBlend = max(0.25, surfaceBlend);
  surfaceBlend = min(0.800000012, surfaceBlend);

  float fresnelThreshold = 0.995000005 * result.fresnelBase;
  float fresnelRange = 1.0 - 0.995000005 * result.fresnelBase;
  float fresnel = abs(halfDotNormal) * abs(halfDotNormal) - fresnelThreshold;
  fresnel = saturate(fresnel / fresnelRange);
  float smoothFresnel = fresnel * fresnel;
  smoothFresnel = (3.0 - 2.0 * fresnel) * smoothFresnel;
  result.fresnel = saturate(smoothFresnel * result.fresnelBase);
  surfaceBlend = surfaceBlend * result.reflectionStrength + result.fresnel;
  result.surfaceBlend = saturate(complements.y * 0.25 + surfaceBlend);
  return result;
}

#endif
