// Typed low-quality glass behind pass using the recovered light-cap material.

#include "main_part_light_cap.hlsl"

struct MainPartBehindGlassMaterial
{
  float3 viewDirection;
  float3 normalView;
  float gloss;
  float specularScale;
  float surfaceCoverage;
  float4 surfaceColor;
};

struct MainPartBehindDirectionalLighting
{
  float3 color;
  float specular;
};

struct MainPartBehindGlassComposite
{
  float3 weightedColor;
  float2 accumulation;
};

void RejectMainPartBehindOpaqueDepth(float3 screenUv)
{
  float opaqueDepth = tDepth.SampleLevel(
      PointClampClamp_s, screenUv.xy, 0).x;
  if (screenUv.z < opaqueDepth)
    discard;
}

MainPartBehindGlassMaterial EvaluateMainPartBehindLightCapMaterial(
    float3 viewPosition,
    float2 uv,
    float3 normalView,
    float4 vertexColor)
{
  MainPartBehindGlassMaterial result;
  float inverseViewLength = rsqrt(dot(-viewPosition, -viewPosition));
  result.viewDirection = -viewPosition * inverseViewLength;

  float3 asg = tAsg.SampleBias(
      LinearWrapWrap_s, uv, cb_fMipBias).yzw;
  result.gloss = asg.x;
  result.surfaceCoverage = vertexColor.w * asg.y;
  result.specularScale = asg.z;

  result.normalView = normalView * rsqrt(dot(normalView, normalView));
  float2 lightCapUv = ComputeMainPartLightCapUv(
      viewPosition, result.viewDirection, result.normalView);

  float4 diffuse = tDif.SampleBias(
      LinearWrapWrap_s, uv, cb_fMipBias);
  diffuse.xyz = (diffuse.xyz - vertexColor.xyz) * diffuse.w
      + vertexColor.xyz;
  // The source keeps ASG/vertex coverage in the fourth component while the
  // diffuse alpha is used only for tint interpolation.
  diffuse.w = result.surfaceCoverage;
  float4 lightCap = tLightCap.Sample(LinearClampClamp_s, lightCapUv);
  result.surfaceColor = (lightCap - diffuse) * lightCap.w + diffuse;
  return result;
}

MainPartBehindDirectionalLighting EvaluateMainPartBehindDirectionalLighting(
    float3 viewPosition,
    MainPartBehindGlassMaterial material)
{
  MainPartBehindDirectionalLighting result;
  if (cb_fDirectionalLightIntensity != 0.0)
  {
    float viewDistance = sqrt(dot(viewPosition, viewPosition));
    float glossExponent = material.gloss * material.gloss;
    float specularStrength = material.specularScale * material.gloss;
    glossExponent = glossExponent * 750.0 + 35.0;

    float normalDotLight = dot(
        material.normalView, -cb_vDirectionalLightDirectionView);
    float halfLambert = normalDotLight * 0.5 + 0.5;
    float absoluteNormalDotLight = min(1.0, abs(normalDotLight));

    float distanceShape = min(1.0, 0.00400000019 * viewDistance);
    distanceShape = 1.0 - distanceShape;
    distanceShape *= distanceShape;
    distanceShape = distanceShape * 0.200000018 + 0.400000006;
    float2 shapeRange = float2(1.0, 1.20000005) - distanceShape;
    float shapedLight = saturate(halfLambert - distanceShape);
    shapedLight /= shapeRange.x;
    shapedLight *= shapedLight;
    distanceShape = shapedLight * shapeRange.y + distanceShape;

    float2 lightMapUv = float2(cb_fTimeOfDay, saturate(halfLambert));
    float3 mappedLight = tLightColorMap.SampleLevel(
        LinearWrapClamp_s, lightMapUv, 0).xyz;
    mappedLight = (mappedLight - cb_vDirectionalShadowColor.xyz)
        * halfLambert + cb_vDirectionalShadowColor.xyz;
    distanceShape *= cb_fDirectionalLightMapMul;
    result.color = mappedLight * distanceShape
        * cb_fDirectionalLightIntensity;

    float3 halfDirection = material.viewDirection
        - cb_vDirectionalLightDirectionView.xyz;
    halfDirection *= rsqrt(dot(halfDirection, halfDirection));
    float specular = dot(halfDirection, material.normalView) * 0.5 + 0.5;
    specular = log2(abs(specular));
    specular = glossExponent * specular;
    specular = exp2(specular);
    specular *= absoluteNormalDotLight;
    result.specular = saturate(specular * specularStrength);
  }
  else
  {
    result.color = 0.0;
    result.specular = 0.0;
  }
  return result;
}

MainPartBehindGlassComposite ComposeMainPartBehindGlass(
    float depth,
    bool frontFace,
    MainPartBehindGlassMaterial material,
    MainPartBehindDirectionalLighting lighting)
{
  MainPartBehindGlassComposite result;
  float3 lightResponse = 1.0 - lighting.color;
  lightResponse = material.surfaceColor.w * lightResponse + lighting.color;

  float normalFacing = dot(material.viewDirection, material.normalView);
  float edgeColor = 0.119999997 * material.gloss;
  float minimumFresnel = material.gloss * 0.5 + 0.00999999978;
  float fresnelRange = 1.0 - minimumFresnel;
  float grazing = 1.0 - normalFacing;
  float fresnel = grazing * grazing;
  fresnel *= fresnel;
  fresnel *= grazing;
  fresnel = fresnelRange * fresnel + minimumFresnel;

  float faceTransparency = frontFace
      ? cb_glass.fTransparencyFront
      : cb_glass.fTransparencyBack;
  float transparency = saturate(
      faceTransparency + lighting.specular + fresnel);
  float reflectionEnergy = lighting.specular + fresnel;
  float3 composedColor = material.surfaceColor.xyz * lightResponse + edgeColor;
  composedColor += lightResponse * reflectionEnergy;

  float3 channelDifferences = material.surfaceColor.xxy
      - material.surfaceColor.zyz;
  float oitWeight = depth + abs(channelDifferences.x)
      + abs(channelDifferences.y) + abs(channelDifferences.z);
  float weightedAlpha = oitWeight * transparency;
  result.weightedColor = weightedAlpha * composedColor;
  result.accumulation = float2(
      weightedAlpha * transparency, weightedAlpha);
  return result;
}

void WriteMainPartBehindGlass(
    MainPartBehindGlassComposite value,
    out float3 colorTarget,
    out float2 accumulationTarget)
{
  colorTarget = value.weightedColor;
  accumulationTarget = value.accumulation;
}
